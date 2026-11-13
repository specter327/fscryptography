"""Production MasterKey v1.0 container and Tink keyset integration."""

from __future__ import annotations

import base64
import binascii
import os
import struct
from dataclasses import dataclass

import tink
from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tink import aead, secret_key_access, streaming_aead

from .errors import (
    AuthenticationError,
    BackendError,
    FormatError,
    KeyDerivationError,
    UnsupportedFormatVersionError,
)

_MAGIC = b"FSCRKEY\0"
_MAJOR = 1
_MINOR = 0
_SCHEMA = 1
_MODE_RANDOM = 0
_MODE_PASSWORD = 1
_HEADER_RANDOM = 20
_HEADER_PASSWORD = 61
_MAX_KEYSET = 32 * 1024
_MAX_LOGICAL_PAYLOAD = 128 * 1024
_MAX_BINARY = 131_149
_MAX_BASE64 = 174_868
_ARGON2_VERSION = 19
_ARGON2_MEMORY_KIB = 65_536
_ARGON2_TIME = 3
_ARGON2_PARALLELISM = 1
_SALT_LENGTH = 16
_NONCE_LENGTH = 12
_TAG_LENGTH = 16


@dataclass(frozen=True, slots=True)
class _KeyMaterial:
    content: streaming_aead.StreamingAead
    names: aead.Aead


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("password must be str")
    try:
        value = password.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("password must be valid UTF-8 text") from exc
    if not value or len(value) > 1024:
        raise ValueError("password must contain 1 to 1024 UTF-8 bytes")
    return value


def _derive_wrapping_key(password: bytes, salt: bytes) -> bytes:
    try:
        return hash_secret_raw(
            secret=password,
            salt=salt,
            time_cost=_ARGON2_TIME,
            memory_cost=_ARGON2_MEMORY_KIB,
            parallelism=_ARGON2_PARALLELISM,
            hash_len=32,
            type=Type.ID,
            version=_ARGON2_VERSION,
        )
    except Exception as exc:
        raise KeyDerivationError("MasterKey key derivation failed") from exc


def _serialize_keyset(handle: tink.KeysetHandle) -> bytes:
    try:
        return tink.proto_keyset_format.serialize(
            handle, secret_key_access.TOKEN
        )
    except Exception as exc:
        raise BackendError("unable to serialize MasterKey keyset") from exc


def _new_keysets() -> tuple[bytes, bytes]:
    try:
        streaming_aead.register()
        aead.register()
        content_template = getattr(
            streaming_aead.streaming_aead_key_templates,
            "AES256_GCM_HKDF_1MB",
        )
        names_template = aead.aead_key_templates.AES256_GCM
        content = _serialize_keyset(tink.new_keyset_handle(content_template))
        names = _serialize_keyset(tink.new_keyset_handle(names_template))
    except BackendError:
        raise
    except Exception as exc:
        raise BackendError("unable to generate MasterKey keysets") from exc
    return content, names


def _frame_payload(content_keyset: bytes, names_keyset: bytes) -> bytes:
    if not content_keyset or not names_keyset:
        raise BackendError("Tink generated an empty keyset")
    if len(content_keyset) > _MAX_KEYSET or len(names_keyset) > _MAX_KEYSET:
        raise BackendError("Tink keyset exceeds the MasterKey size limit")
    payload = (
        struct.pack(">I", len(content_keyset))
        + content_keyset
        + struct.pack(">I", len(names_keyset))
        + names_keyset
    )
    if len(payload) > _MAX_LOGICAL_PAYLOAD:
        raise BackendError("MasterKey payload exceeds the size limit")
    return payload


def _split_payload(payload: bytes) -> tuple[bytes, bytes]:
    if not isinstance(payload, bytes) or len(payload) < 8:
        raise FormatError("MasterKey payload framing is truncated")
    first_length = struct.unpack_from(">I", payload, 0)[0]
    if first_length == 0 or first_length > _MAX_KEYSET:
        raise FormatError("invalid content keyset length")
    first_end = 4 + first_length
    if len(payload) < first_end + 4:
        raise FormatError("MasterKey name keyset length is missing")
    second_length = struct.unpack_from(">I", payload, first_end)[0]
    if second_length == 0 or second_length > _MAX_KEYSET:
        raise FormatError("invalid name keyset length")
    second_start = first_end + 4
    second_end = second_start + second_length
    if second_end != len(payload):
        raise FormatError("MasterKey payload has truncated or trailing data")
    return payload[4:first_end], payload[second_start:second_end]


def _restore_key_material(content_keyset: bytes, names_keyset: bytes) -> _KeyMaterial:
    try:
        streaming_aead.register()
        aead.register()
        content_handle = tink.proto_keyset_format.parse(
            content_keyset, secret_key_access.TOKEN
        )
        names_handle = tink.proto_keyset_format.parse(
            names_keyset, secret_key_access.TOKEN
        )
        content = content_handle.primitive(streaming_aead.StreamingAead)
        names = names_handle.primitive(aead.Aead)
    except Exception as exc:
        raise FormatError("MasterKey contains invalid or unexpected Tink keysets") from exc
    return _KeyMaterial(content=content, names=names)


