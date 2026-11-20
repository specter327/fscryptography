# Open design decisions

This register separates fixed project requirements from details that must be decided before implementation.

## Fixed requirements
- Exactly one resource per operation; no batch or recursive behavior.
- Files: encrypt/decrypt content; preserve the original name and extension; append/remove only the final .fscrypt suffix.
- Directories: append/remove only the directory's own .fscrypt suffix; never traverse or alter contents. This is a rename convention, not cryptographic name encryption.
- No directory integrity verification method.
- Symmetric cryptography only.
- No project-authored cryptographic primitives or improvised segmented-AEAD construction.
- Cold whole-file operations only; no public live read/write/stream interface.
- Sequential bounded-memory processing; proposed default I/O buffer size 1 MiB.
- Self-contained encrypted-file and key representations.
- Base64 key serialization.
- Authenticated integrity and explicit corruption/tampering detection.
- Transaction-oriented publication of completed outputs.
- GNU/Linux, Windows, macOS, Termux, and Android are target environments.
- Names remain visible; filename confidentiality is out of scope.
- Google Tink is rejected and must not be used.

## Decisions required before implementation

### A. AES-GCM backend and file format
- **Primary candidate:** PyCA `cryptography`, using one low-level AES-256-GCM cipher context per complete file and incremental I/O through repeated `update()` calls.
- The official Termux package repository maintains a native `python-cryptography` build recipe. This is promising packaging evidence, not proof of runtime compatibility; the exact package must be installed and tested on the target device.
- The 1 MiB setting is an I/O buffer size, not an independently authenticated cryptographic segment.
- One GCM invocation is limited to (2^{39}-256) plaintext bits (approximately 64 GiB minus 32 bytes). Decide whether this maximum file size is acceptable.
- Do not bypass the GCM limit with an improvised multi-invocation nonce/counter/segment protocol.
- Every GCM invocation needs a unique nonce for its AES key. Evaluate a reviewed per-file key-separation design using a standard KDF and fresh per-file randomness; do not implement ad hoc nonce allocation.
- The complete decryption output must remain private staging data until GCM finalization verifies the full tag.
- Define the outer container header, version, authenticated metadata, nonce, salt/key-derivation metadata, ciphertext, tag placement, parser strictness, and trailing-data behavior.
- Confirm exact maximum file size, tag size, nonce size, and cryptographic usage bounds.
- **Alternative only with explicit algorithm approval:** libsodium SecretStream (XChaCha20-Poly1305). It does not satisfy the current AES-256-GCM requirement.

See [Cross-platform cryptographic backend feasibility review](../research/platform-dependency-feasibility.md).

### B. Password derivation
- Selected Argon2id implementation and supported runtime on every target, especially Termux.
- Exact KDF parameters and profile version.
- Password encoding and Unicode normalization.
- Stable salt/domain separation compatible with deterministic derivation.
- Key representation fields required to preserve derivation compatibility.
- Benchmark memory and latency on low-end Android hardware.

The native Argon2 package in Termux does not by itself prove that a supported Python binding is available. Test argon2-cffi source build/runtime or another maintained binding; do not write a custom Argon2 implementation.

### C. Block and file-size configuration
- Minimum and maximum I/O buffer sizes.
- Whether buffer size is configurable per operation.
- Explicit maximum file size compatible with one GCM invocation.
- Compatibility rules for future container versions and cryptographic profiles.
- Do not call the I/O buffer a cryptographic segment size.

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
- Tampering, truncation, wrong-key, missing-tag, and malformed-input tests.
- Filesystem interruption and recovery tests.
- Independent cryptographic review criteria.

## Implementation gate
Implementation must not begin until security-critical items in A and B, observable behavior in D and E, and interoperability strategy in F have an approved specification. The GCM file-size limit and key/nonce strategy are mandatory decisions, not implementation details.
