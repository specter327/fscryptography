#!/usr/bin/env python3
"""Compatibility probe for Tink's conventional AEAD name-encryption candidate.

This validates the exact AES256_GCM template and its keyset round-trip.
It is a backend probe, not production filename-encryption code.
"""

from __future__ import annotations

import platform
import sys
import unittest
from importlib.metadata import PackageNotFoundError, version

import tink
from tink import aead, secret_key_access


PROFILE_NAME = "AES256_GCM"
AAD = b"fscryptography/filename-encryption/v1"


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def make_primitive_from_serialized_keyset():
    aead.register()
    template = getattr(aead.aead_key_templates, PROFILE_NAME)
    handle = tink.new_keyset_handle(template)
    serialized = tink.proto_keyset_format.serialize(
        handle, secret_key_access.TOKEN
    )
    restored = tink.proto_keyset_format.parse(
        serialized, secret_key_access.TOKEN
    )
    primitive = restored.primitive(aead.Aead)
    return primitive, serialized


class TinkFilenameAeadValidation(unittest.TestCase):
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

    def test_round_trip_empty_ascii_and_unicode_names(self):
        names = (
            b"",
            b"document.txt",
            "informe-acción-日本語.txt".encode("utf-8"),
            bytes(range(1, 256)),
        )
        for plaintext in names:
            with self.subTest(plaintext_length=len(plaintext)):
                ciphertext = self.primitive.encrypt(plaintext, AAD)
                self.assertNotEqual(ciphertext, plaintext)
                self.assertEqual(
                    self.primitive.decrypt(ciphertext, AAD), plaintext
                )

    def test_wrong_aad_is_rejected(self):
        ciphertext = self.primitive.encrypt(b"private-name", AAD)
        with self.assertRaises(Exception):
            self.primitive.decrypt(ciphertext, b"wrong-associated-data")

    def test_ciphertext_corruption_is_rejected(self):
        ciphertext = bytearray(
            self.primitive.encrypt(b"private-name", AAD)
        )
        ciphertext[-1] ^= 0x01
        with self.assertRaises(Exception):
            self.primitive.decrypt(bytes(ciphertext), AAD)

    def test_truncated_ciphertext_is_rejected(self):
        ciphertext = self.primitive.encrypt(b"private-name", AAD)
        with self.assertRaises(Exception):
            self.primitive.decrypt(ciphertext[:-1], AAD)

    def test_ciphertext_has_bounded_overhead(self):
        # Tink's TINK output prefix (5 bytes), AES-GCM nonce (12 bytes),
        # and authentication tag (16 bytes) add 33 bytes to plaintext.
        # This invariant is useful for filename-component length budgeting.
        for length in (0, 1, 16, 128, 255):
            plaintext = b"x" * length
            ciphertext = self.primitive.encrypt(plaintext, AAD)
            self.assertEqual(len(ciphertext), length + 33)


if __name__ == "__main__":
    unittest.main(verbosity=2)
