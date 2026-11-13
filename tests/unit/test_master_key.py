from __future__ import annotations

import base64

import pytest

from fscryptography._master_key import generate_master_key, open_master_key
from fscryptography.errors import AuthenticationError, FormatError
from fscryptography.names import decrypt_name, encrypt_name


def test_random_master_key_restores_independent_tink_primitives():
    master_key = generate_master_key()
    material = open_master_key(master_key)

    encrypted_name = encrypt_name("documento-ñ.txt", material.names)
    assert decrypt_name(encrypted_name, material.names) == "documento-ñ.txt"

    with pytest.raises(Exception):
        open_master_key(master_key, password="unexpected")


def test_password_protected_master_key_requires_password_and_round_trips():
    master_key = generate_master_key(password="contraseña segura")
    with pytest.raises(ValueError):
        open_master_key(master_key)
    material = open_master_key(master_key, password="contraseña segura")

    encrypted_name = encrypt_name("資料.txt", material.names)
    assert decrypt_name(encrypted_name, material.names) == "資料.txt"


def test_wrong_password_and_modified_payload_are_authentication_errors():
    master_key = generate_master_key(password="correct password")
    with pytest.raises(AuthenticationError):
        open_master_key(master_key, password="wrong password")

    binary = bytearray(base64.b64decode(master_key))
    binary[-1] ^= 1
    altered = base64.b64encode(binary).decode("ascii")
    with pytest.raises(AuthenticationError):
        open_master_key(altered, password="correct password")


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "not-base64!",
        "FSCRKEY",
        " " * 8,
        "!!!!",
    ],
)
def test_malformed_master_key_is_rejected(candidate):
    with pytest.raises(FormatError):
        open_master_key(candidate)


def test_noncanonical_base64_is_rejected():
    master_key = generate_master_key()
    binary = base64.b64decode(master_key)
    noncanonical = base64.b64encode(binary).decode("ascii").rstrip("=") + "===="
    with pytest.raises(FormatError):
        open_master_key(noncanonical)


def test_protected_header_profile_is_validated_before_kdf():
    master_key = generate_master_key(password="password")
    binary = bytearray(base64.b64decode(master_key))
    binary[22:26] = (8 * 1024).to_bytes(4, "big")
    altered = base64.b64encode(binary).decode("ascii")
    with pytest.raises(FormatError):
        open_master_key(altered, password="password")


def test_password_limits_are_enforced():
    with pytest.raises(ValueError):
        generate_master_key(password="")
    with pytest.raises(ValueError):
        generate_master_key(password="é" * 513)
