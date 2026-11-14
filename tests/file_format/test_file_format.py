from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from fscryptography.file_format import (
    FLAG_ENCRYPTED_NAME,
    MAX_HEADER_SIZE,
    build_header,
    parse_header,
    split_extension,
)
from fscryptography.errors import FormatError, UnsupportedFormatVersionError


@pytest.mark.parametrize(
    ("name", "base", "extension"),
    [
        ("document.txt", "document", ".txt"),
        ("archive.tar.gz", "archive.tar", ".gz"),
        (".profile", ".profile", None),
        (".config.json", ".config", ".json"),
        ("README", "README", None),
        ("report.", "report.", None),
    ],
)
def test_split_extension(name, base, extension):
    assert split_extension(name) == (base, extension)


@pytest.mark.parametrize(
    ("original", "output"),
    [
        (".txt", ".fscrypt"),
        (None, ".fscrypt"),
    ],
)
def test_visible_header_round_trip(original, output):
    header = build_header(original_extension=original, output_extension=output)
    parsed = parse_header(header)
    assert parsed.original_extension == original
    assert parsed.output_extension == output
    assert parsed.encrypted_name is False
    assert parsed.raw == header


def test_encrypted_name_header_has_no_cleartext_extension_metadata():
    header = build_header(
        original_extension=None,
        output_extension=None,
        encrypted_name=True,
    )
    parsed = parse_header(header)
    assert parsed.encrypted_name is True
    assert parsed.original_extension is None
    assert parsed.output_extension is None
    assert struct.unpack_from(">H", header, 10)[0] == FLAG_ENCRYPTED_NAME


def test_custom_output_extension_is_self_contained():
    header = build_header(original_extension=".txt", output_extension=".locked")
    parsed = parse_header(header)
    assert parsed.original_extension == ".txt"
    assert parsed.output_extension == ".locked"


@pytest.mark.parametrize(
    "header",
    [
        b"",
        b"short",
        b"BADMAGIC" + b"\x01\x00" + b"\x00\x00" + b"\x00\x00\x00\x14" + b"\x00" * 4,
    ],
)
def test_rejects_truncated_or_invalid_header(header):
    with pytest.raises(FormatError):
        parse_header(header)


def test_rejects_unsupported_version():
    header = bytearray(build_header(original_extension=None, output_extension=".fscrypt"))
    header[8] = 2
    with pytest.raises(UnsupportedFormatVersionError):
        parse_header(bytes(header))


def test_rejects_reserved_flags():
    header = bytearray(build_header(original_extension=None, output_extension=".fscrypt"))
    header[10:12] = struct.pack(">H", 0x8000)
    with pytest.raises(FormatError):
        parse_header(bytes(header))


def test_rejects_inconsistent_header_length():
    header = bytearray(build_header(original_extension=None, output_extension=".fscrypt"))
    header[12:16] = struct.pack(">I", len(header) + 1)
    with pytest.raises(FormatError):
        parse_header(bytes(header))


def test_rejects_invalid_utf8_metadata():
    header = bytearray(build_header(original_extension=None, output_extension=".fscrypt"))
    header[-1] = 0xFF
    with pytest.raises(FormatError):
        parse_header(bytes(header))


def test_encrypted_name_rejects_exposed_extension():
    with pytest.raises(ValueError):
        build_header(
            original_extension=".txt",
            output_extension=None,
            encrypted_name=True,
        )


def test_header_size_bound_is_enforced():
    extension = "." + ("a" * 1019)
    header = build_header(original_extension=extension, output_extension=extension)
    assert len(header) <= MAX_HEADER_SIZE


def test_visible_header_golden_vector():
    header = build_header(original_extension=".txt", output_extension=".fscrypt")
    assert header.hex() == (
        "4653435246494c00"  # FSCRFIL\\0
        "0100"              # version
        "0001"              # original extension present
        "00000020"          # 32-byte header
        "0004"              # original extension length
        "0008"              # output extension length
        "2e747874"          # .txt
        "2e66736372797074"  # .fscrypt
    )


def test_empty_output_extension_is_preserved():
    header = build_header(original_extension=".txt", output_extension="")
    parsed = parse_header(header)
    assert parsed.original_extension == ".txt"
    assert parsed.output_extension == ""


def test_original_extension_flag_must_match_length():
    header = bytearray(build_header(original_extension=".txt", output_extension=".fscrypt"))
    header[10:12] = struct.pack(">H", 0)
    with pytest.raises(FormatError):
        parse_header(bytes(header))



def test_v1_header_golden_vectors():
    fixture_path = Path(__file__).parent / "fixtures" / "file_header_v1_vectors.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    for vector in fixture["vectors"]:
        fields = vector["fields"]
        header = build_header(
            original_extension=fields["original_extension"],
            output_extension=fields["output_extension"],
            encrypted_name=fields["encrypted_name"],
        )
        assert header.hex() == vector["header_hex"], vector["id"]
        parsed = parse_header(header)
        assert parsed.original_extension == fields["original_extension"]
        assert parsed.output_extension == fields["expected_output_extension"]
        assert parsed.encrypted_name is fields["encrypted_name"]


def test_v1_header_parser_rejects_every_truncated_golden_header():
    header = bytes.fromhex(
        "4653435246494c000100000100000020000400082e7478742e66736372797074"
    )
    for end in range(len(header)):
        with pytest.raises(FormatError):
            parse_header(header[:end])


def test_v1_header_parser_rejects_trailing_bytes():
    header = build_header(original_extension=".txt", output_extension=".fscrypt")
    with pytest.raises(FormatError, match="length"):
        parse_header(header + b"\x00")


def test_v1_header_parser_rejects_each_reserved_flag_bit():
    header = build_header(original_extension=None, output_extension=".fscrypt")
    for bit in range(2, 16):
        mutated = bytearray(header)
        flags = struct.unpack_from(">H", mutated, 10)[0] | (1 << bit)
        mutated[10:12] = struct.pack(">H", flags)
        with pytest.raises(FormatError, match="reserved flags"):
            parse_header(bytes(mutated))


@pytest.mark.parametrize("length_offset", [16, 18])
def test_v1_header_parser_rejects_oversized_metadata_lengths(length_offset):
    header = bytearray(build_header(original_extension=".txt", output_extension=".fscrypt"))
    header[length_offset:length_offset + 2] = struct.pack(">H", 0xFFFF)
    with pytest.raises(FormatError):
        parse_header(bytes(header))
