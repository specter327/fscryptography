# fscryptography

A cross-platform Python library for authenticated, transactional encryption and decryption of individual files, plus reversible name marking for individual directories.

> **Project status:** specification and design phase. No cryptographic format, protocol, or implementation is currently declared stable.

## Scope

- Encrypt and decrypt the **contents of one regular file per operation**.
- Encrypt and decrypt the **name of one directory per operation** by appending or removing the `.fscrypt` suffix. Directory contents are never traversed or modified.
- Preserve original file and directory names; append or remove only the `.fscrypt` suffix.
- Support GNU/Linux, Windows, macOS, Termux, and Android, with room for future platforms.
- Use symmetric cryptography through established, maintained cryptographic implementations. The library will not implement cryptographic primitives.
- Process files sequentially in configurable blocks, with a default block size of 1 MiB.
- Authenticate encrypted file content and keep the data required for portability inside the encrypted resource.
- Publish completed results transactionally: incomplete output must never be presented as a completed encrypted or decrypted resource.

## API direction

```python
random_secret_key = fscryptography.key.generate()
password_secret_key = fscryptography.key.derive(password="...")
manager = fscryptography.Manager(key=random_secret_key)

manager.file.encrypt(filepath="...")
manager.file.decrypt(filepath="...")
manager.file.is_encrypted(filepath="...")
manager.file.verify_integrity(filepath="...")

manager.dir.encrypt(dirpath="...")
manager.dir.decrypt(dirpath="...")
manager.dir.is_encrypted(dirpath="...")
```

The API above is the intended public direction, not yet a released compatibility contract. In particular, `dir.is_encrypted()` identifies the suffix convention; it cannot prove that a directory was previously processed by this library. File integrity verification authenticates the complete file content and does not trust the suffix.

## Naming convention

| Resource | Before encryption | After encryption |
|---|---|---|
| File | `file1.txt` | `file1.txt.fscrypt` |
| Directory | `dir1/` | `dir1.fscrypt/` |

Decryption removes only the final `.fscrypt` suffix. Original names and extensions remain visible; filename confidentiality is explicitly out of scope.

## Documentation

- [Functional specification](docs/specification/functional-specification.md)
- [Public API contract](docs/specification/public-api.md)
- [Filesystem and transaction behavior](docs/specification/filesystem-behavior.md)
- [Cryptographic design requirements](docs/specification/cryptographic-requirements.md)
- [Streaming encryption construction review](docs/research/streaming-encryption-review.md)
- [Open design decisions](docs/specification/open-decisions.md)

## Security status

The current cryptographic requirement is AES-256-GCM, but the project now prefers evaluating an established Streaming AEAD construction (Tink AES-256-GCM-HKDF 1 MiB profile) rather than designing its own block protocol. This remains conditional on proving dependency and API support across all target platforms. No wire format or dependency is approved yet. See the [construction review](docs/research/streaming-encryption-review.md).

Base64 is an encoding for convenient serialization and transport. It does not protect or conceal key material: anyone who obtains a serialized secret key can use it.

## Project guarantees

The project will require documented behavior, format/version specifications, automated tests, interoperability tests across supported platforms, corruption/tampering tests, and demonstrations before claiming a capability is supported.
