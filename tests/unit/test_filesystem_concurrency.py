from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier

import pytest

import fscryptography
import fscryptography._filesystem as _filesystem


@pytest.fixture
def manager():
    instance = fscryptography.Manager(fscryptography.generate())
    try:
        yield instance
    finally:
        instance.close()


def test_shared_manager_supports_concurrent_independent_file_operations(
    manager, tmp_path
):
    """Concurrent operations on distinct resources must remain independent."""
    payloads = {
        f"resource-{index:02d}.bin": bytes([index]) * (256 * 1024 + index)
        for index in range(8)
    }
    for name, payload in payloads.items():
        (tmp_path / name).write_bytes(payload)

    barrier = Barrier(len(payloads))

    def encrypt_and_decrypt(name: str, payload: bytes) -> None:
        source = tmp_path / name
        encrypted = source.with_suffix(".fscrypt")
        barrier.wait(timeout=10)

        manager.file.encrypt(source)
        assert encrypted.is_file()
        assert not source.exists()

        manager.file.decrypt(encrypted)
        assert source.is_file()
        assert source.read_bytes() == payload

    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        futures = [
            executor.submit(encrypt_and_decrypt, name, payload)
            for name, payload in payloads.items()
        ]
        for future in futures:
            future.result(timeout=60)

    assert sorted(path.name for path in tmp_path.glob("*.fscrypt")) == []


def test_competing_encryption_of_same_source_never_publishes_multiple_results(
    manager, tmp_path
):
    """Two callers racing on one source must not create two valid outcomes."""
    source = tmp_path / "contended.bin"
    payload = b"single-source contention payload" * 8192
    source.write_bytes(payload)

    barrier = Barrier(2)

    def encrypt():
        barrier.wait(timeout=10)
        try:
            manager.file.encrypt(source)
        except Exception as error:
            return error
        return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: encrypt(), range(2)))

    assert sum(outcome is None for outcome in outcomes) == 1, outcomes
    assert sum(isinstance(outcome, Exception) for outcome in outcomes) == 1

    encrypted = tmp_path / "contended.fscrypt"
    assert encrypted.is_file()
    assert not source.exists()

    manager.file.decrypt(encrypted)
    assert source.is_file()
    assert source.read_bytes() == payload


def test_concurrent_encrypted_names_can_publish_duplicate_results(
    manager, tmp_path, monkeypatch
):
    """Randomized encrypted names allow both results to publish before source retirement."""
    source = tmp_path / "private-name.txt"
    payload = b"same source processed concurrently with randomized destination names"
    source.write_bytes(payload)

    barrier = Barrier(2)
    copy_encrypt = _filesystem._copy_encrypt

    def synchronize_after_stream(primitive, original, destination, aad):
        copy_encrypt(primitive, original, destination, aad)
        barrier.wait(timeout=15)

    monkeypatch.setattr(_filesystem, "_copy_encrypt", synchronize_after_stream)

    def encrypt():
        try:
            manager.file.encrypt(source, encrypt_name=True)
        except Exception as error:
            return error
        return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: encrypt(), range(2)))

    outputs = sorted(
        path for path in tmp_path.iterdir()
        if path.is_file() and path.name.startswith("~1")
    )
    assert len(outputs) == 2
    assert sum(outcome is None for outcome in outcomes) == 1, outcomes
    assert sum(isinstance(outcome, fscryptography.AtomicOperationError) for outcome in outcomes) == 1
    assert not source.exists()

    # Either published result is independently decryptable. The other remains
    # as a duplicate ciphertext and is intentionally not auto-cleaned.
    manager.file.decrypt(outputs[0])
    assert source.read_bytes() == payload
    assert outputs[1].is_file()



@pytest.mark.skipif(not __import__("sys").platform.startswith("linux"), reason="descriptor-relative source staging is GNU/Linux-only")
def test_encrypt_rejects_source_mutation_between_streaming_and_retirement(
    manager, tmp_path, monkeypatch
):
    """A same-inode write after streaming must not cause the changed source to be retired."""
    source = tmp_path / "late-mutation.bin"
    original_payload = b"original source bytes"
    source.write_bytes(original_payload)
    rename_noreplace = _filesystem.DirectoryAnchor.rename_noreplace
    mutated = False

    def mutate_before_staging(anchor, source_name, destination_fd, destination_name):
        nonlocal mutated
        if source_name == source.name and destination_name.startswith(".fscryptography-source-") and not mutated:
            source.write_bytes(original_payload + b" changed after streaming")
            mutated = True
        return rename_noreplace(anchor, source_name, destination_fd, destination_name)

    monkeypatch.setattr(
        _filesystem.DirectoryAnchor, "rename_noreplace", mutate_before_staging
    )

    with pytest.raises(
        fscryptography.AtomicOperationError, match="source identity changed before retirement"
    ):
        manager.file.encrypt(source)

    assert mutated
    assert source.read_bytes() == original_payload + b" changed after streaming"
    assert (tmp_path / "late-mutation.fscrypt").is_file()
    assert not list(tmp_path.glob(".fscryptography-source-*"))


