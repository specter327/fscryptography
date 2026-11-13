from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from fscryptography._journal import inspect




_CRASH_EXIT = 73


@pytest.mark.parametrize(
    ("target_state", "stage", "expected_state", "expected_classification"),
    [
        ("prepared", "before", None, "corrupt"),
        ("prepared", "after", "prepared", "prepared_no_output"),
        ("result_ready", "before", "prepared", "result_incomplete_or_unverified"),
        ("result_ready", "after", "result_ready", "result_ready"),
        ("published", "before", "result_ready", "published_source_present"),
        ("published", "after", "published", "published_source_present"),
        ("source_retained", "before", "published", "source_retained"),
        ("source_retained", "after", "source_retained", "source_retained"),
        ("source_removed", "before", "source_retained", "published_source_missing"),
        ("source_removed", "after", "source_removed", "source_removed"),
        ("complete", "before", "source_removed", "source_removed"),
        ("complete", "after", "complete", "source_removed"),
    ],
)
def test_abrupt_process_exit_leaves_inspectable_transaction_state(
    tmp_path: Path,
    target_state: str,
    stage: str,
    expected_state: str | None,
    expected_classification: str,
):
    """os._exit simulates process death without finally blocks or Python cleanup."""
    parent = tmp_path / f"{target_state}-{stage}"
    parent.mkdir()
    source = parent / "payload.bin"
    payload = b"crash-recovery-payload" * 8192
    source.write_bytes(payload)

    script = r"""
import os
import sys
from pathlib import Path

import fscryptography
from fscryptography._journal import Transaction

parent = Path(sys.argv[1])
target_state = sys.argv[2]
stage = sys.argv[3]
original_persist = Transaction._persist

def crash_at_persistence(self):
    if self.data.get("state") == target_state:
        if stage == "before":
            os._exit(73)
        original_persist(self)
        os._exit(73)
    return original_persist(self)

Transaction._persist = crash_at_persistence
manager = fscryptography.Manager(fscryptography.generate())
manager.file.encrypt(parent / "payload.bin")
os._exit(0)
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(parent),
            target_state,
            stage,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == _CRASH_EXIT, (
        f"child did not stop at {target_state}/{stage}: "
        f"returncode={completed.returncode}, stderr={completed.stderr}"
    )

    first = inspect(parent)
    second = inspect(parent)
    assert first == second
    assert len(first) == 1
    record = first[0]
    assert record.classification == expected_classification
    assert record.state == expected_state

    destination = parent / "payload.fscrypt"
    if target_state in {"prepared", "result_ready"}:
        assert source.is_file()
        assert not destination.exists()
    elif target_state == "published":
        assert source.is_file()
        assert destination.is_file()
    else:
        assert not source.exists()
        assert destination.is_file()

    # Inspection must not clean up or rewrite any transaction evidence.
    transaction_dir = next(parent.glob(".fscryptography-txn-*"))
    journal = transaction_dir / "journal.json"
    journal_bytes = journal.read_bytes() if journal.exists() else None
    names_before = sorted(path.name for path in transaction_dir.iterdir())
    inspect(parent)
    assert sorted(path.name for path in transaction_dir.iterdir()) == names_before
    if journal_bytes is not None:
        assert journal.read_bytes() == journal_bytes
