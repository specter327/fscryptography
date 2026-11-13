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

from .errors import NameConstraintError
from .names import NameProfile, validate_name

_PREFIX = ".fscryptography-txn-"
_ID = re.compile(r"^[0-9a-f]{32}$")
_MAX_RECORD = 16 * 1024
_OPERATIONS = {"file_encrypt", "file_decrypt", "dir_encrypt", "dir_decrypt"}
_STATES = {"prepared", "result_ready", "published", "source_retained", "source_removed", "complete"}
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

    def __init__(self, parent: Path, directory: Path, data: dict[str, Any], *, parent_fd: int | None = None):
        self.parent = parent
        self.directory = directory
        self.data = data
        self.parent_fd = os.dup(parent_fd) if parent_fd is not None else None
        self.directory_fd: int | None = None
        try:
            if self.parent_fd is not None:
                self.directory_fd = os.open(
                    directory.name,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=self.parent_fd,
                )
        except BaseException:
            if self.parent_fd is not None:
                os.close(self.parent_fd)
                self.parent_fd = None
            raise

    @classmethod
    def begin(cls, parent: Path, operation: str, source_name: str, destination_name: str,
              source_info: os.stat_result, *, parent_fd: int | None = None) -> "Transaction":
        if operation not in _OPERATIONS or not _component(source_name) or not _component(destination_name):
            raise ValueError("invalid transaction parameters")
        if source_name == destination_name:
            raise ValueError("source and destination must differ")
        parent_info = os.fstat(parent_fd) if parent_fd is not None else parent.stat()
        for _ in range(8):
            transaction_id = secrets.token_hex(16)
            directory = parent / (_PREFIX + transaction_id)
            try:
                if parent_fd is not None:
                    os.mkdir(directory.name, 0o700, dir_fd=parent_fd)
                else:
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
        transaction = cls(parent, directory, data, parent_fd=parent_fd)
        try:
            transaction._persist()
            if parent_fd is not None:
                os.fsync(parent_fd)
            else:
                _sync_directory(parent)
        except Exception:
            # Preserve any directory that may contain a partially durable journal.
            transaction.close()
            raise
        return transaction

    @property
    def result_path(self) -> Path:
        if self.directory_fd is not None:
            raise RuntimeError("descriptor-anchored transactions do not expose pathname results")
        return self.directory / "result"

    @property
    def retained_path(self) -> Path:
        if self.directory_fd is not None:
            raise RuntimeError("descriptor-anchored transactions do not expose pathname entries")
        return self.directory / "source"

    def open_result(self) -> int:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        if self.directory_fd is not None:
            return os.open("result", flags, 0o600, dir_fd=self.directory_fd)
        return os.open(self.result_path, flags, 0o600)

    def stat_result(self) -> os.stat_result:
        if self.directory_fd is not None:
            return os.stat("result", dir_fd=self.directory_fd, follow_symlinks=False)
        return self.result_path.lstat()

    def rename_result_to(self, parent_fd: int, destination_name: str) -> None:
        if self.directory_fd is None:
            raise RuntimeError("transaction is not descriptor-anchored")
        from ._directory import _renameat2
        _renameat2(self.directory_fd, "result", parent_fd, destination_name)

    def unlink_retained(self) -> None:
        if self.directory_fd is not None:
            os.unlink("source", dir_fd=self.directory_fd)
        else:
            self.retained_path.unlink()

    def close(self) -> None:
        if self.directory_fd is not None:
            os.close(self.directory_fd)
            self.directory_fd = None
        if self.parent_fd is not None:
            os.close(self.parent_fd)
            self.parent_fd = None

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
        temporary_name = ".journal-" + secrets.token_hex(8)
        temporary = self.directory / temporary_name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        if self.directory_fd is not None:
            fd = os.open(temporary_name, flags, 0o600, dir_fd=self.directory_fd)
        else:
            fd = os.open(temporary, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if self.directory_fd is not None:
                os.replace(
                    temporary_name, "journal.json",
                    src_dir_fd=self.directory_fd, dst_dir_fd=self.directory_fd,
                )
                os.fsync(self.directory_fd)
            else:
                os.replace(temporary, self.directory / "journal.json")
                _sync_directory(self.directory)
        except Exception:
            try:
                if self.directory_fd is not None:
                    os.unlink(temporary_name, dir_fd=self.directory_fd)
                else:
                    temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def finish(self) -> None:
        # Keep the completed record as durable evidence. Cleanup is intentionally
        # deferred until a separately specified, identity-safe retention policy exists.
        if self.data["state"] != "complete":
            raise RuntimeError("transaction is not complete")


def _inspect_path_based(parent: str | os.PathLike[str]) -> tuple[RecoveryRecord, ...]:
    """Windows fallback; path-based inspection has weaker race guarantees."""
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
            fd = os.open(journal, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            opened_info = os.fstat(fd)
            if not stat.S_ISREG(opened_info.st_mode) or _identity(opened_info) != _identity(journal_info):
                os.close(fd)
                raise ValueError("journal changed during inspection")
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(_MAX_RECORD + 1)
            data = _decode(raw, transaction_id, root_info)
            if data["parent_identity"] != _identity(root_info):
                records.append(RecoveryRecord(transaction_id, data["operation"], data["state"], "ambiguous",
                    data["source_name"], data["destination_name"], data["temporary_name"], "parent directory identity mismatch"))
                continue
            source_kind, source_id = _lstat_identity(root / data["source_name"])
            dest_kind, dest_id = _lstat_identity(root / data["destination_name"])
            temp_kind, temp_id = ("missing", None)
            if data["temporary_name"] is not None:
                temp_kind, temp_id = _lstat_identity(entry / "result")
            retained_kind, retained_id = ("missing", None)
            if data["operation"].startswith("file_"):
                retained_kind, retained_id = _lstat_identity(entry / "source")
            expected_source, expected_result = data["source_identity"], data["result_identity"]
            classification = "ambiguous"
            if any(kind in {"symlink", "other"} for kind in (source_kind, dest_kind, temp_kind, retained_kind)):
                classification = "ambiguous"
            elif data["operation"].startswith("dir_"):
                if source_kind == "directory" and source_id == expected_source and dest_kind == "missing":
                    classification = "prepared_no_output" if data["state"] == "prepared" else "ambiguous"
                elif source_kind == "missing" and dest_kind == "directory" and dest_id == expected_source:
                    classification = "source_removed" if data["state"] in {"source_removed", "complete"} else "published_source_missing"
            elif retained_kind != "missing":
                if retained_kind == "regular" and retained_id == expected_source and source_kind == "missing" and dest_kind == "regular" and expected_result is not None and dest_id == expected_result:
                    classification = "source_retained"
            elif source_kind == "regular" and source_id == expected_source and dest_kind == "missing" and temp_kind == "missing":
                classification = "prepared_no_output" if data["state"] == "prepared" else "ambiguous"
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


def _lstat_identity(path: Path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing", None
    if stat.S_ISLNK(info.st_mode):
        return "symlink", None
    return ("regular" if stat.S_ISREG(info.st_mode) else "directory" if stat.S_ISDIR(info.st_mode) else "other"), _identity(info)


def inspect(parent: str | os.PathLike[str]) -> tuple[RecoveryRecord, ...]:
    """Inspect journals without modifying entries; Linux uses descriptor-relative traversal."""
    if not sys.platform.startswith("linux"):
        return _inspect_path_based(parent)
    root = Path(os.path.abspath(os.fspath(parent)))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    root_fd = os.open(root, flags)
    try:
        root_info = os.fstat(root_fd)
        if not stat.S_ISDIR(root_info.st_mode):
            raise NotADirectoryError("recovery inspection requires a real directory")
        records: list[RecoveryRecord] = []
        for entry_name in sorted(os.listdir(root_fd)):
            if not entry_name.startswith(_PREFIX):
                continue
            transaction_id = entry_name[len(_PREFIX):]
            if not _ID.fullmatch(transaction_id):
                records.append(RecoveryRecord(transaction_id, None, None, "corrupt", detail="invalid transaction directory name"))
                continue
            entry_fd = None
            journal_fd = None
            try:
                entry_fd = os.open(
                    entry_name,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=root_fd,
                )
                entry_info = os.fstat(entry_fd)
                if not stat.S_ISDIR(entry_info.st_mode):
                    raise ValueError("transaction entry is not a real directory")
                journal_info = os.stat("journal.json", dir_fd=entry_fd, follow_symlinks=False)
                if not stat.S_ISREG(journal_info.st_mode) or journal_info.st_size > _MAX_RECORD:
                    raise ValueError("journal is not a bounded regular file")
                journal_fd = os.open("journal.json", os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=entry_fd)
                opened_info = os.fstat(journal_fd)
                if not stat.S_ISREG(opened_info.st_mode) or _identity(opened_info) != _identity(journal_info):
                    raise ValueError("journal changed during inspection")
                with os.fdopen(journal_fd, "rb") as stream:
                    journal_fd = None
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

                def identity_at(directory_fd: int, name: str):
                    try:
                        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                    except FileNotFoundError:
                        return "missing", None
                    if stat.S_ISLNK(info.st_mode):
                        return "symlink", None
                    kind = "regular" if stat.S_ISREG(info.st_mode) else "directory" if stat.S_ISDIR(info.st_mode) else "other"
                    return kind, _identity(info)

                source_kind, source_id = identity_at(root_fd, data["source_name"])
                dest_kind, dest_id = identity_at(root_fd, data["destination_name"])
                temp_kind, temp_id = ("missing", None)
                if data["temporary_name"] is not None:
                    temp_kind, temp_id = identity_at(entry_fd, "result")
                retained_kind, retained_id = ("missing", None)
                if data["operation"].startswith("file_"):
                    retained_kind, retained_id = identity_at(entry_fd, "source")
                expected_source = data["source_identity"]
                expected_result = data["result_identity"]
                classification = "ambiguous"
                if (
                    source_kind in {"symlink", "other"}
                    or dest_kind in {"symlink", "other"}
                    or temp_kind in {"symlink", "other"}
                    or retained_kind in {"symlink", "other"}
                ):
                    classification = "ambiguous"
                elif data["operation"].startswith("dir_"):
                    if source_kind == "directory" and source_id == expected_source and dest_kind == "missing":
                        classification = "prepared_no_output" if data["state"] == "prepared" else "ambiguous"
                    elif source_kind == "missing" and dest_kind == "directory" and dest_id == expected_source:
                        classification = "source_removed" if data["state"] in {"source_removed", "complete"} else "published_source_missing"
                else:
                    if retained_kind != "missing":
                        if (
                            retained_kind == "regular" and retained_id == expected_source
                            and source_kind == "missing" and dest_kind == "regular"
                            and expected_result is not None and dest_id == expected_result
                        ):
                            classification = "source_retained"
                        else:
                            classification = "ambiguous"
                    elif source_kind == "regular" and source_id == expected_source and dest_kind == "missing" and temp_kind == "missing":
                        classification = "prepared_no_output" if data["state"] == "prepared" else "ambiguous"
                    elif source_kind == "regular" and source_id == expected_source and dest_kind == "missing" and temp_kind == "regular":
                        classification = "result_ready" if expected_result is not None and temp_id == expected_result else "result_incomplete_or_unverified"
                    elif dest_kind == "regular" and expected_result is not None and dest_id == expected_result and source_kind == "regular" and source_id == expected_source:
                        classification = "published_source_present"
                    elif dest_kind == "regular" and expected_result is not None and dest_id == expected_result and source_kind == "missing":
                        classification = "source_removed" if data["state"] in {"source_removed", "complete"} else "published_source_missing"
                records.append(RecoveryRecord(
                    transaction_id, data["operation"], data["state"], classification,
                    data["source_name"], data["destination_name"], data["temporary_name"],
                ))
            except Exception as exc:
                records.append(RecoveryRecord(transaction_id, None, None, "corrupt", detail=str(exc)))
            finally:
                if journal_fd is not None:
                    os.close(journal_fd)
                if entry_fd is not None:
                    os.close(entry_fd)
        return tuple(records)
    finally:
        os.close(root_fd)