@pytest.mark.skipif(os.name != "nt", reason="Windows path-based source staging")
def test_windows_encrypt_rejects_source_mutation_between_streaming_and_retirement(
    manager, tmp_path, monkeypatch
):
    """A same-inode write after streaming must be restored, not deleted, on Windows."""
    source = tmp_path / "late-mutation.bin"
    original_payload = b"original source bytes"
    source.write_bytes(original_payload)
    real_rename = os.rename
    mutated = False

    def mutate_before_staging(src, dst, *args, **kwargs):
        nonlocal mutated
        if (
            not mutated
            and os.fspath(src) == os.fspath(source)
            and os.fspath(dst).startswith(".fscryptography-source-")
        ):
            source.write_bytes(original_payload + b" changed after streaming")
            mutated = True
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(_filesystem.os, "rename", mutate_before_staging)

    with pytest.raises(
        fscryptography.AtomicOperationError, match="source identity changed during staging"
    ):
        manager.file.encrypt(source)

    assert mutated
    assert source.read_bytes() == original_payload + b" changed after streaming"
    assert (tmp_path / "late-mutation.fscrypt").is_file()
    assert not list(tmp_path.glob(".fscryptography-source-*"))



def test_encrypt_rejects_in_place_source_mutation_during_streaming(
    manager, tmp_path, monkeypatch
):
    """A same-inode write during streaming must not produce a published result."""
    source = tmp_path / "mutated.bin"
    original_payload = b"A" * (2 * 1024 * 1024)
    source.write_bytes(original_payload)
    copy_encrypt = fscryptography._filesystem._copy_encrypt

    def mutate_after_copy(primitive, src, dst, aad):
        copy_encrypt(primitive, src, dst, aad)
        with source.open("r+b") as writer:
            writer.seek(0)
            writer.write(b"B")

    monkeypatch.setattr(fscryptography._filesystem, "_copy_encrypt", mutate_after_copy)

    with pytest.raises(
        fscryptography.AtomicOperationError, match="changed during the operation"
    ):
        manager.file.encrypt(source)

    assert source.is_file()
    assert source.read_bytes() != original_payload
    assert not (tmp_path / "mutated.fscrypt").exists()


def test_decrypt_rejects_in_place_ciphertext_mutation_during_streaming(
    manager, tmp_path, monkeypatch
):
    """Authenticated output is not published if its ciphertext source changes."""
    source = tmp_path / "ciphertext.bin"
    source.write_bytes(b"authenticated payload" * 100_000)
    manager.file.encrypt(source)
    encrypted = tmp_path / "ciphertext.fscrypt"
    original_ciphertext = encrypted.read_bytes()
    copy_decrypt = fscryptography._filesystem._copy_decrypt

    def mutate_after_copy(primitive, src, dst, aad):
        copy_decrypt(primitive, src, dst, aad)
        with encrypted.open("r+b") as writer:
            writer.seek(-1, os.SEEK_END)
            last = writer.read(1)
            writer.seek(-1, os.SEEK_END)
            writer.write(bytes([last[0] ^ 1]))

    monkeypatch.setattr(fscryptography._filesystem, "_copy_decrypt", mutate_after_copy)

    with pytest.raises(
        fscryptography.AtomicOperationError, match="changed during the operation"
    ):
        manager.file.decrypt(encrypted)

    assert encrypted.is_file()
    assert encrypted.read_bytes() != original_ciphertext
    assert not source.exists()
    assert not (tmp_path / "ciphertext.bin").exists()


@pytest.mark.skipif(os.name == "nt", reason="descriptor-relative publication is GNU/Linux-only")
def test_destination_created_at_publication_is_never_overwritten(
    manager, tmp_path, monkeypatch
):
    source = tmp_path / "publication-race.bin"
    source.write_bytes(b"source must survive")
    destination = tmp_path / "publication-race.fscrypt"
    existing_payload = b"concurrent destination owner"
    rename_result = fscryptography._filesystem.Transaction.rename_result_to

    def create_destination_before_publish(transaction, parent_fd, destination_name):
        destination.write_bytes(existing_payload)
        return rename_result(transaction, parent_fd, destination_name)

    monkeypatch.setattr(
        fscryptography._filesystem.Transaction,
        "rename_result_to",
        create_destination_before_publish,
    )

    with pytest.raises(fscryptography.DestinationConflictError):
        manager.file.encrypt(source)

    assert source.read_bytes() == b"source must survive"
    assert destination.read_bytes() == existing_payload

