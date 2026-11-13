from __future__ import annotations

import os

import pytest

from fscryptography._journal import Transaction, inspect


def _transaction(tmp_path, operation="file_encrypt"):
    source = tmp_path / ("source" if operation.startswith("file_") else "source-dir")
    if operation.startswith("file_"):
        source.write_bytes(b"source")
    else:
        source.mkdir()
    destination = tmp_path / ("destination" if operation.startswith("file_") else "destination-dir")
    return source, destination, Transaction.begin(
        tmp_path, operation, source.name, destination.name, source.lstat()
    )


def test_inspection_reports_prepared_transaction_without_mutation(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    before = sorted(path.name for path in tmp_path.iterdir())

    records = inspect(tmp_path)

    assert len(records) == 1
    assert records[0].classification == "prepared_no_output"
    assert records[0].state == "prepared"
    assert source.read_bytes() == b"source"
    assert not destination.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_inspection_recognizes_verified_result_ready(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    transaction.result_path.write_bytes(b"encrypted-result")
    with transaction.result_path.open("ab") as stream:
        stream.flush()
        os.fsync(stream.fileno())
    transaction.set_result_ready(transaction.result_path.lstat())

    record = inspect(tmp_path)[0]

    assert record.classification == "result_ready"
    assert source.exists()
    assert not destination.exists()


def test_inspection_recognizes_published_result_and_source_removal(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    transaction.result_path.write_bytes(b"encrypted-result")
    transaction.set_result_ready(transaction.result_path.lstat())
    os.rename(transaction.result_path, destination)
    transaction.set_state("published")

    record = inspect(tmp_path)[0]
    assert record.classification == "published_source_present"

    source.unlink()
    transaction.set_state("source_removed")
    transaction.set_state("complete")

    record = inspect(tmp_path)[0]
    assert record.classification == "source_removed"
    assert record.state == "complete"


def test_directory_rename_is_inspected_by_identity(tmp_path):
    source, destination, transaction = _transaction(tmp_path, "dir_encrypt")
    identity = (source.stat().st_dev, source.stat().st_ino)
    os.rename(source, destination)
    transaction.set_state("published")

    record = inspect(tmp_path)[0]

    assert record.classification == "published_source_missing"
    assert (destination.stat().st_dev, destination.stat().st_ino) == identity


def test_corrupt_journal_is_reported_without_mutation(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    journal = transaction.directory / "journal.json"
    journal.write_bytes(b'{"format":1,"format":1}')
    before = journal.read_bytes()

    record = inspect(tmp_path)[0]

    assert record.classification == "corrupt"
    assert journal.read_bytes() == before
    assert source.exists()


def test_symlink_journal_is_never_followed(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    journal = transaction.directory / "journal.json"
    journal.unlink()
    target = tmp_path / "outside.json"
    target.write_text("{}", encoding="utf-8")
    try:
        journal.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    record = inspect(tmp_path)[0]

    assert record.classification == "corrupt"
    assert target.read_text(encoding="utf-8") == "{}"


def test_identity_mismatch_is_ambiguous(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"other")
    replacement.replace(source)

    record = inspect(tmp_path)[0]

    assert record.classification == "ambiguous"
    assert source.exists()
    assert source.read_bytes() == b"other"


def test_inspection_result_is_immutable(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    record = inspect(tmp_path)[0]

    with pytest.raises((AttributeError, TypeError)):
        record.state = "complete"


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"{",
        b'{"format":1,"format":1}',
        b'{"format":2}',
        b'{"format":NaN}',
        b"\xef\xbb\xbf{}",
        b"{}\n",
    ],
)
def test_malformed_and_noncanonical_journals_are_corrupt(tmp_path, payload):
    source, destination, transaction = _transaction(tmp_path)
    journal = transaction.directory / "journal.json"
    journal.write_bytes(payload)

    record = inspect(tmp_path)[0]

    assert record.classification == "corrupt"
    assert journal.read_bytes() == payload
    assert source.read_bytes() == b"source"
    assert not destination.exists()


def test_parent_identity_mismatch_is_ambiguous(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    journal = transaction.directory / "journal.json"
    import json

    data = json.loads(journal.read_text(encoding="utf-8"))
    data["parent_identity"]["inode"] += 1
    journal.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    record = inspect(tmp_path)[0]

    assert record.classification == "ambiguous"
    assert source.read_bytes() == b"source"


def test_result_identity_mismatch_is_unverified(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    transaction.result_path.write_bytes(b"expected result")
    transaction.set_result_ready(transaction.result_path.lstat())
    transaction.result_path.write_bytes(b"replacement with different inode")
    retained = transaction.directory / "retained-result"
    transaction.result_path.rename(retained)
    transaction.result_path.write_bytes(b"replacement with a different identity")

    record = inspect(tmp_path)[0]

    assert record.classification == "result_incomplete_or_unverified"
    assert source.exists()
    assert not destination.exists()


def test_destination_identity_mismatch_is_ambiguous(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    transaction.result_path.write_bytes(b"result")
    transaction.set_result_ready(transaction.result_path.lstat())
    os.rename(transaction.result_path, destination)
    transaction.set_state("published")
    retained = tmp_path / "retained-destination"
    destination.rename(retained)
    destination.write_bytes(b"unrelated replacement")

    record = inspect(tmp_path)[0]

    assert record.classification == "ambiguous"
    assert source.exists()
    assert destination.read_bytes() == b"unrelated replacement"


def test_transaction_directory_symlink_is_not_followed(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "marker"
    marker.write_text("untouched", encoding="utf-8")
    transaction.directory.rename(tmp_path / "saved-transaction")
    try:
        transaction.directory.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    record = inspect(tmp_path)[0]

    assert record.classification == "corrupt"
    assert marker.read_text(encoding="utf-8") == "untouched"
    assert source.exists()


def test_inspection_is_idempotent_and_read_only(tmp_path):
    source, destination, transaction = _transaction(tmp_path)
    before = {
        path.name: (
            path.is_symlink(),
            path.stat().st_size if path.is_file() else None,
            path.read_bytes() if path.is_file() else None,
        )
        for path in tmp_path.iterdir()
    }

    first = inspect(tmp_path)
    second = inspect(tmp_path)

    after = {
        path.name: (
            path.is_symlink(),
            path.stat().st_size if path.is_file() else None,
            path.read_bytes() if path.is_file() else None,
        )
        for path in tmp_path.iterdir()
    }
    assert first == second
    assert before == after
    assert source.read_bytes() == b"source"
    assert not destination.exists()


def test_failed_journal_replace_preserves_previous_record(tmp_path, monkeypatch):
    from fscryptography import _journal

    source, destination, transaction = _transaction(tmp_path)
    journal = transaction.directory / "journal.json"
    original = journal.read_bytes()

    def fail_replace(*args, **kwargs):
        raise OSError("injected journal replacement failure")

    monkeypatch.setattr(_journal.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        transaction.set_state("published")

    assert journal.read_bytes() == original
    assert inspect(tmp_path)[0].state == "prepared"
    assert source.exists()
    assert not destination.exists()


def test_failed_parent_sync_leaves_inspectable_prepared_journal(tmp_path, monkeypatch):
    from fscryptography import _journal

    calls = []

    def fail_parent_sync(path):
        calls.append(path)
        if path == tmp_path:
            raise OSError("injected parent sync failure")

    monkeypatch.setattr(_journal, "_sync_directory", fail_parent_sync)
    source = tmp_path / "source"
    source.write_bytes(b"source")
    with pytest.raises(OSError, match="injected"):
        Transaction.begin(tmp_path, "file_encrypt", "source", "destination", source.lstat())

    records = inspect(tmp_path)

    assert len(calls) == 2
    assert calls[-1] == tmp_path
    assert len(records) == 1
    assert records[0].classification == "prepared_no_output"
    assert source.read_bytes() == b"source"
