# Filesystem hardening: source identity and retirement

## Symlink-safe source opening

File encryption and decryption open the inspected source with `O_NOFOLLOW`
where available, then verify through `fstat()` that the descriptor is a regular
file and has the device/inode identity captured by the initial `lstat()`.
This closes the lstat/open symlink substitution window on Linux. Windows keeps
the descriptor identity check, although its open primitive does not provide the
same `O_NOFOLLOW` guarantee.

## Journaled source retirement on GNU/Linux

After the encrypted or decrypted result has been published, file operations no
longer perform a pathname identity check followed by unlinking the original
entry. Instead they:

1. Atomically rename the source into the transaction directory as `source`,
   using the no-replace rename primitive.
2. Inspect the moved entry with `lstat()` and compare its device/inode identity
   with the identity recorded before processing.
3. If the identity differs, attempt a no-replace restoration to the original
   basename. The unexpected entry is never unlinked.
4. If the identity matches, persist the `source_retained` journal state, unlink
   the retained entry, synchronize the transaction directory, and persist
   `source_removed`.

The transaction directory is created with mode 0700 on GNU/Linux. A crash after
the rename but before unlink leaves the original object at
`.fscryptography-txn-<id>/source`. Read-only recovery inspection recognizes
that exact identity and reports `source_retained`; it does not delete or restore
the object. A mismatched retained entry is reported as `ambiguous`.

This protocol narrows the check-then-unlink window for processes that cannot
access the private transaction directory. It is not a defense against a
malicious process running under the same UID, which can access that UID's
private files and race their names.

## Windows limitation

The transaction directory currently inherits its parent directory's Windows
ACL. The implementation therefore does not use it as a protected quarantine.
Windows retains the previous pathname identity-check/removal sequence; the
check-to-unlink race remains unresolved there. A future Windows-specific change
must establish and verify a restrictive ACL or use handle-based file operations
before claiming equivalent source-retirement guarantees.

## Remaining limitations

- Parent-directory replacement and fully descriptor-relative publication,
  transaction creation, and source retirement remain unresolved.
- The GNU/Linux quarantine uses pathname-based rename/unlink operations; it
  relies on the transaction directory's 0700 permissions against other UIDs.
- Same-UID hostile concurrency is not prevented.
- Windows source retirement remains vulnerable to a check-then-unlink race.
- Directory rename operations are atomic no-replace renames, but do not use the
  file-source quarantine protocol.

Do not interpret these incremental changes as complete hostile-concurrency
protection. Recovery inspection remains read-only and no automatic destructive
recovery or transaction cleanup is performed.

## Validation

Regression tests cover Linux symlink substitution, source replacement before
quarantine, and interruption after a source has been retained. The Windows
matrix exercises the platform's existing file operations but skips tests that
require the GNU/Linux private-quarantine protocol.
