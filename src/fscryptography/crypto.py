"""Public Crypto facade for MasterKey-backed filesystem cryptography."""

from __future__ import annotations

from ._master_key import _KeyMaterial, generate_master_key, open_master_key
from .errors import ClosedInstanceError


class Crypto:
    """An opened MasterKey context.

    Passwords are consumed during initialization and are never retained.
    File and directory operations are exposed by this facade in subsequent
    implementation stages.
    """

    def __init__(self, *, master_key: str, password: str | None = None) -> None:
        self._material: _KeyMaterial | None = open_master_key(
            master_key, password=password
        )

    @staticmethod
    def generate(*, password: str | None = None) -> str:
        """Generate a random MasterKey or protect it with a password."""
        return generate_master_key(password=password)

    @staticmethod
    def derive(*, text: str) -> str:
        """Generate a MasterKey protected by the supplied passphrase."""
        if not isinstance(text, str):
            raise TypeError("text must be str")
        return generate_master_key(password=text)

    @property
    def _content_primitive(self):
        return self._require_open().content

    @property
    def _names_primitive(self):
        return self._require_open().names

    def _require_open(self) -> _KeyMaterial:
        if self._material is None:
            raise ClosedInstanceError("Crypto instance is closed")
        return self._material

    def close(self) -> None:
        """Invalidate this instance and release references to its primitives."""
        self._material = None

    def __enter__(self) -> Crypto:
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
