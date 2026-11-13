"""Filesystem operations backed by a Manager's reusable Tink primitives."""

from __future__ import annotations

import ctypes
import errno
import os
import stat
import struct
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

from .errors import (
    AtomicOperationError,
    AuthenticationError,
    BackendError,
    DestinationConflictError,
    FormatError,
    InvalidPathError,
    UnsupportedResourceError,
)
from .file_format import (
    FIXED_HEADER_SIZE,
    MAX_HEADER_SIZE,
    build_header,
    parse_header,
    split_extension,
)
from .names import NameProfile, decrypt_name, encrypt_name, validate_name

_CHUNK_SIZE = 1024 * 1024
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1


class _NonClosing:
    """Delegate binary I/O while keeping ownership with the caller."""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream

    def read(self, size: int = -1):
        return self._stream.read(size)

    def write(self, data: bytes):
        return self._stream.write(data)

    def flush(self):
        return self._stream.flush()

    def close(self):
        self._stream.flush()


def _profile() -> NameProfile:
    if os.name == "nt":
        return NameProfile.WINDOWS
    if sys.platform.startswith("linux"):
        return NameProfile.GNU_LINUX
    raise UnsupportedResourceError("only Windows and GNU/Linux are supported")


def _component_limit(parent: Path) -> int:
    if os.name == "nt":
        return 255
    try:
        value = os.pathconf(parent, "PC_NAME_MAX")
    except (AttributeError, OSError, ValueError):
        value = 255
    return int(value) if isinstance(value, int) and value > 0 else 255


def _path(value: str | os.PathLike[str]) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise TypeError("path must be str or os.PathLike")
    result = Path(os.path.abspath(os.fspath(value)))
    if result.name in {"", ".", ".."}:
        raise InvalidPathError("path must identify a filesystem resource")
    return result


def _validate_component(name: str, parent: Path) -> None:
    validate_name(
        name,
        profile=_profile(),
        max_component_bytes=_component_limit(parent),
    )


def _publish_noreplace(source: Path, destination: Path) -> None:
    """Atomically rename within one filesystem without replacing a destination."""
    if source.parent != destination.parent:
        raise AtomicOperationError("temporary and destination must share a directory")
    if os.name == "nt":
        try:
            os.rename(source, destination)
            return
        except FileExistsError as exc:
            raise DestinationConflictError("destination already exists") from exc
        except OSError as exc:
            raise AtomicOperationError("Windows no-replace publication failed") from exc

    if sys.platform.startswith("linux"):
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = libc.renameat2
        except (AttributeError, OSError) as exc:
            raise AtomicOperationError("renameat2(RENAME_NOREPLACE) is unavailable") from exc
        renameat2.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        renameat2.restype = ctypes.c_int
        result = renameat2(
            _AT_FDCWD,
            os.fsencode(source),
            _AT_FDCWD,
            os.fsencode(destination),
            _RENAME_NOREPLACE,
        )
        if result == 0:
            return
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise DestinationConflictError("destination already exists")
        raise AtomicOperationError(
            f"Linux no-replace publication failed: {os.strerror(error)}"
        ) from OSError(error, os.strerror(error))

    raise AtomicOperationError("no verified no-replace primitive for this platform")


def _check_source(path: Path, *, directory: bool) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError:
        raise
    if stat.S_ISLNK(info.st_mode):
        raise UnsupportedResourceError("symbolic links are not supported")
    if directory and not stat.S_ISDIR(info.st_mode):
        raise UnsupportedResourceError("resource is not a directory")
    if not directory and not stat.S_ISREG(info.st_mode):
        raise UnsupportedResourceError("resource is not a regular file")
    return info


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        part = stream.read(size - len(chunks))
        if not part:
            raise FormatError("file header is truncated")
        chunks.extend(part)
    return bytes(chunks)


def _read_header(stream: BinaryIO):
    fixed = _read_exact(stream, FIXED_HEADER_SIZE)
    header_length = struct.unpack_from(">I", fixed, 12)[0]
    if header_length < FIXED_HEADER_SIZE or header_length > MAX_HEADER_SIZE:
        raise FormatError("file header length is outside supported limits")
    return parse_header(fixed + _read_exact(stream, header_length - FIXED_HEADER_SIZE))


def _copy_encrypt(primitive, source: BinaryIO, destination: BinaryIO, aad: bytes) -> None:
    try:
        with primitive.new_encrypting_stream(_NonClosing(destination), aad) as encrypted:
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                encrypted.write(chunk)
    except Exception as exc:
        raise BackendError("Tink Streaming AEAD encryption failed") from exc


def _copy_decrypt(primitive, source: BinaryIO, destination: BinaryIO, aad: bytes) -> None:
    try:
        with primitive.new_decrypting_stream(_NonClosing(source), aad) as decrypted:
            while True:
                chunk = decrypted.read(_CHUNK_SIZE)
                if not chunk:
                    break
                destination.write(chunk)
    except Exception as exc:
        raise AuthenticationError("file content authentication failed") from exc


def _temporary_file(parent: Path) -> tuple[int, Path]:
    fd, name = tempfile.mkstemp(prefix=".fscryptography-", dir=parent)
    return fd, Path(name)


def _sync_close(stream: BinaryIO) -> None:
    stream.flush()
    os.fsync(stream.fileno())
    stream.close()


