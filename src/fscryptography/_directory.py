"""Descriptor-relative directory operations for GNU/Linux filesystem safety."""

from __future__ import annotations

import ctypes
import errno
import os
import stat
import sys
from pathlib import Path

from .errors import AtomicOperationError, DestinationConflictError, InvalidPathError, UnsupportedResourceError

_RENAME_NOREPLACE = 1


def _renameat2(source_fd: int, source_name: str, destination_fd: int, destination_name: str) -> None:
    if not sys.platform.startswith("linux"):
        raise AtomicOperationError("descriptor-relative no-replace rename is only available on GNU/Linux")
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise AtomicOperationError("renameat2(RENAME_NOREPLACE) is unavailable") from exc
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_fd, os.fsencode(source_name),
        destination_fd, os.fsencode(destination_name),
        _RENAME_NOREPLACE,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise DestinationConflictError("destination already exists")
    if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}:
        raise AtomicOperationError(
            f"Linux no-replace rename is unsupported: {os.strerror(error)}"
        ) from OSError(error, os.strerror(error))
    raise OSError(error, os.strerror(error), destination_name)


class DirectoryAnchor:
    """Hold a verified directory descriptor and operate on direct children only."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        if not sys.platform.startswith("linux"):
            raise UnsupportedResourceError("directory descriptor anchoring is currently GNU/Linux-only")
        self.path = Path(os.path.abspath(os.fspath(path)))
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            self.fd = os.open(self.path, flags)
        except OSError as exc:
            raise InvalidPathError("parent directory could not be opened without following a symlink") from exc
        self.closed = False
        try:
            self.info = os.fstat(self.fd)
            if not stat.S_ISDIR(self.info.st_mode):
                raise InvalidPathError("parent is not a directory")
        except BaseException:
            os.close(self.fd)
            self.closed = True
            raise

    def stat(self, name: str) -> os.stat_result:
        return os.stat(name, dir_fd=self.fd, follow_symlinks=False)

    def open(self, name: str, flags: int, mode: int = 0o600) -> int:
        return os.open(name, flags | getattr(os, "O_NOFOLLOW", 0), mode, dir_fd=self.fd)

    def mkdir(self, name: str, mode: int = 0o700) -> None:
        os.mkdir(name, mode, dir_fd=self.fd)

    def unlink(self, name: str) -> None:
        os.unlink(name, dir_fd=self.fd)

    def rename_noreplace(self, source_name: str, destination_fd: int, destination_name: str) -> None:
        _renameat2(self.fd, source_name, destination_fd, destination_name)

    def sync(self) -> None:
        os.fsync(self.fd)

    def verify_path_still_names_anchor(self) -> None:
        """Reject a replaced parent pathname while retaining the original anchor."""
        current = os.stat(self.path, follow_symlinks=False)
        if stat.S_ISLNK(current.st_mode) or (current.st_dev, current.st_ino) != (self.info.st_dev, self.info.st_ino):
            raise InvalidPathError("parent directory was replaced during the operation")

    def close(self) -> None:
        if not self.closed:
            os.close(self.fd)
            self.closed = True

    def __enter__(self) -> "DirectoryAnchor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
