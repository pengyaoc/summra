import json
import re
import sqlite3

import pytest

from plainly.reader_config import PLAINLY_READER
from shared.auth.user_models import UserDatabase
from shared.reader.config import (
    KindleOptions, ReaderConfig, ReaderFeatures, ReaderMember, ReaderMode,
)
from shared.reader.index import create_reader_tables
from shared.reader.modes import ALL_MODES

SXS_MEMBERS = (ReaderMember('original', 'Original', 'original'), ReaderMember('plain', 'Plain', 'modern'))


def make(modes=(ReaderMode('summary', 'Summary'), ReaderMode('original', 'Original')),
         default_modes=('original',), features=ReaderFeatures(kindle=False),
         cache_visibility='private', **kwargs):
    return ReaderConfig(app_name='T', cache_db_name='t', cache_visibility=cache_visibility,
                        modes=modes, default_modes=default_modes, features=features, **kwargs)


def test_plainly_config_matches_todays_literals():
    c = PLAINLY_READER
    assert [(m.id, m.label) for m in c.modes] == [
        ('summary', 'Summary'), ('original', 'Original'),
        ('plain', 'Plain English'), ('side_by_side', 'Side-by-Side')]
    sxs = c.mode('side_by_side')
    assert sxs.min_width == 1024
    assert [(m.id, m.cell_class) for m in sxs.members] == [('original', 'original'), ('plain', 'modern')]
    assert sxs.narrow_fallback == ('plain', 'original')
    assert c.cache_db_name == 'summra-reader-v2'
    assert c.cache_visibility == 'public'
    assert c.default_modes == ('plain', 'original')
    s = c.settings
    assert (s.font_default, s.size_min, s.size_max, s.size_default, s.theme_default) == ('georgia', 12, 24, 16, 'light')


def test_unknown_mode_id_rejected():
    with pytest.raises(ValueError):
        make(modes=(ReaderMode('bogus', 'Bogus'),), default_modes=())
    with pytest.raises(ValueError):
        make(modes=(ReaderMode('summary', 'A'), ReaderMode('summary', 'B')), default_modes=())


def test_side_by_side_members_must_match_storage():
    with pytest.raises(ValueError):
        make(modes=(ReaderMode('side_by_side', 'SxS', layout='side_by_side'),), default_modes=())
    with pytest.raises(ValueError):
        make(modes=(ReaderMode('summary', 'S', layout='grid'),), default_modes=())
    ok = ReaderMode('side_by_side', 'SxS', layout='side_by_side', members=SXS_MEMBERS)
    assert make(modes=(ok,), default_modes=('side_by_side',)).mode('side_by_side') is ok


def test_default_and_fallback_modes_must_be_configured():
    with pytest.raises(ValueError):
        make(default_modes=('plain',))
    with pytest.raises(ValueError):
        make(modes=(ReaderMode('summary', 'S', narrow_fallback=('plain',)),), default_modes=('summary',))
    with pytest.raises(ValueError):
        make(cache_visibility='shared')


def test_kindle_feature_requires_kindle_options():
    with pytest.raises(ValueError):
        make(features=ReaderFeatures(kindle=True))
    with pytest.raises(ValueError):
        make(features=ReaderFeatures(kindle=True), kindle=KindleOptions((('plain', 'Plain'),), 'plain'))
    assert make(features=ReaderFeatures(kindle=True),
                kindle=KindleOptions((('original', 'Original'),), 'original')).kindle


def test_to_client_is_json_and_omits_kindle():
    client = PLAINLY_READER.to_client()
    json.dumps(client)
    assert 'kindle' not in client and 'hint_keys' not in client
    assert client['cache_db_name'] == 'summra-reader-v2'
    modes = {m['id']: m for m in client['modes']}
    assert modes['plain']['library_label'] == 'Plain English'
    assert modes['side_by_side']['library_label'] == 'Side by side'
    assert client['features']['kindle'] is True


def test_registry_matches_schema_checks(tmp_path):
    expected = ', '.join(f"'{m}'" for m in ALL_MODES)
    content = sqlite3.connect(tmp_path / 'c.db')
    create_reader_tables(content.cursor())
    UserDatabase(db_path=tmp_path / 'u.db')
    user = sqlite3.connect(tmp_path / 'u.db')
    for conn, table in ((content, 'reader_unit'), (user, 'mode_reading_state'), (user, 'progress_mutation')):
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
        assert re.search(r"CHECK\(mode IN \(([^)]*)\)\)", sql).group(1) == expected, table
