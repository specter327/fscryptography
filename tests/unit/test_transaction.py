from __future__ import annotations

import os

from fscryptography._transaction import Transaction


def _transaction(tmp_path):
    return Transaction.begin(
        tmp_path,
        "file_encrypt",
        "source.txt",
        "destination.fscrypt",
    )


def test_close_removes_unpublished_result(tmp_path):
    transaction = _transaction(tmp_path)
    descriptor = transaction.open_result()
    os.write(descriptor, b"partial result")
    os.close(descriptor)

    assert transaction.result_path.is_file()

    transaction.close()

    assert not transaction.result_path.exists()


def test_close_does_not_remove_entry_recreated_after_publication(tmp_path):
    transaction = _transaction(tmp_path)
    descriptor = transaction.open_result()
    os.write(descriptor, b"published result")
    os.close(descriptor)

    destination = tmp_path / "destination.fscrypt"
    transaction.result_path.rename(destination)
    transaction.mark_result_published()

    # Another actor may legitimately reuse the old temporary name after rename.
    transaction.result_path.write_bytes(b"unrelated file")
    transaction.close()

    assert destination.read_bytes() == b"published result"
    assert transaction.result_path.read_bytes() == b"unrelated file"
