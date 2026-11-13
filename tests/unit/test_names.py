from __future__ import annotations

import base64

import pytest

from fscryptography.errors import (
    AuthenticationError,
    FormatError,
    NameConstraintError,
)
from fscryptography.names import (
    AAD,
    MARKER,
    NameProfile,
    decrypt_name,
    encrypt_name,
    is_canonical_candidate,
    validate_name,
)


class FakeAead:
    def encrypt(self, plaintext: bytes, associated_data: bytes) -> bytes:
        assert associated_data == AAD
        return b"TINK!" + b"N" * 12 + plaintext + b"T" * 16

    def decrypt(self, ciphertext: bytes, associated_data: bytes) -> bytes:
        assert associated_data == AAD
        if not ciphertext.endswith(b"T" * 16) or len(ciphertext) < 33:
            raise ValueError("authentication failed")
        return ciphertext[17:-16]


class RejectingAead(FakeAead):
    def decrypt(self, ciphertext: bytes, associated_data: bytes) -> bytes:
        raise ValueError("authentication failed")


@pytest.mark.parametrize("name", ["file.txt", "acción-日本語", "name~1abc"])
def test_linux_name_round_trip(name):
    primitive = FakeAead()
    encrypted = encrypt_name(name, primitive)
    assert encrypted.startswith(MARKER)
    assert decrypt_name(encrypted, primitive) == name


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "a/b", "a\x00b", "bad\ud800"],
)
def test_linux_rejects_invalid_components(name):
    with pytest.raises(NameConstraintError):
        validate_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "bad<name", "bad>name", "bad:name", 'bad"name', "bad/name",
        "bad\\name", "bad|name", "bad?name", "bad*name",
        "trailing.", "trailing ", "CON", "con.txt", "NUL.log",
        "COM1", "LPT9.txt", "COM¹", "LPT²", "CONIN$", "CLOCK$.txt",
        "control\x1f",
    ],
)
def test_windows_rejects_forbidden_names(name):
    with pytest.raises(NameConstraintError):
        validate_name(name, profile=NameProfile.WINDOWS)


@pytest.mark.parametrize("name", ["normal.txt", "COM10", "report.con", "a~1"])
def test_windows_accepts_valid_names(name):
    validate_name(name, profile=NameProfile.WINDOWS)


def test_utf8_bytes_not_codepoints_control_component_limit():
    assert len(validate_name("á" * 78)) == 156
    with pytest.raises(NameConstraintError):
        validate_name("á" * 79, max_component_bytes=156)


def test_encoded_name_156_byte_boundary():
    primitive = FakeAead()
    name = "a" * 156
    encoded = encrypt_name(name, primitive, max_component_bytes=255)
    assert len(encoded.encode("ascii")) == 254
    with pytest.raises(NameConstraintError):
        encrypt_name("a" * 157, primitive, max_component_bytes=255)


def test_canonical_base64url_required():
    primitive = FakeAead()
    encoded = encrypt_name("name", primitive)
    assert is_canonical_candidate(encoded)
    with pytest.raises(FormatError):
        decrypt_name(encoded + "=", primitive)
    with pytest.raises(FormatError):
        decrypt_name(encoded + " ", primitive)
    with pytest.raises(FormatError):
        decrypt_name("~1***", primitive)


def test_marker_alone_does_not_mean_already_encrypted():
    primitive = FakeAead()
    assert encrypt_name("~1not-a-ciphertext", primitive)


def test_active_key_double_encryption_is_rejected():
    primitive = FakeAead()
    encoded = encrypt_name("secret.txt", primitive)
    with pytest.raises(NameConstraintError):
        encrypt_name(encoded, primitive)


def test_other_key_candidate_is_treated_as_possible_plaintext():
    encoded = encrypt_name("secret.txt", FakeAead())
    result = encrypt_name(encoded, RejectingAead())
    assert result.startswith(MARKER)


def test_authentication_failure_does_not_fallback_to_plaintext():
    primitive = RejectingAead()
    with pytest.raises(AuthenticationError):
        decrypt_name(encrypt_name("secret", FakeAead()), primitive)


def test_destination_component_limit_is_enforced_after_decryption():
    primitive = FakeAead()
    encoded = encrypt_name("a" * 20, primitive)
    with pytest.raises(NameConstraintError):
        decrypt_name(encoded, primitive, max_component_bytes=10)
