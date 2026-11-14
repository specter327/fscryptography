#!/usr/bin/env python3
"""Run the existing Hypothesis suite repeatedly and preserve campaign evidence.

This is a long-running Hypothesis campaign runner, not coverage-guided fuzzing.
It uses only the Python standard library and works on supported Python versions
on GNU/Linux and Windows.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def command_output(command: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=24 * 60 * 60,
        help="Target campaign duration (default: 86400 seconds).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/fuzz"),
        help="Directory for the manifest and per-iteration logs.",
    )
    parser.add_argument(
        "--tests",
        default="tests",
        help="Pytest target (default: tests).",
    )
    args = parser.parse_args()

    if args.duration_seconds < 1:
        parser.error("--duration-seconds must be greater than zero")

    root = Path.cwd().resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "campaign.json"
    if manifest_path.exists():
        parser.error(f"refusing to overwrite existing campaign: {manifest_path}")

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--hypothesis-show-statistics",
        args.tests,
    ]
    manifest: dict[str, Any] = {
        "started_at": utc_now(),
        "target_duration_seconds": args.duration_seconds,
        "working_directory": str(root),
        "git_commit": command_output(["git", "rev-parse", "HEAD"], root),
        "git_status_porcelain": command_output(
            ["git", "status", "--porcelain"], root
        ),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version,
        "pytest": package_version("pytest"),
        "hypothesis": package_version("hypothesis"),
        "fscryptography": package_version("fscryptography"),
        "command": command,
        "iterations": [],
        "status": "running",
    }
    write_json(manifest_path, manifest)

    deadline = time.monotonic() + args.duration_seconds
    campaign_log = output_dir / "campaign.log"
    iteration = 0
    exit_code = 0

    with campaign_log.open("a", encoding="utf-8") as summary:
        summary.write(
            f"campaign_started={manifest['started_at']}\n"
            f"target_duration_seconds={args.duration_seconds}\n"
            f"git_commit={manifest['git_commit']}\n"
            f"command={command!r}\n"
        )
        summary.flush()

        while time.monotonic() < deadline:
            iteration += 1
            started_at = utc_now()
            log_path = output_dir / f"run-{iteration:04d}.log"
            print(f"[campaign] iteration {iteration}: {started_at}", flush=True)

            with log_path.open("w", encoding="utf-8") as log:
                log.write(f"started_at={started_at}\ncommand={command!r}\n\n")
                log.flush()
                try:
                    result = subprocess.run(
                        command,
                        cwd=root,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                    exit_code = result.returncode
                except OSError as exc:
                    log.write(f"\nrunner_error={exc!r}\n")
                    exit_code = 127

            finished_at = utc_now()
            record = {
                "iteration": iteration,
                "started_at": started_at,
                "finished_at": finished_at,
                "exit_code": exit_code,
                "log": log_path.name,
            }
            manifest["iterations"].append(record)
            summary.write(
                f"iteration={iteration} exit_code={exit_code} "
                f"started_at={started_at} finished_at={finished_at} "
                f"log={log_path.name}\n"
            )
            summary.flush()
            write_json(manifest_path, manifest)

            if exit_code != 0:
                print(
                    f"[campaign] failed in iteration {iteration}; "
                    f"see {log_path}",
                    file=sys.stderr,
                    flush=True,
                )
                break

    manifest["finished_at"] = utc_now()
    manifest["effective_duration_seconds"] = round(
        time.monotonic() - (deadline - args.duration_seconds), 3
    )
    manifest["status"] = "failed" if exit_code else "completed"
    manifest["exit_code"] = exit_code
    write_json(manifest_path, manifest)

    print(
        f"[campaign] {manifest['status']}; "
        f"{iteration} iteration(s); evidence: {output_dir}",
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
