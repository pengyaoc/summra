from distill.models import DistillDatabase
from distill.scripts.push_book import main


def test_dry_run_does_not_create_db(sample_book, write_book, tmp_path, capsys):
    folder = write_book(sample_book)
    db_path = tmp_path / 'distill.db'

    assert main([str(folder), '--dry-run', '--db', str(db_path)]) == 0

    assert not db_path.exists()
    out = capsys.readouterr().out
    assert 'My Book' in out
    assert 'Chapters: 4' in out  # Overview + three chapters
    assert 'Images: 1' in out


def test_import_prints_id_and_returns_0(sample_book, write_book, tmp_path, capsys):
    folder = write_book(sample_book)
    db_path = tmp_path / 'distill.db'

    assert main([str(folder), '--db', str(db_path)]) == 0

    assert 'Imported my-book as book 1' in capsys.readouterr().out
    assert DistillDatabase(db_path).get_book_by_slug('my-book')['id'] == 1


def test_words_count_cjk_characters_individually(sample_book, write_book, tmp_path, capsys):
    sample_book['overview'] = []
    sample_book['parts'] = [{'title': None, 'chapters': [
        {'title': '1. Only', 'blocks': [{'type': 'p', 'text': '你好，世界。 hello'}]}]}]
    folder = write_book(sample_book)

    assert main([str(folder), '--dry-run', '--db', str(tmp_path / 'distill.db')]) == 0

    assert 'Words: 5' in capsys.readouterr().out  # 4 CJK characters + "hello"


def test_invalid_folder_returns_1_and_lists_errors(sample_book, write_book, tmp_path, capsys):
    sample_book['format'] = 2
    sample_book['lang'] = 'english'
    folder = write_book(sample_book)
    db_path = tmp_path / 'distill.db'

    assert main([str(folder), '--db', str(db_path)]) == 1

    out = capsys.readouterr().out
    assert 'format: must be 1' in out
    assert 'lang: required' in out
    assert not db_path.exists()
