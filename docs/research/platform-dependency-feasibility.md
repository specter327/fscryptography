# Platform feasibility review: Tink Streaming AEAD and Argon2id

**Review date:** 2026-11-19  
**Status:** documentation-based assessment only; no target-device installation or execution was performed.  
**Decision:** do not approve either dependency as satisfying the complete five-environment requirement yet.

## 1. Scope

This review evaluates the current Python dependency candidates for:

- File-content encryption: Google Tink Python, Streaming AEAD, AES-256-GCM-HKDF 1 MiB.
- Password-derived keys: Argon2id through argon2-cffi.
- Required environments: GNU/Linux, Windows, macOS, Termux, and Android.

The project requirement is cross-platform behavior without changing the public API or silently substituting a different cryptographic algorithm.

## 2. Executive result

| Environment | Tink Python 1.16.1 | argon2-cffi | Evidence status |
|---|---|---|---|
| GNU/Linux x86-64 | Officially supported | Official wheels; source build documented | Documentation-supported |
| GNU/Linux ARM64 | Officially supported | ARM wheels are published for supported Linux ABIs; source build documented | Documentation-supported, ABI-specific |
| Windows x86-64 | Officially supported | Official wheels | Documentation-supported |
| Windows ARM64 | Not listed in Tink's supported Python platforms | Recent bindings publish Windows ARM64 wheels for some Python ABIs | Tink platform gap |
| macOS x86-64 | Officially supported | Official wheels | Documentation-supported |
| macOS ARM64 | Officially supported | Official wheels | Documentation-supported |
| Termux / Android ARM64 | Not listed or officially supported by Tink Python | No official Android/Termux wheel guarantee; source compilation may be possible but is unverified | **Unverified / blocking** |

The five required environments are not equivalent to the desktop platform labels. In particular, Android/Termux uses Android's Bionic C library and Android-specific Python/build environments. A Linux manylinux ARM64 wheel targets glibc and must not be treated as an Android wheel.

**Conclusion:** Tink is a viable documented candidate for the listed desktop targets, but current public support statements do not establish Termux/Android compatibility. The combined dependency stack therefore fails the project's all-targets approval gate for now.

## 3. Google Tink Python

### 3.1 Current documented release and platform support

The official Tink Python setup guide currently identifies release **1.16.1**, requires Python **3.10 or newer**, and lists these supported platforms:

- macOS x86-64 and ARM64
- Linux x86-64 and ARM64
- Windows x86-64

The guide says pip installs a binary distribution when one is available. Otherwise pip falls back to the source distribution, which requires Bazel or Bazelisk and the Protocol Buffers compiler.

Official references:

- https://developers.google.com/tink/setup/py
- https://developers.google.com/tink/supported-key-types
- https://developers.google.com/tink/streaming-aead
- https://developers.google.com/tink/streaming-aead/aes_gcm_hkdf_streaming
- https://pypi.org/project/tink/

### 3.2 Primitive availability

The official language matrix lists Streaming AEAD for Python. Tink documents the AES-GCM-HKDF Streaming AEAD family and the AES256_GCM_HKDF_1MB profile.

This confirms that the required primitive/profile exists in Tink's Python API. It does **not** prove that the package builds or runs on every operating system/ABI.

Tink recommends AES128_GCM_HKDF_1MB for most use cases in its general guidance; AES-256 remains available as a profile and is retained here because it is the project's requested direction, not because it is Tink's general default recommendation.

### 3.3 Packaging assessment

The current Tink Python guide's supported-platform list excludes Android and Termux. The PyPI release publishes desktop platform wheels, including Linux ARM64 wheels tagged for manylinux (glibc), not Android/Bionic.

For a platform without a compatible wheel, pip's documented fallback is a source build requiring Bazel/Bazelisk and protoc. That fallback is not proof of Android compatibility. It must be built and executed in the actual Termux environment. The previous Termux protoc loader failure is an additional reason not to assume that the source-build path works.

Do not:
- install a manylinux wheel by renaming or retagging it for Android;
- infer Android support from Linux ARM64 support;
- claim that a successful desktop build proves Termux support;
- replace Tink's construction with a project-authored AES-GCM block protocol.

### 3.4 Preliminary verdict

- GNU/Linux x86-64/ARM64, Windows x86-64, and macOS x86-64/ARM64: **documented candidate**.
- Windows ARM64: **not in the current Tink Python support list**.
- Termux/Android: **unsupported by the published support statement; actual source-build feasibility unknown**.

Tink remains the primary candidate, but is not approved as the cross-platform dependency.

## 4. Argon2id through argon2-cffi

### 4.1 Packaging facts

The argon2-cffi installation documentation states that:

- argon2-cffi uses argon2-cffi-bindings;
- the bindings vendor Argon2 C source by default;
- binary wheels are published for macOS, Windows, and Linux;
- building from source requires a working C compiler and CFFI environment;
- the implementation is documented as compiling on common x86 and ARM platforms.

Official references:

