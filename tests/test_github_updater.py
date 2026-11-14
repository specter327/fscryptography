"""Regression tests for the GitHub checkout updater."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPDATER = PROJECT_ROOT / "scripts" / "update" / "github.py"


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        capture_output=True,
        check=True,
    )


def create_checkout(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repository = tmp_path / "checkout"
    repository.mkdir()
    config = tmp_path / "gitconfig"
    environment = os.environ.copy()
    environment["GIT_CONFIG_GLOBAL"] = str(config)
    environment["GIT_AUTHOR_NAME"] = "Test"
    environment["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    environment["GIT_COMMITTER_NAME"] = "Test"
    environment["GIT_COMMITTER_EMAIL"] = "test@example.invalid"

    subprocess.run(
        ["git", "init", "--bare", str(tmp_path / "remote.git")],
        check=True,
        capture_output=True,
        env=environment,
    )
    run_git(repository, "init")
    run_git(repository, "config", "user.name", "Test")
    run_git(repository, "config", "user.email", "test@example.invalid")
    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    run_git(repository, "add", "tracked.txt")
    run_git(repository, "commit", "-m", "initial")
    run_git(repository, "branch", "-M", "main")
    run_git(repository, "remote", "add", "origin", str(tmp_path / "remote.git"))
    run_git(repository, "push", "-u", "origin", "main")
    return repository, environment


def run_updater(repository: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(UPDATER), str(repository)],
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def test_untracked_files_are_detected_when_git_hides_them_by_default(tmp_path: Path) -> None:
    repository, environment = create_checkout(tmp_path)
    subprocess.run(
        ["git", "config", "--global", "status.showUntrackedFiles", "no"],
        check=True,
        capture_output=True,
        env=environment,
    )
    (repository / "untracked-secret.txt").write_text("preserve me\n", encoding="utf-8")

    result = run_updater(repository, environment)

    assert result.returncode == 2
    assert "working tree contains local changes" in result.stderr


def test_tracked_modifications_are_rejected(tmp_path: Path) -> None:
    repository, environment = create_checkout(tmp_path)
    (repository / "tracked.txt").write_text("modified\n", encoding="utf-8")

    result = run_updater(repository, environment)

    assert result.returncode == 2
    assert "working tree contains local changes" in result.stderr


def test_clean_checkout_proceeds_to_fast_forward_pull(tmp_path: Path) -> None:
    repository, environment = create_checkout(tmp_path)

    result = run_updater(repository, environment)

    assert result.returncode == 0
    assert "git pull --ff-only" in result.stdout
