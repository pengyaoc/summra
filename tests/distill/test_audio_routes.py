import json

import pytest

from distill.audio.spoken import spoken_checksum, spoken_units

from .conftest import HEADERS

AUDIO = bytes(range(256)) * 4  # 1024 bytes


@pytest.fixture
def audio_env(app_env):
    client, db, _, book_id = app_env
    chapter = db.get_chapters(book_id)[1]
    timings = [{'paragraph_id': f"{chapter['id']}.0", 'start_ms': 0, 'end_ms': 900}]
    db.save_chapter_audio(chapter['id'], AUDIO, timings, 900, spoken_checksum(spoken_units(chapter)),
                          'say:system', 'say', None)
    return client, db, book_id, chapter


def url(chapter):
    return f"/books/my-book/audio/{chapter['id']}.m4a"


def test_audio_range_206(audio_env):
    client, _, _, chapter = audio_env
    response = client.get(url(chapter), headers={**HEADERS, 'Range': 'bytes=0-99'})
    assert response.status_code == 206
    assert response.headers['Content-Range'] == f'bytes 0-99/{len(AUDIO)}'
    assert response.data == AUDIO[:100]
    assert response.mimetype == 'audio/mp4'


def test_audio_full_200_has_accept_ranges(audio_env):
    client, _, _, chapter = audio_env
    response = client.get(url(chapter), headers=HEADERS)
    assert response.status_code == 200 and response.data == AUDIO
    assert response.headers['Accept-Ranges'] == 'bytes'
    assert 'private' in response.headers['Cache-Control']


def test_audio_requires_login(audio_env):
    client, _, _, chapter = audio_env
    assert client.get(url(chapter)).status_code == 401
    assert client.get('/api/books/my-book/audio').status_code == 401


def test_audio_stale_404(audio_env):
    client, db, _, chapter = audio_env
    with db.get_connection() as conn:
        conn.execute('UPDATE chapters SET blocks = ? WHERE id = ?',
                     (json.dumps([{'type': 'p', 'text': 'changed'}]), chapter['id']))
    assert client.get(url(chapter), headers=HEADERS).status_code == 404


def test_audio_range_past_end_416(audio_env):
    client, _, _, chapter = audio_env
    response = client.get(url(chapter), headers={**HEADERS, 'Range': f'bytes={len(AUDIO) + 10}-'})
    assert response.status_code == 416


def test_audio_api_lists_current_only(audio_env):
    client, _, book_id, chapter = audio_env
    data = client.get('/api/books/my-book/audio', headers=HEADERS).get_json()
    assert data['book_id'] == book_id
    assert [c['chapter_id'] for c in data['chapters']] == [chapter['id']]
    item = data['chapters'][0]
    assert item['url'].endswith(url(chapter)) and item['duration_ms'] == 900
    assert item['title'] == chapter['title'] and item['timings'][0]['end_ms'] == 900


def test_audio_unknown_book_404(audio_env):
    client = audio_env[0]
    assert client.get('/api/books/nope/audio', headers=HEADERS).status_code == 404


def test_audio_is_revalidated_not_immutable(audio_env):
    """The URL stays the same across re-renders, so the browser must check the ETag."""
    client, db, _, chapter = audio_env
    response = client.get(url(chapter), headers=HEADERS)
    assert 'no-cache' in response.headers['Cache-Control'] and 'immutable' not in response.headers['Cache-Control']
    etag = response.headers['ETag']
    assert client.get(url(chapter), headers={**HEADERS, 'If-None-Match': etag}).status_code == 304
    timings = [{'paragraph_id': f"{chapter['id']}.0", 'start_ms': 0, 'end_ms': 800}]
    db.save_chapter_audio(chapter['id'], AUDIO[:512], timings, 800, spoken_checksum(spoken_units(chapter)),
                          'say:system', 'say', None)
    again = client.get(url(chapter), headers={**HEADERS, 'If-None-Match': etag})
    assert again.status_code == 200 and again.data == AUDIO[:512]
