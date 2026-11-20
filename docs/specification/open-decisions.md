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
- Sequential bounded-memory processing.
- No fixed application-level maximum file size. The selected format's unavoidable limits and the host platform's filesystem limits must be documented.
- Self-contained encrypted-file and key representations.
- Base64 key serialization.
- Authenticated integrity and explicit corruption/tampering detection.
- Transaction-oriented publication of completed outputs.
- GNU/Linux, Windows, macOS, Termux, and Android are target environments.
- Names remain visible; filename confidentiality is out of scope.
- Google Tink is rejected and must not be used.

## Current cryptographic comparison

The previous single-invocation AES-256-GCM architecture is rejected because it cannot meet the no-fixed-maximum-file-size requirement. A project-authored segmented-GCM construction is not an acceptable workaround.

Two candidates are under evaluation.

### A. libsodium XChaCha20-Poly1305 SecretStream

- Purpose-built authenticated sequence of messages for streaming/file encryption.
- Per-message authentication, sequence-integrity protection, final-message marker, automatic nonce handling and rekeying.
- No practical total stream length or message-count limit documented by libsodium; each individual message still has a finite maximum.
- Python binding candidate: PyNaCl.
- Termux native libsodium package exists; PyNaCl build/import/runtime on Termux is not yet proven.
- Best conceptual fit for sequential-only file operations.
- Must require TAG_FINAL, strict EOF, and private staging until the complete stream validates.

### B. AEGIS-256 Random-Access File (RAF)

- Maintained libaegis C implementation and pyaegis Python binding expose a random-access authenticated file format.
- RAF v1 uses independently authenticated records, file identity and chunk-index AAD, per-record nonces, authenticated header metadata, and optional external Merkle commitment.
- RAF v1 logical file size is unsigned 64-bit: finite format-level maximum 2^64 - 1 bytes.
- RAF v1 uses 16-byte tags, not 32-byte tags.
- RAF v1 defines a custom Keccak-p[1600,12]-based KDF; do not reimplement it.
- The RAF format does not define crash recovery or atomic multi-record commit; fscryptography must stage and publish transactionally.
- pyaegis's generic streaming decryptor buffers all plaintext until final authentication and is not suitable for arbitrary-size bounded-memory decryption. Evaluate RAF only.
- Source compilation is documented, but all target builds, especially Termux, remain unverified.

Research details: [Streaming cryptographic construction comparison](../research/streaming-cryptographic-construction-comparison.md).

## Decisions required before implementation

### A. Algorithm and dependency
- Complete the same proof-of-compatibility harness for SecretStream/PyNaCl and AEGIS-256 RAF/pyaegis.
- Validate package maintenance, releases, licenses, dependency tree, and security advisories.
- Prove source/wheel installation and runtime on GNU/Linux, Windows, macOS, Termux, and native Android if distinct.
- Compare throughput, peak memory, CPU behavior, and low-end Android performance.
- Select exactly one versioned construction for the first file format; do not create silent fallback between different algorithms/formats.
- Decide whether the RAF v1 2^64 - 1 byte size bound is acceptable if RAF is selected. SecretStream is preferred if avoiding a format-level total-size field is more important.
- No candidate is approved yet.

### B. Encrypted-file container
- Exact magic, version, algorithm identifier, header layout, authenticated metadata, framing, and trailing-data policy.
- For SecretStream: header placement, record framing, message-size limit, final-tag requirement, strict EOF behavior, and how metadata is bound to the stream.
- For RAF: exact upstream version, algorithm identifier, file ID, chunk size, key derivation, record validation, and how RAF is wrapped without modifying its cryptographic format.
- Key identifier/profile metadata and future migration behavior.
- No custom cryptographic composition without independent review.

### C. Key derivation
- Key type and entropy requirements for random master keys.
- Standard, reviewed key derivation/domain separation for file-specific keys if required.
- Exact Argon2id binding and supported runtime on every target.
- Exact KDF parameters and profile version.
- Password encoding and Unicode normalization.
- Stable salt/domain separation compatible with deterministic password-derived keys.
- Benchmark memory and latency on low-end Android hardware.

### D. Filesystem contract
- Exact symlink/reparse-point policy on each platform.
- Hard-link behavior.
- Special-file rejection rules.
- Destination collision and overwrite policy.
- Metadata preservation requirements.
- Concurrent source modification detection.
- Temporary-file naming, permissions, cleanup, and recovery.
- Exact atomicity/durability guarantees per platform.
- Ensure no output is published before complete authentication and structural validation.

### E. Public API
- Concrete key object and Base64 serialization interface.
- Return values for mutating operations.
- Exception hierarchy and error taxonomy.
- Exact semantics of file.is_encrypted() versus file.verify_integrity().
- Whether format recognition performs bounded structural parsing or full validation.
- Manager/key lifecycle and secret-memory handling expectations.

### F. Compatibility and verification
- Supported Python versions and packaging targets.
- Cross-platform interoperability test matrix.
- Golden test vectors for key and file formats.
- Tampering, truncation, wrong-key, missing-final, malformed-input, and trailing-data tests.
- Filesystem interruption and recovery tests.
- Independent cryptographic review criteria.
- Synthetic/sparse tests for very large logical sizes without allocating the entire file.

## Implementation gate

Implementation must not begin until the algorithm/dependency, container format, key derivation/KDF profile, observable filesystem behavior, transaction guarantees, and interoperability strategy have an approved specification. No fixed project-level file-size maximum is permitted.
