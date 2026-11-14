from __future__ import annotations

import pytest

import fscryptography
from fscryptography.errors import (
    AuthenticationError,
    FormatError,
    UnsupportedResourceError,
)


@pytest.fixture
def manager():
    instance = fscryptography.Manager(fscryptography.generate())
    try:
        yield instance
    finally:
        instance.close()


def test_master_key_boundary_preserves_argument_and_format_errors():
    with pytest.raises(TypeError):
        fscryptography.Manager(123)

    with pytest.raises(FormatError):
        fscryptography.Manager("not-base64")


def test_password_protected_master_key_classifies_authentication_failure():
    protected = fscryptography.generate(password="correct horse battery staple")

    with pytest.raises(ValueError):
        fscryptography.Manager(protected)

    with pytest.raises(AuthenticationError):
        fscryptography.Manager(
            protected,
            password="incorrect horse battery staple",
        )


def test_closed_manager_rejects_new_operations_with_public_error():
    instance = fscryptography.Manager(fscryptography.generate())
    instance.close()

    with pytest.raises(fscryptography.ClosedInstanceError):
        instance.file.encrypt("unused.txt")


def test_missing_source_preserves_standard_filesystem_error(manager, tmp_path):
    missing = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        manager.file.encrypt(missing)


def test_file_operation_rejects_directory_as_unsupported_resource(manager, tmp_path):
    directory = tmp_path / "directory"
    directory.mkdir()

    with pytest.raises(UnsupportedResourceError):
        manager.file.encrypt(directory)


def test_malformed_file_header_is_a_format_error_and_preserves_source(manager, tmp_path):
    source = tmp_path / "malformed.fscrypt"
    source.write_bytes(b"not a valid FSCRFIL header")

    with pytest.raises(FormatError):
        manager.file.decrypt(source)

    assert source.read_bytes() == b"not a valid FSCRFIL header"



def test_encrypted_directory_name_classifies_malformed_envelope(manager, tmp_path):
    malformed = tmp_path / "~1!"
    malformed.mkdir()

    with pytest.raises(FormatError):
        manager.dir.decrypt(malformed)

    assert malformed.is_dir()


def test_encrypted_directory_name_classifies_authentication_failure(manager, tmp_path):
    import base64

    raw_ciphertext = b"\\x00" * 33
    encoded = base64.urlsafe_b64encode(raw_ciphertext).rstrip(b"=").decode("ascii")
    candidate = tmp_path / ("~1" + encoded)
    candidate.mkdir()

    with pytest.raises(AuthenticationError):
        manager.dir.decrypt(candidate)

    assert candidate.is_dir()
