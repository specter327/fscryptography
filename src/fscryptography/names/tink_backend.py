"""Google Tink adapter for filename AEAD keysets."""

from __future__ import annotations

import tink
from tink import aead, secret_key_access

from ..errors import BackendError


def load_name_primitive(serialized_keyset: bytes) -> aead.Aead:
    """Restore a Tink Aead primitive from a serialized protobuf keyset.

    The caller is responsible for obtaining the names keyset from the
    authenticated MasterKey container. This function never generates keys.
    """
    if not isinstance(serialized_keyset, bytes):
        raise TypeError("serialized_keyset must be bytes")
    if not serialized_keyset:
        raise ValueError("serialized_keyset must not be empty")
    try:
        aead.register()
        handle = tink.proto_keyset_format.parse(
            serialized_keyset, secret_key_access.TOKEN
        )
        return handle.primitive(aead.Aead)
    except Exception as exc:
        raise BackendError("unable to load filename AEAD keyset") from exc