- https://argon2-cffi.readthedocs.io/en/stable/installation.html
- https://pypi.org/project/argon2-cffi/
- https://pypi.org/project/argon2-cffi-bindings/

### 4.2 Android/Termux caveat

The upstream installation documentation does not promise Termux or Android support. Linux ARM64 wheels are built for Linux ABI tags such as manylinux; these are not interchangeable with Android/Bionic.

Because the bindings include native code, Termux requires a real build-and-run test with its own Python, compiler, CFFI, headers, and linker environment. A successful source build on GNU/Linux is insufficient.

### 4.3 KDF design caveat

Argon2id is a candidate, not yet an approved derivation profile. Before implementation, specify and version:

- Argon2 variant (Argon2id);
- salt/domain-separation rule compatible with the requested deterministic behavior;
- memory cost, time cost, and parallelism;
- output length;
- password byte encoding and Unicode normalization;
- profile/version identifier and future migration rules.

A random per-call salt would make identical passwords produce different keys, contradicting the current deterministic-key requirement. A fixed public application-specific salt/domain value can provide deterministic output, but it is not secret and does not compensate for a weak password. KDF parameters must be selected with real low-end Android device memory/latency measurements, not desktop benchmarks alone.

### 4.4 Preliminary verdict

- Desktop platforms: **documented candidate**.
- Termux/Android: **plausible source-build path, not verified or officially guaranteed**.
- Argon2id profile: **not specified sufficiently for implementation**.

## 5. Required proof-of-compatibility spike

No production library code should be written as part of this spike. Use an isolated test harness and pinned dependency versions.

### 5.1 Environment inventory

For each target, record:

- OS and exact version;
- CPU architecture and ABI;
- Python implementation and exact version;
- pip version and supported wheel tags;
- compiler, linker, Bazel/Bazelisk, protoc, CFFI versions where applicable;
- dependency version and artifact selected by pip.

Required environments:

1. GNU/Linux x86-64.
2. GNU/Linux ARM64.
3. Windows x86-64.
4. macOS x86-64.
5. macOS ARM64.
6. Termux on Android ARM64.
7. Native Android execution environment, if distinct from Termux is a project target.

Windows ARM64 should be recorded as a separate compatibility gap unless the project explicitly excludes it from the Windows target.

### 5.2 Tink tests

For each environment:

1. Install the exact pinned Tink version using the documented path.
2. If pip selects an sdist, record and reproduce the complete build toolchain.
3. Import tink and tink.streaming_aead.
4. Confirm the AES256_GCM_HKDF_1MB template exists in the installed version.
5. Register the required configuration and create the Streaming AEAD primitive.
6. Encrypt and decrypt empty, short, boundary-sized, and multi-segment files.
7. Verify cross-platform interoperability using a ciphertext created on one platform and decrypted on another.
8. Verify wrong-key, bit-flip, truncation, segment deletion, segment reordering, and trailing-data behavior.
9. Confirm final-stream authentication failure never publishes staged plaintext.

### 5.3 Argon2id tests

For each environment:

1. Install the exact pinned argon2-cffi version.
2. Record whether a wheel or source build was used.
3. Import the binding and execute Argon2id.
4. Verify a shared deterministic test vector across platforms.
5. Verify changes in password/profile inputs produce the expected distinct outputs.
6. Measure memory consumption and latency on representative low-end Android hardware.
7. Confirm parameter/version metadata can be serialized and interpreted without changing the public API.

### 5.4 Acceptance criteria

A dependency is approved only when:

- all required target environments install and execute it reproducibly;
- no wheel is retagged or treated as compatible across ABIs without evidence;
- the selected Tink profile is available in the exact installed package;
- cross-platform ciphertext interoperability passes;
- malformed, truncated, reordered, and modified ciphertext is rejected;
- failed decryption never publishes plaintext;
- Argon2id produces the same output for the same versioned profile and password across all targets;
- resource use is acceptable on low-end Android hardware;
- dependency versions, licenses, build instructions, and artifacts are recorded.

## 6. Decision and next action

**Do not select Tink + argon2-cffi as the final dependency stack yet.**

Tink has an explicit platform-support gap for Android/Termux (and Windows ARM64), while argon2-cffi's Android source-build path is unverified. The desktop story is substantially stronger, but the project requirement is not desktop-only.

The next action is to execute the proof-of-compatibility spike on actual target environments, beginning with:
1. Linux Mint x86-64 / Python 3.12;
2. Termux Android ARM64 / the actual installed Python version;
3. Windows x86-64;
4. macOS x86-64 and ARM64;
5. Linux ARM64.

If Tink cannot be made to work reproducibly on Termux/Android, stop and evaluate a maintained alternative with an explicit AES-256-GCM-compatible Streaming AEAD construction. Do not silently change to XChaCha20-Poly1305 and do not implement a custom nonce/segment protocol. Any algorithm change requires explicit project approval.

**No production dependency, cryptographic format, or public API change is approved by this review.**
