# Open design decisions

This register separates requirements already stated by the project from details that must be decided before implementation.

## Fixed requirements

- One resource per operation; no batch or recursive behavior.
- Files: encrypt/decrypt content; preserve original name and extension; append/remove only the final `.fscrypt` suffix.
- Directories: append/remove only the directory's own `.fscrypt` suffix; never traverse or alter contents.
- No directory integrity verification method.
- Symmetric cryptography only.
- No project-authored cryptographic primitives.
- Cold whole-file operations only; no public live read/write/stream interface.
- Sequential bounded-memory processing; proposed default block size 1 MiB.
- Self-contained encrypted file and key formats.
- Base64 key serialization.
- Authenticated integrity and explicit corruption/tampering detection.
- Transaction-oriented publication of completed outputs.
- GNU/Linux, Windows, macOS, Termux, and Android are target environments.

## Decisions required before implementation

### A. Cryptographic protocol

- Adopt an existing authenticated streaming/file-encryption construction or define a reviewed custom container?
- Exact container magic, versioning, field encodings, and canonical parser rules.
- Exact AES-GCM nonce allocation strategy across resources and processes.
- Per-resource subkey derivation strategy, if used.
- AAD field layout and authentication coverage.
- Final authenticated record and truncation-detection design.
- GCM tag length and supported profile identifiers.
- Maximum block count, file size, and aggregate data per key.
- Retry and interrupted-operation nonce behavior.

### B. Password derivation

- Selected password KDF and supported implementation on every target.
- Exact KDF parameters and profile version.
- Password encoding and Unicode normalization.
- Stable salt/domain separation strategy compatible with deterministic derivation.
- Key representation fields required to preserve derivation compatibility.

### C. Block configuration

- Minimum and maximum accepted block sizes.
- Whether block size is selected per operation or fixed in a key/container profile.
- Compatibility rules when decrypting a file created with a different supported block size.

### D. Filesystem contract

- Exact symlink/reparse-point policy on each platform.
- Hard-link behavior.
- Special-file rejection rules.
- Destination collision and overwrite policy.
- Metadata preservation requirements.
- Concurrent source modification detection.
- Temporary-file naming, permissions, cleanup, and recovery.
- Exact atomicity/durability guarantees per platform.

### E. Public API

- Concrete key object and Base64 serialization interface.
- Return values for mutating operations.
- Exception hierarchy and error taxonomy.
- Exact semantics of `file.is_encrypted()` versus `file.verify_integrity()`.
- Whether format recognition performs bounded structural parsing or full validation.
- Manager/key lifecycle and secret-memory handling expectations.

### F. Compatibility and verification

- Supported Python versions and packaging targets.
- Cryptographic dependency availability and maintenance status on each platform.
- Cross-platform interoperability test matrix.
- Golden test vectors for key and file formats.
- Tampering, truncation, reordering, wrong-key, and malformed-input tests.
- Filesystem interruption and recovery tests.
- Independent cryptographic review criteria.

## Implementation gate

Implementation must not begin until the security-critical items in A and B, the observable behavior in D and E, and the interoperability strategy in F have an approved specification. A proposed algorithm list is not a substitute for a complete protocol.
