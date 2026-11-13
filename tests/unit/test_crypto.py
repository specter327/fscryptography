import pytest

from fscryptography import ClosedInstanceError, Crypto


def test_crypto_generate_and_open_random_master_key():
    master_key = Crypto.generate()
    crypto = Crypto(master_key=master_key)
    assert crypto._names_primitive is not None
    assert crypto._content_primitive is not None
    crypto.close()
    with pytest.raises(ClosedInstanceError):
        crypto._names_primitive


def test_crypto_generate_and_open_password_protected_master_key():
    master_key = Crypto.generate(password="correct horse")
    with Crypto(master_key=master_key, password="correct horse") as crypto:
        assert crypto._names_primitive is not None
    with pytest.raises(ClosedInstanceError):
        crypto._content_primitive


def test_crypto_derive_is_password_protected_generation_alias():
    master_key = Crypto.derive(text="passphrase")
    crypto = Crypto(master_key=master_key, password="passphrase")
    assert crypto._names_primitive is not None
    crypto.close()


def test_crypto_context_manager_closes_on_exception():
    crypto = Crypto(master_key=Crypto.generate())
    with pytest.raises(RuntimeError):
        with crypto:
            raise RuntimeError("test")
    with pytest.raises(ClosedInstanceError):
        crypto._content_primitive
