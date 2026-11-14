"""Ephemeral in-memory transaction state for filesystem operations.

No transaction metadata is written to disk. Result and source-staging entries
are ordinary temporary siblings and may remain after abrupt process/system
termination; they are not discoverable or recoverable by this library.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path


class Transaction:
    """Track one operation in memory and allocate collision-resistant siblings."""

    def __init__(self, parent: Path, operation: str, source_name: str,
                 destination_name: str, *, parent_fd: int | None = None):
        self.parent = parent
        self.operation = operation
        self.source_name = source_name
        self.destination_name = destination_name
        self.result_name = ".fscryptography-result-" + secrets.token_hex(16)
        self.retained_name = ".fscryptography-source-" + secrets.token_hex(16)
        self.result_path = parent / self.result_name
        self.retained_path = parent / self.retained_name
        self.directory = parent
        self.directory_fd = os.dup(parent_fd) if parent_fd is not None else None
        self.state = "prepared"
        self._result_created = False
        self._result_identity: tuple[int, int] | None = None
        self._closed = False

    @classmethod
    def begin(cls, parent: Path, operation: str, source_name: str,
              destination_name: str, *, parent_fd: int | None = None):
        if operation not in {"file_encrypt", "file_decrypt", "dir_encrypt", "dir_decrypt"}:
            raise ValueError("invalid transaction operation")
        if not source_name or not destination_name or source_name == destination_name:
            raise ValueError("invalid transaction resource names")
        return cls(parent, operation, source_name, destination_name, parent_fd=parent_fd)

    def open_result(self) -> int:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        if self.directory_fd is not None:
            fd = os.open(self.result_name, flags, 0o600, dir_fd=self.directory_fd)
        else:
            fd = os.open(self.result_path, flags, 0o600)
        try:
            info = os.fstat(fd)
            self._result_identity = (info.st_dev, info.st_ino)
            self._result_created = True
            return fd
        except BaseException:
            os.close(fd)
            raise

    def stat_result(self):
        if self.directory_fd is not None:
            return os.stat(self.result_name, dir_fd=self.directory_fd, follow_symlinks=False)
        return self.result_path.lstat()

    def mark_result_published(self) -> None:
        """Disable cleanup after the temporary entry has been renamed to its destination."""
        self._result_created = False
        self._result_identity = None

    def rename_result_to(self, parent_fd: int, destination_name: str) -> None:
        if self.directory_fd is None:
            raise RuntimeError("transaction is not descriptor-anchored")
        from ._directory import _renameat2
        _renameat2(self.directory_fd, self.result_name, parent_fd, destination_name)
        self.mark_result_published()

    def unlink_retained(self) -> None:
        if self.directory_fd is not None:
            os.unlink(self.retained_name, dir_fd=self.directory_fd)
        else:
            self.retained_path.unlink()

    def set_result_ready(self, result_info) -> None:
        self.state = "result_ready"

    def set_state(self, state: str) -> None:
        if state not in {"prepared", "result_ready", "published", "source_retained", "source_removed", "complete"}:
            raise ValueError("invalid transaction state")
        self.state = state

    def finish(self) -> None:
        if self.state != "complete":
            raise RuntimeError("transaction is not complete")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Best-effort cleanup: refuse to unlink an entry that already differs
        # from the object created by open_result(). The stat/unlink pair is
        # not atomic, so this does not protect against a concurrent same-dir actor.
        if self._result_created and self._result_identity is not None:
            try:
                if self.directory_fd is not None:
                    current = os.stat(
                        self.result_name,
                        dir_fd=self.directory_fd,
                        follow_symlinks=False,
                    )
                else:
                    current = self.result_path.lstat()
                if (current.st_dev, current.st_ino) == self._result_identity:
                    if self.directory_fd is not None:
                        os.unlink(self.result_name, dir_fd=self.directory_fd)
                    else:
                        self.result_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
        if self.directory_fd is not None:
            os.close(self.directory_fd)
            self.directory_fd = None
