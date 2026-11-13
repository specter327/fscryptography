# Filesystem hardening: identity, anchoring, and retirement

## Source opening

File encryption and decryption open the inspected source with `O_NOFOLLOW`
where available, then verify through `fstat()` that the descriptor is a regular
file and has the device/inode identity captured by the initial inspection.
GNU/Linux operations perform the lookup and open relative to an already-open
parent-directory descriptor. Windows retains pathname-based lookup plus
descriptor identity verification; it does not provide the same no-follow
or parent-handle anchoring guarantee here.

## GNU/Linux parent-directory anchoring

Each filesystem operation opens its parent directory with
`O_DIRECTORY | O_NOFOLLOW` and retains that descriptor for the operation.
Transaction directories are created relative to that descriptor. Source
lookups, source opens, result creation, result publication, source quarantine,
directory renames, journal replacement, and recovery inspection use
descriptor-relative operations.

The transaction directory is separately opened with `O_DIRECTORY | O_NOFOLLOW`.
Journal files and transaction entries are opened without following symlinks.
The implementation does not use `/proc/self/fd` path aliases for anchored
result or journal I/O.

If the parent directory is renamed or its original pathname is replaced after
the operation has opened it, the operation remains bound to the original
directory object. Its output and transaction evidence therefore follow that
original directory object, which may now be reachable under a different path.
The replacement directory at the old pathname is not used. Recovery inspection
must be run against the directory's current pathname.

This is an anchoring guarantee, not a guarantee that the original pathname
continues to identify the directory. It also does not prevent a process running
under the same UID from manipulating objects it can access inside a mode-0700
transaction directory.

## Journaled source retirement

After a file result is published, GNU/Linux file operations atomically rename
the source into the transaction directory as `source`, using a no-replace
rename with both directory descriptors. The moved entry is checked against
the recorded device/inode identity. If it differs, restoration is attempted
without replacement and the unexpected entry is not unlinked. If it matches,
the implementation persists `source_retained`, unlinks the retained entry
relative to the transaction descriptor, synchronizes the directory, and
persists `source_removed`.

A crash after quarantine but before removal leaves the entry in
`.fscryptography-txn-<id>/source`. Read-only inspection recognizes the retained
identity but never deletes or restores it. A mismatch is classified as
ambiguous.

## Recovery inspection

On GNU/Linux, inspection opens the requested parent once and enumerates it
through the directory descriptor. It opens each transaction directory with
`O_NOFOLLOW`, opens `journal.json` relative to that descriptor, verifies the
opened file identity and size, and inspects source, destination, result, and
quarantine entries using `stat(..., dir_fd=..., follow_symlinks=False)`.
Inspection is read-only. It does not follow transaction-directory or journal
symlinks and does not follow a replacement of the parent pathname after the
initial open.

## Windows limitations

Windows does not yet use equivalent directory-handle-relative operations.
Transaction directories inherit the parent ACL, so they are not treated as a
protected quarantine. Source retirement retains the pathname identity-check
and removal sequence; its check-to-unlink race remains unresolved. Namespace
durability across power loss is not promised by the directory-fsync protocol.

## Remaining security boundaries

- These changes do not eliminate all TOCTOU races or protect against hostile
  processes running as the same UID.
- Windows does not have the GNU/Linux parent-directory anchoring or quarantine
  guarantees in this implementation.
- Alternative and network filesystems have not been exhaustively validated;
  required no-replace rename and directory synchronization semantics may vary.
- Recovery remains read-only. There is no automatic destructive recovery or
  transaction cleanup policy.

The implementation must not be described as complete hostile-concurrency
protection.
