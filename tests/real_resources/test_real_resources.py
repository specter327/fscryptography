"""End-to-end demonstration against real filesystem resources.

Run from any working directory:
    python tests/real_resources/test_real_resources.py

The generated resources are retained under tests/resources/runs/ for inspection.
Each execution gets a unique directory; existing files are never reused or removed.
"""

from __future__ import annotations

import hashlib
import platform
import sys
import uuid
from pathlib import Path

import pytest

import fscryptography
from fscryptography import AuthenticationError, DestinationConflictError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOURCES_ROOT = PROJECT_ROOT / "tests" / "resources"
RUNS_ROOT = RESOURCES_ROOT / "runs"


def _log(message: str) -> None:
    print(f"[fscryptography integration] {message}", flush=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert(condition: bool, message: str) -> None:
    assert condition, message
    _log(f"PASS: {message}")


def test_real_filesystem_resources() -> None:
    """Exercise the public API using actual files and directories on disk."""
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    workspace = RUNS_ROOT / f"run-{uuid.uuid4().hex}"
    workspace.mkdir()

    _log("=" * 72)
    _log("REAL FILESYSTEM INTEGRATION")
    _log(f"Python: {sys.version.split()[0]}")
    _log(f"Platform: {platform.platform()}")
    _log(f"Package: fscryptography {fscryptography.__version__}")
    _log(f"Resource workspace: {workspace}")
    _log("Generated resources are retained; no pre-existing resource is modified.")

    # Create all input resources physically below tests/resources/.
    text_source = workspace / "readme.txt"
    text_payload = (
        "fscryptography — integración sobre recursos reales.\n"
        "UTF-8: áéíóú, ñ, 東京, 🔐\n"
        "La librería cifra rutas del filesystem y conserva el contenido.\n"
    ).encode("utf-8")
    text_source.write_bytes(text_payload)

    empty_source = workspace / "empty.bin"
    empty_source.write_bytes(b"")

    large_source = workspace / "large-payload.bin"
    large_payload = bytes(range(256)) * (12 * 1024)  # 3 MiB
    large_source.write_bytes(large_payload)

    custom_source = workspace / "archive.tar.gz"
    custom_payload = b"custom extension round-trip\n" * 8192
    custom_source.write_bytes(custom_payload)

    private_source = workspace / "confidential report.txt"
    private_payload = b"filename encryption test\n" * 1024
    private_source.write_bytes(private_payload)

    directory_source = workspace / "private-directory"
    directory_source.mkdir()
    child_payload = b"This child must remain unchanged.\n" * 128
    child_source = directory_source / "child.txt"
    child_source.write_bytes(child_payload)
    nested = directory_source / "nested"
    nested.mkdir()
    nested_payload = b"Nested data is not recursively encrypted.\n"
    (nested / "data.bin").write_bytes(nested_payload)

    _log("Created real input resources:")
    for path in (
        text_source,
        empty_source,
        large_source,
        custom_source,
        private_source,
        directory_source,
    ):
        _log(f"  - {path.relative_to(RESOURCES_ROOT)}")

    # Generate and open a random MasterKey. The manager owns the open context.
    master_key = fscryptography.generate()
    _assert(isinstance(master_key, str) and bool(master_key), "generate() returns a non-empty Base64 string")

    with fscryptography.Manager(key=master_key) as manager:
        _assert(manager.export_key() == master_key, "export_key() returns the active MasterKey")

        # Visible filename + default .fscrypt extension.
        _log("1/9 Encrypt/decrypt a UTF-8 text file using the default extension.")
        manager.file.encrypt(text_source)
        text_encrypted = workspace / "readme.fscrypt"
        _assert(text_encrypted.is_file(), "encrypted text file is published at readme.fscrypt")
        _assert(not text_source.exists(), "plaintext source is retired after successful publication")
        manager.file.decrypt(text_encrypted)
        _assert(text_source.read_bytes() == text_payload, "text file round-trip preserves exact bytes")

        # Empty file.
        _log("2/9 Encrypt/decrypt an empty file.")
        manager.file.encrypt(empty_source)
        empty_encrypted = workspace / "empty.fscrypt"
        _assert(empty_encrypted.is_file(), "empty file produces an encrypted resource")
        manager.file.decrypt(empty_encrypted)
        _assert(empty_source.read_bytes() == b"", "empty file round-trip preserves zero bytes")

        # Multi-segment Streaming AEAD file.
        _log("3/9 Encrypt/decrypt a multi-megabyte binary file.")
        original_large_hash = hashlib.sha256(large_payload).hexdigest()
        manager.file.encrypt(large_source)
        large_encrypted = workspace / "large-payload.fscrypt"
        _assert(large_encrypted.is_file(), "large encrypted file exists")
        _assert(large_encrypted.stat().st_size > len(large_payload), "encrypted file includes format and AEAD overhead")
        manager.file.decrypt(large_encrypted)
        _assert(_sha256(large_source) == original_large_hash, "large-file round-trip preserves SHA-256")

        # Custom extension.
        _log("4/9 Use a caller-selected output extension.")
        manager.file.encrypt(custom_source, new_extension=".locked")
        custom_encrypted = workspace / "archive.tar.locked"
        _assert(custom_encrypted.is_file(), "custom output extension is applied to the resource name")
        manager.file.decrypt(custom_encrypted)
        _assert(custom_source.read_bytes() == custom_payload, "custom-extension round-trip restores original name and bytes")

        # Encrypt the entire filename.
        _log("5/9 Encrypt the filename as well as the file contents.")
        manager.file.encrypt(private_source, encrypt_name=True)
        encrypted_name_candidates = [
            path for path in workspace.iterdir()
            if path.is_file() and path.name.startswith("~1")
        ]
        _assert(len(encrypted_name_candidates) == 1, "encrypted filename uses the ~1 marker")
        private_encrypted = encrypted_name_candidates[0]
        _assert("confidential report" not in private_encrypted.name, "plaintext filename is not visible")
        manager.file.decrypt(private_encrypted)
        _assert(private_source.read_bytes() == private_payload, "encrypted-filename round-trip restores original resource")

        # Directory names only; descendants are intentionally untouched.
        _log("6/9 Encrypt/decrypt a directory name without traversing its contents.")
        child_hash_before = _sha256(child_source)
        nested_hash_before = _sha256(nested / "data.bin")
        manager.dir.encrypt(directory_source)
        encrypted_directories = [
            path for path in workspace.iterdir()
            if path.is_dir() and path.name.startswith("~1")
        ]
        _assert(len(encrypted_directories) == 1, "directory name is replaced by its encrypted representation")
        encrypted_directory = encrypted_directories[0]
        _assert((encrypted_directory / "child.txt").is_file(), "child file remains in place")
        _assert(_sha256(encrypted_directory / "child.txt") == child_hash_before, "child file bytes are unchanged")
        _assert(_sha256(encrypted_directory / "nested" / "data.bin") == nested_hash_before, "nested file bytes are unchanged")
        manager.dir.decrypt(encrypted_directory)
        _assert(directory_source.is_dir(), "directory name is restored")
        _assert(_sha256(child_source) == child_hash_before, "directory decryption does not alter child content")

        # Existing destination must never be overwritten.
        _log("7/9 Verify no-overwrite behavior on destination conflicts.")
        conflict_source = workspace / "collision.txt"
        conflict_source.write_bytes(b"source must survive")
        conflict_destination = workspace / "collision.fscrypt"
        conflict_destination.write_bytes(b"pre-existing destination")
        with pytest.raises(DestinationConflictError):
            manager.file.encrypt(conflict_source)
        _assert(conflict_source.read_bytes() == b"source must survive", "source survives a destination conflict")
        _assert(conflict_destination.read_bytes() == b"pre-existing destination", "existing destination is not overwritten")

        # Authenticated decryption must not publish plaintext after tampering.
        _log("8/9 Alter ciphertext and verify authenticated decryption fails safely.")
        tamper_source = workspace / "tamper-me.bin"
        tamper_payload = b"authenticated payload for tamper detection\n" * 4096
        tamper_source.write_bytes(tamper_payload)
        manager.file.encrypt(tamper_source)
        tamper_encrypted = workspace / "tamper-me.fscrypt"
        damaged = bytearray(tamper_encrypted.read_bytes())
        damaged[-1] ^= 0x01
        tamper_encrypted.write_bytes(damaged)
        with pytest.raises(AuthenticationError):
            manager.file.decrypt(tamper_encrypted)
        _assert(tamper_encrypted.is_file(), "tampered ciphertext is retained for diagnosis")
        _assert(not tamper_source.exists(), "unauthenticated plaintext is not published")
        recovery_records = manager.inspect_recovery(workspace)
        _assert(
            any(
                record.operation == "file_decrypt"
                and record.classification == "result_incomplete_or_unverified"
                for record in recovery_records
            ),
            "recovery inspection reports the unverified decryption result",
        )

        # Key replacement is validated before becoming active.
        _log("9/9 Replace the active key and use the new context.")
        replacement_key = fscryptography.generate()
        manager.change_key(replacement_key)
        _assert(manager.export_key() == replacement_key, "change_key() activates the replacement MasterKey")
        rotation_source = workspace / "after-key-change.txt"
        rotation_payload = b"operation performed with the replacement key"
        rotation_source.write_bytes(rotation_payload)
        manager.file.encrypt(rotation_source)
        rotation_encrypted = workspace / "after-key-change.fscrypt"
        manager.file.decrypt(rotation_encrypted)
        _assert(rotation_source.read_bytes() == rotation_payload, "filesystem operations use the replacement context")

        # Inspect the transaction journal without changing its state.
        records_before = manager.inspect_recovery(workspace)
        records_after = manager.inspect_recovery(workspace)
        _assert(records_before == records_after, "recovery inspection is repeatable and read-only")
        _log(f"Recovery journal entries observed: {len(records_after)}")
        for record in records_after:
            _log(
                f"  operation={record.operation} "
                f"state={record.state} "
                f"classification={record.classification}"
            )

    _log("Manager context has been closed.")
    _log(f"All generated resources remain available at: {workspace}")
    _log("RESULT: all real-filesystem integration assertions passed.")
    _log("=" * 72)


if __name__ == "__main__":
    test_real_filesystem_resources()
