# fscryptography

A focused, cross-platform Python library for authenticated encryption/decryption of individual stored files and reversible suffix-based renaming of individual directories.

> **Status:** requirements and design phase. No cryptographic format, dependency, or implementation is approved as stable.

## Scope
- Encrypt/decrypt the complete content of exactly one regular file per operation.
- For a directory, modify only its own name by appending/removing the literal **.fscrypt** suffix. Never encrypt its name cryptographically, enumerate children, or modify contents.
- Preserve original file and directory names; append/remove only the final suffix.
- Target GNU/Linux, Windows, macOS, Termux, and Android, with future extensibility.
- Use symmetric cryptography only and delegate primitives to established, maintained libraries.
- Process files sequentially with bounded memory; proposed default I/O buffer size: 1 MiB.
- Use self-contained, versioned key and encrypted-file representations.
- Publish outputs only after processing and authentication succeed.

## API direction
```python
random_secret_key = fscryptography.key.generate()
password_secret_key = fscryptography.key.derive(password="...")
manager = fscryptography.Manager(key=secret_key)

manager.file.encrypt(filepath="...")
manager.file.decrypt(filepath="...")
manager.file.is_encrypted(filepath="...")
manager.file.verify_integrity(filepath="...")

manager.dir.encrypt(dirpath="...")
manager.dir.decrypt(dirpath="...")
manager.dir.is_encrypted(dirpath="...")
```

This is the intended API shape, not yet a released compatibility contract. file.is_encrypted() recognizes the encrypted file format, not the suffix alone. file.verify_integrity() authenticates the complete encrypted content. dir.is_encrypted() checks only the suffix convention and cannot prove prior processing. There is no directory integrity operation.

## Naming convention
| Resource | Before | After |
|---|---|---|
| File | file1.txt | file1.txt.fscrypt |
| Directory | dir1/ | dir1.fscrypt/ |

Decryption removes exactly the final suffix. Original names and extensions remain visible. **Names are not cryptographically encrypted**; the suffix is only a naming convention.

## Documentation
- [Functional specification](docs/specification/functional-specification.md)
- [Public API contract](docs/specification/public-api.md)
- [Filesystem and transaction behavior](docs/specification/filesystem-behavior.md)
- [Cryptographic design requirements](docs/specification/cryptographic-requirements.md)
- [Streaming encryption construction review](docs/research/streaming-encryption-review.md)
- [Cross-platform cryptographic backend feasibility review](docs/research/platform-dependency-feasibility.md)
- [Open design decisions](docs/specification/open-decisions.md)

## Cryptographic direction
AES-256-GCM remains the required algorithm. Google Tink is rejected because its Python support does not include Termux/Android.

PyCA `cryptography` is the primary backend candidate. Its low-level AES-GCM context supports incremental processing of one complete file using bounded I/O buffers, and the official Termux package repository maintains an Android-specific `python-cryptography` build. Actual installation, runtime, interoperability, and security tests are still required on every target.

A single GCM invocation has a maximum plaintext size of (2^{39}-256) bits (approximately 64 GiB minus 32 bytes). The project must explicitly decide whether that maximum is acceptable. The 1 MiB buffer is not a cryptographic segment size; no custom segmented-GCM protocol is approved.

libsodium SecretStream is a technically credible streaming alternative, but it uses XChaCha20-Poly1305 and therefore requires explicit approval to change the algorithm.

Base64 is an encoding for serialization and transport; it does not protect secret key material.

## Guarantees and validation
Before claiming support, the project requires coherent specifications, automated tests, cross-platform interoperability tests, tampering/corruption/truncation tests, filesystem interruption tests, and reproducible demonstrations. The project does not promise secure deletion or protection against a compromised host.
