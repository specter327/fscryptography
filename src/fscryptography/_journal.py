"""Persistent transaction journal and read-only recovery inspection.

The journal is diagnostic evidence, not an authorization to mutate resources.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .names import NameProfile, validate_name

_PREFIX = ".fscryptography-txn-"
_ID = re.compile(r"^[0-9a-f]{32}$")
_MAX_RECORD = 16 * 1024
_OPERATIONS = {"file_encrypt", "file_decrypt", "dir_encrypt", "dir_decrypt"}
_STATES = {"prepared", "result_ready", "published", "source_removed", "complete"}
_FIELDS = {
    "format", "transaction_id", "operation", "state", "parent_identity",
    "source_name", "destination_name", "temporary_name", "source_identity",
    "result_identity", "created_ns",
}


@dataclass(frozen=True, slots=True)
class RecoveryRecord:
    transaction_id: str
    operation: str | None
    state: str | None
    classification: str
    source_name: str | None = None
    destination_name: str | None = None
    temporary_name: str | None = None
    detail: str | None = None


def _identity(info: os.stat_result) -> dict[str, int]:
    return {"device": int(info.st_dev), "inode": int(info.st_ino)}


def _valid_identity(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"device", "inode"}
        and type(value["device"]) is int
        and type(value["inode"]) is int
        and 0 <= value["device"] <= 2**64 - 1
        and 0 <= value["inode"] <= 2**64 - 1
    )


def _component(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value not in {".", ".."}
        and "\x00" not in value
        and "/" not in value
        and "\\" not in value
        and len(value.encode("utf-8", "strict")) <= 4096
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _encode(data: dict[str, Any]) -> bytes:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > _MAX_RECORD:
        raise ValueError("journal exceeds maximum size")
    return raw


def _decode(raw: bytes, transaction_id: str, parent_info: os.stat_result) -> dict[str, Any]:
    if not raw or len(raw) > _MAX_RECORD or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("journal size or encoding is invalid")
    text = raw.decode("utf-8", "strict")
    data = json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON constant")))
    if not isinstance(data, dict) or set(data) != _FIELDS:
        raise ValueError("journal fields do not match schema")
    if type(data["format"]) is not int or data["format"] != 1:
        raise ValueError("unsupported journal format")
    if data["transaction_id"] != transaction_id or not _ID.fullmatch(transaction_id):
        raise ValueError("transaction identifier mismatch")
    if data["operation"] not in _OPERATIONS or data["state"] not in _STATES:
        raise ValueError("unknown operation or state")
    if not _valid_identity(data["parent_identity"]) or not _valid_identity(data["source_identity"]):
        raise ValueError("invalid resource identity")
    if not _valid_identity(data["result_identity"]) and data["result_identity"] is not None:
        raise ValueError("invalid result identity")
    if not _component(data["source_name"]) or not _component(data["destination_name"]):
        raise ValueError("invalid resource basename")
    if data["source_name"] == data["destination_name"]:
        raise ValueError("source and destination names are equal")
    is_file = data["operation"].startswith("file_")
    if data["temporary_name"] != ("result" if is_file else None):
        raise ValueError("temporary name does not match operation")
    if type(data["created_ns"]) is not int or not 0 <= data["created_ns"] <= 2**63 - 1:
        raise ValueError("invalid creation timestamp")
    # Canonical representation is required; this also rejects trailing bytes/newlines.
    if _encode(data) != raw:
        raise ValueError("journal is not canonically encoded")
    return data


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    if not sys.platform.startswith("linux"):
        raise OSError("directory fsync is unsupported")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Transaction:
    """Internal writer for one transaction directory."""

    def __init__(self, parent: Path, directory: Path, data: dict[str, Any]):
        self.parent = parent
        self.directory = directory
        self.data = data

    @classmethod
    def begin(cls, parent: Path, operation: str, source_name: str, destination_name: str,
              source_info: os.stat_result) -> "Transaction":
        if operation not in _OPERATIONS or not _component(source_name) or not _component(destination_name):
            raise ValueError("invalid transaction parameters")
        if source_name == destination_name:
            raise ValueError("source and destination must differ")
        parent_info = parent.stat()
        for _ in range(8):
            transaction_id = secrets.token_hex(16)
            directory = parent / (_PREFIX + transaction_id)
            try:
                os.mkdir(directory, 0o700 if os.name != "nt" else 0o777)
                break
            except FileExistsError:
                continue
        else:
            raise FileExistsError("could not allocate unique transaction directory")
        data = {
            "format": 1,
            "transaction_id": transaction_id,
            "operation": operation,
            "state": "prepared",
            "parent_identity": _identity(parent_info),
            "source_name": source_name,
            "destination_name": destination_name,
            "temporary_name": "result" if operation.startswith("file_") else None,
            "source_identity": _identity(source_info),
            "result_identity": None,
            "created_ns": __import__("time").time_ns(),
        }
        transaction = cls(parent, directory, data)
        try:
            transaction._persist()
            _sync_directory(parent)
        except Exception:
            # Preserve any directory that may contain a partially durable journal.
            raise
        return transaction

    @property
    def result_path(self) -> Path:
        return self.directory / "result"

    def set_result_ready(self, result_info: os.stat_result) -> None:
        self.data["result_identity"] = _identity(result_info)
        self.data["state"] = "result_ready"
        self._persist()

    def set_state(self, state: str) -> None:
        if state not in _STATES:
            raise ValueError("invalid transaction state")
        self.data["state"] = state
        self._persist()

    def _persist(self) -> None:
        raw = _encode(self.data)
        temporary = self.directory / (".journal-" + secrets.token_hex(8))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / "journal.json")
            _sync_directory(self.directory)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def finish(self) -> None:
        # Keep the completed record as durable evidence. Cleanup is intentionally
        # deferred until a separately specified, identity-safe retention policy exists.
        if self.data["state"] != "complete":
            raise RuntimeError("transaction is not complete")


def _lstat_identity(path: Path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing", None
    if stat.S_ISLNK(info.st_mode):
        return "symlink", None
    return ("regular" if stat.S_ISREG(info.st_mode) else "directory" if stat.S_ISDIR(info.st_mode) else "other"), _identity(info)


def inspect(parent: str | os.PathLike[str]) -> tuple[RecoveryRecord, ...]:
    """Inspect transaction directories without modifying any filesystem entry."""
    root = Path(os.path.abspath(os.fspath(parent)))
    root_info = root.lstat()
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise NotADirectoryError("recovery inspection requires a real directory")
    records: list[RecoveryRecord] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.name.startswith(_PREFIX):
            continue
        transaction_id = entry.name[len(_PREFIX):]
        if not _ID.fullmatch(transaction_id):
            records.append(RecoveryRecord(transaction_id, None, None, "corrupt", detail="invalid transaction directory name"))
            continue
        try:
            entry_info = entry.lstat()
            if not stat.S_ISDIR(entry_info.st_mode) or stat.S_ISLNK(entry_info.st_mode):
                raise ValueError("transaction entry is not a real directory")
            journal = entry / "journal.json"
            journal_info = journal.lstat()
            if not stat.S_ISREG(journal_info.st_mode) or stat.S_ISLNK(journal_info.st_mode) or journal_info.st_size > _MAX_RECORD:
                raise ValueError("journal is not a bounded regular file")
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(journal, flags)
            opened_info = os.fstat(fd)
            if not stat.S_ISREG(opened_info.st_mode) or _identity(opened_info) != _identity(journal_info):
                os.close(fd)
                raise ValueError("journal changed during inspection")
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(_MAX_RECORD + 1)
            data = _decode(raw, transaction_id, root_info)
            if data["parent_identity"] != _identity(root_info):
                records.append(RecoveryRecord(
                    transaction_id, data["operation"], data["state"], "ambiguous",
                    data["source_name"], data["destination_name"], data["temporary_name"],
                    "parent directory identity mismatch",
                ))
                continue
            if data["parent_identity"]["inode"] == 0 or data["source_identity"]["inode"] == 0:
                records.append(RecoveryRecord(
                    transaction_id, data["operation"], data["state"], "ambiguous",
                    data["source_name"], data["destination_name"], data["temporary_name"],
                    "filesystem identity is not verifiable on this platform",
                ))
                continue
            source = root / data["source_name"]
            destination = root / data["destination_name"]
            source_kind, source_id = _lstat_identity(source)
            dest_kind, dest_id = _lstat_identity(destination)
            temp_kind, temp_id = ("missing", None)
            if data["temporary_name"] is not None:
                temp_kind, temp_id = _lstat_identity(entry / "result")
            expected_source = data["source_identity"]
            expected_result = data["result_identity"]
            classification = "ambiguous"
            if source_kind in {"symlink", "other"} or dest_kind in {"symlink", "other"} or temp_kind in {"symlink", "other"}:
                classification = "ambiguous"
            elif data["operation"].startswith("dir_"):
                if source_kind == "directory" and source_id == expected_source and dest_kind == "missing":
                    classification = "prepared_no_output" if data["state"] == "prepared" else "ambiguous"
                elif source_kind == "missing" and dest_kind == "directory" and dest_id == expected_source:
                    classification = "source_removed" if data["state"] in {"source_removed", "complete"} else "published_source_missing"
            else:
                if source_kind == "regular" and source_id == expected_source and dest_kind == "missing" and temp_kind == "missing":
                    classification = "prepared_no_output"
                elif source_kind == "regular" and source_id == expected_source and dest_kind == "missing" and temp_kind == "regular":
                    classification = "result_ready" if expected_result is not None and temp_id == expected_result else "result_incomplete_or_unverified"
                elif dest_kind == "regular" and expected_result is not None and dest_id == expected_result and source_kind == "regular" and source_id == expected_source:
                    classification = "published_source_present"
                elif dest_kind == "regular" and expected_result is not None and dest_id == expected_result and source_kind == "missing":
                    classification = "source_removed" if data["state"] in {"source_removed", "complete"} else "published_source_missing"
            records.append(RecoveryRecord(transaction_id, data["operation"], data["state"], classification,
                                          data["source_name"], data["destination_name"], data["temporary_name"]))
        except Exception as exc:
            records.append(RecoveryRecord(transaction_id, None, None, "corrupt", detail=str(exc)))
    return tuple(records)
