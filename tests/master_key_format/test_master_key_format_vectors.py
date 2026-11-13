#!/usr/bin/env python3
"""Conformance tests for the approved MasterKey v1.0 binary layout.

These tests exercise a test-only structural verifier against immutable golden
vectors. They do not implement or stand in for the production MasterKey parser.
The keyset byte strings in the fixtures are opaque synthetic placeholders, not
valid Tink protobuf keysets. Argon2id fixture costs are intentionally weak.
"""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "master_key_v1_vectors.json"
FIXTURES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
EXPECTED = FIXTURES["expected"]
MAGIC = bytes.fromhex(EXPECTED["magic_hex"])
MAX_KEYSET_LENGTH = 32 * 1024
MAX_LOGICAL_PAYLOAD_LENGTH = 128 * 1024
MAX_PROTECTED_PAYLOAD_LENGTH = MAX_LOGICAL_PAYLOAD_LENGTH + 16


class FormatError(ValueError):
    """A malformed or unsupported MasterKey v1.0 container."""


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _derive_fixture_key(header: bytes, password: str) -> bytes:
    if len(header) != 61:
        raise FormatError("invalid protected header length")
    if header[20] != 1 or header[21] != 19 or header[48] != 1:
        raise FormatError("unsupported KDF, KDF version, or AEAD")
    memory_cost = _u32(header, 22)
    time_cost = _u32(header, 26)
    parallelism = _u16(header, 30)
    # Deliberately bounded test policy. These are fixture limits, not production
    # recommendations or the final production Argon2id policy.
    if not (8 * 1024 <= memory_cost <= 16 * 1024):
        raise FormatError("fixture memory cost outside test policy")
    if not (1 <= time_cost <= 2) or not (1 <= parallelism <= 2):
        raise FormatError("fixture Argon2id parameters outside test policy")
    return hash_secret_raw(
        secret=password.encode("utf-8", errors="strict"),
        salt=header[32:48],
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=32,
        type=Type.ID,
        version=19,
    )


def _open_container(blob: bytes, password: str | None = None) -> bytes:
    if len(blob) < 20:
        raise FormatError("truncated common prefix")
    if blob[:8] != MAGIC:
        raise FormatError("invalid magic")
    if blob[8:10] != b"\x01\x00":
        raise FormatError("unsupported version")
    mode, schema = blob[10], blob[11]
    if mode not in (0, 1) or schema != 1:
        raise FormatError("unsupported mode or payload schema")
    if _u16(blob, 12) != 0:
        raise FormatError("reserved flags must be zero")
    header_length = _u16(blob, 14)
    payload_length = _u32(blob, 16)
    expected_header_length = 20 if mode == 0 else 61
    payload_limit = MAX_LOGICAL_PAYLOAD_LENGTH if mode == 0 else MAX_PROTECTED_PAYLOAD_LENGTH
    if header_length != expected_header_length:
        raise FormatError("unexpected header length")
    if payload_length > payload_limit:
        raise FormatError("payload exceeds limit")
    if len(blob) != header_length + payload_length:
        raise FormatError("container length mismatch")
    header, payload = blob[:header_length], blob[header_length:]
    if mode == 0:
        return payload
    if password is None:
        raise FormatError("password required")
    key = _derive_fixture_key(header, password)
    nonce = header[49:61]
    return AESGCM(key).decrypt(nonce, payload, header)


def _split_synthetic_payload(payload: bytes) -> tuple[bytes, bytes]:
    if len(payload) < 8:
        raise FormatError("truncated payload framing")
    first_length = _u32(payload, 0)
    if first_length == 0 or first_length > MAX_KEYSET_LENGTH:
        raise FormatError("invalid first keyset length")
    first_end = 4 + first_length
    if len(payload) < first_end + 4:
        raise FormatError("missing second keyset length")
    second_length = _u32(payload, first_end)
    if second_length == 0 or second_length > MAX_KEYSET_LENGTH:
        raise FormatError("invalid second keyset length")
    second_start = first_end + 4
    second_end = second_start + second_length
    if second_end != len(payload):
        raise FormatError("truncated or trailing payload data")
    return payload[4:first_end], payload[second_start:second_end]


