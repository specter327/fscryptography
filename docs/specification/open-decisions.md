# Open design decisions

This register separates fixed project requirements from details that must be decided before implementation.

## Fixed requirements
- Exactly one resource per operation; no batch or recursive behavior.
- Files: encrypt/decrypt content; preserve the original name and extension; append/remove only the final .fscrypt suffix.
- Directories: append/remove only the directory's own .fscrypt suffix; never traverse or alter contents. This is a rename convention, not cryptographic name encryption.
- No directory integrity verification method.
- Symmetric cryptography only.
- No project-authored cryptographic primitives.
- Cold whole-file operations only; no public live read/write/stream interface.
- Sequential bounded-memory processing; proposed default block size 1 MiB.
- Self-contained encrypted-file and key representations.
- Base64 key serialization.
- Authenticated integrity and explicit corruption/tampering detection.
- Transaction-oriented publication of completed outputs.
- GNU/Linux, Windows, macOS, Termux, and Android are target environments.
- Names remain visible; filename confidentiality is out of scope.

## Decisions required before implementation

### A. Cryptographic construction and file format
- **Preferred candidate:** Google Tink Streaming AEAD, AES-256-GCM-HKDF 1 MiB profile, subject to exact Python API and reproducible support across every target.
- **Alternative only with explicit algorithm approval:** libsodium secretstream (XChaCha20-Poly1305); it does not satisfy the current AES-256-GCM requirement.
- Do not implement a project-authored AES-GCM segment protocol as the default workaround.
- The suggested custom 96-bit-per-block nonce + counter + random resource identifier design is not approved. Nonce uniqueness across files, retries, processes, and restarts has not been established.
- Decide whether the selected construction already provides sufficient self-description or whether a minimal outer file identifier/version is required.
- Confirm exact profile identifiers, key size, framing, parser behavior, limits, and final-stream validation from the selected implementation/specification.
- Ensure the filesystem layer does not publish staged plaintext until the complete stream has been authenticated.

See [Streaming encryption construction review](../research/streaming-encryption-review.md).

### B. Password derivation
- Selected password KDF and supported implementation on every target.
- Exact KDF parameters and profile version.
- Password encoding and Unicode normalization.
- Stable salt/domain separation compatible with deterministic derivation.
- Key representation fields required to preserve derivation compatibility.

### C. Block configuration
- Minimum and maximum accepted block sizes.
- Whether the block size is configurable per operation or fixed by the selected file-format profile.
- Compatibility rules when decrypting a file created with a different supported profile.
- Clarify whether the public block-size option maps directly to the selected construction's segment size.

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
- Exact semantics of file.is_encrypted() versus file.verify_integrity().
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
Implementation must not begin until security-critical items in A and B, observable behavior in D and E, and interoperability strategy in F have an approved specification. A proposed algorithm list is not a complete protocol.
