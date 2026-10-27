"""Distill's Kindle e-ink pages: library, contents and reader, server-rendered.

The shared platform (shared.kindle) does the dispatch, paging helpers and
progress recording; this module supplies Distill's pages. The reader is served
at the web reader's URL, so a block's relative image src resolves to the
private image route there. Distill has one text, the summary, so there is no
Text row and no search.
"""
import re

from flask import Blueprint, request

from distill.reader_config import DISTILL_READER
from distill.routes import _card_for, _db, newest_first, reading_cards
from shared.kindle import pages as kindle_pages
from shared.kindle.pages import (
    CONTENTS_PAGE_SIZE, LIBRARY_PAGE_SIZE, READING_ON_HOME, account_user_id, cookie_path, font_family, font_size,
    not_found_page, page_number, paginate, register_kindle_pages, render_page, url,
)
from shared.kindle.progress import save_progress as shared_save_progress
from shared.progress import routes as progress_routes
from shared.reader.blocks import block_element, block_text
from shared.reader.index import ReaderIndexMixin

bp = Blueprint('distill_kindle', __name__)

TEXT = 'summary'  # Distill's one text


def _saved_position(book_id, chapters):
    """(chapter ordinal, block index) of the account's saved place, or None."""
    user_id = account_user_id()
    saved = kindle_pages.saved_marker(
        progress_routes.user_db, _db(), user_id, book_id, (TEXT,)) if user_id is not None else None
    if not saved:
        return None
    chapter_id, index, _ = saved
    ordinal = next((c['ordinal'] for c in chapters if c['id'] == chapter_id), None)
    return None if ordinal is None else (ordinal, index)


def library_page():
    db = _db()
    books = newest_first(db)
    reading = reading_cards(db, account_user_id(), books) if account_user_id() is not None else []
    show = 'reading' if request.args.get('show') == 'reading' and reading else 'all'
    shown, page, pages = paginate(reading if show == 'reading' else books, LIBRARY_PAGE_SIZE, page_number())

    def page_url(n):
        return url('/', show='reading' if show == 'reading' else None, page=n)

    return render_page(
        'library.html',
        books=shown if show == 'all' else [], show=show, page=page, pages=pages,
        prev_url=page_url(page - 1) if page > 1 else None,
        next_url=page_url(page + 1) if page < pages else None,
        reading=shown if show == 'reading' else (reading[:READING_ON_HOME] if page == 1 else []),
        reading_count=len(reading),
    )


def book_page(slug):
    book = _db().get_book_by_slug(slug)
    if not book:
        return not_found_page()
    outline = _db().get_chapter_outline(book['id'])
    shown, page, pages = paginate(outline, CONTENTS_PAGE_SIZE, page_number())
    saved = _saved_position(book['id'], outline)
    rows, part = [], None
    for chapter in shown:
        # A heading opens each part, and repeats where a page starts inside one.
        if chapter['part_title'] and (chapter['part_title'] != part or not rows):
            rows.append({'part': chapter['part_title']})
        part = chapter['part_title']
        rows.append({'chapter': chapter})

    def page_url(n):
        return url(f'/books/{slug}', page=n)

    cover = book.get('cover_image')
    return render_page(
        'book.html',
        book=book, rows=rows, page=page, pages=pages, saved=saved, card=_card_for(book['id']),
        cover_url=(url(f'/books/{slug}/cover/{book["cover_thumbnail_token"]}.jpg')
                   if book.get('cover_thumbnail_token') else url(f'/books/{slug}/images/{cover}') if cover else None),
        prev_url=page_url(page - 1) if page > 1 else None,
        next_url=page_url(page + 1) if page < pages else None,
    )


def reader_page(slug):
    book = _db().get_book_by_slug(slug)
    chapters = _db().get_chapters(book['id']) if book else []
    if not chapters:
        return not_found_page()
    ordinals = [c['ordinal'] for c in chapters]
    saved = _saved_position(book['id'], chapters)
    start = 0
    if 'ch' in request.args:
        if not re.fullmatch(r'[0-9]+', request.args['ch']):
            return not_found_page()
        ordinal = int(request.args['ch'])
    elif 'chapter' in request.args:
        # The web reader's key is a chapter id; map it to this reader's ordinal.
        if not re.fullmatch(r'[0-9]+', request.args['chapter']):
            return not_found_page()
        by_id = {c['id']: c['ordinal'] for c in chapters}
        ordinal = by_id.get(int(request.args['chapter']), -1)
    else:
        ordinal = saved[0] if saved and saved[0] in ordinals else ordinals[0]
    if ordinal not in ordinals:
        return not_found_page()
    if saved and saved[0] == ordinal:
        start = saved[1]

    position = ordinals.index(ordinal)
    chapter = chapters[position]

    def chars(c):
        return sum(len(block_text(b)) for b in c['blocks'])

    def chapter_url(i):
        return url(f'/books/{slug}/read', ch=ordinals[i]) if 0 <= i < len(chapters) else None

    flow = [block_element(b, i, DISTILL_READER.image_base) for i, b in enumerate(chapter['blocks'])]
    return render_page(
        'reader.html',
        book=book, chapter={'chapter_number': ordinal, 'chapter_title': chapter['title']},
        text=TEXT, flow=flow, start=start,
        font_size=font_size(),
        font_family=font_family(),
        chars_before=sum(chars(c) for c in chapters[:position]),
        chapter_chars=chars(chapter),
        total_chars=sum(chars(c) for c in chapters) or 1,
        prev_url=chapter_url(position - 1),
        next_url=chapter_url(position + 1),
        next_title=chapters[position + 1]['title'] if chapter_url(position + 1) else None,
        text_urls={TEXT: chapter_url(position)},
        cookie_path=cookie_path(),
        sync_url=url('/api/kindle/progress') if account_user_id() is not None else None,
    )


def _position(db, book_id, ordinal, index, text):
    """Distill's side of the shared progress handler: (unit id, quote) of block
    `index` of the chapter with this ordinal, or None if unknown."""
    chapter = db.get_chapter(book_id, ordinal)
    if not chapter:
        return None
    blocks = chapter['blocks']
    quote = re.sub(r'\s+', ' ', block_text(blocks[index])).strip()[:180] if index < len(blocks) else None
    quote = quote or None  # a block with no text (an image without a caption) has no quote
    return ReaderIndexMixin._reader_unit_id(chapter['id'], index), quote


@bp.route('/api/kindle/progress', methods=['POST'])
def save_progress():
    """Record the Kindle reader's page as a web-reader progress mutation
    (shared.kindle.progress.save_progress; ch is the chapter ordinal)."""
    return shared_save_progress(DISTILL_READER, progress_routes.user_db, _db(), account_user_id(), _position)


register_kindle_pages(bp, {
    'distill.library': library_page,
    'distill.book_page': book_page,
    'distill.reader': reader_page,
}, DISTILL_READER)
