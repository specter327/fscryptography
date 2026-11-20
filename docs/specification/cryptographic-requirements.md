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
The project must not implement cryptographic primitives. It must delegate AES-GCM and supporting cryptographic operations to established, maintained, reviewed, tested implementations.

The project may define a versioned key representation and an outer encrypted-file container. It must not invent a segmented GCM construction, nonce counter scheme, or authentication composition around raw AES-GCM.

## 3. Required cryptographic properties
- Symmetric encryption only.
- AES-256-GCM remains the requested algorithm.
- Authenticated encryption with associated data (AEAD).
- Sequential bounded-memory file processing.
- Proposed default I/O buffer size: 1 MiB. This is an I/O detail, not a cryptographic segment size.
- Authentication of the complete file, including format metadata that affects interpretation.
- Detection of modification, corruption, truncation, missing tag, and invalid finalization.
- Self-contained, versioned encrypted-file data that can be decrypted across supported platforms.

AEAD is a security interface/property of a construction, not an additional cipher to combine with GCM.

## 4. Primary backend candidate: PyCA cryptography

Google Tink is rejected because its Python support statement does not include Termux/Android. It must not be used or retained as a candidate dependency.

PyCA `cryptography` is the primary candidate because:
- it provides AES-GCM through its low-level cipher context API;
- the GCM context supports incremental `update()` calls and finalization, enabling bounded-memory processing of one complete file as one AEAD message;
- its documentation explicitly requires that decrypted bytes not be used until GCM finalization succeeds;
- the official Termux package repository maintains a native `python-cryptography` package with an Android-specific build recipe.

This is a candidate, not yet an approved dependency. Actual installation, runtime, interoperability, and tampering tests must pass on every target platform.

References:
- https://cryptography.io/en/stable/hazmat/primitives/symmetric-encryption/
- https://github.com/termux/termux-packages/blob/master/packages/python-cryptography/build.sh

### 4.1 Whole-file GCM processing

The proposed processing model is one AES-256-GCM invocation per encrypted file:
1. Initialize one GCM context.
2. Process the source sequentially through bounded I/O buffers using the same context.
3. Finalize encryption and persist its full authentication tag in the versioned container.
4. For decryption, process all ciphertext into a private temporary file.
5. Validate the complete authentication tag with finalization.
6. Publish plaintext only after authentication and structural validation succeed.

The I/O buffer boundaries are not cryptographic segment boundaries. There is one final authentication tag for the complete file. No plaintext from an unauthenticated GCM decryptor may be published or consumed.

### 4.2 GCM size limit

A single GCM invocation is limited to (2^{39}-256) bits of plaintext (approximately 64 GiB minus 32 bytes). The project must explicitly decide whether this maximum file size is acceptable.

Do not bypass this limit by silently creating multiple GCM invocations with an improvised nonce/counter protocol. If larger files are mandatory, revisit the algorithm/construction requirement and select a reviewed streaming construction through an explicit design decision.

### 4.3 Key and nonce separation

Every GCM invocation requires a unique nonce for its AES key. Reusing a nonce with the same key can catastrophically compromise security.

A possible design is a fresh random per-file salt, a standard KDF deriving a distinct per-file AES key from the manager key, and a fresh random 96-bit GCM nonce. This is only a candidate requiring a precise versioned format, analysis of collision/usage bounds, and independent review. Do not implement ad hoc key derivation or nonce allocation.

## 5. Alternative construction requiring explicit algorithm change

libsodium SecretStream is a maintained authenticated streaming construction using XChaCha20-Poly1305. It provides per-message authentication, final-stream signaling, and automatic rekeying. It does **not** satisfy the current AES-256-GCM requirement.

It may be considered only if the project explicitly approves changing the algorithm requirement. It must not be silently substituted.

Reference:
- https://doc.libsodium.org/secret-key_cryptography/secretstream

## 6. Password-derived keys
Password derivation must use an established password-based KDF and a documented, versioned parameter profile. The design must address:
- deterministic behavior across platforms and versions;
- domain separation;
- password text encoding and normalization;
- KDF parameters and profile version;
- offline password-guessing resistance;
- implications of a deterministic reusable key.

Argon2id remains the preferred candidate, but its Python binding and runtime must be validated on Termux as well as desktop platforms. The official Termux repository packages the native Argon2 reference implementation; this does not prove that argon2-cffi or another Python binding works in Termux.

A random per-call salt conflicts with same-password/same-profile determinism. A fixed public salt/domain value is not secret and does not make weak passwords strong. Never replace this with a single fast hash or silently change parameters for an existing profile.

## 7. Key representation
The serialized key representation must be self-describing, versioned, and Base64 encoded. It must identify enough information to interpret key type and profile safely, including derivation metadata where applicable.

Base64 is only an encoding. It does not encrypt, authenticate, or conceal the secret key. Parsing must be strict and unambiguous, with downgrade-prone representations rejected.

## 8. Verification and errors
File integrity verification must read and authenticate the complete encrypted resource. Invalid or unauthentic content must be distinguishable from operational failures such as I/O and permission errors. Exact public return and exception semantics remain pending.

## 9. Implementation gate
Do not implement a cryptographic file format until the backend, maximum file size, key separation, nonce strategy, KDF profile, framing, versioning, error semantics, and platform interoperability plan are specified and reviewed. A list of algorithms is not a complete protocol.
