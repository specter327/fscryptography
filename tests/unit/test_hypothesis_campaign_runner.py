"""Contract tests for the reproducible Hypothesis campaign runner."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "fuzz" / "run_hypothesis_campaign.py"
TEST_DIRECTORY = ROOT / "tests" / "unit"


def _run_campaign(work_dir: Path, test_source: str, *extra: str):
    target = work_dir / "campaign_target.py"
    target.write_text(test_source, encoding="utf-8")
    output_dir = work_dir / "artifacts"
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--duration-seconds",
            "1",
            "--output-dir",
            str(output_dir),
            "--tests",
            str(target),
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, output_dir


def test_campaign_runner_records_successful_iteration() -> None:
    with tempfile.TemporaryDirectory(
        prefix=".campaign-runner-", dir=TEST_DIRECTORY
    ) as directory:
        result, output_dir = _run_campaign(
            Path(directory),
            "def test_campaign_target():\\n    assert 2 + 2 == 4\\n",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        manifest = json.loads(
            (output_dir / "campaign.json").read_text(encoding="utf-8")
        )
        assert manifest["status"] == "completed"
        assert manifest["exit_code"] == 0
        assert manifest["iterations"]
        assert all(item["exit_code"] == 0 for item in manifest["iterations"])
        assert (output_dir / "campaign.log").is_file()
        assert all(
            (output_dir / item["log"]).is_file()
            for item in manifest["iterations"]
        )


def test_campaign_runner_stops_and_records_failure() -> None:
    with tempfile.TemporaryDirectory(
        prefix=".campaign-runner-", dir=TEST_DIRECTORY
    ) as directory:
        result, output_dir = _run_campaign(
            Path(directory),
            "def test_campaign_target():\\n"
            "    assert False, 'intentional failure'\\n",
        )

        assert result.returncode != 0
        manifest = json.loads(
            (output_dir / "campaign.json").read_text(encoding="utf-8")
        )
        assert manifest["status"] == "failed"
        assert manifest["exit_code"] != 0
        assert len(manifest["iterations"]) == 1
        log = output_dir / manifest["iterations"][0]["log"]
        assert "intentional failure" in log.read_text(encoding="utf-8")


def test_campaign_runner_refuses_to_overwrite_existing_manifest() -> None:
    with tempfile.TemporaryDirectory(
        prefix=".campaign-runner-", dir=TEST_DIRECTORY
    ) as directory:
        output_dir = Path(directory) / "artifacts"
        output_dir.mkdir()
        manifest_path = output_dir / "campaign.json"
        manifest_path.write_text(
            '{"status": "preserve"}\\n', encoding="utf-8"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--duration-seconds",
                "1",
                "--output-dir",
                str(output_dir),
                "--tests",
                "tests",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        assert "refusing to overwrite existing campaign" in result.stderr
        assert manifest_path.read_text(encoding="utf-8") == (
            '{"status": "preserve"}\\n'
        )