class MasterKeyV1GoldenVectorTests(unittest.TestCase):
    def setUp(self):
        self.random_blob = bytes.fromhex(FIXTURES["random_container_hex"])
        self.protected_blob = bytes.fromhex(FIXTURES["protected_container_hex"])
        self.logical_payload = bytes.fromhex(FIXTURES["logical_payload_hex"])
        self.password = FIXTURES["password_utf8"]

    def test_random_golden_vector_is_byte_exact(self):
        self.assertEqual(len(self.random_blob[:20]), EXPECTED["random_header_length"])
        self.assertEqual(_open_container(self.random_blob), self.logical_payload)

    def test_protected_golden_vector_is_byte_exact_and_authenticates(self):
        self.assertEqual(len(self.protected_blob[:61]), EXPECTED["protected_header_length"])
        self.assertEqual(_open_container(self.protected_blob, self.password), self.logical_payload)

    def test_synthetic_keyset_framing_round_trip(self):
        content_keyset, name_keyset = _split_synthetic_payload(self.logical_payload)
        self.assertEqual(content_keyset.hex(), EXPECTED["synthetic_content_keyset_hex"])
        self.assertEqual(name_keyset.hex(), EXPECTED["synthetic_name_keyset_hex"])

    def test_protected_vector_rejects_wrong_password(self):
        with self.assertRaises(InvalidTag):
            _open_container(self.protected_blob, "wrong-password")

    def test_every_protected_header_byte_is_rejected_when_altered(self):
        for offset in range(61):
            altered = bytearray(self.protected_blob)
            altered[offset] ^= 0x01
            with self.subTest(offset=offset), self.assertRaises((FormatError, InvalidTag)):
                _open_container(bytes(altered), self.password)

    def test_protected_ciphertext_and_tag_alterations_are_rejected(self):
        for offset in (61, len(self.protected_blob) - 1):
            altered = bytearray(self.protected_blob)
            altered[offset] ^= 0x01
            with self.subTest(offset=offset), self.assertRaises(InvalidTag):
                _open_container(bytes(altered), self.password)

    def test_truncation_and_trailing_bytes_are_rejected(self):
        for candidate in (self.random_blob[:-1], self.protected_blob[:-1],
                          self.random_blob + b"\x00", self.protected_blob + b"\x00"):
            with self.subTest(length=len(candidate)), self.assertRaises(FormatError):
                _open_container(candidate, self.password)

    def test_unknown_mode_schema_version_and_flags_are_rejected(self):
        mutations = ((10, 0x02), (11, 0x02), (8, 0x02))
        for offset, value in mutations:
            altered = bytearray(self.random_blob)
            altered[offset] = value
            with self.subTest(offset=offset), self.assertRaises(FormatError):
                _open_container(bytes(altered))

        altered_flags = bytearray(self.random_blob)
        altered_flags[13] = 0x01
        with self.assertRaises(FormatError):
            _open_container(bytes(altered_flags))

    def test_header_and_payload_lengths_are_strict(self):
        for offset, value in ((14, 0x13), (16, 0x01), (19, 0x0C)):
            altered = bytearray(self.random_blob)
            altered[offset] = value
            with self.subTest(offset=offset), self.assertRaises(FormatError):
                _open_container(bytes(altered))

    def test_protected_mode_requires_password(self):
        with self.assertRaises(FormatError):
            _open_container(self.protected_blob)

    def test_payload_framing_rejects_zero_truncated_and_trailing_fields(self):
        malformed = (
            b"\x00\x00\x00\x00" + self.logical_payload[4:],
            b"\x00\x00\x00\x03abc\x00\x00\x00\x00",
            b"\x00\x00\x00\x03abc\x00\x00\x00\x03de",
            self.logical_payload + b"\x00",
            self.logical_payload[:-1],
        )
        for payload in malformed:
            with self.subTest(payload=payload.hex()), self.assertRaises(FormatError):
                _split_synthetic_payload(payload)

    def test_keyset_size_limits_are_enforced_by_framing_verifier(self):
        too_large_first = struct.pack(">I", MAX_KEYSET_LENGTH + 1)
        with self.assertRaises(FormatError):
            _split_synthetic_payload(too_large_first + b"x" * (MAX_KEYSET_LENGTH + 1) + b"\x00\x00\x00\x01y")


if __name__ == "__main__":
    unittest.main(verbosity=2)
