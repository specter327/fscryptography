#!/usr/bin/env python3
"""End-to-end demonstration against real filesystem resources.

Run from the repository root after installing the package:
    python -m pip install -e ".[test]"
    python tests/real_resources.py

Every run creates a unique directory under tests/resources/. Existing resources
are never overwritten or removed. The generated directory is intentionally kept
for manual inspection.
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import fscryptography


ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = ROOT / "resources"
PASSWORD = "fscryptography-real-resource-demo-password"


def log(message: str) -> None:
    print(f"[fscryptography] {message}", flush=True)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_bytes(path: Path, expected: bytes, description: str) -> None:
    assert path.is_file(), f"{description}: expected a regular file at {path}"
    actual = path.read_bytes()
    assert actual == expected, (
        f"{description}: content mismatch "
        f"(expected {len(expected)} bytes, got {len(actual)} bytes)"
    )
    log(f"PASS {description}: {len(actual):,} bytes, SHA-256={digest(actual)}")


def main() -> int:
    RESOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:12]
    )
    workspace = RESOURCE_ROOT / f"run-{run_id}"
    workspace.mkdir(mode=0o700 if os.name != "nt" else 0o777)

    log("=" * 72)
    log("REAL FILESYSTEM RESOURCE DEMONSTRATION")
    log(f"Version: {fscryptography.__version__}")
    log(f"Platform: {sys.platform} | Python: {sys.version.split()[0]}")
    log(f"Resource workspace: {workspace}")
    log("Existing files are not overwritten; this run is retained for inspection.")
    log("=" * 72)

    log("\n[1/9] MasterKey generation and Manager lifecycle")
    master_key = fscryptography.generate()
    assert isinstance(master_key, str) and master_key
    manager = fscryptography.Manager(key=master_key)
    assert manager.export_key() == master_key
    log("PASS random MasterKey generated as Base64 text")
    log("PASS Manager opened and exported the identical MasterKey")

    log("\n[2/9] Real file encryption and byte-for-byte restoration")
    small_data = (
        "Filesystem cryptography demonstration\n"
        "Unicode: México — 東京 — Ελληνικά\n"
        "This is a real file, not an in-memory mock.\n"
    ).encode("utf-8")
    large_data = (bytes(range(256)) * 16_384) + b"END-OF-FILE"
    empty_data = b""

    small_source = workspace / "meeting-notes.txt"
    large_source = workspace / "large-dataset.bin"
    empty_source = workspace / "empty-file.dat"
    small_source.write_bytes(small_data)
    large_source.write_bytes(large_data)
    empty_source.write_bytes(empty_data)

    manager.file.encrypt(small_source)
    small_encrypted = workspace / "meeting-notes.fscrypt"
    assert small_encrypted.is_file() and not small_source.exists()
    log(f"PASS encrypted small file: {small_encrypted.name}")
    manager.file.decrypt(small_encrypted)
    assert_bytes(small_source, small_data, "small-file round trip")

    manager.file.encrypt(large_source)
    large_encrypted = workspace / "large-dataset.fscrypt"
    assert large_encrypted.is_file() and not large_source.exists()
    log(f"PASS encrypted large file: {large_encrypted.name}")
    manager.file.decrypt(large_encrypted)
    assert_bytes(large_source, large_data, "multi-megabyte streaming round trip")

    manager.file.encrypt(empty_source)
    empty_encrypted = workspace / "empty-file.fscrypt"
    assert empty_encrypted.is_file()
    manager.file.decrypt(empty_encrypted)
    assert_bytes(empty_source, empty_data, "empty-file round trip")

    log("\n[3/9] Custom output extension and original suffix restoration")
    archive_data = b"ARCHIVE-DEMO\x00" + bytes(range(128)) * 1024
    archive_source = workspace / "backup.tar.gz"
    archive_source.write_bytes(archive_data)
    manager.file.encrypt(archive_source, new_extension=".locked")
    archive_encrypted = workspace / "backup.tar.locked"
    assert archive_encrypted.is_file() and not archive_source.exists()
    log(f"PASS custom encrypted suffix: {archive_encrypted.name}")
    manager.file.decrypt(archive_encrypted)
    assert_bytes(archive_source, archive_data, "custom-extension round trip")

    log("\n[4/9] File-name encryption")
    private_data = b"Confidential document body\n" * 4096
    private_source = workspace / "private-client-record.txt"
    private_source.write_bytes(private_data)
    manager.file.encrypt(private_source, encrypt_name=True)
    encrypted_candidates = [
        path for path in workspace.iterdir()
        if path.is_file() and path.name.startswith("~1")
    ]
    assert len(encrypted_candidates) == 1, (
        f"expected one encrypted-name file, found {len(encrypted_candidates)}"
    )
    private_encrypted = encrypted_candidates[0]
    assert not private_source.exists()
    assert private_encrypted.name != "private-client-record.txt"
    log(f"PASS visible filename concealed as: {private_encrypted.name}")
    manager.file.decrypt(private_encrypted)
    assert_bytes(private_source, private_data, "encrypted-name file round trip")

    log("\n[5/9] Directory-name encryption (contents must remain untouched)")
    directory = workspace / "restricted-project"
    directory.mkdir()
    child_data = b"Child content is deliberately not encrypted.\n"
    nested = directory / "nested"
    nested.mkdir()
    child = directory / "readme.txt"
    nested_child = nested / "payload.bin"
    child.write_bytes(child_data)
    nested_child.write_bytes(bytes(range(64)) * 128)
    nested_before = nested_child.read_bytes()

    manager.dir.encrypt(directory)
    encrypted_directories = [
        path for path in workspace.iterdir()
        if path.is_dir() and path.name.startswith("~1")
    ]
    assert len(encrypted_directories) == 1
    encrypted_directory = encrypted_directories[0]
    assert not directory.exists()
    assert (encrypted_directory / "readme.txt").read_bytes() == child_data
    assert (encrypted_directory / "nested" / "payload.bin").read_bytes() == nested_before
    log("PASS directory component encrypted; child names and file contents unchanged")

    manager.dir.decrypt(encrypted_directory)
    assert directory.is_dir()
    assert_bytes(child, child_data, "directory child preserved")
    assert nested_child.read_bytes() == nested_before
    log("PASS directory name restored without traversing or transforming its contents")

    log("\n[6/9] No-overwrite behavior on destination collision")
    conflict_source = workspace / "collision.txt"
    conflict_destination = workspace / "collision.fscrypt"
    source_data = b"original source must survive"
    destination_data = b"pre-existing destination must survive"
    conflict_source.write_bytes(source_data)
    conflict_destination.write_bytes(destination_data)
    try:
        manager.file.encrypt(conflict_source)
    except fscryptography.DestinationConflictError:
        log("PASS expected DestinationConflictError raised")
    else:
        raise AssertionError("encryption unexpectedly overwrote an existing destination")
    assert_bytes(conflict_source, source_data, "source preserved after destination conflict")
    assert_bytes(conflict_destination, destination_data, "destination preserved after conflict")

    log("\n[7/9] Tamper detection and wrong-key rejection")
    tamper_source = workspace / "tamper-check.txt"
    tamper_data = b"Authenticated payload used for tamper detection.\n" * 8192
    tamper_source.write_bytes(tamper_data)
    manager.file.encrypt(tamper_source)
    tamper_ciphertext = workspace / "tamper-check.fscrypt"
    tampered = bytearray(tamper_ciphertext.read_bytes())
    assert len(tampered) > 1
    tampered[-1] ^= 0x01
    tamper_ciphertext.write_bytes(tampered)
    try:
        manager.file.decrypt(tamper_ciphertext)
    except fscryptography.AuthenticationError:
        log("PASS modified ciphertext rejected with AuthenticationError")
    else:
        raise AssertionError("tampered ciphertext was accepted")
    assert tamper_ciphertext.is_file() and not tamper_source.exists()
    log("PASS failed authenticated decryption did not publish plaintext or remove ciphertext")

    wrong_key_source = workspace / "wrong-key-check.txt"
    wrong_key_data = b"Only the original MasterKey may decrypt this.\n" * 1024
    wrong_key_source.write_bytes(wrong_key_data)
    manager.file.encrypt(wrong_key_source)
    wrong_key_ciphertext = workspace / "wrong-key-check.fscrypt"
    wrong_key_manager = fscryptography.Manager(fscryptography.generate())
    try:
        try:
            wrong_key_manager.file.decrypt(wrong_key_ciphertext)
        except fscryptography.AuthenticationError:
            log("PASS ciphertext rejected under an unrelated MasterKey")
        else:
            raise AssertionError("ciphertext was decrypted with an unrelated key")
    finally:
        wrong_key_manager.close()
    assert wrong_key_ciphertext.is_file() and not wrong_key_source.exists()

    log("\n[8/9] Password-protected MasterKey and key replacement")
    protected_key = fscryptography.generate(password=PASSWORD)
    with fscryptography.Manager(key=protected_key, password=PASSWORD) as protected_manager:
        assert protected_manager.export_key() == protected_key
        protected_source = workspace / "protected-master-key.txt"
        protected_data = b"Password-protected MasterKey context.\n"
        protected_source.write_bytes(protected_data)
        protected_manager.file.encrypt(protected_source)
        protected_ciphertext = workspace / "protected-master-key.fscrypt"
        protected_manager.file.decrypt(protected_ciphertext)
        assert_bytes(protected_source, protected_data, "protected-MasterKey round trip")
    log("PASS protected MasterKey opened; password was supplied only at construction")

    replacement_key = fscryptography.generate()
    manager.change_key(replacement_key)
    assert manager.export_key() == replacement_key
    rotated_source = workspace / "after-key-change.txt"
    rotated_data = b"Operation uses the replacement key.\n"
    rotated_source.write_bytes(rotated_data)
    manager.file.encrypt(rotated_source)
    rotated_ciphertext = workspace / "after-key-change.fscrypt"
    manager.file.decrypt(rotated_ciphertext)
    assert_bytes(rotated_source, rotated_data, "operation after Manager.change_key")
    log("PASS Manager.change_key switched the active cryptographic context")

    log("\n[9/9] Persistent recovery journal inspection")
    records = manager.inspect_recovery(workspace)
    assert isinstance(records, tuple)
    assert records, "expected filesystem operations to leave inspectable journal records"
    for record in records:
        log(
            "JOURNAL "
            f"operation={record.operation} "
            f"state={record.state} "
            f"classification={record.classification}"
        )
    assert all(record.classification != "corrupt" for record in records), (
        "unexpected corrupt transaction journal detected"
    )
    log(f"PASS inspected {len(records)} immutable recovery records without modifying them")

    manager.close()
    log("\n" + "=" * 72)
    log("ALL REAL-RESOURCE DEMONSTRATIONS PASSED")
    log(f"Artifacts retained at: {workspace}")
    log("No pre-existing resource was overwritten or removed.")
    log("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
