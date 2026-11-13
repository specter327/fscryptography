from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier

import pytest

import fscryptography


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

    assert sum(outcome is None for outcome in outcomes) == 1
    assert sum(isinstance(outcome, Exception) for outcome in outcomes) == 1

    encrypted = tmp_path / "contended.fscrypt"
    assert encrypted.is_file()
    assert not source.exists()

    manager.file.decrypt(encrypted)
    assert source.is_file()
    assert source.read_bytes() == payload

    # Repeated inspection must remain read-only after concurrent operations.
    before = manager.inspect_recovery(tmp_path)
    after = manager.inspect_recovery(tmp_path)
    assert before == after

 
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
