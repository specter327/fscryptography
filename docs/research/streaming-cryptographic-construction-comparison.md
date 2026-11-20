# Streaming cryptographic construction comparison

**Review date:** 2026-11-20  
**Status:** upstream documentation review only. No dependency installation, runtime test, benchmark, or device test was executed. Neither algorithm nor dependency is approved.

## 1. Requirements and decision context

fscryptography performs cold operations on exactly one real file per operation. It must process sequentially with bounded memory, authenticate all content, and publish decrypted output only after complete authentication and structural validation.

The project must not impose a fixed application-level maximum file size. This means practical size independence, not mathematically infinite storage: unavoidable format integer widths, native API limits, platform APIs, filesystem limits, and available storage must be documented.

The previous one-invocation AES-256-GCM proposal is rejected because GCM has a finite per-invocation plaintext limit. A project-authored segmented-GCM protocol is also rejected. Google Tink remains rejected because it does not meet the required Termux support.

The user authorized comparison of:
1. libsodium XChaCha20-Poly1305 SecretStream;
2. AEGIS-256 Random-Access File (RAF).

Platform compatibility takes priority over preserving AES. A format specific to fscryptography is acceptable.

## 2. Executive comparison

| Criterion | libsodium SecretStream | AEGIS-256 RAF |
|---|---|---|
| Construction | Authenticated sequence of messages | Authenticated random-access file records |
| Primitive | XChaCha20-Poly1305 | AEGIS-256 AEAD + AEGIS-MAC header |
| Intended use | Sequential streams and file encryption | Encrypted files with random access |
| Bounded-memory processing | Yes | Yes |
| Total length | No practical total-stream limit documented | RAF v1 uses unsigned 64-bit logical file size |
| Per-unit limit | Each message has a finite maximum | Chunk size 1 KiB–1 MiB |
| Ordering/truncation | Sequence integrity and TAG_FINAL | Record index bound in AAD; required records validated |
| Rekeying | Built-in automatic rekeying | Per-file keys and fresh per-record nonces; no SecretStream-style ratchet |
| Python binding | PyNaCl exposes SecretStream | pyaegis exposes RAF classes |
| Termux | Native libsodium package exists; PyNaCl source/runtime unverified | C sources bundled and source compilation documented; actual build/runtime unverified |
| Main concern | Strict framing/final-tag enforcement required | More complex format, finite 64-bit size field, transaction gaps |

## 3. Candidate A — libsodium XChaCha20-Poly1305 SecretStream

libsodium SecretStream is designed for authenticated message sequences, including a single large file split into chunks. It provides:
- initialization header;
- per-message authentication;
- detection of modified, removed, reordered, duplicated, and truncated messages;
- TAG_FINAL completion marker;
- automatic nonce handling and rekeying;
- no practical total-stream length or message-count limit documented by libsodium.

Each individual message still has a finite API maximum. This does not impose a total-file limit: a file can be represented as as many bounded messages as required.

Official documentation: https://doc.libsodium.org/secret-key_cryptography/secretstream

### Python binding

PyNaCl exposes low-level bindings for SecretStream initialization, push, pull, rekey, constants, and tags. Each message is passed as a bounded Python bytes object; the adapter must not accumulate the full stream.

References:
- https://github.com/pyca/pynacl/blob/main/src/nacl/bindings/crypto_secretstream.py
- https://pynacl.readthedocs.io/en/latest/vectors/secretstream_vectors/

### Platform feasibility

- GNU/Linux, Windows, macOS: PyNaCl publishes wheels for common desktop environments; exact Python/architecture combinations must be pinned and tested.
- Termux: the Termux package repository provides native libsodium. This does not prove PyNaCl imports or builds correctly in the user's Termux environment. Test source installation and runtime on the actual target.
- Native Android embedding: treat separately from Termux if the project intends APK distribution or embedded Python. A Termux result is not evidence for an APK build.

### Risks and controls

- Version the outer container and authenticate relevant metadata.
- Require exactly one TAG_FINAL.
- Reject EOF before TAG_FINAL, bytes after final, malformed lengths, truncated tags, and invalid sequence state.
- A valid message may yield plaintext before the final message is seen. Write only to private staging; publish nothing until TAG_FINAL and strict EOF checks succeed.
- verify_integrity must consume and authenticate the complete file.
- Define key derivation and domain separation separately; do not reuse a stream key for another cryptographic role.

