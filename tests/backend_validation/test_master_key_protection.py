#!/usr/bin/env python3
"""Executable probes for Argon2id and AES-256-GCM MasterKey wrapping.

These tests validate dependency APIs and the proposed composition. They are
not production container parsing, parameter-policy, or filesystem tests.
"""

from __future__ import annotations

import os
import platform
import sys
import unittest
from importlib.metadata import PackageNotFoundError, version

from argon2.low_level import ARGON2_VERSION, Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SALT = bytes.fromhex("00112233445566778899aabbccddeeff")
PASSWORD = b"correct horse battery staple"
WRONG_PASSWORD = b"incorrect password"
AAD = b"fscryptography/master-key/v1"
PAYLOAD = b"serialized-keysets-placeholder" * 19

# Deliberately modest parameters for a compatibility probe. These are NOT
# normative production parameters for fscryptography.
ARGON2_PARAMETERS = {
    "time_cost": 1,
    "memory_cost": 8 * 1024,  # KiB
    "parallelism": 1,
    "hash_len": 32,
    "type": Type.ID,
    "version": ARGON2_VERSION,
}


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def derive_wrapping_key(password: bytes, salt: bytes = SALT) -> bytes:
    return hash_secret_raw(secret=password, salt=salt, **ARGON2_PARAMETERS)


class MasterKeyProtectionBackendValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print(f"Python: {sys.version.split()[0]}")
        print(f"Platform: {platform.platform()}")
        print(f"argon2-cffi: {package_version('argon2-cffi')}")
        print(f"cryptography: {package_version('cryptography')}")
        print(f"Argon2 version: {ARGON2_VERSION}")
        cls.key = derive_wrapping_key(PASSWORD)
        cls.aead = AESGCM(cls.key)
        cls.iv = os.urandom(12)
        cls.ciphertext = cls.aead.encrypt(cls.iv, PAYLOAD, AAD)

    def test_argon2id_returns_32_bytes(self):
        self.assertEqual(len(self.key), 32)

    def test_argon2id_is_deterministic_for_same_inputs(self):
        self.assertEqual(self.key, derive_wrapping_key(PASSWORD, SALT))

    def test_argon2id_changes_with_password_or_salt(self):
        self.assertNotEqual(self.key, derive_wrapping_key(WRONG_PASSWORD, SALT))
        other_salt = bytes.fromhex("10112233445566778899aabbccddeeff")
        self.assertNotEqual(self.key, derive_wrapping_key(PASSWORD, other_salt))

    def test_aes256_gcm_round_trip_with_aad(self):
        self.assertEqual(self.aead.decrypt(self.iv, self.ciphertext, AAD), PAYLOAD)

    def test_aes_gcm_rejects_wrong_password_and_modified_aad(self):
        wrong_key = derive_wrapping_key(WRONG_PASSWORD, SALT)
        with self.assertRaises(InvalidTag):
            AESGCM(wrong_key).decrypt(self.iv, self.ciphertext, AAD)
        with self.assertRaises(InvalidTag):
            self.aead.decrypt(self.iv, self.ciphertext, b"modified-header")

    def test_aes_gcm_rejects_modified_nonce_and_ciphertext(self):
        modified_nonce = bytes([self.iv[0] ^ 1]) + self.iv[1:]
        modified_ciphertext = bytearray(self.ciphertext)
        modified_ciphertext[len(modified_ciphertext) // 2] ^= 1
        with self.assertRaises(InvalidTag):
            self.aead.decrypt(modified_nonce, self.ciphertext, AAD)
        with self.assertRaises(InvalidTag):
            self.aead.decrypt(self.iv, bytes(modified_ciphertext), AAD)


if __name__ == "__main__":
    unittest.main(verbosity=2)
