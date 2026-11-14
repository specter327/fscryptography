from __future__ import annotations

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


def test_wrong_master_key_never_publishes_plaintext(tmp_path):
    source = tmp_path / "protected.txt"
    payload = b"authenticated data must not be released with an unrelated key"
    source.write_bytes(payload)

    with fscryptography.Manager(fscryptography.generate()) as writer:
        writer.file.encrypt(source)

    encrypted = tmp_path / "protected.fscrypt"
    with fscryptography.Manager(fscryptography.generate()) as unrelated:
        with pytest.raises(AuthenticationError):
            unrelated.file.decrypt(encrypted)

    assert encrypted.is_file()
    assert encrypted.read_bytes() != payload
    assert not source.exists()
    assert not any(path.is_file() and path.name == source.name for path in tmp_path.iterdir())


def test_truncated_ciphertext_never_publishes_plaintext(manager, tmp_path):
    source = tmp_path / "truncated.txt"
    source.write_bytes(b"payload" * 8192)
    manager.file.encrypt(source)
    encrypted = tmp_path / "truncated.fscrypt"

    encrypted.write_bytes(encrypted.read_bytes()[:-32])

    with pytest.raises(AuthenticationError):
        manager.file.decrypt(encrypted)

    # Failed authentication must preserve the ciphertext and must not publish
    # plaintext or leave a result temporary during normal exception cleanup.
    assert encrypted.is_file()
    assert not source.exists()
    assert not list(tmp_path.glob(".fscryptography-result-*"))


def test_encrypted_unicode_filename_round_trip(manager, tmp_path):
    original_name = "informe-confidencial-東京-ñ-🔐.txt"
    source = tmp_path / original_name
    payload = "Contenido UTF-8: áéíóú, ñ, 東京, 🔐".encode("utf-8")
    source.write_bytes(payload)

    # encrypt_name=True owns the complete output name; do not pass new_extension.
    manager.file.encrypt(source, encrypt_name=True)
    encrypted_candidates = [
        path for path in tmp_path.iterdir()
        if path.is_file() and path.name.startswith("~1")
    ]

    assert len(encrypted_candidates) == 1
    encrypted = encrypted_candidates[0]
    assert original_name not in encrypted.name
    manager.file.decrypt(encrypted)

    assert source.is_file()
    assert source.read_bytes() == payload


def test_encrypted_name_rejects_custom_extension_without_mutation(manager, tmp_path):
    source = tmp_path / "name-contract.txt"
    source.write_bytes(b"must remain untouched")

    with pytest.raises(ValueError, match="new_extension cannot be used"):
        manager.file.encrypt(
            source,
            new_extension=".locked",
            encrypt_name=True,
        )

    assert source.read_bytes() == b"must remain untouched"
    assert sorted(path.name for path in tmp_path.iterdir()) == [source.name]
