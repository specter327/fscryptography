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
