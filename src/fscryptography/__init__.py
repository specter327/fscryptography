"""Filesystem-oriented cryptographic operations."""

from .crypto import Manager, generate
from ._journal import RecoveryRecord

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
    "Manager",
    "generate",
    "RecoveryRecord",
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
