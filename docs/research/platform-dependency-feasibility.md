# Cross-platform cryptographic backend feasibility review

**Review date:** 2026-11-20  
**Status:** documentation and upstream packaging review only; no dependency installation or runtime test was executed on the user's devices.  
**Decision:** reject Google Tink. Select PyCA `cryptography` as the primary AES-256-GCM backend candidate for a bounded-memory, single-message GCM design, pending implementation-spike tests on every target. Argon2id remains a separate unresolved dependency decision.

## 1. Requirements and scope

The library must:
- preserve AES-256-GCM as the requested file-content encryption algorithm;
- process one real file per operation with bounded memory;
- authenticate the complete encrypted file before publishing decrypted plaintext;
- support GNU/Linux, Windows, macOS, Termux, and Android;
- avoid changing the intended public API;
- delegate cryptographic primitives and mode implementation to maintained libraries;
- avoid an improvised per-block GCM nonce/segment protocol.

The public 1 MiB block setting is currently a proposed I/O buffer size. It must not be assumed to be an independently authenticated cryptographic segment size.

## 2. Decision summary

| Candidate | AES-256-GCM | Bounded-memory file processing | Termux evidence | Current decision |
|---|---:|---:|---|---|
| Google Tink Python Streaming AEAD | Yes, documented profile | Yes, segmented construction | Android/Termux not in supported platform list; user's Termux toolchain already encountered a protoc loader failure | **Rejected by project decision** |
| PyCA `cryptography` low-level `Cipher(AES, GCM)` context | Yes | Yes, incremental `update()` calls in one GCM invocation | Official Termux package recipe exists and builds cryptography for Android using Termux's Rust/maturin toolchain | **Primary candidate; runtime validation pending** |
| libsodium `crypto_secretstream_xchacha20poly1305` | No | Yes, purpose-built authenticated streams | libsodium has broad bindings; Termux native package feasibility is plausible but Python binding/runtime still needs testing | Alternative only if algorithm change is explicitly approved |
| PyNaCl | No direct AES-GCM Streaming AEAD equivalent | SecretStream binding availability/API needs validation | PyNaCl's documented wheels are desktop manylinux/macOS/Windows; no official Android wheel promise | Not selected |

## 3. PyCA cryptography and Termux

### 3.1 Direct Termux packaging evidence

The official `termux/termux-packages` repository contains `packages/python-cryptography/build.sh`. The reviewed recipe pins cryptography **50.0.2** and explicitly:
- builds from the upstream PyCA cryptography source;
- uses Termux's Rust setup and Android API level;
- uses maturin and CFFI build dependencies;
- installs into the Termux Python prefix;
- patches the extension's dependency on `libpython` for Android linker behavior.

This is direct evidence that Termux maintains a native Android/Bionic build path for PyCA cryptography. It is materially stronger than inferring Android compatibility from a manylinux wheel.

Official source:
- https://github.com/termux/termux-packages/blob/master/packages/python-cryptography/build.sh
- https://github.com/termux/termux-packages/tree/master/packages/python-cryptography

The recipe's existence does **not** prove that the package is installed on the user's current device, that every supported Termux repository mirror currently serves it, or that the exact Python/OpenSSL combination passes fscryptography's required tests. Those must be checked on-device.

### 3.2 AES-GCM incremental context

PyCA documents a low-level `CipherContext` interface with repeated `update(data)` calls followed by `finalize()`. For AEAD modes such as GCM, the context also supports authenticated associated data. The encryption tag is available after finalization; decryption can use `finalize_with_tag(tag)`.

PyCA explicitly warns that GCM provides no ciphertext-integrity guarantee until decryption is complete and that decrypted bytes must not be used before finalization succeeds.

Official documentation:
- https://cryptography.io/en/stable/hazmat/primitives/symmetric-encryption/

This supports a bounded-memory implementation strategy without a custom segmented-AEAD protocol:
1. Create one AES-256-GCM context for the entire file.
2. Read the source sequentially in bounded I/O buffers.
3. Pass each buffer through the same context's `update()`.
4. Write output only to a private staging file.
5. Store the final 128-bit authentication tag in the container after successful encryption finalization.
6. On decryption, feed the entire ciphertext through one GCM decryptor, write only to private staging, and call `finalize_with_tag()`.
7. Publish plaintext only after tag verification and all structural checks succeed.

The I/O buffer boundaries are not cryptographic segment boundaries. There is one AEAD message and one final authentication tag for the complete file.

### 3.3 Important GCM size limit

A single GCM invocation has a finite maximum plaintext length (the GCM specification limit is (2^{39}-256) bits, approximately 64 GiB minus 32 bytes). The project must decide whether this is an acceptable maximum file size.

Do not silently split a file into multiple GCM invocations under a custom nonce/counter construction to bypass this limit. Doing so would reintroduce a project-authored segmented protocol and a nonce-allocation problem.

If the product must support files beyond the single-invocation GCM limit, the project must revisit the algorithm/construction requirement explicitly and select a reviewed streaming construction. This is an implementation blocker, not a detail to hide.

### 3.4 Nonce and key separation

