import pytest
from shared.auth.user_models import UserDatabase


def test_user_database_requires_explicit_path():
    with pytest.raises(TypeError):
        UserDatabase()


def test_hints_are_supplied_by_the_app(tmp_path):
    db = UserDatabase(tmp_path / 'u.db', valid_hints=frozenset({'a'}))
    assert db.valid_hints == frozenset({'a'})
