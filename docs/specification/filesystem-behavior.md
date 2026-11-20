# Filesystem and transaction behavior

**Status:** requirements baseline; platform-specific implementation rules remain to be validated.

## 1. Scope of filesystem access

Every operation targets exactly one real filesystem resource.

- File encryption/decryption operates on one regular file.
- Directory encryption/decryption renames one directory entry only.
- No recursive traversal, child enumeration, or implicit batch behavior is permitted.
- Directory contents must remain untouched.

The library is not intended to operate on virtual resources, archive members, object-store keys, or arbitrary streams.

## 2. File encryption/decryption lifecycle

The implementation must not expose incomplete output as a completed resource.

Required lifecycle:

1. Validate the source resource and derive the exact destination name.
2. Validate destination availability, path constraints, and supported resource type.
3. Create a temporary output on the destination filesystem where feasible.
4. Process the source sequentially using bounded memory and the configured block size.
5. Authenticate all required records, including the finalization record.
6. Flush/synchronize output as required by the platform and implementation contract.
7. Confirm the output is complete and ready for publication.
8. Publish the destination using the strongest supported atomic filesystem operation.
9. Remove the original only after publication has succeeded and the operation's consistency requirements are met.
10. Clean up temporary artifacts on failure where safe.

Decryption must not publish plaintext until every encrypted block and the authenticated end-of-file/finalization data have been verified.

## 3. Transactional guarantees and limitations

The target guarantee is that interrupted or failed processing does not replace the original with a partial result.

The specification must distinguish:
- Atomic visibility of a rename.
- Durability after power loss or kernel/device failure.
- Preservation of the original across all failure points.
- Recovery from abandoned temporary files.

These are not equivalent guarantees. Atomic rename alone does not guarantee durability or a fully transactional operation across every filesystem and operating system. The implementation must document the guarantees actually validated on each platform.

## 4. Destination and naming validation

- Existing destinations must not be overwritten silently.
- The library must detect suffix misuse and destination collisions before processing.
- The added suffix must be checked against platform filename-length and path constraints.
- Decryption removes exactly one final `.fscrypt` suffix.
- A failed destination publication must leave the source intact.
- No fallback may silently choose a different output name.

## 5. Resource types and links

The default policy should not follow symbolic links. Exact behavior for symbolic links, junctions/reparse points, hard links, and special files must be defined consistently across platforms before implementation.

Directory renaming must not resolve into a recursive operation. It changes only the directory entry selected by the caller.

## 6. Concurrent changes

The implementation must define how it detects or handles a source modified while encryption/decryption is in progress. It must not silently claim a coherent result if the input changed during processing.

## 7. Metadata

The implementation should preserve relevant filesystem metadata where practical and documented. Metadata preservation must not weaken transaction safety or cause platform-dependent behavior to be misrepresented as portable.

## 8. Platform validation

Filesystem semantics differ across GNU/Linux, Windows, macOS, Termux, and Android. Tests must cover destination collisions, rename behavior, open-handle restrictions, permissions, filename limits, symlink policies, temporary-file placement, and interruption/recovery behavior on each supported target.
