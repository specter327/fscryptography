from __future__ import annotations

import os

import pytest

import fscryptography
from fscryptography.errors import (
    AtomicOperationError,
    AuthenticationError,
    DestinationConflictError,
    FormatError,
    InvalidPathError,
    UnsupportedResourceError,
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

    if __import__("sys").platform.startswith("linux"):
        monkeypatch.setattr(_filesystem.DirectoryAnchor, "sync", lambda anchor: sync_parent(anchor.path))
        expected_calls = [(True, True), (False, True)]
    else:
        monkeypatch.setattr(_filesystem, "_sync_parent_directory", sync_parent)
        # Windows does not claim directory-entry durability after source retirement.
        expected_calls = [(True, True)]
    manager.file.encrypt(source)

    assert calls == expected_calls


def test_encrypt_preserves_source_when_destination_sync_fails(manager, tmp_path, monkeypatch):
    source = tmp_path / "sync-failure.txt"
    source.write_bytes(b"preserve source")

    def fail_sync(parent):
        raise AtomicOperationError("injected directory sync failure")

    if __import__("sys").platform.startswith("linux"):
        monkeypatch.setattr(_filesystem.DirectoryAnchor, "sync", lambda anchor: fail_sync(anchor.path))
    else:
        monkeypatch.setattr(_filesystem, "_sync_parent_directory", fail_sync)
    with pytest.raises(AtomicOperationError):
        manager.file.encrypt(source)

    assert source.read_bytes() == b"preserve source"
    assert (tmp_path / "sync-failure.fscrypt").is_file()


def test_encrypt_reports_sync_failure_after_source_removal(manager, tmp_path, monkeypatch):
    source = tmp_path / "late-sync-failure.txt"
    source.write_bytes(b"published")
    calls = 0

    def fail_after_source_unlink(parent):
        nonlocal calls
        calls += 1
        failure_call = 2 if os.name == "nt" else 4
        if calls == failure_call:
            raise AtomicOperationError("injected transaction-directory sync failure")

    if __import__("sys").platform.startswith("linux"):
        original_set_state = _filesystem.Transaction.set_state

        def fail_after_source_unlink(transaction, state):
            if state == "source_removed":
                original_set_state(transaction, state)
                raise AtomicOperationError("injected failure after source removal")
            return original_set_state(transaction, state)

        monkeypatch.setattr(_filesystem.Transaction, "set_state", fail_after_source_unlink)
        expected_message = "injected failure after source removal"
    else:
        # Windows persists the journal file but cannot fsync the parent directory.
        # Inject a journal-state failure after the handle-based deletion instead.
        original_set_state = _filesystem.Transaction.set_state

        def fail_after_source_unlink(transaction, state):
            if state == "source_removed":
                raise AtomicOperationError("injected failure after source removal")
            return original_set_state(transaction, state)

        monkeypatch.setattr(_filesystem.Transaction, "set_state", fail_after_source_unlink)
        expected_message = "injected failure after source removal"
    with pytest.raises(AtomicOperationError, match=expected_message):
        manager.file.encrypt(source)

    assert not source.exists()
    assert (tmp_path / "late-sync-failure.fscrypt").is_file()


def test_directory_rename_syncs_parent(manager, tmp_path, monkeypatch):
    directory = tmp_path / "durable-directory"
    directory.mkdir()
    calls = []
    if __import__("sys").platform.startswith("linux"):
        monkeypatch.setattr(
            _filesystem.DirectoryAnchor,
            "sync",
            lambda anchor: calls.append(anchor.path),
        )
    else:
        monkeypatch.setattr(
            _filesystem,
            "_sync_parent_directory",
            lambda parent: calls.append(parent),
        )

    manager.dir.encrypt(directory)

    assert calls == [tmp_path]

@pytest.mark.skipif(os.name == "nt", reason="private quarantine is not enabled for inherited Windows ACLs")
def test_source_replacement_during_retirement_is_restored(manager, tmp_path, monkeypatch):
    source = tmp_path / "replacement.txt"
    retained_original = tmp_path / "original-retained.txt"
    source.write_bytes(b"original source")
    rename_noreplace = _filesystem.DirectoryAnchor.rename_noreplace

    def replace_before_quarantine(anchor, source_name, destination_fd, destination_name):
        if source_name == source.name and destination_name == "source":
            source.rename(retained_original)
            source.write_bytes(b"concurrent replacement")
        return rename_noreplace(anchor, source_name, destination_fd, destination_name)

    monkeypatch.setattr(_filesystem.DirectoryAnchor, "rename_noreplace", replace_before_quarantine)
    with pytest.raises(AtomicOperationError, match="identity changed"):
        manager.file.encrypt(source)

    assert retained_original.read_bytes() == b"original source"
    assert source.read_bytes() == b"concurrent replacement"
    assert (tmp_path / "replacement.fscrypt").is_file()
    assert any(
        record.operation == "file_encrypt" and record.classification == "ambiguous"
        for record in manager.inspect_recovery(tmp_path)
    )


@pytest.mark.skipif(os.name == "nt", reason="private quarantine is not enabled for inherited Windows ACLs")
def test_recovery_inspection_reports_retained_source(manager, tmp_path, monkeypatch):
    source = tmp_path / "interrupted.txt"
    source.write_bytes(b"source retained for recovery")
    original_set_state = _filesystem.Transaction.set_state

    def interrupt_after_quarantine(self, state):
        if state == "source_retained":
            raise RuntimeError("injected interruption after quarantine")
        return original_set_state(self, state)

    monkeypatch.setattr(_filesystem.Transaction, "set_state", interrupt_after_quarantine)
    with pytest.raises(AtomicOperationError, match="retirement is incomplete"):
        manager.file.encrypt(source)

    assert not source.exists()
    assert (tmp_path / "interrupted.fscrypt").is_file()
    records = manager.inspect_recovery(tmp_path)
    assert any(
        record.operation == "file_encrypt"
        and record.classification == "source_retained"
        for record in records
    )


@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"), reason="directory descriptor anchoring is GNU/Linux-only")
def test_operations_remain_anchored_when_parent_path_is_replaced(manager, tmp_path, monkeypatch):
    source = tmp_path / "anchored.txt"
    source.write_bytes(b"anchored payload")
    moved_parent = tmp_path.with_name(tmp_path.name + "-moved")
    original_copy = _filesystem._copy_encrypt
    replaced = False

    def replace_parent_after_transaction(primitive, src, dst, aad):
        nonlocal replaced
        if not replaced:
            tmp_path.rename(moved_parent)
            tmp_path.mkdir()
            replaced = True
        return original_copy(primitive, src, dst, aad)

    monkeypatch.setattr(_filesystem, "_copy_encrypt", replace_parent_after_transaction)
    manager.file.encrypt(source)

    assert replaced
    assert (moved_parent / "anchored.fscrypt").is_file()
    assert not (moved_parent / "anchored.txt").exists()
    assert list(tmp_path.iterdir()) == []
    records = manager.inspect_recovery(moved_parent)
    assert any(record.operation == "file_encrypt" and record.classification == "source_removed" for record in records)


@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"), reason="descriptor-relative inspection is GNU/Linux-only")
def test_recovery_inspection_does_not_follow_transaction_symlink(manager, tmp_path):
    transaction_link = tmp_path / (".fscryptography-txn-" + "0" * 32)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "journal.json").write_text("not a journal", encoding="utf-8")
    transaction_link.symlink_to(outside, target_is_directory=True)

    records = manager.inspect_recovery(tmp_path)
    assert len(records) == 1
    assert records[0].classification == "corrupt"


