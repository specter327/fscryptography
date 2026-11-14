#!/usr/bin/env python3
"""Fast-forward update a clean fscryptography Git checkout."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        check=False,
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Update a Git checkout from its configured upstream. "
            "Local modifications and non-fast-forward updates are rejected."
        )
    )
    parser.add_argument(
        "repository",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository path (defaults to this script's project checkout)",
    )
    args = parser.parse_args()
    repository = args.repository.expanduser().resolve()

    if not repository.is_dir():
        parser.error(f"repository directory does not exist: {repository}")

    check = git(repository, "rev-parse", "--is-inside-work-tree")
    if check.returncode != 0 or check.stdout.strip() != "true":
        parser.error(f"not a Git working tree: {repository}")

    branch = git(repository, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode != 0:
        print("Refusing to update a detached HEAD.", file=sys.stderr)
        return 2

    upstream = git(
        repository,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
    )
    if upstream.returncode != 0:
        print(
            f"Refusing to update branch '{branch.stdout.strip()}': "
            "no upstream branch is configured.",
            file=sys.stderr,
        )
        return 2

    status = git(repository, "status", "--porcelain", "--untracked-files=normal")
    if status.returncode != 0:
        print(status.stderr, file=sys.stderr)
        return status.returncode
    if status.stdout.strip():
        print(
            "Refusing to update: the working tree contains local changes. "
            "Commit, stash, or otherwise preserve them before retrying.",
            file=sys.stderr,
        )
        return 2

    print(
        f"Updating {repository} ({branch.stdout.strip()} "
        f"from {upstream.stdout.strip()}) using git pull --ff-only...",
        flush=True,
    )
    result = git(repository, "pull", "--ff-only")
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
