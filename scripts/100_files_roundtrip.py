#!/usr/bin/env python3
"""End-to-end demonstration: generate, encrypt, decrypt and verify 100 files.

Run from a checkout of the repository:
    python scripts/100_files_roundtrip.py
    python scripts/100_files_roundtrip.py --count 250 --keep-workspace

The test uses disposable data. It never downloads remote files and never
operates on files outside its newly-created workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import shutil
import string
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import fscryptography


TEXT_EXTENSIONS = {".txt", ".json", ".csv", ".py", ".html", ".xml", ".md"}
BINARY_PREFIXES = {
    ".pdf": b"%PDF-1.7\n% fscryptography integration fixture\n",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff\xe0",
    ".zip": b"PK\x03\x04",
    ".wav": b"RIFF\x00\x00\x00\x00WAVE",
    ".bin": b"FSCRYPTOGRAPHY-BINARY-FIXTURE\x00",
    ".dat": b"FSCRYPTOGRAPHY-DATA-FIXTURE\x00",
}
EXTENSIONS = (
    ".txt", ".json", ".csv", ".py", ".html", ".xml", ".md",
    ".pdf", ".png", ".jpg", ".zip", ".wav", ".bin", ".dat",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def random_text(rng: random.Random, index: int) -> bytes:
    alphabet = string.ascii_letters + string.digits + " áéíóú ñ,.;:-_\n"
    lines = [
        f"fscryptography integration fixture {index}",
        "".join(rng.choice(alphabet) for _ in range(rng.randint(80, 500))),
        f"random-record={rng.getrandbits(128):032x}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def fixture_bytes(extension: str, index: int, rng: random.Random) -> bytes:
    """Build varied fixtures; binary fixtures carry format signatures only."""
    if extension in TEXT_EXTENSIONS:
        return random_text(rng, index)

    prefix = BINARY_PREFIXES.get(extension, b"")
    body = os.urandom(rng.randint(256, 8192))
    return prefix + body


def create_fixtures(root: Path, count: int, seed: int) -> list[Path]:
    rng = random.Random(seed)
    directories = [root / "source" / f"folder-{number:02d}" for number in range(10)]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for index in range(count):
        directory = directories[index % len(directories)]
        extension = EXTENSIONS[index % len(EXTENSIONS)]
        path = directory / f"sample-{index + 1:03d}{extension}"
        path.write_bytes(fixture_bytes(extension, index + 1, rng))
        created.append(path)
    return created


def print_transition(stage: str, source: Path, destination: Path, size: int, digest: str) -> None:
    print(
        f"[{stage}] {source.name} -> {destination.name} "
        f"| {size:>7,} bytes | sha256 {digest[:16]}…"
    )


def encrypt_all(manager, originals: Iterable[Path]) -> list[Path]:
    encrypted: list[Path] = []
    for index, source in enumerate(originals, start=1):
        size = source.stat().st_size
        digest = sha256(source)
        expected = source.with_name(source.name + ".fscrypt")

        manager.file.encrypt(source)

        if source.exists():
            raise RuntimeError(f"El origen no fue retirado después del cifrado: {source}")
        if not expected.is_file():
            raise RuntimeError(f"No se publicó el archivo cifrado esperado: {expected}")

        encrypted.append(expected)
        print_transition(f"ENCRYPT {index:03d}/ {len(originals):03d}", source, expected, size, digest)
    return encrypted


def decrypt_all(manager, encrypted: Iterable[Path], expected_hashes: dict[str, str]) -> int:
    verified = 0
    items = list(encrypted)
    for index, ciphertext in enumerate(items, start=1):
        restored = ciphertext.with_name(ciphertext.name.removesuffix(".fscrypt"))
        manager.file.decrypt(ciphertext)

        if ciphertext.exists():
            raise RuntimeError(f"El ciphertext no fue retirado después del descifrado: {ciphertext}")
        if not restored.is_file():
            raise RuntimeError(f"No se restauró el archivo esperado: {restored}")

        actual_hash = sha256(restored)
        expected_hash = expected_hashes[str(restored)]
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"SHA-256 no coincide para {restored}: "
                f"esperado={expected_hash}, obtenido={actual_hash}"
            )

        verified += 1
        print_transition(
            f"DECRYPT {index:03d}/{len(items):03d}",
            ciphertext,
            restored,
            restored.stat().st_size,
            actual_hash,
        )
    return verified


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera archivos desechables y prueba el round-trip de fscryptography."
    )
    parser.add_argument("--count", type=int, default=100, help="Número de archivos (por defecto: 100).")
    parser.add_argument("--seed", type=int, default=20261114, help="Semilla para los fixtures de texto.")
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Conservar el directorio de prueba después de finalizar.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Directorio vacío donde crear el entorno desechable.",
    )
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count debe ser mayor que cero.")
    if args.workspace is not None and args.workspace.exists() and any(args.workspace.iterdir()):
        parser.error("--workspace debe no existir o estar vacío.")
    return args


def main() -> int:
    args = parse_args()
    temporary_workspace = False
    failed = False

    if args.workspace is not None:
        workspace = args.workspace.expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
    elif args.keep_workspace:
        workspace = Path(tempfile.mkdtemp(prefix="fscryptography-100-files-"))
    else:
        temporary_workspace = True
        workspace = Path(tempfile.mkdtemp(prefix="fscryptography-100-files-"))

    try:
        print("=" * 78)
        print("FSCRYPTOGRAPHY · 100-FILE FILESYSTEM ROUND-TRIP")
        print(f"Version: {fscryptography.__version__}")
        print(f"Workspace: {workspace}")
        print(f"Files: {args.count} | directories: 10 | seed: {args.seed}")
        print("=" * 78)

        originals = create_fixtures(workspace, args.count, args.seed)
        expected_hashes = {str(path): sha256(path) for path in originals}
        total_bytes = sum(path.stat().st_size for path in originals)
        print(f"\n[GENERATED] {len(originals)} files across 10 directories ({total_bytes:,} bytes)")
        for extension in sorted({path.suffix for path in originals}):
            print(f"  {extension or '[no extension]'}: {sum(p.suffix == extension for p in originals)}")

        # Keep the key only in memory; never write it to the workspace or logs.
        master_key = fscryptography.generate()
        with fscryptography.Manager(key=master_key) as manager:
            print("\n--- PHASE 1: PLAINTEXT -> CIPHERTEXT ---")
            encrypted = encrypt_all(manager, originals)

            print("\n--- PHASE 2: CIPHERTEXT -> PLAINTEXT ---")
            verified = decrypt_all(manager, encrypted, expected_hashes)

        leftovers = list(workspace.rglob("*.fscrypt"))
        if leftovers:
            raise RuntimeError(f"Quedaron {len(leftovers)} archivos cifrados inesperados.")

        print("\n" + "=" * 78)
        print("RESULTADO")
        print(f"  Archivos generados:       {len(originals)}")
        print(f"  Archivos cifrados:        {len(encrypted)}")
        print(f"  Archivos descifrados:     {verified}")
        print(f"  SHA-256 coincidentes:     {verified}/{len(originals)}")
        print(f"  Bytes de plaintext:       {total_bytes:,}")
        print(f"  Ciphertexts pendientes:   {len(leftovers)}")
        print("  Estado:                   PASS")
        if args.keep_workspace or args.workspace is not None:
            print(f"  Workspace conservado:     {workspace}")
        else:
            print("  Workspace temporal:       se eliminará al terminar")
        print("=" * 78)
        return 0

    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"Workspace para inspección: {workspace}", file=sys.stderr)
        failed = True
        return 1
    finally:
        if temporary_workspace and not failed:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
