"""Filesystem name validation independent from path traversal or mutation."""

from __future__ import annotations

from enum import Enum

from ..errors import NameConstraintError


class NameProfile(str, Enum):
    """Name constraints applied to a single filesystem component."""

    WINDOWS = "windows"
    GNU_LINUX = "gnu-linux"


_WINDOWS_FORBIDDEN = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"}
)
_SUPERSCRIPT_DIGITS = "¹²³"


def _as_component_bytes(name: str) -> bytes:
    if not isinstance(name, str):
        raise TypeError("name must be str")
    try:
        encoded = name.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise NameConstraintError("name is not valid UTF-8") from exc
    if not name:
        raise NameConstraintError("name component must not be empty")
    if name in {".", ".."}:
        raise NameConstraintError("dot path components are not valid resource names")
    if "\x00" in name or "/" in name:
        raise NameConstraintError("name must be a single path component")
    return encoded


def _is_reserved_windows_device(name: str) -> bool:
    stem = name.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        return True
    if len(stem) == 4 and stem[:3] in {"COM", "LPT"}:
        return stem[3] in "123456789" or stem[3] in _SUPERSCRIPT_DIGITS
    return False


def validate_name(
    name: str,
    *,
    profile: NameProfile = NameProfile.GNU_LINUX,
    max_component_bytes: int | None = None,
) -> bytes:
    """Validate one plaintext component and return its strict UTF-8 bytes.

    The caller supplies the effective destination component limit when known.
    No Unicode normalization or case folding is performed.
    """
    encoded = _as_component_bytes(name)
    try:
        selected = NameProfile(profile)
    except ValueError as exc:
        raise ValueError(f"unsupported name profile: {profile!r}") from exc

    if selected is NameProfile.WINDOWS:
        if any(char in _WINDOWS_FORBIDDEN for char in name):
            raise NameConstraintError("name contains a character forbidden by Windows")
        if any(ord(char) < 0x20 for char in name):
            raise NameConstraintError("name contains a Windows control character")
        if name.endswith((".", " ")):
            raise NameConstraintError("Windows names must not end in dot or space")
        if _is_reserved_windows_device(name):
            raise NameConstraintError("name is a reserved Windows device name")

    if max_component_bytes is not None:
        if isinstance(max_component_bytes, bool) or not isinstance(max_component_bytes, int):
            raise TypeError("max_component_bytes must be an integer or None")
        if max_component_bytes <= 0:
            raise ValueError("max_component_bytes must be positive")
        if len(encoded) > max_component_bytes:
            raise NameConstraintError("name exceeds the destination component limit")

    return encoded