## 4. Candidate B — AEGIS-256 Random-Access File (RAF)

The maintained libaegis C project provides AEGIS variants and a Random-Access File API. RAF v1 consists of an authenticated header and fixed-size records. Each record contains a fresh public nonce, encrypted chunk data, and an AEAD tag. Record authentication binds file identity, record index, and chunk size.

RAF v1 documents:
- 64-byte authenticated header;
- unsigned 64-bit logical file-size field;
- random 24-byte file identifier;
- chunk size from 1,024 through 1,048,576 bytes, divisible by 16;
- independent per-record authentication;
- fresh random nonce for every record encryption;
- authenticated header metadata and per-file key derivation;
- optional Merkle-tree commitment maintained separately from the RAF file.

RAF v1 therefore has a finite format-level maximum of 2^64 - 1 logical bytes. This is far beyond ordinary current filesystem capacities, but it is not mathematically unlimited and must be disclosed.

References:
- https://github.com/aegis-aead/libaegis
- https://github.com/aegis-aead/libaegis/blob/main/RAF.md
- https://www.rfc-editor.org/rfc/rfc10032.html

### Primitive and format caveats

AEGIS-256 uses a 256-bit key and nonce. RFC 10032 specifies a finite per-message plaintext maximum of 2^61 - 1 bytes. RFC 10032 is an Informational RFC from the IRTF Crypto Forum Research Group, not an Internet Standards Track specification.

RAF v1 uses 16-byte (128-bit) authentication tags, even though AEGIS-256 itself supports 32-byte tags. Do not describe RAF v1 as using a 256-bit tag.

RAF v1 specifies a custom RAF_KDF based on one Keccak-p[1600,12] sponge operation. It explicitly is not HKDF, SHAKE, KMAC, or KangarooTwelve. Do not reproduce or modify it in project code; if RAF is selected, rely on the maintained upstream implementation and validate published vectors. RAF KDF is not a password-hardening KDF.

RAF v1 does not define a journal, redundant header, generation counter, atomic multi-record commit, write ordering, durability, or crash recovery. fscryptography must provide private staging and transactional publication.

### Python binding and platform feasibility

pyaegis is the Python binding for libaegis. Its documentation exposes AegisRaf256, FileStorage, random-access operations, probing, and optional Merkle-tree support. Its source-install instructions state that C sources are bundled and compiled using an installed C compiler. This makes a Termux source build plausible, but does not establish successful builds or runtime on Termux or every desktop ABI.

References:
- https://github.com/jedisct1/pyaegis
- https://pypi.org/project/pyaegis/

### Important distinction: generic streaming vs RAF

pyaegis also documents generic streaming AEAD classes. Its streaming decryptor buffers all plaintext internally and releases it only after final tag verification. That defeats bounded-memory decryption for arbitrarily large files. Do not use those streaming classes for fscryptography; evaluate the RAF API only.

### Risks and controls

- RAF is random-access, while fscryptography's public contract is sequential. RAF can be driven sequentially, but its extra semantics and complexity may be unnecessary.
- Full-file verification must authenticate every required record. Header authentication alone does not authenticate chunk contents.
- The optional Merkle commitment is separate from the RAF file. A trusted root must be stored externally if persistent whole-file commitment is required.
- RAF v1's finite 64-bit size field must be considered against the no-project-limit requirement.
- The filesystem layer must provide transaction and recovery behavior absent from RAF v1.

## 5. Comparative assessment

### SecretStream advantages
- Simpler fit for sequential-only file operations.
- Explicit final-message semantics and sequence-integrity protection.
- Automatic nonce handling and rekeying.
- No practical total stream-length limit documented.
- No random-access format machinery.

### SecretStream disadvantages
- Each message has a finite maximum and framing must be implemented correctly.
- PyNaCl's Termux installation/runtime is not yet proven.
- The adapter must enforce final-tag and strict EOF semantics before publishing staged plaintext.

### AEGIS-256 RAF advantages
- Documented authenticated file format with per-record integrity.
- Random access and optional Merkle commitment.
- Python RAF API and source-build path.

