# Cryptographic requirements

**Status:** security requirements and candidate direction. No cryptographic dependency or wire format is approved.

## 1. Security model
The library provides symmetric encryption for stored file contents and authenticated integrity for encrypted file resources.

It does not provide:
- Filename confidentiality. Original file and directory names remain visible.
- Cryptographic protection of directory contents through directory operations.
- Protection against an attacker who obtains the secret key or password.
- Protection against a compromised host while plaintext or keys are in use.
- A live encrypted filesystem or secure deletion guarantee.

Directory “encryption” is a reversible suffix-based rename only. It is not a cryptographic operation.

## 2. Delegation and format ownership
The project must not implement cryptographic primitives. It must delegate primitives and secure streaming constructions to established, maintained, reviewed, tested implementations.

The project may define its own versioned key representation and outer file-container/identification format. It must not reimplement an established construction's internal segment protocol, nonce allocation, or authentication composition. A custom container does not become safe merely because it contains a recognized cipher.

## 3. Required cryptographic properties
- Symmetric encryption only.
- AES-256-GCM is the requested algorithm direction.
- Authenticated encryption with associated data (AEAD).
- Sequential bounded-memory processing of large files.
- Proposed default plaintext processing segment/block size: 1 MiB, subject to the selected construction's actual semantics and limits.
- Authentication bound to each segment's position and to its encrypted resource.
- Detection of modification, corruption, truncation, missing/reordered/duplicated segments, and invalid finalization.
- Self-contained, versioned encrypted-file data that can be decrypted across supported platforms.

AEAD is a security interface/property of a construction, not an additional cipher to combine with GCM.

## 4. Nonce and segment protocol
The initially suggested custom design (96-bit GCM nonce per block, counter, random resource/operation identifier, and AAD) is **not approved for implementation**.

Nonce reuse under the same AES-GCM key can catastrophically compromise confidentiality and authenticity. A random resource identifier plus a block counter does not, without a complete quantitative analysis and exact encoding, establish a robust uniqueness guarantee across:
- multiple files encrypted with the same key;
- repeated encryption and retries;
- concurrent processes;
- process crashes and restarts;
- all supported platforms and implementations.

The preferred direction is to use an established Streaming AEAD construction that already specifies key derivation, nonce construction, segment framing, position binding, and finalization. Do not independently compose these elements around raw AES-GCM.

If a custom protocol is ever reconsidered, it requires a complete written specification, explicit usage bounds, and independent cryptographic review before code is written.

## 5. Candidate construction
The current candidate is Google Tink Streaming AEAD with the AES-256-GCM-HKDF 1 MiB profile, conditional on reproducible Python support on GNU/Linux, Windows, macOS, Termux, and Android.

This candidate is not yet an approved dependency or file format. The project must verify exact package version, profile availability, Python API, installation/build requirements, platform/ABI support, maintenance, license, and cross-platform interoperability.

Do not wrap the candidate in a second project-authored segment protocol. The project-specific container should add only the minimal version/format identification required by the public contract, unless the selected construction already supplies it.

libsodium secretstream is a technically credible alternative but uses XChaCha20-Poly1305, not AES-GCM. It requires explicit approval to change the algorithm requirement and must not be silently substituted.

See [Streaming encryption construction review](../research/streaming-encryption-review.md).

## 6. Whole-file authentication and transaction boundary
Per-segment authentication does not establish that the entire file is complete. Decryption must write only to a private temporary file, consume the complete encrypted input, validate the construction's final completion condition, and reject malformed/trailing data as required by the format. Plaintext must not be published until all checks succeed.

file.verify_integrity() must consume and authenticate the complete encrypted file, including finalization. Header or suffix inspection is insufficient.

## 7. Password-derived keys
Password derivation must use an established password-based KDF and a documented, versioned parameter profile. The design must address:
- deterministic behavior across platforms and versions;
- domain separation;
- password text encoding and normalization;
- KDF parameters and profile version;
- offline password-guessing resistance;
- implications of a deterministic reusable key.

A random per-call salt conflicts with same-password/same-profile determinism. Argon2id remains a candidate pending platform availability and resource testing. A fixed public salt/domain value is not secret and does not make weak passwords strong. Never replace this with a single fast hash or silently change parameters for an existing profile.

## 8. Key representation
The serialized key representation must be self-describing, versioned, and Base64 encoded. It must identify enough information to interpret key type and profile safely, including derivation metadata where applicable.

Base64 is only an encoding. It does not encrypt, authenticate, or conceal the secret key. Parsing must be strict and unambiguous, with downgrade-prone representations rejected.

## 9. Verification and errors
File integrity verification must read and authenticate the complete encrypted resource. Invalid or unauthentic content must be distinguishable from operational failures such as I/O and permission errors. Exact public return and exception semantics remain pending.

## 10. Implementation gate
Do not implement a cryptographic file format until the streaming construction, key strategy, KDF profile, framing, versioning, limits, error semantics, and platform interoperability plan are specified and reviewed. The nonce proposal above is a rejected design direction, not an unfinished implementation task.
