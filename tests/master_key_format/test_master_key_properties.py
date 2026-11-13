from __future__ import annotations

import base64

from hypothesis import given, settings, strategies as st

from fscryptography._master_key import _decode_master_key, _split_payload
from fscryptography.errors import FormatError


@given(payload=st.binary(max_size=4096))
@settings(max_examples=500, deadline=None)
def test_master_key_payload_framing_is_total_for_arbitrary_bounded_bytes(payload):
    try:
        content_keyset, names_keyset = _split_payload(payload)
    except FormatError:
        return

    assert content_keyset
    assert names_keyset
    assert len(content_keyset) <= 32 * 1024
    assert len(names_keyset) <= 32 * 1024


@given(encoded=st.text(max_size=1024))
@settings(max_examples=500, deadline=None)
def test_master_key_base64_decoder_is_total_for_arbitrary_text(encoded):
    try:
        decoded = _decode_master_key(encoded)
    except FormatError:
        return

    assert base64.b64encode(decoded).decode("ascii") == encoded
