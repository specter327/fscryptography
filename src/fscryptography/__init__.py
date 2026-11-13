"""Filesystem-oriented cryptographic operations."""

from .crypto import Crypto

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
    "Crypto",
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
