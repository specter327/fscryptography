# Cross-platform cryptographic backend feasibility review

**Review date:** 2026-11-20  
**Status:** upstream documentation and packaging review only. No dependency installation, runtime test, benchmark, or device test was executed. Neither candidate is approved.  
**Decision:** compare libsodium SecretStream/PyNaCl and AEGIS-256 RAF/pyaegis. Practical file-size independence and real support across all targets take priority over retaining AES.

## 1. Requirements

The library must encrypt/decrypt exactly one real file per operation, process sequentially with bounded memory, impose no fixed application-level maximum file size, authenticate all content and relevant metadata, reject truncation/reordering/corruption/incomplete finalization, and publish plaintext only after complete validation.

Targets: GNU/Linux, Windows, macOS, Termux, and Android. A native Android embedding/runtime must be treated separately from Termux if it is a distinct delivery target.

"Any size" means no artificial maximum imposed by fscryptography. Format and platform limits must be documented honestly.

## 2. Candidate summary

| Candidate | Python integration | Termux evidence | Size semantics | Current decision |
|---|---|---|---|---|
| libsodium SecretStream via PyNaCl | PyNaCl exposes low-level SecretStream bindings | Termux packages native libsodium; PyNaCl build/import/runtime untested | No practical total stream-length/message-count limit documented; finite per-message maximum | Provisional preference; validation pending |
| AEGIS-256 RAF via pyaegis/libaegis | pyaegis exposes RAF classes and FileStorage | Bundled C sources and documented source build; actual Termux build/runtime untested | RAF v1 unsigned 64-bit logical-size field (2^64 - 1 maximum) | Serious alternative; validation pending |
| pyaegis generic streaming AEAD | Incremental API exists | Same unverified status | Decryptor buffers all plaintext until final verification | Rejected for bounded-memory arbitrary-size decryption |
| PyCA AES-GCM single invocation | Incremental context exists | Termux package recipe exists | One GCM invocation has finite ~64 GiB plaintext limit | Rejected for current file-size requirement |
| Google Tink Streaming AEAD | Python implementation exists | Does not meet required Termux support | Segmented stream | Rejected by project decision |

## 3. libsodium SecretStream / PyNaCl

libsodium documents SecretStream specifically for encrypted streams and file encryption. It supports authenticated messages, sequence-integrity protection, detection of truncation/removal/reordering/duplication/modification, TAG_FINAL, automatic nonce handling and rekeying, and no practical limit to total stream length or message count. Each individual message has a finite maximum.

PyNaCl source exposes SecretStream initialization, push, pull, rekey, constants, and tags. Each message is passed as a bounded Python bytes object.

Sources:
- https://doc.libsodium.org/secret-key_cryptography/secretstream
- https://github.com/pyca/pynacl/blob/main/src/nacl/bindings/crypto_secretstream.py
- https://pynacl.readthedocs.io/en/latest/vectors/secretstream_vectors/

### Platform evidence and gaps

- GNU/Linux / Windows / macOS: PyNaCl publishes wheels for common desktop platforms; exact Python/architecture combinations must be checked against the selected release.
- Termux: Termux's package repository provides native libsodium. This proves availability of the native dependency only. It does not prove PyNaCl source build, CFFI integration, dynamic linkage, import, or runtime tests pass on the user's device.
- Native Android: Termux packaging is not evidence for Android APK embedding or distribution.

Required controls: bounded messages, exactly one TAG_FINAL, strict EOF, reject trailing bytes and malformed/truncated records, and stage plaintext until final and EOF validation succeed.

## 4. AEGIS-256 RAF / libaegis / pyaegis

libaegis provides AEGIS primitives and a Random-Access File API. pyaegis exposes RAF classes, including AegisRaf256, and file-backed storage.

RAF v1 documents a 64-byte authenticated header, an unsigned 64-bit logical file-size field, a random 24-byte file ID, 1 KiB–1 MiB chunk size, fresh random nonce per record, per-record AEAD authentication, file ID/chunk index/chunk size in AAD, and optional external Merkle commitment. Its finite format-level logical size is 2^64 - 1 bytes.

RAF v1 uses 16-byte tags, not 32-byte tags. It specifies a custom Keccak-p[1600,12]-based RAF_KDF, not HKDF/SHAKE/KMAC. Do not reproduce it in project code. RAF is not a password KDF.

