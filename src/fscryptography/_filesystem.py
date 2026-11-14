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
from ._journal import Transaction
from ._directory import DirectoryAnchor, _renameat2

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

    def readable(self):
        return self._stream.readable()

    def writable(self):
        return self._stream.writable()

    def seekable(self):
        return self._stream.seekable()

    @property
    def closed(self):
        return self._stream.closed

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
    # Transaction results live in a private sibling directory on the same filesystem.
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
        if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}:
            raise AtomicOperationError(
                f"Linux no-replace publication is unsupported: {os.strerror(error)}"
            ) from OSError(error, os.strerror(error))
        raise OSError(error, os.strerror(error), str(destination))

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
    if not directory and info.st_nlink != 1:
        raise UnsupportedResourceError(
            "files with multiple hard links are not supported; other links would retain the original content"
        )
    return info


def _open_source(path: Path, expected: os.stat_result) -> BinaryIO:
    """Open the previously inspected regular file without following symlinks.

    O_NOFOLLOW closes the lstat/open symlink substitution window on Linux.
    The descriptor identity is checked again after open on every platform.
    The returned stream owns the descriptor.
    """
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise UnsupportedResourceError("resource is not a regular file")
        if current.st_nlink != 1:
            raise UnsupportedResourceError(
                "files with multiple hard links are not supported; other links would retain the original content"
            )
        if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
            raise InvalidPathError("source changed while the operation was starting")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise




def _check_source_at(anchor: DirectoryAnchor, name: str, *, directory: bool) -> os.stat_result:
    info = anchor.stat(name)
    if stat.S_ISLNK(info.st_mode):
        raise UnsupportedResourceError("symbolic links are not supported")
    if directory and not stat.S_ISDIR(info.st_mode):
        raise UnsupportedResourceError("resource is not a directory")
    if not directory and not stat.S_ISREG(info.st_mode):
        raise UnsupportedResourceError("resource is not a regular file")
    if not directory and info.st_nlink != 1:
        raise UnsupportedResourceError(
            "files with multiple hard links are not supported; other links would retain the original content"
        )
    return info


