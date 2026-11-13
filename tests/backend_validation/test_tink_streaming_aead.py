#!/usr/bin/env python3
"""Executable compatibility probe for Tink Python Streaming AEAD.

This is an integration probe, not production fscryptography code.
It deliberately tests the exact AES256_GCM_HKDF_1MB profile and does not
fall back to a different Streaming AEAD template.
"""

from __future__ import annotations

import io
import platform
import sys
import unittest
from importlib.metadata import PackageNotFoundError, version

import tink
from tink import secret_key_access, streaming_aead


AAD = b"fscryptography/backend-validation/v1"
PROFILE_NAME = "AES256_GCM_HKDF_1MB"


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def get_profile_template():
    """Resolve the exact requested template or fail with an actionable error."""
    streaming_aead.register()
    templates = streaming_aead.streaming_aead_key_templates
    try:
        return getattr(templates, PROFILE_NAME)
    except AttributeError as exc:
        raise RuntimeError(
            f"Tink {package_version('tink')} exposes no "
            f"streaming_aead_key_templates.{PROFILE_NAME}"
        ) from exc


def make_primitive_from_serialized_keyset():
    template = get_profile_template()
    handle = tink.new_keyset_handle(template)

    # Use Tink's own binary Protobuf keyset format. The explicit secret-key
    # access token remains confined to this internal validation script.
    serialized = tink.proto_keyset_format.serialize(
        handle, secret_key_access.TOKEN
    )
    restored_handle = tink.proto_keyset_format.parse(
        serialized, secret_key_access.TOKEN
    )
    primitive = restored_handle.primitive(streaming_aead.StreamingAead)
    return primitive, serialized


def encrypt(primitive, plaintext: bytes, aad: bytes = AAD) -> bytes:
    destination = io.BytesIO()
    with primitive.new_encrypting_stream(destination, aad) as stream:
        stream.write(plaintext)
    return destination.getvalue()


def decrypt(primitive, ciphertext: bytes, aad: bytes = AAD) -> bytes:
    source = io.BytesIO(ciphertext)
    with primitive.new_decrypting_stream(source, aad) as stream:
        return stream.read()


class StreamingAeadBackendValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print(f"Python: {sys.version.split()[0]}")
        print(f"Platform: {platform.platform()}")
        print(f"Tink: {package_version('tink')}")
        print(f"Profile: {PROFILE_NAME}")
        cls.primitive, cls.serialized_keyset = (
            make_primitive_from_serialized_keyset()
        )
        print(f"Serialized keyset bytes: {len(cls.serialized_keyset)}")

    def test_keyset_serialization_and_recovery(self):
        self.assertTrue(self.serialized_keyset)
        # setUpClass already parsed the serialized keyset and constructed the
        # primitive from the recovered handle. Successful setup proves both.

    def test_round_trip_empty_small_and_multi_segment_payloads(self):
        payloads = (
            b"",
            b"fscryptography" * 37,
            bytes(range(256)) * 8192,  # 2 MiB; crosses a 1 MiB segment target.
        )
        for plaintext in payloads:
            with self.subTest(plaintext_length=len(plaintext)):
                ciphertext = encrypt(self.primitive, plaintext)
                self.assertNotEqual(ciphertext, plaintext)
                self.assertEqual(decrypt(self.primitive, ciphertext), plaintext)

    def test_wrong_aad_is_rejected(self):
        ciphertext = encrypt(self.primitive, b"authenticated payload")
        with self.assertRaises(Exception):
            decrypt(self.primitive, ciphertext, b"wrong-associated-data")

    def test_truncation_is_rejected(self):
        ciphertext = encrypt(self.primitive, b"payload" * 300_000)
        self.assertGreater(len(ciphertext), 1)
        with self.assertRaises(Exception):
            decrypt(self.primitive, ciphertext[:-1])

    def test_ciphertext_corruption_is_rejected(self):
        ciphertext = bytearray(encrypt(self.primitive, b"payload" * 300_000))
        index = len(ciphertext) // 2
        ciphertext[index] ^= 0x01
        with self.assertRaises(Exception):
            decrypt(self.primitive, bytes(ciphertext))


if __name__ == "__main__":
    unittest.main(verbosity=2)
