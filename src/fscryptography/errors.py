"""Public exception hierarchy for fscryptography."""

class FsCryptographyError(Exception):
    """Base class for errors raised by fscryptography."""


class InvalidPathError(FsCryptographyError):
    """A path or path component cannot be used by the requested operation."""


class UnsupportedResourceError(FsCryptographyError):
    """The resource exists but is not supported by the operation."""


class FormatError(FsCryptographyError):
    """An encoded representation is malformed or not recognized."""


class UnsupportedFormatVersionError(FormatError):
    """The encoded representation uses an unsupported version."""


class AuthenticationError(FsCryptographyError):
    """Authenticated decryption failed."""


class KeyDerivationError(FsCryptographyError):
    """A key derivation operation failed."""


class DestinationConflictError(FsCryptographyError):
    """The destination conflicts with an existing filesystem entry."""


class NameConstraintError(FsCryptographyError):
    """A name violates the selected filesystem name profile."""


class BackendError(FsCryptographyError):
    """A cryptographic backend operation failed unexpectedly."""


class ClosedInstanceError(FsCryptographyError):
    """An operation was attempted on a closed Manager instance."""


class AtomicOperationError(FsCryptographyError):
    """A filesystem transformation could not complete its expected publication or source-retirement sequence."""