Each encrypted file operation needs a fresh 96-bit GCM nonce for the AES-GCM key used by that invocation. Reusing a nonce with the same key is catastrophic.

The key strategy must therefore prevent nonce reuse across multiple files, retries, concurrent processes, and restarts. A candidate design is to derive a per-file encryption key from the manager's master key and a fresh random per-file salt using a standard KDF (e.g. HKDF), then use a fresh random 96-bit GCM nonce. This is only a design candidate: it requires a precise versioned format, cryptographic review, and usage-bound analysis before implementation. It is not permission to invent ad hoc key derivation or nonce logic.

Official PyCA AES-GCM documentation:
- https://cryptography.io/en/stable/hazmat/primitives/aead/

## 4. libsodium SecretStream alternative

libsodium provides `crypto_secretstream_xchacha20poly1305`, specifically designed for encrypted streams and file encryption. It authenticates messages, marks a final message, detects invalid/incomplete streams, and automatically rekeys before its internal counter wraps.

Official documentation:
- https://doc.libsodium.org/secret-key_cryptography/secretstream

However, it uses **XChaCha20-Poly1305**, not AES-256-GCM. It is not a drop-in backend replacement under the current algorithm requirement. It must not be selected without explicit project approval to change that requirement. PyNaCl is a Python binding to libsodium, but its published wheel guidance describes desktop macOS, Windows, and manylinux distributions, not an official Termux wheel guarantee:
- https://pypi.org/project/PyNaCl/

## 5. Argon2id status

Argon2id remains the preferred password KDF candidate, but its Python binding is not yet approved.

The official Termux package repository includes a native `argon2` package built from the reference C implementation:
- https://github.com/termux/termux-packages/blob/master/packages/argon2/build.sh

This is useful evidence that the native Argon2 implementation is packaged for Termux. It does **not** establish that `argon2-cffi` installs, links, and runs correctly in Termux Python. Options to test include:
- building and running a pinned `argon2-cffi` source distribution in Termux;
- evaluating a maintained Python binding against Termux's packaged native `libargon2`;
- using a carefully isolated binding layer only if its ABI, portability, and maintenance are demonstrably sound.

No custom Argon2 implementation is permitted.

The KDF profile still needs versioned decisions for Argon2 variant, memory/time/parallelism, output length, password encoding and normalization, salt/domain separation, and deterministic behavior. A random per-call salt conflicts with the current same-password/same-profile deterministic-key requirement.

## 6. Required proof-of-compatibility spike

Do not write production library code as part of this spike. Build a disposable test harness and pin exact versions.

### 6.1 Target matrix

- [ ] GNU/Linux x86-64
- [ ] GNU/Linux ARM64
- [ ] Windows x86-64
- [ ] Windows ARM64 (record separately if in scope)
- [ ] macOS x86-64
- [ ] macOS ARM64
- [ ] Termux Android ARM64
- [ ] Native Android embedding/runtime, only if it is a distinct delivery target from Termux

For each environment, record OS version, CPU/ABI, Python version, OpenSSL version, cryptography version, installation source, and package artifact.

### 6.2 PyCA cryptography tests

- [ ] Install from the platform's supported package path; on Termux, test the official `pkg install python-cryptography` package.
- [ ] Import `cryptography`, `Cipher`, `algorithms.AES`, and `modes.GCM`.
- [ ] Confirm AES-256-GCM context creation and 16-byte tag behavior.
- [ ] Encrypt/decrypt empty, small, buffer-boundary, and large test files using repeated `update()` calls.
- [ ] Verify cross-platform ciphertext interoperability.
- [ ] Verify wrong-key, wrong-nonce, wrong-AAD, tag tampering, ciphertext tampering, truncation, and missing-tag rejection.
- [ ] Verify no staged plaintext is published when final authentication fails.
- [ ] Verify source modification, I/O errors, and process interruption do not publish partial output.
- [ ] Confirm actual file-size limit behavior and reject inputs beyond the approved limit before destructive work.
- [ ] Measure throughput and memory usage on low-end Android hardware.

### 6.3 Argon2id tests

- [ ] Test a pinned `argon2-cffi` source build and runtime on Termux.
- [ ] Test the native Termux Argon2 package and identify whether a supported Python binding can use it.
- [ ] Verify published Argon2id test vectors and identical cross-platform outputs for the proposed versioned profile.
- [ ] Benchmark memory and latency on low-end Android hardware.
- [ ] Record ABI/linker/runtime dependencies and packaging reproducibility.

## 7. Acceptance gate and current decision

PyCA cryptography is the **primary candidate**, not yet an approved production dependency. Approval requires:
- successful installation and runtime tests on every required target;
- reproducible cross-platform AES-256-GCM interoperability;
- strict final-tag verification before publishing plaintext;
- a reviewed key-separation and nonce strategy;
- an explicit accepted maximum file size;
- acceptable memory and performance measurements;
- a versioned container specification and independent security review.

Google Tink is rejected and must not remain in implementation plans or dependency recommendations.

libsodium SecretStream remains a fallback only if the project explicitly authorizes changing AES-256-GCM to XChaCha20-Poly1305.

No production code, public API, or encrypted-file format is approved by this review.
