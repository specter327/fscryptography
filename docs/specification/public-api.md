# Public API contract

**Status:** intended API shape; exact types, exceptions, and compatibility guarantees are pending.

## 1. Key creation

### Random key

```python
secret_key = fscryptography.key.generate()
```

Creates a cryptographically random symmetric secret key. The key is portable and serializable in the library's versioned Base64 representation.

### Password-derived key

```python
secret_key = fscryptography.key.derive(password="...")
```

Derives a reusable key deterministically from a password. The derivation profile is part of the serialized key representation or otherwise unambiguously identified by it. Password encoding, normalization, and derivation parameters must be specified before implementation.

## 2. Manager

```python
manager = fscryptography.Manager(key=secret_key)
```

Creates a cryptographic context bound to the supplied key. The manager exposes specialized file and directory operations that inherit this context. Consumers do not instantiate low-level cryptographic engines or internal handlers.

## 3. File operations

```python
manager.file.encrypt(filepath="...")
manager.file.decrypt(filepath="...")
manager.file.is_encrypted(filepath="...") -> bool
manager.file.verify_integrity(filepath="...") -> bool
```

- `encrypt`: encrypts the complete content of one regular file and appends `.fscrypt` to its name.
- `decrypt`: authenticates and decrypts one encrypted file and removes the final `.fscrypt` suffix.
- `is_encrypted`: checks whether the target is recognized as a file in the library's encrypted format. It must not infer encryption from the suffix alone.
- `verify_integrity`: authenticates the complete encrypted file. It must not trust the filename suffix. A successful result means the complete resource passed the selected format's authentication checks.

No public file operation exposes live file handles, plaintext/ciphertext streams, or generic read/write functionality.

## 4. Directory operations

```python
manager.dir.encrypt(dirpath="...")
manager.dir.decrypt(dirpath="...")
manager.dir.is_encrypted(dirpath="...") -> bool
```

- `encrypt`: renames one directory by appending `.fscrypt`.
- `decrypt`: renames one directory by removing its final `.fscrypt` suffix.
- `is_encrypted`: checks the suffix convention only.

There is no `manager.dir.verify_integrity()` method. Directory operations do not cryptographically transform or authenticate directory contents.

## 5. Naming and behavior invariants

- The original basename and extension are preserved.
- Only the final `.fscrypt` suffix is added or removed.
- Exactly one resource is targeted per call.
- Directory children are never traversed or modified.
- Existing destinations must not be silently overwritten.
- Failed operations must not leave a partial output presented as complete.

## 6. Pending API details

Before implementation, specify:

- Return values for mutating operations.
- Exception hierarchy and error codes.
- Whether `is_encrypted` reports format recognition or a narrower structural validation result.
- Exact behavior for symlinks, hard links, special files, permissions, and concurrent modification.
- Collision handling and overwrite policy.
- Key object type, serialization methods, and validation behavior.
- Password input type and normalization policy.

These details must be resolved without exposing internal providers or implementation components as public dependencies.
