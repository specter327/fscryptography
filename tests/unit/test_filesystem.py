from __future__ import annotations

import os

import pytest

import fscryptography
from fscryptography.errors import (
    AtomicOperationError,
    AuthenticationError,
    DestinationConflictError,
    FormatError,
)
from fscryptography import _filesystem


@pytest.fixture
def manager():
    instance = fscryptography.Manager(fscryptography.generate())
    try:
        yield instance
    finally:
        instance.close()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation may require elevated Windows privileges")
def test_source_open_rejects_symlink_substitution(tmp_path):
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    retained = tmp_path / "retained.bin"
    source.write_bytes(b"original")
    target.write_bytes(b"must not be opened")
    expected = source.stat()

    source.rename(retained)
    source.symlink_to(target)

    with pytest.raises(OSError):
        _filesystem._open_source(source, expected)

    assert retained.read_bytes() == b"original"
    assert target.read_bytes() == b"must not be opened"


def test_file_visible_name_round_trip(manager, tmp_path):
    source = tmp_path / "report.txt"
    payload = b"file payload" * 100_000
    source.write_bytes(payload)

    manager.file.encrypt(source)
    encrypted = tmp_path / "report.fscrypt"
    assert encrypted.is_file()
    assert not source.exists()

    manager.file.decrypt(encrypted)
    assert source.read_bytes() == payload
    assert not encrypted.exists()


def test_file_custom_extension_round_trip(manager, tmp_path):
    source = tmp_path / "archive.tar.gz"
    source.write_bytes(b"archive")

    manager.file.encrypt(source, new_extension=".locked")
    encrypted = tmp_path / "archive.tar.locked"
    assert encrypted.exists()

    manager.file.decrypt(encrypted)
    assert source.read_bytes() == b"archive"


def test_file_without_original_extension_round_trip(manager, tmp_path):
    source = tmp_path / "README"
    source.write_bytes(b"readme")

    manager.file.encrypt(source)
    encrypted = tmp_path / "README.fscrypt"
    manager.file.decrypt(encrypted)
    assert source.read_bytes() == b"readme"


def test_empty_file_round_trip(manager, tmp_path):
    source = tmp_path / "empty.bin"
    source.write_bytes(b"")

    manager.file.encrypt(source)
    encrypted = tmp_path / "empty.fscrypt"
    manager.file.decrypt(encrypted)
    assert source.read_bytes() == b""


def test_file_encrypted_name_round_trip(manager, tmp_path):
    source = tmp_path / "private document.txt"
    source.write_bytes(b"secret")

    manager.file.encrypt(source, encrypt_name=True)
    encrypted = next(path for path in tmp_path.iterdir() if path.name.startswith("~1"))
    assert encrypted.name.startswith("~1")
    assert not source.exists()

    manager.file.decrypt(encrypted)
    assert source.read_bytes() == b"secret"


def test_file_destination_conflict_preserves_source(manager, tmp_path):
    source = tmp_path / "conflict.txt"
    source.write_bytes(b"source")
    destination = tmp_path / "conflict.fscrypt"
    destination.write_bytes(b"existing")

    with pytest.raises(DestinationConflictError):
        manager.file.encrypt(source)

    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"existing"


def test_tampered_file_preserves_ciphertext(manager, tmp_path):
    source = tmp_path / "tamper.txt"
    source.write_bytes(b"authenticated" * 20_000)
    manager.file.encrypt(source)
    encrypted = tmp_path / "tamper.fscrypt"

    data = bytearray(encrypted.read_bytes())
    data[-1] ^= 1
    encrypted.write_bytes(data)

    with pytest.raises(AuthenticationError):
        manager.file.decrypt(encrypted)

    assert encrypted.exists()
    assert not source.exists()
    records = manager.inspect_recovery(tmp_path)
    assert any(
        record.operation == "file_decrypt"
        and record.classification == "result_incomplete_or_unverified"
        for record in records
    )


def test_invalid_header_preserves_source(manager, tmp_path):
    source = tmp_path / "invalid.fscrypt"
    source.write_bytes(b"not a valid header")

    with pytest.raises(FormatError):
        manager.file.decrypt(source)

    assert source.read_bytes() == b"not a valid header"


def test_directory_only_renames_its_own_component(manager, tmp_path):
    directory = tmp_path / "private"
    directory.mkdir()
    child = directory / "child.txt"
    child.write_text("unchanged", encoding="utf-8")

    manager.dir.encrypt(directory)
    encrypted = next(path for path in tmp_path.iterdir() if path.is_dir() and path.name.startswith("~1"))
    assert encrypted.name.startswith("~1")
    assert (encrypted / "child.txt").read_text(encoding="utf-8") == "unchanged"

    manager.dir.decrypt(encrypted)
    assert child.read_text(encoding="utf-8") == "unchanged"
    assert directory.is_dir()


def test_closed_manager_rejects_filesystem_operations():
    manager = fscryptography.Manager(fscryptography.generate())
    manager.close()
    with pytest.raises(fscryptography.ClosedInstanceError):
        manager.file


def test_empty_new_extension_is_supported(manager, tmp_path):
    source = tmp_path / "extension.txt"
    source.write_bytes(b"content")
    manager.file.encrypt(source, new_extension="")
    encrypted = tmp_path / "extension"
    assert encrypted.exists()
    manager.file.decrypt(encrypted)
    assert source.read_bytes() == b"content"


def test_encrypt_syncs_destination_before_removing_source(manager, tmp_path, monkeypatch):
    source = tmp_path / "durable.txt"
    source.write_bytes(b"durability")
    calls = []

    def sync_parent(parent):
        calls.append((source.exists(), (tmp_path / "durable.fscrypt").exists()))

    monkeypatch.setattr(_filesystem, "_sync_parent_directory", sync_parent)
    manager.file.encrypt(source)

    assert calls == [(True, True), (False, True)]


def test_encrypt_preserves_source_when_destination_sync_fails(manager, tmp_path, monkeypatch):
    source = tmp_path / "sync-failure.txt"
    source.write_bytes(b"preserve source")

    def fail_sync(parent):
        raise AtomicOperationError("injected directory sync failure")

    monkeypatch.setattr(_filesystem, "_sync_parent_directory", fail_sync)
    with pytest.raises(AtomicOperationError):
        manager.file.encrypt(source)

    assert source.read_bytes() == b"preserve source"
    assert (tmp_path / "sync-failure.fscrypt").is_file()


def test_encrypt_reports_sync_failure_after_source_removal(manager, tmp_path, monkeypatch):
    source = tmp_path / "late-sync-failure.txt"
    source.write_bytes(b"published")
    calls = 0

    def fail_second_sync(parent):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise AtomicOperationError("injected second sync failure")

    monkeypatch.setattr(_filesystem, "_sync_parent_directory", fail_second_sync)
    with pytest.raises(AtomicOperationError, match="source was removed"):
        manager.file.encrypt(source)

    assert not source.exists()
    assert (tmp_path / "late-sync-failure.fscrypt").is_file()


def test_directory_rename_syncs_parent(manager, tmp_path, monkeypatch):
    directory = tmp_path / "durable-directory"
    directory.mkdir()
    calls = []
    monkeypatch.setattr(
        _filesystem,
        "_sync_parent_directory",
        lambda parent: calls.append(parent),
    )

    manager.dir.encrypt(directory)

    assert calls == [tmp_path]
