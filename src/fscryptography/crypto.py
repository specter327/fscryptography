"""Public Manager API for MasterKey-backed filesystem cryptography."""

from __future__ import annotations

import base64
from threading import RLock

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
        self._state_lock = RLock()
        self._context: tuple[bytes, _KeyMaterial] | None = (key_bytes, material)
        from ._filesystem import _DirectoryOperations, _FileOperations
        self._file_operations = _FileOperations(self)
        self._directory_operations = _DirectoryOperations(self)

    def _require_open(self) -> _KeyMaterial:
        with self._state_lock:
            context = self._context
        if context is None:
            raise ClosedInstanceError("Manager is closed")
        return context[1]

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
        with self._state_lock:
            if self._context is None:
                raise ClosedInstanceError("Manager is closed")
        key_bytes = _decode_master_key(new_key)
        material = _open_master_key_bytes(key_bytes, password=password)
        with self._state_lock:
            if self._context is None:
                raise ClosedInstanceError("Manager is closed")
            self._context = (key_bytes, material)

    def inspect_recovery(self, parent):
        """Return immutable, read-only diagnostics for transactions under parent."""
        from ._journal import inspect
        return inspect(parent)

    def export_key(self) -> str:
        """Return the current MasterKey container as canonical Base64 text."""
        with self._state_lock:
            context = self._context
        if context is None:
            raise ClosedInstanceError("Manager is closed")
        return base64.b64encode(context[0]).decode("ascii")

    def close(self) -> None:
        """Invalidate this manager and release references to its key material."""
        with self._state_lock:
            self._context = None

    def __enter__(self) -> Manager:
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
