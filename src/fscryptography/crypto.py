"""Public Manager API for MasterKey-backed filesystem cryptography."""

from __future__ import annotations

import base64

from ._master_key import (
    _KeyMaterial,
    _decode_master_key,
    _open_master_key_bytes,
    generate_master_key,
)
from .errors import ClosedInstanceError


def generate(*, password: str | None = None) -> str:
    """Generate a Base64 MasterKey, optionally protected by a password."""
    return generate_master_key(password=password)


class Manager:
    """An opened cryptographic context bound to one MasterKey.

    The public key representation is Base64 text. The manager retains the
    decoded binary container and the opened Tink primitives. Passwords are
    consumed during initialization or key replacement and are never retained.
    """

    def __init__(self, key: str, *, password: str | None = None) -> None:
        key_bytes = _decode_master_key(key)
        material = _open_master_key_bytes(key_bytes, password=password)
        self._key: bytes | None = key_bytes
        self._material: _KeyMaterial | None = material
        from ._filesystem import _DirectoryOperations, _FileOperations
        self._file_operations = _FileOperations(self)
        self._directory_operations = _DirectoryOperations(self)

    def _require_open(self) -> _KeyMaterial:
        if self._material is None or self._key is None:
            raise ClosedInstanceError("Manager is closed")
        return self._material

    @property
    def _content_primitive(self):
        return self._require_open().content

    @property
    def _names_primitive(self):
        return self._require_open().names

    @property
    def file(self):
        self._require_open()
        return self._file_operations

    @property
    def dir(self):
        self._require_open()
        return self._directory_operations

    def change_key(self, new_key: str, *, password: str | None = None) -> None:
        """Replace the active context only after the new key opens successfully."""
        self._require_open()
        key_bytes = _decode_master_key(new_key)
        material = _open_master_key_bytes(key_bytes, password=password)
        self._key = key_bytes
        self._material = material

    def export_key(self) -> str:
        """Return the current MasterKey container as canonical Base64 text."""
        self._require_open()
        return base64.b64encode(self._key).decode("ascii")

    def close(self) -> None:
        """Invalidate this manager and release references to its key material."""
        self._material = None
        self._key = None

    def __enter__(self) -> Manager:
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
