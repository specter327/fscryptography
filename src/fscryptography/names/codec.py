"""Tink-backed codec for encrypted filesystem name components."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Protocol

from ..errors import AuthenticationError, BackendError, FormatError, NameConstraintError
from .validation import NameProfile, validate_name

MARKER = "~1"
AAD = b"fscryptography:filename:v1"
TINK_AES256_GCM_OVERHEAD = 33
_BASE64URL = re.compile(r"[A-Za-z0-9_-]+", re.ASCII)


class AeadPrimitive(Protocol):
    def encrypt(self, plaintext: bytes, associated_data: bytes) -> bytes: ...
    def decrypt(self, ciphertext: bytes, associated_data: bytes) -> bytes: ...


def _encode_ciphertext(ciphertext: bytes) -> str:
    return base64.urlsafe_b64encode(ciphertext).rstrip(b"=").decode("ascii")


def _decode_ciphertext(value: str) -> bytes:
    if not isinstance(value, str):
        raise TypeError("encoded_name must be str")
    if not value.startswith(MARKER):
        raise FormatError("encrypted name marker is missing")
    body = value[len(MARKER):]
    if not body or _BASE64URL.fullmatch(body) is None:
        raise FormatError("encrypted name is not canonical Base64URL")
    try:
        raw = base64.b64decode(
            body + "=" * ((4 - len(body) % 4) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise FormatError("encrypted name is not valid Base64URL") from exc
    if _encode_ciphertext(raw) != body:
        raise FormatError("encrypted name is not canonical Base64URL")
    # A TINK-prefixed AES256_GCM ciphertext needs 5 prefix + 12 nonce + 16 tag.
    if len(raw) < TINK_AES256_GCM_OVERHEAD:
        raise FormatError("encrypted name ciphertext is truncated")
    return raw


def is_canonical_candidate(value: str) -> bool:
    """Return whether value has the complete canonical textual envelope."""
    if not isinstance(value, str) or not value.startswith(MARKER):
        return False
    try:
        _decode_ciphertext(value)
    except (FormatError, TypeError):
        return False
    return True


def encrypt_name(
    name: str,
    primitive: AeadPrimitive,
    *,
    profile: NameProfile = NameProfile.GNU_LINUX,
    max_component_bytes: int | None = 255,
) -> str:
    """Encrypt a plaintext component, refusing active-key double encryption."""
    plaintext = validate_name(name, profile=profile)
    if is_canonical_candidate(name):
        try:
            primitive.decrypt(_decode_ciphertext(name), AAD)
        except Exception:
            # A syntactically valid candidate that does not authenticate remains
            # a possible plaintext name. Do not disclose why authentication failed.
            pass
        else:
            raise NameConstraintError("name is already encrypted with the active key")

    try:
        ciphertext = primitive.encrypt(plaintext, AAD)
    except Exception as exc:
        raise BackendError("filename encryption backend failed") from exc

    if not isinstance(ciphertext, bytes):
        raise BackendError("filename encryption backend returned an invalid value")
    encoded = MARKER + _encode_ciphertext(ciphertext)
    encoded_size = len(encoded.encode("ascii"))
    if max_component_bytes is not None and encoded_size > max_component_bytes:
        raise NameConstraintError("encrypted name exceeds the destination component limit")
    return encoded


def decrypt_name(
    encoded_name: str,
    primitive: AeadPrimitive,
    *,
    profile: NameProfile = NameProfile.GNU_LINUX,
    max_component_bytes: int | None = 255,
) -> str:
    """Authenticate and decode a single encrypted component."""
    ciphertext = _decode_ciphertext(encoded_name)
    try:
        plaintext = primitive.decrypt(ciphertext, AAD)
    except Exception as exc:
        raise AuthenticationError("encrypted name authentication failed") from exc
    if not isinstance(plaintext, bytes):
        raise BackendError("filename decryption backend returned an invalid value")
    try:
        name = plaintext.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise FormatError("authenticated filename is not valid UTF-8") from exc
    validate_name(name, profile=profile, max_component_bytes=max_component_bytes)
    return name
