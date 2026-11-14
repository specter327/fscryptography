"""Filesystem-oriented cryptographic operations."""

from .crypto import Manager, generate

from .errors import (
    AtomicOperationError,
    AuthenticationError,
    BackendError,
    ClosedInstanceError,
    DestinationConflictError,
    FormatError,
    FsCryptographyError,
    InvalidPathError,
    KeyDerivationError,
    NameConstraintError,
    UnsupportedFormatVersionError,
    UnsupportedResourceError,
)

__all__ = [
    "Manager",
    "generate",
    "AtomicOperationError",
    "AuthenticationError",
    "BackendError",
    "ClosedInstanceError",
    "DestinationConflictError",
    "FormatError",
    "FsCryptographyError",
    "InvalidPathError",
    "KeyDerivationError",
    "NameConstraintError",
    "UnsupportedFormatVersionError",
    "UnsupportedResourceError",
]

__version__ = "0.1.0"
