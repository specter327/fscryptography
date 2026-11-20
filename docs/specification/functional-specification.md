# Functional specification

**Status:** initial requirements baseline  
**Scope:** externally observable behavior; implementation details are intentionally separated.

## 1. Purpose

Provide a focused library for encrypting and decrypting individual stored files and for reversibly marking individual directory names. Operations target real filesystem resources on ordinary storage volumes. The library is not a general-purpose filesystem manager, archive tool, recursive encryptor, or live encrypted filesystem.

## 2. Resource model

A resource is exactly one of:

- A regular file.
- A directory.

Each public operation receives one target path and acts only on that target. No operation accepts a collection of resources, performs recursive traversal, or implicitly processes children.

### 2.1 Files

Encryption protects the file content. It does not encrypt, hash-replace, or otherwise transform the original filename or extension. The output name is the original name with the literal suffix `.fscrypt` appended.

Examples:

- `file1.txt` → `file1.txt.fscrypt`
- `archive.tar.gz` → `archive.tar.gz.fscrypt`

Decryption authenticates and restores the original content, then removes exactly the final `.fscrypt` suffix from the output name.

### 2.2 Directories

Directory operations affect only the directory's own name:

- `dir1/` → `dir1.fscrypt/`
- `dir1.fscrypt/` → `dir1/`

No directory contents, child names, metadata, or descendants are encrypted, decrypted, traversed, or modified by these operations. A directory operation is a filesystem rename, not cryptographic protection of directory data.

There is deliberately no `dir.verify_integrity()` operation. A suffix cannot establish that a directory was previously renamed by this library, and the directory contents are outside the cryptographic operation.

## 3. Naming rules

- The suffix is exactly `.fscrypt`, including the leading period.
- Encryption appends the suffix; it never replaces the original extension or basename.
- Decryption removes only the final suffix.
- The original name remains visible.
- A name that already has the suffix must not be silently suffixed again.
- A name without the suffix is not a valid decryption target.
- Destination collisions and platform filename-length limits must be detected before publishing output.

The suffix is a naming convention, not proof of encryption, authenticity, or integrity.

## 4. Operating modes

### 4.1 Random secret key

The library generates a random symmetric secret key. Security depends on possession of that key. The same key can encrypt and decrypt compatible resources.

### 4.2 Password-derived secret key

The library derives a symmetric secret key from a caller-supplied password. The intended behavior is deterministic and reusable: the same password under the same stable derivation profile yields the same key.

The derivation profile, domain separation, password encoding/normalization, and resistance to offline guessing must be specified before implementation. Determinism must not be achieved by silently choosing weak parameters.

## 5. Operational characteristics

- Cold, whole-resource operations only: encrypt or decrypt a stored file.
- No public live encrypted-file interface and no public `open`, `read`, `write`, or streaming API.
- Internally, implementations may use bounded sequential I/O to process large files.
- Block size is configurable within documented limits; the proposed default is 1 MiB.
- Encrypted file data must be self-contained and portable between supported platforms.
- Key serialization must be self-contained, versioned, and Base64 encoded for convenient handling.
- The library delegates cryptographic primitives to established, maintained, tested implementations.

## 6. Integrity and failure behavior

Encrypted file content must be authenticated. Modifications, corruption, invalid framing, missing blocks, reordered blocks, and truncation must be detected.

Integrity verification must process and authenticate the complete file; checking its suffix or header alone is insufficient.

The public contract must distinguish invalid/unauthentic content from operational failures such as permission errors and I/O failures. Exact exception types and return semantics remain to be finalized in the API specification.

## 7. Platform scope

Initial targets:

- GNU/Linux
- Windows
- macOS
- Termux
- Android

Compatibility means both that the library can operate in each environment and that encrypted files and serialized keys are interoperable between environments. Termux and native Android environments require separate validation. Future platforms may be added without changing the public conceptual model.

## 8. Explicit non-goals

- Recursive encryption or decryption.
- Batch or multi-resource operations.
- Encryption of directory contents through directory operations.
- Filename confidentiality.
- Live encrypted-file access, filesystem mounts, or transparent/on-the-fly encryption.
- Asymmetric cryptography.
- Implementing cryptographic primitives in this project.
- Claiming that a directory suffix provides cryptographic integrity.
