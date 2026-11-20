# Cryptographic requirements

**Status:** security requirements and candidate comparison. No algorithm, dependency, or encrypted-file format is approved yet.

## 1. Security model

The library provides symmetric encryption for stored file contents and authenticated integrity for encrypted file resources.

It does not provide:
- Filename confidentiality. Original file and directory names remain visible.
- Cryptographic protection of directory contents through directory operations.
- Protection against an attacker who obtains the secret key or password.
- Protection against a compromised host while plaintext or keys are in use.
- A live encrypted filesystem or secure deletion guarantee.

Directory “encryption” is a reversible suffix-based rename only. It is not a cryptographic operation.

## 2. File-size requirement

fscryptography must not impose a fixed maximum file size. The intended guarantee is practical size independence: file processing must use bounded memory and support files as large as the target filesystem and platform can actually represent and store.

This is not a claim of mathematically infinite storage. The selected construction's own format limits, integer widths, native API limits, and platform filesystem limits must be documented. A candidate with a finite format limit must be evaluated against the project requirement and must not be described as unlimited.

The previous one-invocation AES-256-GCM design is rejected because GCM has a finite per-invocation plaintext limit. Do not bypass it with a project-authored segmented-GCM nonce/counter protocol.

## 3. Required cryptographic properties

- Symmetric encryption only.
- Established, maintained cryptographic implementation; no project-authored primitive.
- Authenticated encryption of every data unit.
- Sequential bounded-memory file processing.
- Proposed default I/O buffer/chunk size: 1 MiB, subject to selected construction constraints. This is not a public live-stream API.
- Authentication of all content and metadata that affects interpretation.
- Detection of modification, corruption, missing/reordered/duplicated data, truncation, missing finalization, and malformed containers.
- Self-contained, versioned encrypted-file data that can be decrypted across supported platforms.
- Decrypted plaintext remains in private staging until the entire encrypted resource has passed authentication and structural validation.
- No fixed application-level maximum file size.

## 4. Candidate A: libsodium XChaCha20-Poly1305 SecretStream

libsodium SecretStream is a candidate for sequential file encryption. It provides:
- a stream header;
- independently authenticated messages;
- sequence-integrity protection;
- TAG_FINAL to signal completion;
- automatic nonce handling and rekeying;
- no practical total-stream length or message-count limit documented by libsodium.

Individual messages have a finite maximum. The implementation must use bounded messages and process as many as required. The total file must not be limited by a fixed application-level count or byte-size field.

PyNaCl exposes low-level SecretStream bindings. It is the primary Python binding candidate, not yet an approved dependency. Desktop wheels do not prove Termux compatibility. The Termux repository's native libsodium package is useful evidence, but PyNaCl must be installed/imported and exercised on the actual Termux target.

References:
- https://doc.libsodium.org/secret-key_cryptography/secretstream
- https://github.com/pyca/pynacl/blob/main/src/nacl/bindings/crypto_secretstream.py
- https://github.com/termux/termux-packages/tree/master/packages/libsodium

### Required SecretStream behavior

- Authenticate every message before writing its plaintext to private staging.
- Require exactly one terminal TAG_FINAL.
- Reject EOF before TAG_FINAL.
- Reject bytes after finalization, malformed framing, truncated messages, and invalid sequence state.
- Do not publish output until final tag and strict EOF checks succeed.
- Use fresh stream initialization for each file operation.
- Define and version the outer container and bind metadata as authenticated data where appropriate.
- Keep key derivation/domain separation separate from the stream primitive and specify it before implementation.

## 5. Candidate B: AEGIS-256 Random-Access File (RAF)

libaegis provides AEGIS primitives and a Random-Access File API. pyaegis exposes Python RAF classes, including AegisRaf256, and file-backed storage.

RAF v1 has:
- a 64-byte authenticated header;
- an unsigned 64-bit logical file-size field;
- a random 24-byte file identifier;
- chunk sizes from 1 KiB through 1 MiB, divisible by 16;
- independently authenticated records;
- fresh random nonce per record;
- file identity, chunk index, and chunk size bound into record AAD;
- an optional Merkle-tree commitment maintained separately from the file.

RAF v1 therefore has a finite format-level maximum of 2^64 - 1 logical bytes. This may exceed practical current filesystem limits by a large margin, but the limit must be documented.

RAF v1 uses 16-byte (128-bit) authentication tags, even though AEGIS-256 itself supports 32-byte tags. Do not claim that RAF v1 uses a 256-bit tag.

RAF v1 specifies its own per-file RAF_KDF, based on one Keccak-p[1600,12] sponge operation. This is not HKDF, SHAKE, KMAC, or KangarooTwelve. Do not reproduce or modify it in project code; if RAF is selected, rely on a maintained upstream implementation and verify its published test vectors. RAF KDF is not a password-hardening KDF.

The upstream RAF format does not define a transaction journal, redundant header, generation counter, atomic multi-record commit, or crash-recovery protocol. fscryptography must provide its own filesystem staging/publication transaction around RAF operations.

The pyaegis streaming decryptor buffers all plaintext until final tag verification. That behavior is incompatible with arbitrary-size bounded-memory decryption and must not be used for file processing. Only the RAF API is a candidate.

References:
- https://github.com/aegis-aead/libaegis
- https://github.com/aegis-aead/libaegis/blob/main/RAF.md
- https://github.com/jedisct1/pyaegis
- https://www.rfc-editor.org/rfc/rfc10032.html

RFC 10032 is an Informational RFC from the IRTF Crypto Forum Research Group, not an Internet Standards Track specification. AEGIS-256 specifies a finite per-message maximum; RAF splits files into independently authenticated records.

## 6. Python dependency and platform requirements

Required targets:
- GNU/Linux x86-64 and ARM64;
- Windows x86-64 and ARM64 if in scope;
- macOS x86-64 and ARM64;
- Termux Android ARM64;
- native Android embedding/runtime if that is a distinct delivery target.

A package's source-build instructions or native C library availability are evidence of feasibility, not proof of platform support. For each candidate, record exact OS, architecture/ABI, Python version, compiler, dependency version, installation source, linked library version, and test results.

Google Tink remains rejected and must not be reintroduced as a dependency candidate.

## 7. Password-derived keys

Password derivation must use an established password-based KDF and a documented, versioned parameter profile. The design must address:
- deterministic behavior across platforms and versions;
- domain separation;
- password text encoding and normalization;
- KDF parameters and profile version;
- offline password-guessing resistance;
- implications of a deterministic reusable key.

Argon2id remains the preferred candidate, but its Python binding and runtime must be validated on Termux as well as desktop platforms.

A random per-call salt conflicts with same-password/same-profile determinism. A fixed public salt/domain value is not secret and does not make weak passwords strong. Never replace this with a single fast hash or silently change parameters for an existing profile.

## 8. Key representation

The serialized key representation must be self-describing, versioned, and Base64 encoded. It must identify enough information to interpret key type and profile safely, including derivation metadata where applicable.

Base64 is only an encoding. It does not encrypt, authenticate, or conceal the secret key. Parsing must be strict and unambiguous, with downgrade-prone representations rejected.

## 9. Verification and errors

File integrity verification must read and authenticate the complete encrypted resource. Invalid or unauthentic content must be distinguishable from operational failures such as I/O and permission errors. Exact public return and exception semantics remain pending.

## 10. Implementation gate

Do not implement a cryptographic file format until the algorithm/backend, exact framing, metadata authentication, key derivation, password KDF profile, file-size semantics, error behavior, transaction behavior, and platform interoperability plan are specified and reviewed.

No candidate is selected by this document.
