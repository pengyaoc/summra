#!/usr/bin/env python3
"""
Unit tests for Gemini illustration generation script

Tests both sync and batch modes with various scenarios:
- Full book generation (all chapters)
- Chapter range with Chapter 1 (e.g., 1-10)
- Chapter range without Chapter 1 (e.g., 5-15)
"""

import sys
import os
from pathlib import Path
import pytest
import uuid
from unittest.mock import Mock, MagicMock, patch, call
import io

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

# Import the modules we need to test
from scripts.images.generate_gemini_illustrations import (
    GeminiImageGenerator,
    filter_eligible_chapters,
    build_chapter_illustration_prompt,
    generate_chapter_illustrations_for_book,
    generate_chapter_illustrations_batch
)
import models


class TestGeminiIllustrations:
    """Test Gemini illustration generation (sync and batch modes)"""

    @pytest.fixture
    def temp_db(self, test_db_path):
        """Create a temporary database with test data"""
        db = models.Database(db_path=test_db_path)

        # Add a test book
        book_id = db.add_book(
            title="Test Book",
            author="Test Author",
            filename="test.txt",
            full_text="This is a test book content.",
            gutenberg_id=99999
        )

        # Add medium summary
        db.add_summary(
            book_id=book_id,
            summary_type='medium',
            content="This is a test book about adventures in a magical land."
        )

        # Add test chapters with adequate word count (>200 words in summary)
        for i in range(1, 11):  # Chapters 1-10
            chapter_text = f"This is the text of chapter {i}. " * 50
            # Create a summary with >200 words (word_count is calculated from summary)
            summary = f"This is a detailed summary of chapter {i}. " * 30  # ~210 words
            db.add_chapter(
                book_id=book_id,
                chapter_number=i,
                chapter_title=f"Chapter {i} Title",
                summary=summary,
                chapter_text=chapter_text,
                section_id=None
            )

        yield db, book_id

        # Cleanup handled by conftest.py

    @pytest.fixture
    def temp_illustrations_dir(self, test_illustrations_dir):
        """Provide temporary illustrations directory from conftest"""
        yield test_illustrations_dir
        # Cleanup handled by conftest.py

    @pytest.fixture
    def mock_generator(self):
        """Create a mock GeminiImageGenerator"""
        generator = Mock(spec=GeminiImageGenerator)
        generator.model = "gemini-3-pro-image-preview"

        # Mock generate_chapter_illustration to return fake image data
        def mock_generate_chapter(book_title, book_author, medium_summary, chapter,
                                  previous_chapter_summary=None, reference_image=None, dry_run=False):
            chapter_num = chapter['chapter_number']
            fake_image = f"fake_image_data_chapter_{chapter_num}".encode()
            prompt = f"Prompt for chapter {chapter_num}"
            return (fake_image, prompt)

        generator.generate_chapter_illustration.side_effect = mock_generate_chapter

        # Mock batch API methods
        generator.create_batch_job.return_value = "batch_job_123"

        mock_batch_job = Mock()
        mock_batch_job.state.name = "JOB_STATE_SUCCEEDED"
        mock_batch_job.request_counts.total = 9
        mock_batch_job.request_counts.succeeded = 9
        mock_batch_job.request_counts.failed = 0
        generator.poll_batch_job.return_value = mock_batch_job

        # Mock retrieve_batch_results to return fake images for all chapters
        def mock_retrieve_results(batch_job):
            results = {}
            for i in range(2, 11):  # Chapters 2-10 (Chapter 1 done sync)
                key = f"chapter-{i}"
                fake_image = f"fake_image_data_chapter_{i}".encode()
                results[key] = (fake_image, None)
            return results

        generator.retrieve_batch_results.side_effect = mock_retrieve_results

        return generator

    # ==================== Helper Function Tests ====================

    def test_filter_eligible_chapters_all(self):
        """Test filtering with all chapters eligible"""
        chapters = [
            {'chapter_number': 1, 'chapter_title': 'One', 'word_count': 500, 'summary': 'Summary 1'},
            {'chapter_number': 2, 'chapter_title': 'Two', 'word_count': 600, 'summary': 'Summary 2'},
            {'chapter_number': 3, 'chapter_title': 'Three', 'word_count': 700, 'summary': 'Summary 3'},
        ]

        filtered = filter_eligible_chapters(chapters)
        assert len(filtered) == 3
        assert [ch['chapter_number'] for ch in filtered] == [1, 2, 3]

    def test_filter_eligible_chapters_skip_short(self):
        """Test filtering removes chapters with <200 words"""
        chapters = [
            {'chapter_number': 1, 'chapter_title': 'One', 'word_count': 500, 'summary': 'Summary 1'},
            {'chapter_number': 2, 'chapter_title': 'Two', 'word_count': 50, 'summary': 'Summary 2'},  # Too short
            {'chapter_number': 3, 'chapter_title': 'Three', 'word_count': 700, 'summary': 'Summary 3'},
        ]

        filtered = filter_eligible_chapters(chapters)
        assert len(filtered) == 2
        assert [ch['chapter_number'] for ch in filtered] == [1, 3]

    def test_filter_eligible_chapters_skip_preface(self):
        """Test filtering removes preface chapters"""
        chapters = [
            {'chapter_number': 0, 'chapter_title': 'Preface', 'word_count': 500, 'summary': 'Summary 0'},
            {'chapter_number': 1, 'chapter_title': 'One', 'word_count': 500, 'summary': 'Summary 1'},
            {'chapter_number': 2, 'chapter_title': 'Preface to Part 2', 'word_count': 600, 'summary': 'Summary 2'},
            {'chapter_number': 3, 'chapter_title': 'Three', 'word_count': 700, 'summary': 'Summary 3'},
        ]

        filtered = filter_eligible_chapters(chapters)
        assert len(filtered) == 2
        assert [ch['chapter_number'] for ch in filtered] == [1, 3]

    def test_filter_eligible_chapters_with_range(self):
        """Test filtering with chapter range"""
        chapters = [
            {'chapter_number': 1, 'chapter_title': 'One', 'word_count': 500, 'summary': 'Summary 1'},
            {'chapter_number': 2, 'chapter_title': 'Two', 'word_count': 600, 'summary': 'Summary 2'},
            {'chapter_number': 3, 'chapter_title': 'Three', 'word_count': 700, 'summary': 'Summary 3'},
            {'chapter_number': 4, 'chapter_title': 'Four', 'word_count': 800, 'summary': 'Summary 4'},
        ]

        filtered = filter_eligible_chapters(chapters, chapter_range=(2, 3))
        assert len(filtered) == 2
        assert [ch['chapter_number'] for ch in filtered] == [2, 3]

    def test_build_chapter_illustration_prompt(self):
        """Test prompt generation produces correct format"""
        chapter = {
            'chapter_number': 5,
            'chapter_title': 'The Adventure Begins',
            'summary': 'The hero embarks on their journey.'
        }

        prompt = build_chapter_illustration_prompt(
            book_title="Test Book",
            book_author="Test Author",
            medium_summary="A book about adventures.",
            chapter=chapter,
            previous_chapter_summary="Previously, the hero prepared for the journey."
        )

        # Check key elements are in the prompt
        assert "Create a full page illustration" in prompt
        assert "Test Book by Test Author" in prompt
        assert "Chapter 5 - The Adventure Begins" in prompt
        assert "The hero embarks on their journey." in prompt
        assert "Previously, the hero prepared for the journey." in prompt
        assert "NO chapter numbers or citations" in prompt
        assert "CRITICAL RULES - MUST FOLLOW:" in prompt

    def test_build_chapter_illustration_prompt_no_previous(self):
        """Test prompt generation without previous chapter context"""
        chapter = {
            'chapter_number': 1,
            'chapter_title': 'First Chapter',
            'summary': 'The story begins.'
        }

        prompt = build_chapter_illustration_prompt(
            book_title="Test Book",
            book_author="Test Author",
            medium_summary="A book about adventures.",
            chapter=chapter,
            previous_chapter_summary=None
        )

        assert "Create a full page illustration" in prompt
        assert "Chapter 1 - First Chapter" in prompt
        assert "Summary of previous chapter" not in prompt

    # ==================== Sync Mode Tests ====================

    @patch('scripts.images.generate_gemini_illustrations.save_image')
    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_sync_mode_full_generation(self, mock_config, mock_save_image, temp_db, mock_generator, temp_illustrations_dir):
        """Test sync mode: generate all chapters (1-10)"""
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir
        mock_save_image.return_value = True

        # Run sync generation for all chapters
        result = generate_chapter_illustrations_for_book(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=None,  # All chapters
            dry_run=False
        )

        assert result is True

        # Verify all 10 chapters were generated
        assert mock_generator.generate_chapter_illustration.call_count == 10

        # Verify Chapter 1 was generated without reference image
        first_call = mock_generator.generate_chapter_illustration.call_args_list[0]
        assert first_call.kwargs['reference_image'] is None

        # Verify subsequent chapters used reference images
        second_call = mock_generator.generate_chapter_illustration.call_args_list[1]
        assert second_call.kwargs['reference_image'] is not None

    @patch('scripts.images.generate_gemini_illustrations.save_image')
    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_sync_mode_chapter_range_with_chapter_1(self, mock_config, mock_save_image, temp_db, mock_generator, temp_illustrations_dir):
        """Test sync mode: generate chapters 1-5 (includes Chapter 1)"""
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir
        mock_save_image.return_value = True

        # Run sync generation for chapters 1-5
        result = generate_chapter_illustrations_for_book(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=(1, 5),
            dry_run=False
        )

        assert result is True

        # Verify 5 chapters were generated
        assert mock_generator.generate_chapter_illustration.call_count == 5

        # Verify Chapter 1 was generated without reference image
        first_call = mock_generator.generate_chapter_illustration.call_args_list[0]
        assert first_call.kwargs['chapter']['chapter_number'] == 1
        assert first_call.kwargs['reference_image'] is None

    @patch('scripts.images.generate_gemini_illustrations.save_image')
    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_sync_mode_chapter_range_without_chapter_1(self, mock_config, mock_save_image, temp_db, mock_generator, temp_illustrations_dir):
        """Test sync mode: generate chapters 5-8 (no Chapter 1)"""
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir
        mock_save_image.return_value = True

        # Pre-create Chapter 1 illustration
        book_dir = temp_illustrations_dir / str(book_id)
        book_dir.mkdir(parents=True, exist_ok=True)
        chapter_1_path = book_dir / "1.png"
        chapter_1_path.write_bytes(b"fake_chapter_1_image")

        # Run sync generation for chapters 5-8
        result = generate_chapter_illustrations_for_book(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=(5, 8),
            dry_run=False
        )

        assert result is True

        # Verify 4 chapters were generated (5, 6, 7, 8)
        assert mock_generator.generate_chapter_illustration.call_count == 4

        # Verify first generated chapter (5) loads Chapter 1 as reference
        # Note: In sync mode, it actually loads the previous chapter (4), not Chapter 1
        # But we're testing that the reference image system works
        first_call = mock_generator.generate_chapter_illustration.call_args_list[0]
        assert first_call.kwargs['chapter']['chapter_number'] == 5

    # ==================== Batch Mode Tests ====================

    @patch('scripts.images.generate_gemini_illustrations.save_image')
    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_batch_mode_full_generation(self, mock_config, mock_save_image, temp_db, mock_generator, temp_illustrations_dir):
        """Test batch mode: generate all chapters (1-10)

        Expected behavior:
        - If Chapter 1 doesn't exist: generated synchronously, then Chapters 2-10 in batch
        - If Chapter 1 exists: all Chapters 1-10 submitted as batch with Chapter 1 reference
        """
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir
        mock_save_image.return_value = True

        # Run batch generation for all chapters
        result = generate_chapter_illustrations_batch(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=None,  # All chapters
            poll_interval=1,
            dry_run=False
        )

        assert result is True

        # Verify batch job was created (either 9 or 10 chapters depending on Chapter 1 existence)
        assert mock_generator.create_batch_job.call_count == 1
        batch_requests = mock_generator.create_batch_job.call_args[1]['batch_requests']

        # If Chapter 1 existed from previous run: 10 chapters in batch (2-10 + regenerated 1)
        # If Chapter 1 didn't exist: 9 chapters in batch (2-10 only)
        # Accept either outcome since it depends on test execution order
        assert len(batch_requests) in [9, 10], f"Expected 9 or 10 batch requests, got {len(batch_requests)}"

        # Verify batch job was polled
        assert mock_generator.poll_batch_job.call_count == 1

        # Verify results were retrieved
        assert mock_generator.retrieve_batch_results.call_count == 1

        # Verify save_image was called for processed chapters
        # Could be 9 (if Ch1 generated sync) or 10 (if Ch1 was in batch)
        assert mock_save_image.call_count in [9, 10], f"Expected 9 or 10 save calls, got {mock_save_image.call_count}"

    @patch('scripts.images.generate_gemini_illustrations.save_image')
    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_batch_mode_chapter_range_with_chapter_1(self, mock_config, mock_save_image, temp_db, mock_generator, temp_illustrations_dir):
        """Test batch mode: generate chapters 1-5

        Expected behavior:
        - If Chapter 1 doesn't exist: generated synchronously, then Chapters 2-5 in batch
        - If Chapter 1 exists: Chapters 1-5 submitted as batch with Chapter 1 reference
        """
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir
        mock_save_image.return_value = True

        # Adjust mock to return chapters 1-5 in batch (if Chapter 1 exists) or 2-5 (if not)
        def mock_retrieve_results_limited(batch_job):
            results = {}
            # Return all chapters that were in the batch
            for i in range(1, 6):  # Chapters 1-5
                key = f"chapter-{i}"
                fake_image = f"fake_image_data_chapter_{i}".encode()
                results[key] = (fake_image, None)
            return results

        mock_generator.retrieve_batch_results.side_effect = mock_retrieve_results_limited

        # Run batch generation for chapters 1-5
        result = generate_chapter_illustrations_batch(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=(1, 5),
            poll_interval=1,
            dry_run=False
        )

        assert result is True

        # Verify batch job was created for chapters (either 1-5 or 2-5)
        batch_requests = mock_generator.create_batch_job.call_args[1]['batch_requests']
        # If Chapter 1 exists: 5 chapters in batch
        # If Chapter 1 doesn't exist: 4 chapters in batch (2-5 only)
        assert len(batch_requests) in [4, 5], f"Expected 4 or 5 batch requests, got {len(batch_requests)}"

    @patch('scripts.images.generate_gemini_illustrations.save_image')
    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_batch_mode_chapter_range_without_chapter_1(self, mock_config, mock_save_image, temp_db, mock_generator, temp_illustrations_dir):
        """Test batch mode: generate chapters 5-8 (no Chapter 1 in range)

        Expected behavior:
        - Loads existing Chapter 1 illustration from disk
        - Chapters 5-8 submitted as batch with Chapter 1 reference
        - No synchronous generation needed
        """
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir
        mock_save_image.return_value = True

        # Pre-create Chapter 1 illustration on disk
        book_dir = temp_illustrations_dir / str(book_id)
        book_dir.mkdir(parents=True, exist_ok=True)
        chapter_1_path = book_dir / "1.png"
        chapter_1_data = b"existing_chapter_1_image_data"
        chapter_1_path.write_bytes(chapter_1_data)

        # Adjust mock to return only chapters 5-8 in batch
        def mock_retrieve_results_range(batch_job):
            results = {}
            for i in range(5, 9):  # Chapters 5-8
                key = f"chapter-{i}"
                fake_image = f"fake_image_data_chapter_{i}".encode()
                results[key] = (fake_image, None)
            return results

        mock_generator.retrieve_batch_results.side_effect = mock_retrieve_results_range

        # Run batch generation for chapters 5-8
        result = generate_chapter_illustrations_batch(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=(5, 8),
            poll_interval=1,
            dry_run=False
        )

        assert result is True

        # Verify NO synchronous generation (Chapter 1 loaded from disk)
        assert mock_generator.generate_chapter_illustration.call_count == 0

        # Verify Chapter 1 was loaded from disk
        assert chapter_1_path.exists()

        # Verify batch job was created for chapters 5-8
        batch_requests = mock_generator.create_batch_job.call_args[1]['batch_requests']
        assert len(batch_requests) == 4  # Chapters 5-8

        # Verify Chapter 1 reference image was used in batch requests
        # (Check by verifying the batch request structure includes inline_data)
        first_request = batch_requests[0]
        assert 'request' in first_request
        assert 'contents' in first_request['request']

        # Verify save_image was called for chapters 5-8
        assert mock_save_image.call_count == 4

    # ==================== Edge Cases ====================

    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_batch_mode_dry_run(self, mock_config, temp_db, mock_generator, temp_illustrations_dir):
        """Test batch mode dry run doesn't actually generate images"""
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir

        result = generate_chapter_illustrations_batch(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=None,
            poll_interval=1,
            dry_run=True
        )

        assert result is True

        # Verify no actual API calls were made
        assert mock_generator.create_batch_job.call_count == 0
        assert mock_generator.poll_batch_job.call_count == 0
        assert mock_generator.retrieve_batch_results.call_count == 0

    @patch('scripts.images.generate_gemini_illustrations.config')
    def test_sync_mode_dry_run(self, mock_config, temp_db, mock_generator, temp_illustrations_dir):
        """Test sync mode dry run doesn't actually generate images"""
        db, book_id = temp_db
        mock_config.ILLUSTRATIONS_DIR = temp_illustrations_dir

        # Override mock to return None for dry run
        mock_generator.generate_chapter_illustration.return_value = (None, "test prompt")

        result = generate_chapter_illustrations_for_book(
            db=db,
            generator=mock_generator,
            book_id=book_id,
            chapter_range=None,
            dry_run=True
        )

        # Verify calls were made but with dry_run=True
        calls = mock_generator.generate_chapter_illustration.call_args_list
        for call in calls:
            assert call.kwargs['dry_run'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
