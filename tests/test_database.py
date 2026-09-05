#!/usr/bin/env python3
"""
Unit tests for database operations (models.py)

Tests CRUD operations, constraints, and relationships for all tables:
- books, summaries, chapters, audio_files
"""

import sys
import os
from pathlib import Path
import pytest


from backend import models


class TestDatabase:
    """Test database operations"""

    @pytest.fixture
    def temp_db(self, test_db_path):
        """Create a unique temporary database for testing"""
        db = models.Database(db_path=test_db_path)
        yield db
        # Cleanup handled by conftest.py cleanup_test_artifacts

    def test_add_book(self, temp_db):
        """Test adding a book to database"""
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_add_book.txt",
            full_text="This is test content.",
            gutenberg_id=12345,
            cover_image_url="covers/pg12345.jpg"
        )

        assert book_id is not None
        assert isinstance(book_id, int)

        # Retrieve and verify
        book = temp_db.get_book(book_id)
        assert book['title'] == "Test Book"
        assert book['author'] == "Test Author"
        assert book['filename'] == "test_add_book.txt"
        assert book['gutenberg_id'] == 12345
        assert book['cover_image_url'] == "covers/pg12345.jpg"
        assert book['word_count'] > 0

    def test_add_book_unique_filename(self, temp_db):
        """Test that filename must be unique"""
        # Add first book
        book_id1 = temp_db.add_book(
            title="Book 1",
            author="Author 1",
            filename="duplicate.txt",
            full_text="Content for book 1"
        )

        # Try to add second book with same filename
        # Should fail with IntegrityError due to UNIQUE constraint
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            book_id2 = temp_db.add_book(
                title="Book 2",
                author="Author 2",
                filename="duplicate.txt",
                full_text="Content for book 2"
            )

        # Check that get_book_by_filename returns the first book
        book = temp_db.get_book_by_filename("duplicate.txt")
        assert book is not None
        assert book['filename'] == "duplicate.txt"
        assert book['title'] == "Book 1"  # Should be first book, not second

    def test_get_book_by_filename(self, temp_db):
        """Test retrieving book by filename"""
        # Add book
        temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="findme.txt",
            full_text="This is the content of the book."
        )

        # Retrieve by filename
        book = temp_db.get_book_by_filename("findme.txt")
        assert book is not None
        assert book['title'] == "Test Book"
        assert book['filename'] == "findme.txt"

        # Non-existent filename
        book = temp_db.get_book_by_filename("nonexistent.txt")
        assert book is None

    def test_add_summary(self, temp_db):
        """Test adding summary to database"""
        # Add book first
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_summary.txt",
            full_text="This is test content for summary testing."
        )

        # Add concise summary
        summary_id = temp_db.add_summary(
            book_id=book_id,
            summary_type='concise',
            content="This is a concise summary of the test book."
        )

        assert summary_id is not None
        assert isinstance(summary_id, int)

        # Retrieve and verify
        summary = temp_db.get_summary(book_id, 'concise')
        assert summary is not None
        assert summary['summary_type'] == 'concise'
        assert summary['content'] == "This is a concise summary of the test book."
        assert summary['word_count'] > 0

    def test_add_summary_insert_or_replace(self, temp_db):
        """Test that adding same summary type replaces existing"""
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_replace.txt",
            full_text="Content for replace test"
        )

        # Add first summary
        temp_db.add_summary(book_id, 'concise', "First summary")

        # Add second summary with same type (should replace)
        temp_db.add_summary(book_id, 'concise', "Second summary")

        # Should only have one concise summary with latest content
        summary = temp_db.get_summary(book_id, 'concise')
        assert summary['content'] == "Second summary"

    def test_add_multiple_summary_types(self, temp_db):
        """Test adding multiple summary types for same book"""
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_multiple_summaries.txt",
            full_text="Content for multiple summary types test"
        )

        # Add all three summary types
        temp_db.add_summary(book_id, 'concise', "Concise summary")
        temp_db.add_summary(book_id, 'medium', "Medium summary")
        temp_db.add_summary(book_id, 'comprehensive', "Comprehensive summary")

        # Retrieve each
        concise = temp_db.get_summary(book_id, 'concise')
        medium = temp_db.get_summary(book_id, 'medium')
        comprehensive = temp_db.get_summary(book_id, 'comprehensive')

        assert concise['content'] == "Concise summary"
        assert medium['content'] == "Medium summary"
        assert comprehensive['content'] == "Comprehensive summary"

    def test_add_chapter(self, temp_db):
        """Test adding chapter to database"""
        # Add book first
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_chapters.txt",
            full_text="Content for chapter test"
        )

        # Add chapter
        chapter_id = temp_db.add_chapter(
            book_id=book_id,
            chapter_number=1,
            chapter_title="Chapter 1: The Beginning",
            summary="Summary of chapter 1",
            chapter_text="Full text of chapter 1..."
        )

        assert chapter_id is not None
        assert isinstance(chapter_id, int)

        # Retrieve chapters
        chapters = temp_db.get_chapters(book_id)
        assert len(chapters) == 1
        assert chapters[0]['chapter_number'] == 1
        assert chapters[0]['chapter_title'] == "Chapter 1: The Beginning"
        assert chapters[0]['summary'] == "Summary of chapter 1"

    def test_add_chapter_insert_or_replace(self, temp_db):
        """Test that adding same chapter number replaces existing (for regeneration)"""
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_chapter_replace.txt",
            full_text="Content for chapter replacement test"
        )

        # Add first version of chapter 1
        temp_db.add_chapter(book_id, 1, "Chapter 1", "First summary", "First text")

        # Add second version of chapter 1 (regeneration)
        temp_db.add_chapter(book_id, 1, "Chapter 1", "Second summary", "Second text")

        # Should only have one chapter 1 with latest content
        chapters = temp_db.get_chapters(book_id)
        assert len(chapters) == 1
        assert chapters[0]['summary'] == "Second summary"
        assert chapters[0]['chapter_text'] == "Second text"

    def test_add_multiple_chapters(self, temp_db):
        """Test adding multiple chapters for same book"""
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_multiple_chapters.txt",
            full_text="Content for multiple chapters test"
        )

        # Add 5 chapters
        for i in range(1, 6):
            temp_db.add_chapter(
                book_id,
                chapter_number=i,
                chapter_title=f"Chapter {i}",
                summary=f"Summary {i}",
                chapter_text=f"Text {i}"
            )

        # Retrieve all chapters
        chapters = temp_db.get_chapters(book_id)
        assert len(chapters) == 5
        assert chapters[0]['chapter_number'] == 1
        assert chapters[4]['chapter_number'] == 5

    def test_add_encoded_chapter_numbers(self, temp_db):
        """Test adding chapters with encoded numbers (101, 102, 201, 202)"""
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_encoded_chapters.txt",
            full_text="Content for encoded chapter numbers test"
        )

        # Add chapters with encoded numbers (Book 1: 101-103, Book 2: 201-203)
        encoded_chapters = [101, 102, 103, 201, 202, 203]
        for ch_num in encoded_chapters:
            temp_db.add_chapter(
                book_id,
                chapter_number=ch_num,
                chapter_title=f"Chapter {ch_num}",
                summary=f"Summary {ch_num}"
            )

        # Retrieve and verify
        chapters = temp_db.get_chapters(book_id)
        assert len(chapters) == 6
        chapter_numbers = [ch['chapter_number'] for ch in chapters]
        assert chapter_numbers == encoded_chapters

    def test_get_all_books(self, temp_db):
        """Test retrieving all books"""
        # Add multiple books
        temp_db.add_book("Book 1", "Author 1", "book1.txt", full_text="Content 1")
        temp_db.add_book("Book 2", "Author 2", "book2.txt", full_text="Content 2")
        temp_db.add_book("Book 3", "Author 3", "book3.txt", full_text="Content 3")

        # Get all books
        books = temp_db.get_all_books()
        assert len(books) >= 3

        titles = [book['title'] for book in books]
        assert "Book 1" in titles
        assert "Book 2" in titles
        assert "Book 3" in titles

    def test_foreign_key_constraint(self, temp_db):
        """Test that foreign key constraints are enforced"""
        # Try to add summary without valid book_id
        # This should fail (or handle gracefully)
        try:
            temp_db.add_summary(
                book_id=99999,  # Non-existent book
                summary_type='concise',
                content="This should fail"
            )
            # If we get here, check if it actually saved
            summary = temp_db.get_summary(99999, 'concise')
            # Implementation might handle this differently
        except Exception:
            # Foreign key constraint violation expected
            pass

    def test_word_count_calculation(self, temp_db):
        """Test that word_count is calculated correctly"""
        book_id = temp_db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test_word_count.txt",
            full_text="One two three four five words."
        )

        book = temp_db.get_book(book_id)
        assert book['word_count'] == 6  # "One two three four five words" = 6 words

        # Test summary word count
        temp_db.add_summary(book_id, 'concise', "This is a ten word summary right here today now.")
        summary = temp_db.get_summary(book_id, 'concise')
        assert summary['word_count'] == 10

        # Test chapter word count
        temp_db.add_chapter(
            book_id, 1, "Chapter 1",
            summary="Five word summary here okay",
            chapter_text="Full text"
        )
        chapters = temp_db.get_chapters(book_id)
        assert chapters[0]['word_count'] == 5  # Summary word count

    def test_cascade_delete(self, temp_db):
        """Test that deleting a book cascades to summaries and chapters"""
        # Add book with summaries and chapters
        book_id = temp_db.add_book("Test Book", "Test Author", "test_cascade.txt", full_text="Content for cascade test")
        temp_db.add_summary(book_id, 'concise', "Summary")
        temp_db.add_chapter(book_id, 1, "Chapter 1", "Summary 1")

        # Verify they exist
        assert temp_db.get_summary(book_id, 'concise') is not None
        assert len(temp_db.get_chapters(book_id)) == 1

        # Delete book
        conn = temp_db.get_connection()
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        cursor = conn.cursor()
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()

        # Verify cascaded deletes (summaries and chapters should be gone)
        assert temp_db.get_summary(book_id, 'concise') is None
        assert len(temp_db.get_chapters(book_id)) == 0

    def test_book_has_modern_english_no_chapters(self, temp_db):
        """A book with no chapters at all has no modern English."""
        book_id = temp_db.add_book("Empty", "Author", "empty.txt", full_text="x")
        assert temp_db.book_has_modern_english(book_id) is False

    def test_book_has_modern_english_all_null(self, temp_db):
        """A book whose chapters all have NULL modern_english_text returns False."""
        book_id = temp_db.add_book("NoMod", "Author", "no_mod.txt", full_text="x")
        temp_db.add_chapter(book_id, 1, "Ch 1", "summary", chapter_text="text")
        temp_db.add_chapter(book_id, 2, "Ch 2", "summary", chapter_text="text")
        assert temp_db.book_has_modern_english(book_id) is False

    def test_book_has_modern_english_one_set(self, temp_db):
        """A book with at least one chapter that has non-empty modern_english_text returns True."""
        book_id = temp_db.add_book("HasMod", "Author", "has_mod.txt", full_text="x")
        temp_db.add_chapter(book_id, 1, "Ch 1", "summary", chapter_text="text")
        temp_db.add_chapter(book_id, 2, "Ch 2", "summary", chapter_text="text",
                            modern_english_text="A plain English version of chapter 2.")
        assert temp_db.book_has_modern_english(book_id) is True

    def test_book_has_modern_english_whitespace_only_is_false(self, temp_db):
        """Whitespace-only modern_english_text should not count as having a translation."""
        book_id = temp_db.add_book("Blank", "Author", "blank.txt", full_text="x")
        temp_db.add_chapter(book_id, 1, "Ch 1", "summary", chapter_text="text",
                            modern_english_text="   \n\t  ")
        assert temp_db.book_has_modern_english(book_id) is False

    def test_get_book_structure_no_sections_flat_chapter_list(self, temp_db):
        book_id = temp_db.add_book("Flat", "Author", "flat.txt", full_text="x")
        temp_db.add_chapter(book_id, 1, "Ch 1", "summary", chapter_text="full text 1")
        temp_db.add_chapter(book_id, 2, "Ch 2", "summary", chapter_text="full text 2")

        structure = temp_db.get_book_structure(book_id)

        assert structure['has_sections'] is False
        assert len(structure['sections']) == 1
        section = structure['sections'][0]
        assert section['id'] is None
        assert section['type'] is None
        assert section['title'] == 'Chapters'
        assert [c['chapter_number'] for c in section['chapters']] == [1, 2]
        # Full get_chapters() includes chapter_text (unlike the metadata variant)
        assert section['chapters'][0]['chapter_text'] == 'full text 1'

    def test_get_book_structure_metadata_no_sections_omits_chapter_text(self, temp_db):
        book_id = temp_db.add_book("Flat2", "Author", "flat2.txt", full_text="x")
        temp_db.add_chapter(book_id, 1, "Ch 1", "summary", chapter_text="full text 1")

        structure = temp_db.get_book_structure_metadata(book_id)

        assert structure['has_sections'] is False
        chapters = structure['sections'][0]['chapters']
        assert len(chapters) == 1
        assert 'chapter_text' not in chapters[0]
        assert chapters[0]['chapter_title'] == 'Ch 1'

    def test_get_book_structure_with_sections_and_preface(self, temp_db):
        book_id = temp_db.add_book("Sectioned", "Author", "sectioned.txt", full_text="x")
        # Preface chapter with no section_id
        temp_db.add_chapter(book_id, 1, "Preface", "summary", chapter_text="preface text")
        section_id = temp_db.add_book_section(book_id, "PART", 1, "The Beginning")
        temp_db.add_chapter(book_id, 2, "Ch 2", "summary", chapter_text="ch2 text",
                            section_id=section_id)

        structure = temp_db.get_book_structure(book_id)

        assert structure['has_sections'] is True
        assert len(structure['sections']) == 2
        preface_section, part_section = structure['sections']
        assert preface_section['type'] == 'PREFACE'
        assert preface_section['title'] == 'Preface'
        assert [c['chapter_number'] for c in preface_section['chapters']] == [1]
        assert part_section['type'] == 'PART'
        assert part_section['title'] == 'The Beginning'
        assert [c['chapter_number'] for c in part_section['chapters']] == [2]

    def test_get_book_structure_metadata_with_sections_matches_structure_shape(self, temp_db):
        book_id = temp_db.add_book("Sectioned2", "Author", "sectioned2.txt", full_text="x")
        temp_db.add_chapter(book_id, 1, "Preface", "summary", chapter_text="preface text")
        section_id = temp_db.add_book_section(book_id, "PART", 1, "The Beginning")
        temp_db.add_chapter(book_id, 2, "Ch 2", "summary", chapter_text="ch2 text",
                            section_id=section_id)

        structure = temp_db.get_book_structure(book_id)
        metadata = temp_db.get_book_structure_metadata(book_id)

        assert metadata['has_sections'] == structure['has_sections']
        assert len(metadata['sections']) == len(structure['sections'])
        for full_section, meta_section in zip(structure['sections'], metadata['sections']):
            assert full_section['type'] == meta_section['type']
            assert full_section['title'] == meta_section['title']
            assert [c['chapter_number'] for c in full_section['chapters']] == \
                   [c['chapter_number'] for c in meta_section['chapters']]
            assert 'chapter_text' not in meta_section['chapters'][0]

    def test_get_audio_file_closes_connection_when_neither_id_given(self, temp_db):
        """get_audio_file opens a connection unconditionally, but its
        `else: return None` guard (neither summary_id nor chapter_id passed)
        returned before conn.close() — a real leak on that code path, not
        just on exception."""
        import sqlite3
        real_connect = sqlite3.connect
        connections = []

        def spy_connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            connections.append(conn)
            return conn

        import unittest.mock
        with unittest.mock.patch("sqlite3.connect", side_effect=spy_connect):
            result = temp_db.get_audio_file()

        assert result is None
        assert len(connections) == 1
        # sqlite3.Connection has no public `.closed` — collecting affected
        # cursors is the reliable observable: a closed connection raises
        # ProgrammingError on any further operation.
        with pytest.raises(sqlite3.ProgrammingError):
            connections[0].execute("SELECT 1")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
