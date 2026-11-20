# Cryptographic requirements

**Status:** requirements and proposal only. This document does not define an approved cryptographic wire format.

## 1. Security model

The library provides symmetric encryption for stored file contents and authenticated integrity for encrypted file resources.

It does not provide:
- Filename confidentiality; original names remain visible.
- Cryptographic protection of directory contents through directory operations.
- Protection against an attacker who obtains the secret key or password.
- Protection against a compromised host while plaintext or keys are in use.
- A live encrypted filesystem or secure deletion guarantee.

## 2. Delegation

The project must not implement cryptographic primitives. It must delegate to established, maintained, reviewed, and tested implementations.

The project may define its own versioned key and file-container formats, but protocol composition must be reviewed. A custom format is not safe merely because it uses a recognized cipher.

## 3. Proposed cryptographic direction

The initial proposal is:

- AES with a 256-bit key.
- Galois/Counter Mode (GCM).
- Authenticated encryption with associated data (AEAD).
- 96-bit GCM nonces.
- Sequential independently authenticated blocks.
- Configurable block size, proposed default 1 MiB.
- Authenticated block sequence/position using AAD.
- A self-contained, versioned file container.
- A self-contained, versioned Base64 key representation.

AEAD describes the security interface/property of the construction; it is not a separate cipher to combine with GCM.

These choices remain subject to protocol review and cross-platform dependency validation.

## 4. Block protocol requirements

A valid protocol must specify:

- Exact binary framing and canonical field encodings.
- Version and cryptographic profile identification.
- Resource/operation identity and its entropy requirements.
- Nonce construction and a defensible uniqueness guarantee for every encryption under a given key.
- Block sequence numbering, ordering, lengths, and final-block behavior.
- Exact AAD encoding, including authenticated block position and relevant metadata.
- Authentication tag size and verification rules.
- A final authenticated record that detects truncation and binds total block count and plaintext length.
- Limits on plaintext size, block count, and total invocations/processed data per key.
- Behavior for malformed, unsupported, duplicated, missing, reordered, or truncated records.

A random resource identifier must have sufficient collision resistance for the expected number of resources encrypted under one key. A short random identifier plus a counter must not be assumed safe without quantitative analysis.

## 5. GCM nonce safety

Nonce reuse with the same AES-GCM key is catastrophic to security. The protocol must establish uniqueness, not merely make collisions seem unlikely without analysis.

The design must account for multiple files encrypted with the same key, retries, interrupted operations, concurrent processes, and repeated encryption of the same source. If uniqueness cannot be reliably guaranteed for the full supported usage model, derive per-resource subkeys using an established KDF and specify the derivation and nonce construction precisely.

GCM usage limits and security bounds must be explicit. The library must not imply support for arbitrarily large aggregate data under one key without a defined safe limit or key-separation strategy.

## 6. Password-derived keys

Password derivation must use an established password-based KDF and a documented parameter profile. The design must address:

- Determinism and stable derivation across platforms and versions.
- Domain separation from other uses of the same password.
- Password text encoding and normalization.
- KDF parameters and versioning.
- Offline password-guessing resistance.
- The implications of a deterministic, reusable key.

A random per-call salt would conflict with the requested same-password/same-key determinism unless the salt is itself stable and specified. A fixed public salt/domain value has trade-offs and must be reviewed; do not improvise a weak derivation scheme.

## 7. Key representation

The serialized key representation must be self-describing, versioned, and Base64 encoded. It must identify enough information to interpret the key type and profile safely, including derivation metadata when applicable.

Base64 is only an encoding. It does not encrypt, authenticate, or conceal the secret key. The representation must be validated strictly and must not permit ambiguous or downgrade-prone parsing.

## 8. Verification semantics

File integrity verification must read and authenticate the complete encrypted resource, including its final authenticated record. Header inspection, suffix recognition, or unauthenticated metadata parsing is insufficient.

Invalid or unauthentic content must be distinguishable from operational failures such as I/O and permission errors. Exact public return and exception semantics remain pending.

## 9. Required review before implementation

No file format or cryptographic protocol should be implemented until the nonce/key strategy, framing, AAD, finalization, KDF, usage limits, and failure semantics have been specified and reviewed. Prefer an established streaming/file-encryption construction if it meets the functional constraints; otherwise obtain focused cryptographic review of the custom composition.


## 10. Construction selection update

The project has evaluated established streaming authenticated-encryption constructions. The preferred candidate is Google Tink Streaming AEAD using the AES-256-GCM-HKDF 1 MiB profile, **conditional on verifying the exact Python API/profile and reproducible support on GNU/Linux, Windows, macOS, Termux, and Android**.

The evaluation is documented in [Streaming encryption construction review](../research/streaming-encryption-review.md).

This is a candidate, not an approved dependency or file format. The project should not reproduce Tink's segment protocol or invent a parallel AES-GCM nonce scheme. If the required implementation cannot be supported on the target matrix, stop and report the incompatibility. libsodium secretstream is a technically credible alternative, but uses XChaCha20-Poly1305 and therefore requires explicit approval to change the algorithm requirement.

## 11. Transactional use of streaming AEAD

Per-segment authentication does not mean a whole file has been successfully decrypted. The filesystem layer must write decrypted segments only to a private temporary file, consume the complete encrypted input, validate the construction's final completion condition, reject malformed trailing data as required by the format, and publish plaintext only after all checks succeed. The same full-consumption rule applies to `file.verify_integrity()`.

## 12. Deterministic password derivation direction

A random salt generated for each call is incompatible with the specified deterministic behavior. The candidate direction is a password KDF with a fixed, public, application-specific salt/domain value and versioned parameters. Argon2id remains a candidate pending platform availability and resource testing. The salt is not secret; deterministic derivation means equal password/profile inputs intentionally yield equal key material. Weak passwords remain vulnerable to offline guessing. Never replace this construction with a single fast hash of the password or silently change parameters within an existing profile.