@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"), reason="directory descriptor anchoring is GNU/Linux-only")
def test_directory_replacement_during_rename_is_restored(manager, tmp_path, monkeypatch):
    source = tmp_path / "directory"
    retained_original = tmp_path / "original-directory"
    source.mkdir()
    (source / "original.txt").write_text("original", encoding="utf-8")
    rename_noreplace = _filesystem.DirectoryAnchor.rename_noreplace
    replaced = False

    def replace_before_rename(anchor, source_name, destination_fd, destination_name):
        nonlocal replaced
        if source_name == source.name and destination_name != source.name and not replaced:
            source.rename(retained_original)
            source.mkdir()
            (source / "replacement.txt").write_text("replacement", encoding="utf-8")
            replaced = True
        return rename_noreplace(anchor, source_name, destination_fd, destination_name)

    monkeypatch.setattr(_filesystem.DirectoryAnchor, "rename_noreplace", replace_before_rename)

    with pytest.raises(InvalidPathError, match="directory identity changed"):
        manager.dir.encrypt(source)

    assert replaced
    assert (retained_original / "original.txt").read_text(encoding="utf-8") == "original"
    assert (source / "replacement.txt").read_text(encoding="utf-8") == "replacement"
    assert not any(path.name.startswith("~1") for path in tmp_path.iterdir())



def test_file_operations_reject_multiple_hard_links(manager, tmp_path):
    source = tmp_path / "shared.txt"
    alias = tmp_path / "shared-alias.txt"
    source.write_bytes(b"content with another directory entry")
    try:
        os.link(source, alias)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    assert source.stat().st_ino == alias.stat().st_ino
    assert source.stat().st_nlink == 2

    with pytest.raises(UnsupportedResourceError, match="multiple hard links"):
        manager.file.encrypt(source)

    assert source.read_bytes() == b"content with another directory entry"
    assert alias.read_bytes() == b"content with another directory entry"
    assert source.stat().st_nlink == 2


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits are not the Windows ACL contract")
def test_encrypted_and_decrypted_files_use_restrictive_mode(manager, tmp_path):
    source = tmp_path / "private.txt"
    source.write_bytes(b"private payload")
    source.chmod(0o644)

    manager.file.encrypt(source)
    encrypted = tmp_path / "private.fscrypt"
    assert encrypted.stat().st_mode & 0o777 == 0o600

    manager.file.decrypt(encrypted)
    assert source.stat().st_mode & 0o777 == 0o600
    assert source.read_bytes() == b"private payload"

    transaction_dirs = list(tmp_path.glob(".fscryptography-txn-*"))
    assert transaction_dirs
    for transaction_dir in transaction_dirs:
        assert transaction_dir.stat().st_mode & 0o777 == 0o700
        journal = transaction_dir / "journal.json"
        if journal.exists():
            assert journal.stat().st_mode & 0o777 == 0o600


def test_reparse_point_attribute_detection():
    from types import SimpleNamespace

    assert _filesystem._is_reparse_point(SimpleNamespace(st_file_attributes=0x0400))
    assert not _filesystem._is_reparse_point(SimpleNamespace(st_file_attributes=0))
    assert not _filesystem._is_reparse_point(SimpleNamespace())
