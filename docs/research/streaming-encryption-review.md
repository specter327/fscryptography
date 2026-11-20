# Streaming encryption construction review

**Status:** updated candidate comparison. No cryptographic protocol or dependency is approved.

## 1. Objective

Select a construction for encrypting one complete file in bounded-memory sequential blocks. Every data unit must be authenticated, sequence/position integrity must be enforced, truncation must be detected, and the complete encrypted resource must be validated before staged plaintext is published.

The public API remains cold and file-oriented. fscryptography must not impose a fixed maximum file size.

## 2. Rejected approaches

### 2.1 One AES-GCM invocation per file

Rejected. A single GCM invocation has a finite plaintext limit (approximately 64 GiB minus 32 bytes). It cannot meet the no-fixed-maximum-file-size requirement.

### 2.2 Project-authored segmented AES-GCM

Rejected as the default path. It would require the project to design and validate key separation, nonce uniqueness, segment framing, position binding, finalization, malformed-input behavior, cross-file/cross-process safety, and usage bounds. A random identifier plus a counter is not by itself a complete nonce-safety argument.

### 2.3 Google Tink Streaming AEAD

Rejected by project decision because the required Python dependency does not meet the project's Termux support requirement. Do not reintroduce Tink as a candidate.

## 3. Candidate A — libsodium SecretStream

libsodium SecretStream is designed for authenticated message sequences and file encryption. It provides a stream header, per-message authentication, sequence-integrity protection, a final-message tag, automatic nonce handling, and automatic/explicit rekeying. Its documentation states there are no practical limits to total stream length or message count, while each individual message remains bounded by a native API maximum.

PyNaCl exposes low-level SecretStream bindings. Each message is passed as a bounded Python bytes object.

References:
- https://doc.libsodium.org/secret-key_cryptography/secretstream
- https://github.com/pyca/pynacl/blob/main/src/nacl/bindings/crypto_secretstream.py

**Advantages**
- Closely matches sequential file processing.
- No practical total stream length limit documented.
- Built-in sequence integrity, final marker, nonce handling, and rekeying.
- No random-access machinery required.

**Limitations**
- Termux native libsodium availability does not prove PyNaCl installation/runtime.
- The outer file container still needs strict versioning, framing, metadata binding, final-tag handling, and EOF rules.
- The file adapter must not publish plaintext until the final tag and strict EOF checks succeed.

**Assessment:** provisional preferred candidate, pending complete platform validation.

## 4. Candidate B — AEGIS-256 RAF

libaegis provides a random-access authenticated file format. pyaegis exposes RAF classes and file-backed storage. RAF v1 authenticates a header and fixed-size records; record AAD binds file identity, chunk index, and chunk size. It supports chunks from 1 KiB to 1 MiB and uses fresh random nonces per record.

RAF v1 stores logical file size as unsigned 64-bit, so its format-level maximum is 2^64 - 1 bytes. It uses 16-byte tags, not 32-byte tags. Its custom per-file RAF_KDF is based on Keccak-p[1600,12]; do not reproduce it in project code. RAF v1 does not define journaling or crash recovery. An optional Merkle commitment is separate from the RAF file.

References:
- https://github.com/aegis-aead/libaegis
- https://github.com/aegis-aead/libaegis/blob/main/RAF.md
- https://github.com/jedisct1/pyaegis
- https://www.rfc-editor.org/rfc/rfc10032.html

**Advantages**
- Documented authenticated file format and per-record integrity.
- Random access and optional whole-file Merkle commitment.
- pyaegis provides a Python RAF API and source compilation path.

**Limitations**
- More complex than required by the sequential public contract.
- Finite 64-bit logical-size field.
- Custom format KDF and 128-bit tags need explicit review.
- Transaction/recovery behavior must be provided by fscryptography.
- Termux and all desktop builds remain unverified.

**Important:** pyaegis generic streaming decryption buffers all plaintext until final verification. It is not suitable for arbitrary-size bounded-memory decryption. Only the RAF API is a candidate.

**Assessment:** serious alternative, pending platform and security validation.

## 5. Provisional recommendation

Prefer libsodium SecretStream via PyNaCl if it passes Termux and all other platform tests. It is the simpler fit for sequential file operations and avoids a finite total-size field in the encrypted-file format.

Keep AEGIS-256 RAF in the comparative proof-of-compatibility spike. Select it only if test results or project requirements justify random-access semantics and its 64-bit size bound.

This is not final approval. Do not implement production code or a file format yet.

## 6. Transaction boundary

Regardless of the chosen construction:
- Encryption writes only to a private temporary file.
- Decryption writes only to a private temporary plaintext file.
- Every message or required record must authenticate successfully.
- SecretStream must reach exactly one TAG_FINAL; RAF must validate the header and every required record.
- The complete input must be consumed and trailing data handled according to the selected format.
- Only then may the result be published.
- On authentication, parsing, or I/O failure, the destination must not be presented as completed; temporary plaintext must be removed on a best-effort basis.
- verify_integrity must authenticate the complete encrypted file.

Per-message/record authentication does not itself provide a filesystem transaction. That guarantee belongs to fscryptography's filesystem layer.

## 7. Password-derived key direction

The requested deterministic behavior means the same password and same derivation profile must produce the same key. A per-call random salt would violate that requirement.

Argon2id remains a candidate password KDF, but its Python binding and runtime must be tested on every target, especially Termux. A fixed public application salt/domain value is not secret and does not make weak passwords strong. Domain separation and versioned parameters are mandatory. Do not implement a custom Argon2 function.

## 8. Blocking work

- Reproducible PyNaCl/SecretStream install and runtime on all required platforms.
- Reproducible pyaegis/RAF install and runtime on all required platforms.
- Cross-platform fixtures and test vectors.
- Tampering, truncation, reordering, deletion, duplication, missing-final, malformed-container, and trailing-data tests.
- Memory and performance measurements on low-end Android.
- Filesystem interruption and transactional publication tests.
- Dependency maintenance, license, and independent security review.
- Exact file-size semantics and all unavoidable format/platform limits.

No production dependency, algorithm, public API, or encrypted-file format is selected by this review.
