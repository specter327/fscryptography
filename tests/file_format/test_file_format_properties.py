from __future__ import annotations

from hypothesis import given, settings, strategies as st

from fscryptography.errors import FormatError, UnsupportedFormatVersionError
from fscryptography.file_format import build_header, parse_header


_component_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=24,
)
_suffix = _component_text.map(lambda value: "." + value)


@given(
    original=st.one_of(st.none(), _suffix),
    output=st.one_of(st.just(""), _suffix),
)
@settings(max_examples=250, deadline=None)
def test_valid_unicode_extension_headers_round_trip(original, output):
    header = build_header(
        original_extension=original,
        output_extension=output,
    )
    parsed = parse_header(header)
    assert parsed.original_extension == original
    assert parsed.output_extension == output
    assert parsed.raw == header


@given(raw=st.binary(max_size=2076))
@settings(max_examples=500, deadline=None)
def test_header_parser_is_total_for_arbitrary_bounded_bytes(raw):
    try:
        parsed = parse_header(raw)
    except (FormatError, UnsupportedFormatVersionError):
        return

    assert parsed.raw == raw
    assert parse_header(parsed.raw) == parsed