@pytest.mark.skipif(os.name != "nt", reason="Windows handle-based retirement")
def test_windows_source_substitution_during_quarantine_is_never_deleted(
    manager, tmp_path, monkeypatch
):
    """A path swapped immediately before quarantine must not be unlinked."""
    source = tmp_path / "windows-quarantine-race.bin"
    original_payload = b"original source object"
    replacement_payload = b"competing replacement object"
    source.write_bytes(original_payload)
    displaced = tmp_path / "attacker-displaced-original.bin"
    real_rename = os.rename
    swapped = False

    def substitute_before_quarantine(src, dst, *args, **kwargs):
        nonlocal swapped
        if not swapped and os.fspath(src) == os.fspath(source):
            swapped = True
            real_rename(source, displaced)
            source.write_bytes(replacement_payload)
        return real_rename(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "rename", substitute_before_quarantine)

    with pytest.raises(
        fscryptography.AtomicOperationError, match="identity changed during staging"
    ):
        manager.file.encrypt(source)

    assert swapped
    assert source.read_bytes() == replacement_payload
    assert displaced.read_bytes() == original_payload
    assert (tmp_path / "windows-quarantine-race.fscrypt").is_file()
    assert not list(tmp_path.glob(".fscryptography-source-*"))

@pytest.mark.skipif(os.name != "nt", reason="Windows handle-based retirement")
def test_windows_replacement_after_handle_open_is_not_deleted(
    manager, tmp_path, monkeypatch
):
    """Replacing the temporary staging path after handle validation cannot redirect deletion."""
    source = tmp_path / "windows-handle-race.bin"
    source.write_bytes(b"expected source object")
    real_mark = fscryptography._filesystem._windows_mark_handle_for_deletion
    real_rename = os.rename
    moved = tmp_path / "opened-handle-object.bin"
    replacement_payload = b"replacement at quarantine path"
    quarantine_paths = []

    def replace_quarantine_then_delete(handle):
        retained = next(tmp_path.glob(".fscryptography-source-*"))
        quarantine_paths.append(retained)
        real_rename(retained, moved)
        retained.write_bytes(replacement_payload)
        return real_mark(handle)

    monkeypatch.setattr(
        fscryptography._filesystem,
        "_windows_mark_handle_for_deletion",
        replace_quarantine_then_delete,
    )

    manager.file.encrypt(source)

    assert len(quarantine_paths) == 1
    assert not moved.exists()  # The verified original object was deleted by its handle.
    assert quarantine_paths[0].read_bytes() == replacement_payload
    assert not source.exists()
    assert (tmp_path / "windows-handle-race.fscrypt").is_file()



def test_encryption_uses_one_key_snapshot_during_concurrent_rotation(
    tmp_path, monkeypatch
):
    first_key = fscryptography.generate()
    second_key = fscryptography.generate()
    manager = fscryptography.Manager(first_key)
    source = tmp_path / "key-snapshot.txt"
    payload = b"one operation must not mix two manager key generations"
    source.write_bytes(payload)
    original_encrypt_name = fscryptography._filesystem.encrypt_name_fn

    def rotate_after_name_encryption(name, primitive, profile, limit):
        encrypted_name = original_encrypt_name(name, primitive, profile, limit)
        manager.change_key(second_key)
        return encrypted_name

    monkeypatch.setattr(
        fscryptography._filesystem, "encrypt_name_fn", rotate_after_name_encryption
    )
    try:
        manager.file.encrypt(source, encrypt_name=True)
        assert manager.export_key() == second_key

        encrypted = next(
            path for path in tmp_path.iterdir()
            if path.is_file() and path.name.startswith("~1")
        )
        with fscryptography.Manager(first_key) as original_context:
            original_context.file.decrypt(encrypted)
        assert source.read_bytes() == payload
    finally:
        manager.close()


def test_in_flight_operation_completes_with_snapshot_after_manager_close(
    tmp_path, monkeypatch
):
    key = fscryptography.generate()
    manager = fscryptography.Manager(key)
    source = tmp_path / "close-snapshot.txt"
    payload = b"close prevents future operations, not an operation already started"
    source.write_bytes(payload)
    original_encrypt_name = fscryptography._filesystem.encrypt_name_fn

    def close_after_name_encryption(name, primitive, profile, limit):
        encrypted_name = original_encrypt_name(name, primitive, profile, limit)
        manager.close()
        return encrypted_name

    monkeypatch.setattr(
        fscryptography._filesystem, "encrypt_name_fn", close_after_name_encryption
    )
    manager.file.encrypt(source, encrypt_name=True)

    with pytest.raises(fscryptography.ClosedInstanceError):
        manager.export_key()

    encrypted = next(
        path for path in tmp_path.iterdir()
        if path.is_file() and path.name.startswith("~1")
    )
    with fscryptography.Manager(key) as original_context:
        original_context.file.decrypt(encrypted)
    assert source.read_bytes() == payload



@pytest.mark.skipif(os.name != "nt", reason="Windows file-sharing semantics")
def test_windows_source_handle_allows_staging_while_reader_is_open(tmp_path):
    source = tmp_path / "share-delete.bin"
    source.write_bytes(b"source remains readable through the open handle")
    expected = _filesystem._check_source(source, directory=False)
    retained = tmp_path / ".fscryptography-source-test"

    with _filesystem._open_source(source, expected) as reader:
        os.rename(source, retained)
        assert reader.read() == b"source remains readable through the open handle"

    assert retained.read_bytes() == b"source remains readable through the open handle"
    assert not source.exists()
