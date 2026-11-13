"""Filesystem-oriented cryptographic operations."""

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
    RecoveryError,
    UnsupportedFormatVersionError,
    UnsupportedResourceError,
)

__all__ = [
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
    "RecoveryError",
    "UnsupportedFormatVersionError",
    "UnsupportedResourceError",
]

__version__ = "0.1.0"
