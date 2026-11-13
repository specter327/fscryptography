"""Binary file envelope header for fscryptography v1.0."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .errors import FormatError, UnsupportedFormatVersionError

MAGIC = b"FSCRFIL\0"
MAJOR_VERSION = 1
MINOR_VERSION = 0
FIXED_HEADER_SIZE = 16
METADATA_PREFIX_SIZE = 4
MAX_EXTENSION_BYTES = 1020
MAX_HEADER_SIZE = FIXED_HEADER_SIZE + METADATA_PREFIX_SIZE + 2 * MAX_EXTENSION_BYTES

FLAG_ORIGINAL_EXTENSION = 0x0001
FLAG_ENCRYPTED_NAME = 0x0002
_KNOWN_FLAGS = FLAG_ORIGINAL_EXTENSION | FLAG_ENCRYPTED_NAME


@dataclass(frozen=True, slots=True)
class FileHeader:
    """Validated, authenticated metadata carried by a file header."""

    original_extension: str | None
    output_extension: str | None
    encrypted_name: bool
    raw: bytes


def split_extension(name: str) -> tuple[str, str | None]:
    """Return (base, extension); dotfiles and trailing dots have no extension."""
    if not isinstance(name, str):
        raise TypeError("name must be str")
    if not name or name in {".", ".."} or "/" in name or "\\x00" in name:
        raise ValueError("name must be one non-empty filename component")
    dot = name.rfind(".")
    if dot <= 0 or dot == len(name) - 1:
        return name, None
    return name[:dot], name[dot:]


def validate_extension(extension: str | None, *, allow_none: bool = True) -> str | None:
    """Validate an extension value without adding, stripping, or normalizing."""
    if extension is None:
        if allow_none:
            return None
        raise ValueError("extension is required")
    if not isinstance(extension, str):
        raise TypeError("extension must be str or None")
    if extension == "":
        return ""
    if (
        not extension.startswith(".")
        or extension.startswith("..")
        or len(extension) < 2
        or any(ord(char) < 0x20 for char in extension)
    ):
        raise ValueError("extension must be a valid single-component suffix")
    try:
        encoded = extension.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("extension must be valid UTF-8") from exc
    if len(encoded) > MAX_EXTENSION_BYTES:
        raise ValueError("extension exceeds the format metadata limit")
    return extension


def build_header(
    *,
    original_extension: str | None,
    output_extension: str | None,
    encrypted_name: bool = False,
) -> bytes:
    """Serialize the v1.0 header; both extension values are authenticated as AAD.

    For visible names, output_extension is mandatory and may be empty. For
    encrypted names, neither extension is stored in cleartext.
    """
    original = validate_extension(original_extension)
    output = validate_extension(output_extension)
    if original == "":
        raise ValueError("original_extension must be None or a non-empty suffix")
    if not isinstance(encrypted_name, bool):
        raise TypeError("encrypted_name must be bool")
    if encrypted_name:
        if original is not None or output is not None:
            raise ValueError("encrypted-name headers must not expose extensions")
        flags = FLAG_ENCRYPTED_NAME
        original_bytes = output_bytes = b""
    else:
        if output is None:
            raise ValueError("visible-name headers require output_extension")
        flags = 0
        if original is not None:
            flags |= FLAG_ORIGINAL_EXTENSION
        original_bytes = b"" if original is None else original.encode("utf-8")
        output_bytes = output.encode("utf-8")

    metadata = struct.pack(">HH", len(original_bytes), len(output_bytes))
    metadata += original_bytes + output_bytes
    header_length = FIXED_HEADER_SIZE + len(metadata)
    if header_length > MAX_HEADER_SIZE:
        raise ValueError("file header exceeds the format limit")
    fixed = (
        MAGIC
        + bytes((MAJOR_VERSION, MINOR_VERSION))
        + struct.pack(">HI", flags, header_length)
    )
    return fixed + metadata


def parse_header(raw: bytes) -> FileHeader:
    """Parse and strictly validate one complete v1.0 header."""
    if not isinstance(raw, bytes):
        raise TypeError("header must be bytes")
    if len(raw) < FIXED_HEADER_SIZE:
        raise FormatError("file header is truncated")
    if raw[:8] != MAGIC:
        raise FormatError("file magic is invalid")
    if raw[8] != MAJOR_VERSION or raw[9] != MINOR_VERSION:
        raise UnsupportedFormatVersionError("unsupported file format version")
    flags, header_length = struct.unpack_from(">HI", raw, 10)
    if flags & ~_KNOWN_FLAGS:
        raise FormatError("file header contains reserved flags")
    if header_length < FIXED_HEADER_SIZE + METADATA_PREFIX_SIZE:
        raise FormatError("file header length is too small")
    if header_length > MAX_HEADER_SIZE:
        raise FormatError("file header exceeds the format limit")
    if len(raw) != header_length:
        raise FormatError("file header length does not match supplied bytes")

    original_length, output_length = struct.unpack_from(">HH", raw, FIXED_HEADER_SIZE)
    if original_length > MAX_EXTENSION_BYTES or output_length > MAX_EXTENSION_BYTES:
        raise FormatError("file extension metadata exceeds the format limit")
    expected_length = FIXED_HEADER_SIZE + METADATA_PREFIX_SIZE + original_length + output_length
    if expected_length != header_length:
        raise FormatError("file extension metadata lengths are inconsistent")

    original_raw = raw[20 : 20 + original_length]
    output_raw = raw[20 + original_length : header_length]
    try:
        original = original_raw.decode("utf-8", errors="strict") if original_length else None
        output = output_raw.decode("utf-8", errors="strict") if output_length else ""
    except UnicodeDecodeError as exc:
        raise FormatError("file extension metadata is not valid UTF-8") from exc

    original_flag = bool(flags & FLAG_ORIGINAL_EXTENSION)
    encrypted_name = bool(flags & FLAG_ENCRYPTED_NAME)
    if original_flag != (original is not None):
        raise FormatError("original-extension flag and metadata disagree")
    if original is not None:
        try:
            validate_extension(original, allow_none=False)
        except (TypeError, ValueError) as exc:
            raise FormatError("original extension metadata is invalid") from exc
    if encrypted_name:
        if original_length or output_length or original_flag:
            raise FormatError("encrypted-name header exposes extension metadata")
        output_value = None
    else:
        if output_length:
            try:
                validate_extension(output, allow_none=False)
            except (TypeError, ValueError) as exc:
                raise FormatError("output extension metadata is invalid") from exc
        output_value = output

    return FileHeader(
        original_extension=original,
        output_extension=output_value,
        encrypted_name=encrypted_name,
        raw=raw,
    )