def _open_source_at(anchor: DirectoryAnchor, name: str, expected: os.stat_result) -> BinaryIO:
    descriptor = anchor.open(name, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise UnsupportedResourceError("resource is not a regular file")
        if current.st_nlink != 1:
            raise UnsupportedResourceError(
                "files with multiple hard links are not supported; other links would retain the original content"
            )
        if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
            raise InvalidPathError("source changed while the operation was starting")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _rename_directory_checked(
    anchor: DirectoryAnchor,
    source_name: str,
    destination_name: str,
    expected: os.stat_result,
) -> None:
    """Rename a directory without replacement and verify the moved identity."""
    anchor.rename_noreplace(source_name, anchor.fd, destination_name)
    try:
        moved = anchor.stat(destination_name)
        if not stat.S_ISDIR(moved.st_mode) or (moved.st_dev, moved.st_ino) != (expected.st_dev, expected.st_ino):
            raise InvalidPathError("directory identity changed before rename")
        anchor.sync()
    except BaseException as exc:
        try:
            anchor.rename_noreplace(destination_name, anchor.fd, source_name)
            anchor.sync()
        except BaseException as restore_error:
            raise AtomicOperationError(
                "directory identity changed during rename; the moved entry could not be restored safely"
            ) from restore_error
        if isinstance(exc, InvalidPathError):
            raise
        raise AtomicOperationError("directory rename failed verification; original entry was restored") from exc

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


def _assert_source_unchanged(stream: BinaryIO, expected: os.stat_result) -> None:
    """Reject ordinary in-place source mutations observed during streaming.

    This detects identity, size, mtime, and ctime changes. It is not a defense
    against a hostile writer able to manipulate filesystem metadata or race
    within the filesystem timestamp granularity.
    """
    current = os.fstat(stream.fileno())
    identity_before = (expected.st_dev, expected.st_ino)
    identity_after = (current.st_dev, current.st_ino)
    metadata_before = (
        expected.st_size,
        expected.st_nlink,
        getattr(expected, "st_mtime_ns", int(expected.st_mtime * 1_000_000_000)),
        getattr(expected, "st_ctime_ns", int(expected.st_ctime * 1_000_000_000)),
    )
    metadata_after = (
        current.st_size,
        current.st_nlink,
        getattr(current, "st_mtime_ns", int(current.st_mtime * 1_000_000_000)),
        getattr(current, "st_ctime_ns", int(current.st_ctime * 1_000_000_000)),
    )
    if identity_before != identity_after or metadata_before != metadata_after:
        raise AtomicOperationError(
            "source content or identity changed during the operation; source was preserved"
        )


def _copy_encrypt(primitive, source: BinaryIO, destination: BinaryIO, aad: bytes) -> None:
    try:
        with primitive.new_encrypting_stream(_NonClosing(destination), aad) as encrypted:
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                encrypted.write(chunk)
    except OSError:
        raise
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
    except OSError:
        raise
    except Exception as exc:
        raise AuthenticationError("file content authentication failed") from exc


def _temporary_file(parent: Path) -> tuple[int, Path]:
    fd, name = tempfile.mkstemp(prefix=".fscryptography-", dir=parent)
    return fd, Path(name)


def _sync_close(stream: BinaryIO) -> None:
    stream.flush()
    os.fsync(stream.fileno())
    stream.close()


def _sync_parent_directory(parent: Path) -> None:
    """Persist namespace changes where directory fsync is supported.

    Windows currently relies on the platform's rename semantics and does not
    claim crash-durable directory-entry updates through this helper.
    """
    if os.name == "nt":
        return
    if not sys.platform.startswith("linux"):
        raise AtomicOperationError("directory synchronization is unsupported on this platform")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(parent, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise AtomicOperationError(
            "filesystem namespace update could not be synchronized"
        ) from exc




def _windows_mark_handle_for_deletion(handle: int) -> None:
    """Request deletion of the object referenced by an already verified handle."""
    import ctypes
    from ctypes import wintypes

    class FILE_DISPOSITION_INFO(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD,
    )
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    disposition = FILE_DISPOSITION_INFO(True)
    if not kernel32.SetFileInformationByHandle(
        handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _windows_delete_file_by_identity(path: Path, expected: os.stat_result) -> None:
    """Delete the exact verified Windows file object through its open handle.

    The pathname is used only to acquire a handle. Identity and file type are
    checked on that handle, and deletion is requested on the handle itself, so
    replacing the directory entry after CreateFileW cannot redirect deletion.
    """
    if os.name != "nt":
        raise RuntimeError("handle-based Windows deletion is only available on Windows")

    import ctypes
    import msvcrt
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", FILETIME),
            ("ftLastAccessTime", FILETIME),
            ("ftLastWriteTime", FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    class FILE_DISPOSITION_INFO(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
    )
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD,
    )
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    # DELETE | FILE_READ_ATTRIBUTES; share read/write/delete; OPEN_EXISTING;
    # OPEN_REPARSE_POINT prevents following a substituted reparse point.
    handle = kernel32.CreateFileW(
        str(path), 0x00010000 | 0x00000080, 0x00000001 | 0x00000002 | 0x00000004,
        None, 3, 0x00200000, None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    descriptor = None
    try:
        information = BY_HANDLE_FILE_INFORMATION()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(information)):
            raise ctypes.WinError(ctypes.get_last_error())
        if information.dwFileAttributes & (0x00000010 | 0x00000400):
            raise AtomicOperationError("quarantined source is a directory or reparse point")

        descriptor = msvcrt.open_osfhandle(
            int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        handle = None  # descriptor now owns the native handle
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode) or (
            current.st_dev, current.st_ino
        ) != (expected.st_dev, expected.st_ino):
            raise AtomicOperationError(
                "quarantined source identity changed; no file was deleted"
            )

        native_handle = msvcrt.get_osfhandle(descriptor)
        _windows_mark_handle_for_deletion(native_handle)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        elif handle not in (None, invalid_handle):
            kernel32.CloseHandle(handle)


def _retire_source(
    source_path: Path,
    transaction: Transaction,
    expected: os.stat_result,
    anchor: DirectoryAnchor | None,
    *,
    output_kind: str,
) -> None:
    """Move the expected source into private transaction storage before unlinking.

    The quarantine entry is deliberately inside the journaled transaction
    directory, so an interrupted retirement remains visible to recovery
    inspection. The identity check is performed after the atomic rename.
    """
    if anchor is None:
        # Windows has no Python-level unlink-if-this-file-identity primitive.
        # First move the entry into the journaled transaction directory. If a
        # competing process substituted it before the rename, the post-rename
        # identity check detects that and restores the entry without deleting it.
        retained = transaction.retained_path
        try:
            os.rename(source_path, retained)  # Windows rename does not replace an existing target.
        except Exception as exc:
            raise AtomicOperationError(
                f"{output_kind} was published but the source could not be quarantined safely"
            ) from exc

        try:
            moved = retained.lstat()
            if (
                not stat.S_ISREG(moved.st_mode)
                or moved.st_nlink != 1
                or (moved.st_dev, moved.st_ino) != (expected.st_dev, expected.st_ino)
            ):
                try:
                    os.rename(retained, source_path)  # Fails rather than replacing a new source entry.
                except Exception as restore_error:
                    raise AtomicOperationError(
                        "source identity changed; the unexpected entry remains in transaction storage "
                        "for explicit recovery inspection"
                    ) from restore_error
                raise AtomicOperationError(
                    "source identity changed during quarantine; the unexpected entry was restored"
                )

            transaction.set_state("source_retained")
            _windows_delete_file_by_identity(retained, expected)
            transaction.set_state("source_removed")
            return
        except AtomicOperationError:
            raise
        except Exception as exc:
            raise AtomicOperationError(
                "published output remains available; source retirement is incomplete and requires inspection"
            ) from exc

    try:
        if transaction.directory_fd is None:
            raise RuntimeError("anchored source retirement requires a transaction directory descriptor")
        anchor.rename_noreplace(source_path.name, transaction.directory_fd, "source")
    except Exception as exc:
        raise AtomicOperationError(
            f"{output_kind} was published but the source could not be retained safely"
        ) from exc

    try:
        current = os.stat("source", dir_fd=transaction.directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            try:
                _renameat2(transaction.directory_fd, "source", anchor.fd, source_path.name)
                anchor.sync()
                os.fsync(transaction.directory_fd)
            except Exception as restore_error:
                raise AtomicOperationError(
                    "source identity changed; the unexpected entry remains in transaction storage "
                    "for explicit recovery inspection"
                ) from restore_error
            raise AtomicOperationError(
                "source identity changed before retirement; the unexpected source entry was restored"
            )

        # Persist both sides of the cross-directory rename before recording the
        # retained state. A crash from this point is inspectable via txn/source.
        anchor.sync()
        os.fsync(transaction.directory_fd)
        transaction.set_state("source_retained")

        transaction.unlink_retained()
        try:
            os.fsync(transaction.directory_fd)
        except OSError as exc:
            raise AtomicOperationError(
                "source was removed, but transaction storage could not be synchronized"
            ) from exc
        transaction.set_state("source_removed")
    except AtomicOperationError:
        raise
    except Exception as exc:
        raise AtomicOperationError(
            "published output remains available; source retirement is incomplete and requires inspection"
        ) from exc


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
        anchor = DirectoryAnchor(source_path.parent) if sys.platform.startswith("linux") else None
        try:
            source_info = (_check_source_at(anchor, source_path.name, directory=False) if anchor is not None
                           else _check_source(source_path, directory=False))
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

            transaction = Transaction.begin(
                source_path.parent, "file_encrypt", source_path.name, destination.name, source_info,
                parent_fd=anchor.fd if anchor is not None else None,
            )

        except BaseException:
            if anchor is not None:
                anchor.close()
            raise
        temporary = transaction.result_path if anchor is None else None
        output = None
        published = False
        try:
            output = os.fdopen(transaction.open_result(), "wb")
            with (_open_source_at(anchor, source_path.name, source_info) if anchor is not None else _open_source(source_path, source_info)) as original:
                opened_info = os.fstat(original.fileno())
                output.write(header)
                _copy_encrypt(
                    self._manager._content_primitive,
                    original,
                    output,
                    header,
                )
                _assert_source_unchanged(original, opened_info)
                _sync_close(output)
            transaction.set_result_ready(transaction.stat_result())
            if anchor is not None:
                transaction.rename_result_to(anchor.fd, destination.name)
                anchor.sync()
            else:
                _publish_noreplace(temporary, destination)
                _sync_parent_directory(source_path.parent)
            published = True
            transaction.set_state("published")
            _retire_source(
                source_path,
                transaction,
                source_info,
                anchor,
                output_kind="encrypted output",
            )
            transaction.set_state("complete")
            transaction.finish()
        finally:
            if output is not None and not output.closed:
                output.close()
            transaction.close()
            if anchor is not None:
                anchor.close()
            # An unpublished result is retained for explicit inspection.

    def decrypt(self, path: str | os.PathLike[str]) -> None:
        self._manager._require_open()
        source_path = _path(path)
        anchor = DirectoryAnchor(source_path.parent) if sys.platform.startswith("linux") else None
        try:
            source_info = (_check_source_at(anchor, source_path.name, directory=False) if anchor is not None
                           else _check_source(source_path, directory=False))
            profile = _profile()
            limit = _component_limit(source_path.parent)

        except BaseException:
            if anchor is not None:
                anchor.close()
            raise
        transaction = None
        output = None
        published = False
        try:
            with (_open_source_at(anchor, source_path.name, source_info) if anchor is not None else _open_source(source_path, source_info)) as encrypted:
                opened_info = os.fstat(encrypted.fileno())
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
                transaction = Transaction.begin(
                    source_path.parent, "file_decrypt", source_path.name, destination.name, source_info,
                    parent_fd=anchor.fd if anchor is not None else None,
                )
                fd = (os.open("result", os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=transaction.directory_fd)
                      if transaction.directory_fd is not None else
                      os.open(transaction.result_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600))
                output = os.fdopen(fd, "wb")
                _copy_decrypt(
                    self._manager._content_primitive,
                    encrypted,
                    output,
                    header.raw,
                )
                _assert_source_unchanged(encrypted, opened_info)
                _sync_close(output)
            transaction.set_result_ready(transaction.stat_result())
            if anchor is not None:
                transaction.rename_result_to(anchor.fd, destination.name)
                anchor.sync()
                os.fsync(transaction.directory_fd)
            else:
                _publish_noreplace(transaction.result_path, destination)
                _sync_parent_directory(source_path.parent)
                _sync_parent_directory(transaction.directory)
            published = True
            transaction.set_state("published")
            _retire_source(
                source_path,
                transaction,
                source_info,
                anchor,
                output_kind="plaintext",
            )
            transaction.set_state("complete")
            transaction.finish()
        finally:
            if output is not None and not output.closed:
                output.close()
            if transaction is not None:
                transaction.close()
            if anchor is not None:
                anchor.close()
            # Unpublished output is retained for explicit inspection.


class _DirectoryOperations:
    def __init__(self, manager) -> None:
        self._manager = manager

    def encrypt(self, path: str | os.PathLike[str]) -> None:
        self._manager._require_open()
        source = _path(path)
        anchor = DirectoryAnchor(source.parent) if sys.platform.startswith("linux") else None
        transaction = None
        try:
            source_info = (_check_source_at(anchor, source.name, directory=True) if anchor is not None
                           else _check_source(source, directory=True))
            destination_name = encrypt_name_fn(
                source.name,
                self._manager._names_primitive,
                _profile(),
                _component_limit(source.parent),
            )
            _validate_component(destination_name, source.parent)
            destination = source.with_name(destination_name)
            transaction = Transaction.begin(
                source.parent, "dir_encrypt", source.name, destination.name, source_info,
                parent_fd=anchor.fd if anchor is not None else None,
            )
            if anchor is not None:
                _rename_directory_checked(anchor, source.name, destination.name, source_info)
            else:
                _publish_noreplace(source, destination)
                _sync_parent_directory(source.parent)
            transaction.set_state("published")
            transaction.set_state("source_removed")
            transaction.set_state("complete")
            transaction.finish()
        finally:
            if transaction is not None:
                transaction.close()
            if anchor is not None:
                anchor.close()

    def decrypt(self, path: str | os.PathLike[str]) -> None:
        self._manager._require_open()
        source = _path(path)
        anchor = DirectoryAnchor(source.parent) if sys.platform.startswith("linux") else None
        transaction = None
        try:
            source_info = (_check_source_at(anchor, source.name, directory=True) if anchor is not None
                           else _check_source(source, directory=True))
            destination_name = decrypt_name(
                source.name,
                self._manager._names_primitive,
                profile=_profile(),
                max_component_bytes=_component_limit(source.parent),
            )
            _validate_component(destination_name, source.parent)
            destination = source.with_name(destination_name)
            transaction = Transaction.begin(
                source.parent, "dir_decrypt", source.name, destination.name, source_info,
                parent_fd=anchor.fd if anchor is not None else None,
            )
            if anchor is not None:
                anchor.rename_noreplace(source.name, anchor.fd, destination.name)
                anchor.sync()
            else:
                _publish_noreplace(source, destination)
                _sync_parent_directory(source.parent)
            transaction.set_state("published")
            transaction.set_state("source_removed")
            transaction.set_state("complete")
            transaction.finish()
        finally:
            if transaction is not None:
                transaction.close()
            if anchor is not None:
                anchor.close()


def encrypt_name_fn(name: str, primitive, profile: NameProfile, limit: int) -> str:
    return encrypt_name(
        name,
        primitive,
        profile=profile,
        max_component_bytes=limit,
    )
