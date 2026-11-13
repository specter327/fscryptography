# Filesystem hardening: source identity and symlink-safe opening

## Scope of this change

This change hardens the source-open boundary for file encryption and decryption.

Previously, operations performed an initial `lstat()` and then used `Path.open()`. The descriptor identity was checked after opening, which detected many substitutions, but the open itself could follow a symlink introduced between those operations.

The new `_open_source()` helper:

- opens the already-inspected path with `O_NOFOLLOW` where the platform provides it;
- uses binary mode on Windows;
- verifies the opened descriptor is still a regular file;
- compares the descriptor's device/inode identity with the initial `lstat()`;
- closes the descriptor on every failed validation path.

Both file encryption and decryption use this helper. A regression test replaces the source pathname with a symlink after capturing the original identity and verifies that the symlink target is not opened.

## Explicit limitations

This is an incremental hardening step, not a complete TOCTOU solution.

In particular, source removal still uses a pathname-based identity check followed by `unlink()`. A hostile concurrent process may replace the directory entry between those operations. Parent-directory replacement and fully descriptor-relative publication/removal also remain unresolved.

Do not interpret this change as protection against a process with concurrent write access to the parent directory. The next implementation step must address identity-safe source retirement and parent-directory anchoring, with platform-specific guarantees and race-injection tests.

## Validation

The Linux regression test exercises the `O_NOFOLLOW` behavior. Windows skips that specific symlink-creation test because creating symlinks may require elevated privileges; descriptor identity validation remains active on Windows.