class _FileOperations:
    def __init__(self, manager) -> None:
        self._manager = manager

    def encrypt(
        self,
        path: str | os.PathLike[str],
        *,
        new_extension: str | None = None,
        encrypt_name: bool = False,
    ) -> None:
        self._manager._require_open()
        source_path = _path(path)
        source_info = _check_source(source_path, directory=False)
        profile = _profile()
        limit = _component_limit(source_path.parent)
        original_name = source_path.name
        base, original_extension = split_extension(original_name)

        if not isinstance(encrypt_name, bool):
            raise TypeError("encrypt_name must be bool")
        if encrypt_name:
            if new_extension is not None:
                raise ValueError("new_extension cannot be used when encrypt_name=True")
            output_extension = None
            destination_name = encrypt_name_fn(
                original_name, self._manager._names_primitive, profile, limit
            )
        else:
            output_extension = ".fscrypt" if new_extension is None else new_extension
            # build_header performs strict structural validation; validate the
            # complete destination component against the active filesystem too.
            destination_name = base + output_extension
            _validate_component(destination_name, source_path.parent)

        if encrypt_name:
            _validate_component(destination_name, source_path.parent)
        header = build_header(
            original_extension=None if encrypt_name else original_extension,
            output_extension=output_extension,
            encrypted_name=encrypt_name,
        )
        destination = source_path.with_name(destination_name)
        if destination == source_path:
            raise ValueError("encrypted destination must differ from the source path")

        fd, temporary = _temporary_file(source_path.parent)
        published = False
        try:
            with source_path.open("rb") as original:
                current = os.fstat(original.fileno())
                if (current.st_dev, current.st_ino) != (source_info.st_dev, source_info.st_ino):
                    raise InvalidPathError("source changed while the operation was starting")
                with os.fdopen(fd, "wb") as output:
                    output.write(header)
                    _copy_encrypt(
                        self._manager._content_primitive,
                        original,
                        output,
                        header,
                    )
                    _sync_close(output)
            _publish_noreplace(temporary, destination)
            published = True
            try:
                latest = source_path.lstat()
                if (latest.st_dev, latest.st_ino) != (source_info.st_dev, source_info.st_ino):
                    raise AtomicOperationError("source changed before removal; both files were preserved")
                source_path.unlink()
            except Exception as exc:
                if isinstance(exc, AtomicOperationError):
                    raise
                raise AtomicOperationError("encrypted output was published but source removal failed") from exc
        finally:
            if not published:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def decrypt(self, path: str | os.PathLike[str]) -> None:
        self._manager._require_open()
        source_path = _path(path)
        source_info = _check_source(source_path, directory=False)
        profile = _profile()
        limit = _component_limit(source_path.parent)
        fd, temporary = _temporary_file(source_path.parent)
        published = False
        try:
            with source_path.open("rb") as encrypted:
                current = os.fstat(encrypted.fileno())
                if (current.st_dev, current.st_ino) != (source_info.st_dev, source_info.st_ino):
                    raise InvalidPathError("source changed while the operation was starting")
                header = _read_header(encrypted)
                if header.encrypted_name:
                    destination_name = decrypt_name(
                        source_path.name,
                        self._manager._names_primitive,
                        profile=profile,
                        max_component_bytes=limit,
                    )
                else:
                    output_extension = header.output_extension or ""
                    if output_extension and not source_path.name.endswith(output_extension):
                        raise FormatError("current filename does not match authenticated output extension")
                    base = source_path.name[:-len(output_extension)] if output_extension else source_path.name
                    destination_name = base + (header.original_extension or "")
                    _validate_component(destination_name, source_path.parent)

                destination = source_path.with_name(destination_name)
                if destination == source_path:
                    raise ValueError("decrypted destination must differ from the source path")
                with os.fdopen(fd, "wb") as output:
                    _copy_decrypt(
                        self._manager._content_primitive,
                        encrypted,
                        output,
                        header.raw,
                    )
                    _sync_close(output)
            _publish_noreplace(temporary, destination)
            published = True
            try:
                latest = source_path.lstat()
                if (latest.st_dev, latest.st_ino) != (source_info.st_dev, source_info.st_ino):
                    raise AtomicOperationError("source changed before removal; both files were preserved")
                source_path.unlink()
            except Exception as exc:
                if isinstance(exc, AtomicOperationError):
                    raise
                raise AtomicOperationError("plaintext was published but ciphertext removal failed") from exc
        finally:
            if not published:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


class _DirectoryOperations:
    def __init__(self, manager) -> None:
        self._manager = manager

    def encrypt(self, path: str | os.PathLike[str]) -> None:
        self._manager._require_open()
        source = _path(path)
        _check_source(source, directory=True)
        destination_name = encrypt_name_fn(
            source.name,
            self._manager._names_primitive,
            _profile(),
            _component_limit(source.parent),
        )
        _validate_component(destination_name, source.parent)
        _publish_noreplace(source, source.with_name(destination_name))

    def decrypt(self, path: str | os.PathLike[str]) -> None:
        self._manager._require_open()
        source = _path(path)
        _check_source(source, directory=True)
        destination_name = decrypt_name(
            source.name,
            self._manager._names_primitive,
            profile=_profile(),
            max_component_bytes=_component_limit(source.parent),
        )
        _validate_component(destination_name, source.parent)
        _publish_noreplace(source, source.with_name(destination_name))


def encrypt_name_fn(name: str, primitive, profile: NameProfile, limit: int) -> str:
    return encrypt_name(
        name,
        primitive,
        profile=profile,
        max_component_bytes=limit,
    )
