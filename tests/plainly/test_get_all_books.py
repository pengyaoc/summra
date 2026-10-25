"""Database.get_all_books() returns every book with its categories using a
bounded number of queries.

Bug this guards against: it ran one categories query per book, each on a
fresh SQLite connection (91 connects for 90 books). /api/books, the sitemap,
/books and /api/discover/carousels all call it, and it was prod's slowest
endpoint with multi-second spikes under concurrent page loads.
"""
import pytest


@pytest.fixture
def db(test_db_path):
    from plainly import models
    database = models.Database(db_path=test_db_path)
    zeta = database.add_category('Zeta', description='last')
    alpha = database.add_category('Alpha', description='first')
    database.add_category('Unused')

    b1 = database.add_book(title='Beta Book', author='A', filename='b.txt', full_text='x')
    database.add_book_category(b1, zeta)
    database.add_book_category(b1, alpha)
    database.add_book(title='Alpha Book', author='B', filename='a.txt', full_text='x')  # no categories
    b3 = database.add_book(title='Gamma Book', author='C', filename='g.txt', full_text='x')
    database.add_book_category(b3, zeta)
    return database


def test_matches_per_book_category_lookup(db):
    books = db.get_all_books()
    assert [b['title'] for b in books] == ['Alpha Book', 'Beta Book', 'Gamma Book']
    for book in books:
        assert book['categories'] == db.get_book_categories(book['id'])
    by_title = {b['title']: b for b in books}
    assert [c['name'] for c in by_title['Beta Book']['categories']] == ['Alpha', 'Zeta']
    assert by_title['Alpha Book']['categories'] == []


def test_uses_one_connection(db, monkeypatch):
    calls = []
    real = db.get_connection
    monkeypatch.setattr(db, 'get_connection', lambda: calls.append(1) or real())
    db.get_all_books()
    assert len(calls) == 1


def test_empty_library(test_db_path):
    from plainly import models
    assert models.Database(db_path=test_db_path).get_all_books() == []
