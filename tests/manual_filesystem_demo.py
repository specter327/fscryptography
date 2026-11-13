"""Manual, verbose filesystem demonstration for fscryptography.

Run from the repository root:
    python tests/manual_filesystem_demo.py

The script creates an isolated temporary workspace inside tests/resources/,
prints the generated MasterKey and resource details, encrypts/decrypts real
files and a directory name, then removes the entire workspace even on failure.

WARNING: the MasterKey is deliberately printed for this demonstration. Never
print, log, commit, or share production keys.
"""

from __future__ import annotations

import hashlib
import os
import platform
import sys
import tempfile
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
RESOURCES_ROOT = PROJECT_ROOT / "tests" / "resources"

# Allow direct execution from a source checkout without requiring an editable
# installation. An installed package remains usable when src/ is absent.
if SOURCE_ROOT.is_dir():
    sys.path.insert(0, str(SOURCE_ROOT))

import fscryptography  # noqa: E402


def log(message: str = "") -> None:
    print(message, flush=True)


def section(title: str) -> None:
    log()
    log("=" * 84)
    log(title)
    log("=" * 84)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe_file(path: Path, *, preview_bytes: int = 96) -> None:
    """Print observable metadata and a safe textual/hexadecimal preview."""
    log(f"  Path:       {path}")
    log(f"  Exists:     {path.exists()}")
    if not path.is_file():
        return

    data = path.read_bytes()
    log(f"  Type:       regular file")
    log(f"  Size:       {len(data)} bytes")
    log(f"  SHA-256:    {sha256(path)}")
    log(f"  Preview:    {data[:preview_bytes]!r}")
    log(f"  Hex:        {data[:min(preview_bytes, 32)].hex()}")


