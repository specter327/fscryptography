# Functional specification

**Status:** requirements baseline. This document defines externally observable behavior; implementation details are specified separately.

## 1. Purpose
Provide a focused library for encrypting/decrypting individual stored files and reversibly changing individual directory names by a suffix convention. Operations target real filesystem resources on ordinary storage volumes. This is not a general-purpose filesystem manager, archive tool, recursive encryptor, or live encrypted filesystem.

## 2. Resource model
A resource is exactly one of:
- A regular file.
- A directory.

Each public operation receives one target path and acts only on that target. No operation accepts a collection, performs recursive traversal, or implicitly processes children.

## 3. File behavior
File encryption cryptographically protects the complete file content. It does **not** encrypt, conceal, hash-replace, or otherwise transform the original filename or extension.
- Encryption appends the literal suffix **.fscrypt** to the complete original name.
- Decryption authenticates and restores the original content, then removes exactly the final suffix.
- Examples: file1.txt → file1.txt.fscrypt; archive.tar.gz → archive.tar.gz.fscrypt.

The original basename and extension remain visible. Filename confidentiality is explicitly out of scope.

## 4. Directory behavior
Directory operations change only the name of the selected directory entry:
- dir1/ → dir1.fscrypt/
- dir1.fscrypt/ → dir1/

This is a rename operation, not cryptographic encryption of the directory name. No directory contents, child names, metadata, or descendants are encrypted, decrypted, traversed, or modified.

There is deliberately no dir.verify_integrity(). A suffix cannot establish that a directory was previously renamed by this library, and the directory contents are outside the cryptographic operation.

## 5. Naming rules
- The suffix is exactly .fscrypt, including the leading period.
- Encryption appends the suffix; it never replaces the original extension or basename.
- Decryption removes only the final suffix.
- The original name remains visible.
- A name that already ends in .fscrypt must not be suffixed again.
- A name without the suffix is not a valid decryption target.
- Destination collisions and platform filename-length limits must be detected before publication.
- The suffix is a naming convention, not proof of encryption, authenticity, or integrity.

## 6. Key modes
### 6.1 Random secret key
The library generates a random symmetric secret key. Security depends on possession of that key. The same key can encrypt and decrypt compatible resources.

### 6.2 Password-derived secret key
The library derives a symmetric secret key from a caller-supplied password. The intended behavior is deterministic and reusable: the same password under the same stable derivation profile yields the same key.

The derivation profile, domain separation, password encoding/normalization, and resistance to offline guessing must be specified before implementation. Determinism must not be achieved by silently choosing weak parameters.

## 7. Operational characteristics
- Cold, whole-resource operations only: encrypt or decrypt a stored file.
- No public live encrypted-file interface and no public open/read/write/stream API.
- Internally, bounded sequential I/O is permitted to process large files.
- Block size is configurable within documented limits; proposed default: 1 MiB.
- Encrypted file data and serialized keys must be self-contained, versioned, and portable.
- Key serialization uses Base64 for convenient handling; Base64 is not encryption.
- Cryptographic primitives and secure streaming constructions are delegated to established, maintained implementations.

## 8. Integrity and failure behavior
Encrypted file content must be authenticated. Modifications, corruption, invalid framing, missing/reordered/duplicated blocks, and truncation must be detected.

Integrity verification must process and authenticate the complete encrypted file; checking its suffix or header alone is insufficient.

The public contract must distinguish invalid/unauthentic content from operational failures such as permission and I/O errors. Exact exception types and return semantics remain to be finalized.

## 9. Platform scope
Initial targets: GNU/Linux, Windows, macOS, Termux, and Android.

Compatibility means both that the library operates in each environment and that encrypted files and serialized keys interoperate between environments. Termux and native Android environments require separate validation. Future platforms may be added without changing the public conceptual model.

## 10. Explicit non-goals
- Recursive encryption/decryption.
- Batch or multi-resource operations.
- Cryptographic encryption of file or directory names.
- Encryption of directory contents through directory operations.
- Filename confidentiality.
- Live encrypted-file access, filesystem mounts, or transparent/on-the-fly encryption.
- Asymmetric cryptography.
- Implementing cryptographic primitives in this project.
