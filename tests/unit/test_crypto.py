import pytest

import fscryptography
from fscryptography import ClosedInstanceError, Manager
from fscryptography.errors import AuthenticationError


def test_module_generate_and_manager_open_random_key():
    key = fscryptography.generate()
    manager = Manager(key)
    assert manager._names_primitive is not None
    assert manager._content_primitive is not None
    assert manager.export_key() == key
    manager.close()
    with pytest.raises(ClosedInstanceError):
        manager.export_key()


def test_password_protected_key_is_opened_once_by_manager():
    key = fscryptography.generate(password="correct horse")
    manager = Manager(key, password="correct horse")
    assert manager._names_primitive is not None
    assert manager.export_key() == key
    manager.close()


def test_manager_change_key_replaces_context():
    first = fscryptography.generate()
    second = fscryptography.generate()
    manager = Manager(first)
    manager.change_key(second)
    assert manager.export_key() == second
    manager.close()


def test_failed_change_key_preserves_previous_context():
    first = fscryptography.generate()
    protected = fscryptography.generate(password="right")
    manager = Manager(first)
    with pytest.raises(AuthenticationError):
        manager.change_key(protected, password="wrong")
    assert manager.export_key() == first
    assert manager._names_primitive is not None
    manager.close()


def test_change_key_requires_open_manager():
    manager = Manager(fscryptography.generate())
    manager.close()
    with pytest.raises(ClosedInstanceError):
        manager.change_key(fscryptography.generate())


def test_manager_context_manager_closes_on_exception():
    manager = Manager(fscryptography.generate())
    with pytest.raises(RuntimeError):
        with manager:
            raise RuntimeError("test")
    with pytest.raises(ClosedInstanceError):
        manager.export_key()
