# Streaming encryption construction review

**Status:** engineering evaluation; no cryptographic protocol or dependency is approved by this document.

## 1. Objective

Select a construction for encrypting one complete file in bounded-memory sequential blocks. The construction must authenticate every block, bind blocks to their position and file, detect missing/reordered/duplicated/truncated data, and support a final authenticated completion condition.

The public API remains cold and file-oriented. Internal sequential I/O is an implementation detail. Decryption and verification must stage output privately until the entire container has been authenticated.

## 2. Candidates reviewed

### 2.1 Google Tink Streaming AEAD — closest match

Google Tink documents Streaming AEAD for large files and streams. Its segments are bound to their location; segments cannot be removed, reordered, or transplanted between ciphertexts. The documentation describes AES-GCM-HKDF profiles, including 1 MiB profiles, and recommends the 1 MiB profile for general use. The AES-GCM-HKDF construction derives a per-stream key using HKDF and a random salt, and constructs segment nonces from a nonce prefix, segment index, and final-segment indicator.

References:

- https://developers.google.com/tink/streaming-aead
- https://developers.google.com/tink/streaming-aead/aes_gcm_hkdf_streaming

**Advantages**
- Closely matches the requested AES-GCM and 1 MiB segmented processing direction.
- Uses a reviewed, specified construction rather than requiring this project to invent nonce allocation and framing.
- Per-stream key derivation separates files encrypted under a long-lived master key.
- Segment position and final-segment state are incorporated into the construction.
- Has explicit documented limits, rather than implying unbounded AES-GCM use.

**Limitations and integration questions**
- Tink's documented streaming API may expose authenticated plaintext segments before the complete stream has been consumed. This is acceptable only behind this library's private temporary-output transaction; no plaintext destination may be published until final authentication succeeds.
- The Tink wire format is its own format. Wrapping it in another independently designed segment protocol would add unnecessary cryptographic complexity.
- The availability, packaging, supported Python versions, native-extension build requirements, and actual Android/Termux support of the required Tink implementation must be verified. Desktop support alone is insufficient.
- The exact profile and key size must be checked against the installed implementation and its maintained API. Do not infer that a profile is available on every target from the general specification.

**Assessment:** preferred protocol reference and first implementation candidate, subject to a mandatory platform/dependency proof. If adopted, use the standardized construction as specified; do not reproduce its cryptographic internals in project code.

### 2.2 libsodium secretstream — strong alternative, different algorithm

libsodium secretstream provides authenticated message sequences with a header, per-message authentication, ordering protection, a final tag, and automatic/explicit rekeying. Its documented file-encryption example processes files in chunks. It uses XChaCha20-Poly1305, not AES-GCM.

References:

- https://doc.libsodium.org/secret-key_cryptography/secretstream
- https://doc.libsodium.org/secret-key_cryptography/aead

**Advantages**
- Purpose-built for authenticated streams and large files.
- Explicit final-message semantics detect incomplete streams.
- Rekeying is part of the construction.
- Strong fit for bounded-memory sequential processing.

**Limitations**
- Does not meet the current AES-256-GCM direction.
- Python binding availability and native libsodium packaging still require platform validation, especially on Android/Termux.

**Assessment:** technically credible fallback only if the project explicitly revises its AES requirement. It must not be silently substituted.

### 2.3 Project-authored AES-GCM block protocol

A custom design using AES-GCM, random resource identifiers, block counters, and AAD could be made to work, but would require the project to specify and validate key separation, nonce uniqueness, GCM usage limits, framing, finalization, malformed-input behavior, and cross-file/cross-process safety.

A random identifier plus a counter is not by itself a complete nonce-safety argument. Reusing a GCM nonce with the same key is catastrophic. A custom design would duplicate work already addressed by established streaming-AEAD constructions and increase review burden.

**Assessment:** reject as the default path. Reconsider only if no maintained implementation can satisfy the platform matrix and after independent cryptographic review. Do not improvise a new nonce scheme during implementation.

## 3. Recommendation

1. Keep AES-256-GCM as the current project requirement pending explicit approval to change it.
2. Evaluate a maintained Tink Streaming AEAD implementation as the primary candidate, specifically the AES-256-GCM-HKDF 1 MiB profile where available.
3. Do not create a second project-specific block-encryption protocol around Tink. The library's own file container should be limited to the minimum required for format identification and compatibility, unless Tink's format already provides the needed self-description.
4. Implement a platform capability spike before selecting the dependency: GNU/Linux, Windows, macOS, Termux, and Android must all be considered. Record exact Python versions, wheels/native builds, ABI constraints, and reproducible installation steps.
5. Keep libsodium secretstream as a documented alternative, not an interchangeable backend. Switching to it changes the cryptographic algorithm and requires explicit project approval.
6. If no suitable maintained implementation is available on all required platforms, stop before implementation and present the compatibility gap. Do not silently implement the primitive or invent a custom protocol as a workaround.

## 4. Transaction boundary

Regardless of the chosen streaming construction:

- Encryption writes only to a private temporary file.
- Decryption writes only to a private temporary plaintext file.
- Every segment must authenticate successfully.
- The construction's final completion condition must be observed and validated.
- The complete input must be consumed so trailing garbage or malformed extra records can be rejected according to the format.
- Only then may the result be published.
- On any authentication, parsing, or I/O failure, the destination must not be presented as a completed result; temporary plaintext must be removed on a best-effort basis.
- `verify_integrity` must consume and authenticate the entire encrypted file.

A streaming-AEAD API authenticating each segment does not, by itself, provide the filesystem transaction guarantee. That guarantee belongs to the library's filesystem layer.

## 5. Password-derived key direction

The requested deterministic behavior means that the same password and same derivation profile must produce the same key. A per-call random salt would violate that requirement.

Recommended direction for further specification: a password KDF with a fixed, public, application-specific salt/domain value and explicitly versioned parameters. Argon2id is a candidate, but must be evaluated for availability and resource behavior on all target platforms. The fixed salt is not a secret and does not make a weak password strong; it means identical password/profile inputs intentionally produce identical key material. Domain separation and profile versioning are mandatory.

Do not derive a key by hashing the password once, and do not silently change KDF parameters for an existing profile. Any future parameter change must have a distinct profile/version.

## 6. Blocking questions

- Does the selected Tink Python implementation expose the required AES-256-GCM-HKDF streaming profile?
- Can it be installed and run on every required target, especially Termux and Android, without relying on unsupported native builds?
- Is the dependency maintained for the Python versions the project intends to support?
- Does its API expose final-stream validation in a way that can be made mandatory before publication?
- What exact stable password-derivation profile can be supported across all targets?

Until these are answered with reproducible evidence, the cryptographic protocol and dependency remain unapproved.
