from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest

from fscryptography._master_key import _split_payload, open_master_key
from fscryptography.errors import AuthenticationError, FormatError
from fscryptography.names import decrypt_name, encrypt_name


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "master_key_tink_v1_vectors.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _open_vector(container_hex: str, password: str | None = None):
    encoded = base64.b64encode(bytes.fromhex(container_hex)).decode("ascii")
    return open_master_key(encoded, password=password)


def _assert_primitives_round_trip(material):
    encrypted_name = encrypt_name("independent-vector.txt", material.names)
    assert decrypt_name(encrypted_name, material.names) == "independent-vector.txt"

    plaintext = b"independent Tink Streaming AEAD golden vector"
    ciphertext = io.BytesIO()
    with material.content.new_encrypting_stream(ciphertext, b"fscryptography-golden-aad") as stream:
        stream.write(plaintext)

    with material.content.new_decrypting_stream(
        io.BytesIO(ciphertext.getvalue()),
        b"fscryptography-golden-aad",
    ) as stream:
        assert stream.read() == plaintext


def test_random_master_key_golden_vector_opens_valid_tink_keysets():
    material = _open_vector(FIXTURE["random_container_hex"])
    _assert_primitives_round_trip(material)

    content_keyset, names_keyset = _split_payload(bytes.fromhex(FIXTURE["logical_payload_hex"]))
    assert content_keyset.hex() == FIXTURE["content_keyset_hex"]
    assert names_keyset.hex() == FIXTURE["names_keyset_hex"]


def test_password_protected_golden_vector_uses_production_argon2id_profile():
    material = _open_vector(
        FIXTURE["protected_container_hex"],
        password=FIXTURE["password_utf8"],
    )
    _assert_primitives_round_trip(material)


def test_password_protected_golden_vector_rejects_wrong_password():
    with pytest.raises(AuthenticationError):
        _open_vector(
            FIXTURE["protected_container_hex"],
            password="not-the-golden-vector-password",
        )


@pytest.mark.parametrize(
    "case",
    [
        "content_keyset_wrong_primitive",
        "names_keyset_wrong_primitive",
        "content_keyset_malformed",
        "names_keyset_malformed",
    ],
)
def test_invalid_tink_keyset_golden_vectors_are_rejected(case):
    with pytest.raises(FormatError):
        _open_vector(FIXTURE["invalid_containers"][case])