def generate_master_key(*, password: str | None = None) -> str:
    """Generate an opaque Base64 MasterKey v1.0 container."""
    content_keyset, names_keyset = _new_keysets()
    logical_payload = _frame_payload(content_keyset, names_keyset)

    if password is None:
        header = (
            _MAGIC
            + bytes((_MAJOR, _MINOR, _MODE_RANDOM, _SCHEMA))
            + struct.pack(">HHI", 0, _HEADER_RANDOM, len(logical_payload))
        )
        binary = header + logical_payload
    else:
        password_raw = _password_bytes(password)
        salt = os.urandom(_SALT_LENGTH)
        nonce = os.urandom(_NONCE_LENGTH)
        header = (
            _MAGIC
            + bytes((_MAJOR, _MINOR, _MODE_PASSWORD, _SCHEMA))
            + struct.pack(">HHI", 0, _HEADER_PASSWORD, len(logical_payload) + _TAG_LENGTH)
            + bytes((1, _ARGON2_VERSION))
            + struct.pack(">IIH", _ARGON2_MEMORY_KIB, _ARGON2_TIME, _ARGON2_PARALLELISM)
            + salt
            + bytes((1,))
            + nonce
        )
        wrapping_key = _derive_wrapping_key(password_raw, salt)
        try:
            encrypted_payload = AESGCM(wrapping_key).encrypt(
                nonce, logical_payload, header
            )
        except Exception as exc:
            raise BackendError("MasterKey payload protection failed") from exc
        binary = header + encrypted_payload

    if len(binary) > _MAX_BINARY:
        raise BackendError("generated MasterKey exceeds the binary size limit")
    return base64.b64encode(binary).decode("ascii")


def open_master_key(master_key: str, *, password: str | None = None) -> _KeyMaterial:
    """Validate and open a MasterKey container, returning both Tink primitives."""
    if not isinstance(master_key, str):
        raise TypeError("master_key must be str")
    try:
        encoded = master_key.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise FormatError("MasterKey must be standard Base64 ASCII") from exc
    if not encoded or len(encoded) > _MAX_BASE64:
        raise FormatError("MasterKey Base64 length is invalid")
    try:
        binary = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise FormatError("MasterKey is not valid Base64") from exc
    if base64.b64encode(binary) != encoded:
        raise FormatError("MasterKey Base64 is not canonical")
    if len(binary) > _MAX_BINARY or len(binary) < _HEADER_RANDOM:
        raise FormatError("MasterKey binary size is invalid")
    if binary[:8] != _MAGIC:
        raise FormatError("MasterKey magic is invalid")
    if binary[8] != _MAJOR or binary[9] != _MINOR:
        raise UnsupportedFormatVersionError("unsupported MasterKey version")

    mode, schema = binary[10], binary[11]
    if mode not in (_MODE_RANDOM, _MODE_PASSWORD) or schema != _SCHEMA:
        raise FormatError("unsupported MasterKey mode or payload schema")
    flags, header_length, payload_length = struct.unpack_from(">HHI", binary, 12)
    if flags != 0:
        raise FormatError("MasterKey reserved flags must be zero")
    expected_header = _HEADER_RANDOM if mode == _MODE_RANDOM else _HEADER_PASSWORD
    payload_limit = (
        _MAX_LOGICAL_PAYLOAD
        if mode == _MODE_RANDOM
        else _MAX_LOGICAL_PAYLOAD + _TAG_LENGTH
    )
    if header_length != expected_header:
        raise FormatError("MasterKey header length is invalid")
    if payload_length > payload_limit:
        raise FormatError("MasterKey payload exceeds the size limit")
    if mode == _MODE_PASSWORD and payload_length < _TAG_LENGTH:
        raise FormatError("protected MasterKey payload is shorter than its AEAD tag")
    if len(binary) != header_length + payload_length:
        raise FormatError("MasterKey total length does not match its header")

    header = binary[:header_length]
    payload = binary[header_length:]
    if mode == _MODE_RANDOM:
        if password is not None:
            raise ValueError("password must not be supplied for an unprotected MasterKey")
        logical_payload = payload
    else:
        if password is None:
            raise ValueError("password is required for this MasterKey")
        password_raw = _password_bytes(password)
        if (
            header[20] != 1
            or header[21] != _ARGON2_VERSION
            or struct.unpack_from(">I", header, 22)[0] != _ARGON2_MEMORY_KIB
            or struct.unpack_from(">I", header, 26)[0] != _ARGON2_TIME
            or struct.unpack_from(">H", header, 30)[0] != _ARGON2_PARALLELISM
            or header[48] != 1
        ):
            raise FormatError("MasterKey KDF or wrapping profile is unsupported")
        salt = header[32:48]
        nonce = header[49:61]
        if len(salt) != _SALT_LENGTH or len(nonce) != _NONCE_LENGTH:
            raise FormatError("MasterKey salt or nonce length is invalid")
        wrapping_key = _derive_wrapping_key(password_raw, salt)
        try:
            logical_payload = AESGCM(wrapping_key).decrypt(
                nonce, payload, header
            )
        except InvalidTag as exc:
            raise AuthenticationError(
                "MasterKey password or protected payload is invalid"
            ) from exc
        except Exception as exc:
            raise BackendError("MasterKey payload decryption failed") from exc

    if len(logical_payload) > _MAX_LOGICAL_PAYLOAD:
        raise FormatError("MasterKey logical payload exceeds the size limit")
    content_keyset, names_keyset = _split_payload(logical_payload)
    return _restore_key_material(content_keyset, names_keyset)