### AEGIS-256 RAF disadvantages
- Finite 64-bit logical-size field.
- More complex than required for sequential operations.
- Custom RAF KDF and 128-bit tags require explicit review.
- No transaction journal or crash-recovery protocol.
- All Python platform builds remain unverified.

## 6. Provisional recommendation

**Provisional preference: libsodium SecretStream through PyNaCl**, subject to the compatibility gate.

It is the closer fit for sequential bounded-memory file encryption, has explicit final-message semantics and automatic rekeying, and avoids a fixed total-size field in the file format. AEGIS-256 RAF remains a serious alternative and must be tested rather than dismissed. It may be preferable if PyNaCl cannot be made reliable on Termux/Android or if RAF's random-access/Merkle capabilities justify the additional complexity.

This is not final algorithm/dependency selection. No production code or encrypted-file format is approved.

## 7. Required proof-of-compatibility spike

Run the same disposable harness against both candidates. Do not write production library code as part of this spike.

### Platform matrix

- [ ] GNU/Linux x86-64
- [ ] GNU/Linux ARM64
- [ ] Windows x86-64
- [ ] Windows ARM64 (separate status if in scope)
- [ ] macOS x86-64
- [ ] macOS ARM64
- [ ] Termux Android ARM64
- [ ] Native Android embedding/runtime, if distinct from Termux

For every run, record OS/build, CPU/ABI, Python version, compiler, package version, dependency source, linked native library version, install command, and result.

### SecretStream / PyNaCl tests

- [ ] Install/import PyNaCl on every target.
- [ ] Record bundled/system libsodium version and runtime linkage.
- [ ] Confirm key/header/message constants and state initialization.
- [ ] Round-trip empty, one-message, multi-message, exact-boundary, and short-final-message files.
- [ ] Cross-platform fixtures and interoperability.
- [ ] Reject wrong key/header, altered header/ciphertext, missing tag, truncation, deletion, reordering, duplication, missing TAG_FINAL, and appended bytes after final.
- [ ] Confirm plaintext remains private staging until final and strict EOF validation succeed.
- [ ] Simulate read/write failure, process interruption, and insufficient storage.
- [ ] Measure peak RSS and throughput on low-end Android.
- [ ] Verify no application-level total-stream counter or size field imposes a fixed file limit; use synthetic/sparse I/O tests where appropriate.

### AEGIS-256 RAF / pyaegis tests

- [ ] Install/import pyaegis on every target from the documented source path.
- [ ] Record compiler, ABI, Python, and libaegis version.
- [ ] Confirm AegisRaf256, FileStorage, and raf_probe.
- [ ] Validate RAF key-derivation vectors and format behavior against upstream.
- [ ] Round-trip empty, boundary, multi-record, and large sparse files.
- [ ] Verify header MAC and every record tag; test wrong key/file ID, altered AAD/index, modified nonce/ciphertext/tag, missing records, truncation, malformed header, and trailing bytes.
- [ ] Verify full-file integrity authenticates every required record.
- [ ] Test sequential-only adapter and private staging behavior.
- [ ] Simulate failures during header/record writes, sync, and rename.
- [ ] Test RAF v1's unsigned 64-bit size boundary without allocating the file.
- [ ] Measure peak RSS, scratch-buffer requirements, and throughput on low-end Android.

### Shared acceptance tests

- [ ] No fixed application-level maximum file size.
- [ ] Bounded memory independent of total file size.
- [ ] One real file per operation; no recursion or batch processing.
- [ ] Complete authentication before output publication.
- [ ] Strict parsing and rejection of malformed/trailing data.
- [ ] Cross-platform encrypted-file interoperability.
- [ ] Reproducible installs on all required targets.
- [ ] Dependency maintenance, license, and security review.
- [ ] Independent review of the selected construction and container.
- [ ] Document unavoidable platform and format bounds precisely.

## 8. Decision gate

No production dependency, algorithm, or encrypted-file format is approved until both candidates have reproducible results, all required platform installations/runtime tests pass (especially Termux), bounded-memory and transaction requirements pass, format limits are documented, and maintenance/licensing/security reviews are acceptable.

No production code or public API changes are part of this research task.