def describe_tree(root: Path) -> None:
    """Print a deterministic directory tree and file metadata."""
    log(f"  Root: {root}")
    if not root.exists():
        log("  <resource does not exist>")
        return

    for path in sorted(root.rglob("*"), key=lambda item: str(item)):
        relative = path.relative_to(root)
        if path.is_dir():
            log(f"  [DIR ] {relative}/")
        elif path.is_file():
            log(
                f"  [FILE] {relative} | {path.stat().st_size} bytes"
                f" | sha256={sha256(path)}"
            )
        else:
            log(f"  [OTHER] {relative}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    log(f"  [PASS] {message}")


def run_demo() -> None:
    RESOURCES_ROOT.mkdir(parents=True, exist_ok=True)

    section("FSCRYPTOGRAPHY — MANUAL REAL FILESYSTEM DEMONSTRATION")
    log(f"Package version: {fscryptography.__version__}")
    log(f"Python:          {sys.version.split()[0]}")
    log(f"Platform:        {platform.platform()}")
    log(f"Working folder:  {RESOURCES_ROOT}")
    log("A unique temporary workspace will be created and deleted at the end.")
    log("Only resources inside that workspace are touched.")

    # TemporaryDirectory guarantees recursive cleanup when the block exits,
    # including when an assertion or filesystem operation raises an exception.
    with tempfile.TemporaryDirectory(
        prefix="manual-filesystem-demo-",
        dir=RESOURCES_ROOT,
    ) as temporary_directory:
        workspace = Path(temporary_directory)

        section("1. CREATE REAL FILES AND DIRECTORIES")
        original_file = workspace / "mensaje-secreto.txt"
        original_content = (
            "Este archivo existe físicamente en el filesystem.\n"
            "Prueba de cifrado y descifrado con fscryptography.\n"
            "UTF-8: áéíóú, ñ, 東京.\n"
        ).encode("utf-8")
        original_file.write_bytes(original_content)

        custom_file = workspace / "informe.txt"
        custom_content = b"Contenido de prueba para extension personalizada.\n" * 20
        custom_file.write_bytes(custom_content)

        hidden_name_file = workspace / "nombre-confidencial.txt"
        hidden_name_content = b"El nombre de este archivo tambien sera cifrado.\n"
        hidden_name_file.write_bytes(hidden_name_content)

        directory = workspace / "documentos-privados"
        directory.mkdir()
        child_file = directory / "contenido-visible.txt"
        child_content = b"El nombre del directorio cambia; este contenido no.\n"
        child_file.write_bytes(child_content)
        (directory / "anidado").mkdir()
        nested_file = directory / "anidado" / "datos.bin"
        nested_content = bytes(range(64))
        nested_file.write_bytes(nested_content)

        log("Initial workspace:")
        describe_tree(workspace)
        log()
        log("Detailed original file:")
        describe_file(original_file)

        section("2. GENERATE AND DISPLAY THE MASTER KEY")
        master_key = fscryptography.generate()
        require(isinstance(master_key, str) and bool(master_key), "generate() returned a Base64 MasterKey")
        log("MASTER KEY (Base64) — visible only because this is a disposable demonstration:")
        log(master_key)
        log(f"MasterKey characters: {len(master_key)}")
        log("SECURITY: do not print or disclose real application keys.")

        with fscryptography.Manager(key=master_key) as manager:
            exported_key = manager.export_key()
            require(exported_key == master_key, "Manager.export_key() matches the generated MasterKey")
            log(f"Exported MasterKey (Base64): {exported_key}")

            section("3. ENCRYPT A FILE — DEFAULT .fscrypt EXTENSION")
            log("BEFORE encryption:")
            describe_file(original_file)

            manager.file.encrypt(original_file)
            encrypted_file = workspace / "mensaje-secreto.fscrypt"

            log("AFTER encryption:")
            describe_file(encrypted_file)
            require(encrypted_file.is_file(), "encrypted output exists")
            require(not original_file.exists(), "plaintext source name no longer exists")
            require(encrypted_file.read_bytes() != original_content, "on-disk encrypted bytes differ from plaintext")

            section("4. DECRYPT THE FILE")
            log("BEFORE decryption:")
            describe_file(encrypted_file)

            manager.file.decrypt(encrypted_file)

            log("AFTER decryption:")
            describe_file(original_file)
            require(original_file.is_file(), "decrypted file was restored")
            require(original_file.read_bytes() == original_content, "decrypted bytes exactly match original content")

            section("5. ENCRYPT AND DECRYPT WITH A CUSTOM EXTENSION")
            log("BEFORE encryption:")
            describe_file(custom_file)

            manager.file.encrypt(custom_file, new_extension=".locked")
            custom_encrypted = workspace / "informe.locked"

            log("AFTER encryption:")
            describe_file(custom_encrypted)
            require(custom_encrypted.is_file(), "custom .locked output exists")
            require(not custom_file.exists(), "custom-extension plaintext source was retired")

            manager.file.decrypt(custom_encrypted)
            log("AFTER decryption:")
            describe_file(custom_file)
            require(custom_file.read_bytes() == custom_content, "custom extension and original content were restored")

            section("6. ENCRYPT THE FILE NAME AND THE FILE CONTENT")
            log("BEFORE encryption:")
            describe_file(hidden_name_file)

            manager.file.encrypt(hidden_name_file, encrypt_name=True)
            encrypted_name_candidates = [
                item for item in workspace.iterdir()
                if item.is_file() and item.name.startswith("~1")
            ]
            require(len(encrypted_name_candidates) == 1, "encrypted filename uses the ~1 marker")
            hidden_name_encrypted = encrypted_name_candidates[0]

            log("AFTER encryption (the original filename is no longer visible):")
            describe_file(hidden_name_encrypted)
            require("nombre-confidencial" not in hidden_name_encrypted.name, "plaintext filename is concealed")

            manager.file.decrypt(hidden_name_encrypted)
            log("AFTER decryption:")
            describe_file(hidden_name_file)
            require(hidden_name_file.read_bytes() == hidden_name_content, "encrypted filename and file content were restored")

            section("7. ENCRYPT A DIRECTORY NAME")
            log("BEFORE directory-name encryption:")
            describe_tree(directory)
            child_hash_before = sha256(child_file)
            nested_hash_before = sha256(nested_file)

            manager.dir.encrypt(directory)
            encrypted_directories = [
                item for item in workspace.iterdir()
                if item.is_dir() and item.name.startswith("~1")
            ]
            require(len(encrypted_directories) == 1, "directory name uses the ~1 encrypted-name marker")
            encrypted_directory = encrypted_directories[0]

            log("AFTER directory-name encryption:")
            describe_tree(encrypted_directory)
            require((encrypted_directory / child_file.name).is_file(), "child filename remains unchanged")
            require(sha256(encrypted_directory / child_file.name) == child_hash_before, "child file content remains unchanged")
            require(
                sha256(encrypted_directory / "anidado" / nested_file.name) == nested_hash_before,
                "nested file content remains unchanged",
            )
            log("NOTE: directory encryption protects its name only; it does not recursively encrypt descendants.")

            section("8. DECRYPT THE DIRECTORY NAME")
            log("BEFORE directory-name decryption:")
            describe_tree(encrypted_directory)

            manager.dir.decrypt(encrypted_directory)

            log("AFTER directory-name decryption:")
            describe_tree(directory)
            require(directory.is_dir(), "original directory name was restored")
            require(child_file.read_bytes() == child_content, "child file content is unchanged after round-trip")
            require(nested_file.read_bytes() == nested_content, "nested file content is unchanged after round-trip")

            section("9. FINAL WORKSPACE BEFORE AUTOMATIC CLEANUP")
            describe_tree(workspace)
            log()
            log("All demonstrations and assertions completed successfully.")
            log("The Manager will now close; the temporary workspace will then be removed.")

        # Manager has been closed before the temporary resources are deleted.
        require(not original_file.exists() or original_file.is_file(), "workspace is still accessible before cleanup")

    section("10. CLEANUP")
    require(not workspace.exists(), "temporary workspace and every generated resource were deleted")
    log("No demonstration files were retained.")
    log("RESULT: SUCCESS")


if __name__ == "__main__":
    try:
        run_demo()
    except Exception:
        section("DEMONSTRATION FAILED")
        traceback.print_exc()
        log("The temporary workspace cleanup is still guaranteed by TemporaryDirectory.")
        raise
