from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

import fscryptography
from fscryptography import AuthenticationError


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
        encrypted = tmp_path / f"{name}.fscrypt"
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
    payload = b"single-source contention payload\x00" * 8192
    source.write_bytes(payload)

    barrier = Barrier(2)

    def encrypt():
        barrier.wait(timeout=10)
        try:
            manager.file.encrypt(source)
        except Exception as error:  # Capture the losing operation's public failure.
            return error
        return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: encrypt(), range(2)))

    assert sum(outcome is None for outcome in outcomes) == 1

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
