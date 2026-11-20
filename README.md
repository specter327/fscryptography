# fscryptography

A focused, cross-platform Python library for authenticated encryption/decryption of individual stored files and reversible suffix-based renaming of individual directories.

> **Status:** requirements and design phase. No cryptographic algorithm, dependency, encrypted-file format, or implementation is approved as stable.

## Scope
- Encrypt/decrypt the complete content of exactly one regular file per operation.
- For a directory, modify only its own name by appending/removing the literal **.fscrypt** suffix. Never encrypt its name cryptographically, enumerate children, or modify contents.
- Preserve original file and directory names; append/remove only the final suffix.
- Target GNU/Linux, Windows, macOS, Termux, and Android, with future extensibility.
- Use symmetric cryptography only and delegate cryptographic primitives and constructions to established, maintained libraries.
- Process files sequentially with bounded memory.
- Do not impose a fixed application-level maximum file size. Actual limits may arise from the selected format, platform APIs, filesystem, and available storage.
- Use self-contained, versioned key and encrypted-file representations.
- Publish outputs only after complete processing and authentication succeed.

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
- [Streaming cryptographic construction comparison](docs/research/streaming-cryptographic-construction-comparison.md)
- [Cross-platform cryptographic backend feasibility review](docs/research/platform-dependency-feasibility.md)
- [Open design decisions](docs/specification/open-decisions.md)

## Cryptographic direction
The previous one-invocation AES-256-GCM design is rejected because it imposes a finite per-invocation plaintext limit. Google Tink is rejected because it does not meet the project's required Termux support.

Two constructions are under evaluation:
- **libsodium XChaCha20-Poly1305 SecretStream**, through PyNaCl: the provisional preference for sequential file operations. It provides authenticated messages, sequence integrity, a final marker, automatic nonce handling/rekeying, and no practical total-stream limit documented by libsodium.
- **AEGIS-256 Random-Access File (RAF)**, through pyaegis/libaegis: a serious alternative with independently authenticated records, random-access support, and optional Merkle commitment. RAF v1 has a finite unsigned 64-bit logical-size field and uses 16-byte authentication tags.

Neither dependency has passed the complete target-platform test matrix. Termux source-build feasibility is not equivalent to a successful installation/runtime test. See the [comparison and validation plan](docs/research/streaming-cryptographic-construction-comparison.md).

Base64 is an encoding for serialization and transport; it does not protect secret key material.

## Guarantees and validation
Before claiming support, the project requires coherent specifications, automated tests, cross-platform interoperability tests, tampering/corruption/truncation tests, filesystem interruption tests, bounded-memory measurements, and reproducible demonstrations. The project does not promise secure deletion or protection against a compromised host.
