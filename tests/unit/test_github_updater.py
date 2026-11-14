"""Regression tests for the Git checkout updater."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
UPDATER = REPOSITORY_ROOT / "scripts" / "update" / "github.py"


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )


def make_checkout(repository: Path) -> None:
    repository.mkdir()
    commands = (
        ("init", "-b", "main"),
        ("config", "user.name", "fscryptography tests"),
        ("config", "user.email", "tests@example.invalid"),
        ("config", "status.showUntrackedFiles", "no"),
    )
    for command in commands:
        result = run_git(repository, *command)
        assert result.returncode == 0, result.stderr

    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    assert run_git(repository, "add", "tracked.txt").returncode == 0
    assert run_git(repository, "commit", "-m", "initial").returncode == 0

    remote = repository.parent / f"{repository.name}-remote.git"
    result = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert run_git(repository, "remote", "add", "origin", str(remote)).returncode == 0
    assert run_git(repository, "push", "-u", "origin", "main").returncode == 0


def run_updater(repository: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(UPDATER), str(repository)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_refuses_untracked_file_when_git_config_hides_untracked_files(tmp_path: Path) -> None:
    repository = tmp_path / "checkout"
    make_checkout(repository)
    untracked = repository / "secret.txt"
    untracked.write_text("must not be ignored\n", encoding="utf-8")

    result = run_updater(repository)

    assert result.returncode == 2
    assert "working tree contains local changes" in result.stderr
    assert untracked.read_text(encoding="utf-8") == "must not be ignored\n"


def test_refuses_nested_untracked_file_when_git_config_hides_untracked_files(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "checkout"
    make_checkout(repository)
    nested = repository / "untracked-directory"
    nested.mkdir()
    untracked = nested / "data.txt"
    untracked.write_text("preserve\n", encoding="utf-8")

    result = run_updater(repository)

    assert result.returncode == 2
    assert "working tree contains local changes" in result.stderr
    assert untracked.read_text(encoding="utf-8") == "preserve\n"