RAF v1 does not define a journal, redundant header, generation counter, atomic multi-record commit, write ordering, durability, or crash recovery. fscryptography must stage and publish transactionally.

Sources:
- https://github.com/aegis-aead/libaegis
- https://github.com/aegis-aead/libaegis/blob/main/RAF.md
- https://www.rfc-editor.org/rfc/rfc10032.html

RFC 10032 is an Informational IRTF RFC, not an Internet Standards Track specification.

### Python binding and platform evidence

pyaegis documents AegisRaf256, FileStorage, RAF probing, random access, and optional Merkle support. It bundles C sources and documents source compilation with an installed C compiler. This makes a Termux build plausible, but not proven.

Sources:
- https://github.com/jedisct1/pyaegis
- https://pypi.org/project/pyaegis/

### Important distinction

pyaegis generic streaming decryption buffers all plaintext until final tag verification. That defeats bounded-memory decryption for arbitrarily large files. Do not use those streaming classes; evaluate RAF only.

## 5. Provisional direction

SecretStream is the closer fit for a sequential-only file library: no practical total-stream-length limit documented, explicit final marker, automatic nonce handling/rekeying, and no random-access format semantics.

AEGIS-256 RAF is a serious alternative with record-level authentication and optional Merkle commitment, but it adds complexity and a finite 64-bit size field.

**Provisional preference:** SecretStream via PyNaCl, subject to Termux and full platform validation. AEGIS-256 RAF remains in the same proof-of-compatibility spike. This is not final selection.

## 6. Required proof-of-compatibility matrix

Targets:
- [ ] GNU/Linux x86-64
- [ ] GNU/Linux ARM64
- [ ] Windows x86-64
- [ ] Windows ARM64 (separate result if in scope)
- [ ] macOS x86-64
- [ ] macOS ARM64
- [ ] Termux Android ARM64
- [ ] Native Android embedding/runtime, if distinct from Termux

For each target record OS/build, CPU/ABI, Python version, compiler, package version, linked native library version, installation source, exact command, and result.

### SecretStream / PyNaCl
- [ ] Install/import on each target and record runtime libsodium version.
- [ ] Round-trip empty, one-message, multi-message, exact-boundary, and short-final-message files.
- [ ] Cross-platform fixtures and vectors.
- [ ] Wrong key/header, altered header/ciphertext, missing tag, truncation, deletion, reordering, duplication, missing final, appended bytes.
- [ ] Confirm no publication before final and strict EOF.
- [ ] Interruption, I/O errors, low disk space, cleanup.
- [ ] Peak RSS and throughput on low-end Android.
- [ ] Synthetic/sparse tests to verify no application-level total-size counter/field.

### AEGIS-256 RAF / pyaegis
- [ ] Install/import from source on each target and record toolchain.
- [ ] Confirm AegisRaf256, FileStorage, raf_probe.
- [ ] Verify upstream RAF KDF vectors.
- [ ] Round-trip empty, boundary, multi-record, and large sparse files.
- [ ] Header MAC, record tags, wrong key/file ID, altered AAD/index, nonce/ciphertext/tag corruption, missing records, truncation, malformed header, trailing bytes.
- [ ] Full-file verification authenticates every required record.
- [ ] Sequential adapter and private staging behavior.
- [ ] Interruption during header/record writes, sync, rename.
- [ ] 64-bit logical-size boundary checks without allocating the file.
- [ ] Peak RSS, scratch buffer, throughput on low-end Android.

### Shared gates
- [ ] No fixed application-level maximum file size.
- [ ] Memory bounded independently of total file size.
- [ ] Complete authentication before output publication.
- [ ] Cross-platform interoperability.
- [ ] Reproducible dependency installation on all required targets.
- [ ] License, maintenance, dependency, and security review.
- [ ] Document unavoidable platform and format limits.

## 7. Argon2id remains separate

Password derivation is a separate dependency decision. Native Argon2 availability on Termux does not prove a maintained Python binding works there. Test a pinned Argon2id binding on every target; do not implement Argon2.

## 8. Acceptance gate

No production dependency, algorithm, or encrypted-file format is approved until the candidate tests pass on all required platforms, including Termux; bounded-memory and transaction requirements pass; full-stream/record integrity is enforced; file-size semantics are documented; and maintenance, licensing, and security reviews are acceptable.

No production code, public API, or encrypted-file format was changed by this review.
