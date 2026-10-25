import json
import re
import sqlite3
from dataclasses import replace

import pytest

from plainly.reader_config import PLAINLY_READER
from shared.auth.user_models import UserDatabase
from shared.reader.config import (
    DEFAULT_SETTINGS, KindleOptions, ReaderConfig, ReaderFeatures, ReaderMember, ReaderMode,
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


def _plain_mode(mode_id, label, **extra):
    return {'id': mode_id, 'label': label, 'layout': 'single', 'members': [],
            'library_label': label, 'min_width': None, 'narrow_fallback': [], **extra}


def test_plainly_to_client_is_pinned_exactly():
    assert PLAINLY_READER.to_client() == {
        'app_name': 'Plainly',
        'cache_db_name': 'summra-reader-v2',
        'api_base': '/api',
        'extra_page_blocks': '',
        'default_modes': ['plain', 'original'],
        'modes': [
            _plain_mode('summary', 'Summary'),
            _plain_mode('original', 'Original'),
            _plain_mode('plain', 'Plain English'),
            _plain_mode(
                'side_by_side', 'Side-by-Side', layout='side_by_side',
                members=[{'id': 'original', 'label': 'Original', 'cell_class': 'original'},
                         {'id': 'plain', 'label': 'Plain English', 'cell_class': 'modern'}],
                library_label='Side by side', min_width=1024, narrow_fallback=['plain', 'original']),
        ],
        'features': {'progress': True, 'illustrations': True, 'page_turn_hint': True, 'kindle': True},
        'settings': {
            'fonts': [['georgia', 'Reader Serif'], ['system', 'System'], ['figtree', 'Figtree']],
            'font_default': 'georgia', 'size_min': 12, 'size_max': 24, 'size_default': 16,
            'themes': [['light', 'Light'], ['dark', 'Dark']], 'theme_default': 'light',
        },
    }


@pytest.mark.parametrize('change', [
    {'font_default': 'comic'},
    {'theme_default': 'sepia'},
    {'size_default': 30},
    {'size_default': 8},
])
def test_settings_defaults_must_be_valid(change):
    with pytest.raises(ValueError):
        make(settings=replace(DEFAULT_SETTINGS, **change))


def test_kindle_default_text_must_be_a_configured_mode():
    with pytest.raises(ValueError):
        make(features=ReaderFeatures(kindle=True),
             kindle=KindleOptions((('original', 'Original'),), 'summary'))


def test_layout_and_mode_id_must_agree():
    # side_by_side layout needs the side_by_side id
    with pytest.raises(ValueError):
        make(modes=(ReaderMode('original', 'O', layout='side_by_side', members=SXS_MEMBERS),),
             default_modes=('original',))
    # the side_by_side id needs the side_by_side layout
    with pytest.raises(ValueError):
        make(modes=(ReaderMode('side_by_side', 'S'),), default_modes=('side_by_side',))


def test_registry_matches_schema_checks(tmp_path):
    expected = ', '.join(f"'{m}'" for m in ALL_MODES)
    content = sqlite3.connect(tmp_path / 'c.db')
    create_reader_tables(content.cursor())
    UserDatabase(db_path=tmp_path / 'u.db')
    user = sqlite3.connect(tmp_path / 'u.db')
    for conn, table in ((content, 'reader_unit'), (user, 'mode_reading_state'), (user, 'progress_mutation')):
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
        assert re.search(r"CHECK\(mode IN \(([^)]*)\)\)", sql).group(1) == expected, table


def _render(template_source, config, **context):
    from flask import Flask, render_template_string
    from shared.web import install_shared_ui
    app = Flask(__name__)
    install_shared_ui(app)
    with app.test_request_context():
        return render_template_string(template_source, reader_config=config, **context)


def test_settings_panel_single_mode_renders_no_selector():
    html = _render("{% include 'shared/reader/_settings_panel.html' %}", make(modes=(ReaderMode('original', 'Original'),)))
    assert 'reader-mode-settings' not in html and 'data-reader-settings-mode' not in html
    html = _render("{% include 'shared/reader/_settings_panel.html' %}", make())
    assert html.count('data-reader-settings-mode=') == 2
    assert '>Summary</button>' in html and '>Original</button>' in html


def test_settings_panel_renders_configured_fonts_and_size_range():
    from shared.reader.config import ReaderSettings
    settings = ReaderSettings((('serif', 'Book Serif'), ('mono', 'Mono')), 'mono', 10, 30, 18,
                              (('light', 'Light'),), 'light')
    html = _render("{% include 'shared/reader/_settings_panel.html' %}", make(settings=settings))
    assert html.count('<button class="font-choice') == 2
    assert 'class="font-choice active" data-font="mono"' in html
    assert 'class="font-choice" data-font="serif"' in html
    assert '<span>Book Serif</span>' in html
    assert 'min="10" max="30" value="18"' in html
    assert '>18px</div>' in html
    assert html.count('<button class="theme-choice') == 1


def test_library_card_hides_mode_label_for_single_mode_app():
    src = ("{% from 'shared/_library_card.html' import library_card with context %}"
           "{% set cover %}<i>cover</i>{% endset %}{{ library_card(book, cover) }}")
    book = {'id': 7, 'title': 'T', 'author': 'A', 'furthest_percentage': 40, 'last_mode': 'original'}
    single = _render(src, make(modes=(ReaderMode('original', 'Original'),)), book=book)
    assert 'Beginning' in single and ' · ' not in single
    assert '<i>cover</i>' in single and 'data-library-read="7"' in single
    multi = _render(src, make(), book=book)
    assert 'Beginning · Original' in multi
    linked = _render(src.replace("book, cover)", "book, cover, read_href='/r/7')"), make(), book=book)
    assert '<a class="library-read-action" href="/r/7">' in linked and 'data-library-read' not in linked
