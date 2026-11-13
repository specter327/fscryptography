from __future__ import annotations

import tink
from tink import aead, secret_key_access

from fscryptography.names.tink_backend import load_name_primitive
from fscryptography.names import decrypt_name, encrypt_name


def test_real_tink_aes256_gcm_filename_round_trip():
    aead.register()
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    serialized = tink.proto_keyset_format.serialize(
        handle, secret_key_access.TOKEN
    )
    primitive = load_name_primitive(serialized)

    original = "informe-acción-日本語.txt"
    encrypted = encrypt_name(original, primitive)
    assert decrypt_name(encrypted, primitive) == original


def test_real_tink_rejects_wrong_key():
    aead.register()
    first = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    second = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    first_primitive = load_name_primitive(
        tink.proto_keyset_format.serialize(first, secret_key_access.TOKEN)
    )
    second_primitive = load_name_primitive(
        tink.proto_keyset_format.serialize(second, secret_key_access.TOKEN)
    )

    encrypted = encrypt_name("secret.txt", first_primitive)
    from fscryptography.errors import AuthenticationError

    try:
        decrypt_name(encrypted, second_primitive)
    except AuthenticationError:
        pass
    else:
        raise AssertionError("wrong key unexpectedly authenticated")
