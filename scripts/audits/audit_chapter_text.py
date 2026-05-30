#!/usr/bin/env python3
"""
Audit script to compare database chapter_text with Gutenberg source file extraction.
Identifies books with significant discrepancies between stored chapter text and re-extraction.
"""

import sys
import os
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from backend import models
import config
from scripts.content.generate_summaries import SummaryGenerator


class ChapterTextAuditor:
    """Audits database chapter text against source files"""

    def __init__(self):
        self.db = models.Database()
        # Use dummy API key - we only need text processing methods, not LLM calls
        self.generator = SummaryGenerator(api_key="dummy")
        self.books_dir = Path(config.BOOKS_DIR)

    def get_source_file_path(self, filename: str, gutenberg_id: Optional[int]) -> Optional[Path]:
        """
        Find the source file for a book.
        Tries multiple filename patterns.
        """
        if not filename:
            if gutenberg_id:
                # Try pg{ID}.txt format
                pg_file = self.books_dir / f"pg{gutenberg_id}.txt"
                if pg_file.exists():
                    return pg_file
            return None

        # Try the filename as-is
        file_path = self.books_dir / filename
        if file_path.exists():
            return file_path

        # Try with .txt extension
        if not filename.endswith('.txt'):
            file_path = self.books_dir / f"{filename}.txt"
            if file_path.exists():
                return file_path

        # Try pg{ID}.txt if we have a Gutenberg ID
        if gutenberg_id:
            pg_file = self.books_dir / f"pg{gutenberg_id}.txt"
            if pg_file.exists():
                return pg_file

        return None

    def extract_chapters_from_source(self, source_path: Path, is_poetry: bool = False) -> List[Tuple[int, str, str]]:
        """
        Re-extract chapters from source file using the same logic as generate_summaries.py

        Returns:
            List of (chapter_number, chapter_title, chapter_text) tuples
        """
        # Read source file
        with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw_text = f.read()

        # Extract Gutenberg content (remove headers/footers)
        cleaned_text = self.generator.extract_gutenberg_content(raw_text)

        # Detect chapters
        chapters, _ = self.generator.detect_chapters(cleaned_text, toc_structure=None, is_poetry=is_poetry)

        # Normalize chapter text
        normalized_chapters = []
        for chapter_num, chapter_title, chapter_text in chapters:
            normalized_text = self.generator.normalize_chapter_text(chapter_text, is_poetry=is_poetry)
            normalized_chapters.append((chapter_num, chapter_title, normalized_text))

        return normalized_chapters

    def calculate_text_stats(self, text: str) -> Dict[str, int]:
        """Calculate character and word counts for text"""
        if not text:
            return {'chars': 0, 'words': 0}

        char_count = len(text)
        word_count = len(text.split())
        return {'chars': char_count, 'words': word_count}

    def audit_book(self, book: Dict) -> Dict:
        """
        Audit a single book by comparing DB chapter text with re-extracted source.

        Returns:
            Dictionary with audit results
        """
        result = {
            'book_id': book['id'],
            'title': book['title'],
            'author': book['author'],
            'gutenberg_id': book.get('gutenberg_id'),
            'filename': book.get('filename'),
            'is_poetry': book.get('is_poetry', False),
            'source_found': False,
            'db_chapter_count': 0,
            'source_chapter_count': 0,
            'db_total_chars': 0,
            'source_total_chars': 0,
            'db_total_words': 0,
            'source_total_words': 0,
            'char_diff_pct': 0.0,
            'word_diff_pct': 0.0,
            'missing_chapters': [],
            'extra_chapters': [],
            'status': 'unknown',
            'notes': ''
        }

        # Find source file
        source_path = self.get_source_file_path(book.get('filename'), book.get('gutenberg_id'))
        if not source_path:
            result['status'] = 'no_source'
            result['notes'] = 'Source file not found'
            return result

        result['source_found'] = True

        # Get DB chapters
        db_chapters = self.db.get_chapters(book['id'])
        result['db_chapter_count'] = len(db_chapters)

        # Calculate DB stats
        for chapter in db_chapters:
            if chapter.get('chapter_text'):
                stats = self.calculate_text_stats(chapter['chapter_text'])
                result['db_total_chars'] += stats['chars']
                result['db_total_words'] += stats['words']

        # Re-extract from source
        try:
            source_chapters = self.extract_chapters_from_source(source_path, is_poetry=book.get('is_poetry', False))
            result['source_chapter_count'] = len(source_chapters)

            # Calculate source stats
            for _, _, chapter_text in source_chapters:
                stats = self.calculate_text_stats(chapter_text)
                result['source_total_chars'] += stats['chars']
                result['source_total_words'] += stats['words']

            # Compare chapter counts
            db_chapter_nums = {ch['chapter_number'] for ch in db_chapters}
            source_chapter_nums = {ch_num for ch_num, _, _ in source_chapters}

            result['missing_chapters'] = sorted(list(source_chapter_nums - db_chapter_nums))
            result['extra_chapters'] = sorted(list(db_chapter_nums - source_chapter_nums))

            # Calculate discrepancy percentages
            if result['source_total_chars'] > 0:
                char_diff = abs(result['db_total_chars'] - result['source_total_chars'])
                result['char_diff_pct'] = (char_diff / result['source_total_chars']) * 100

            if result['source_total_words'] > 0:
                word_diff = abs(result['db_total_words'] - result['source_total_words'])
                result['word_diff_pct'] = (word_diff / result['source_total_words']) * 100

            # Determine status
            if result['db_total_chars'] == 0:
                result['status'] = 'empty_db'
                result['notes'] = 'No chapter_text in database'
            elif result['char_diff_pct'] < 1:
                result['status'] = 'perfect'
                result['notes'] = 'Perfect or near-perfect match'
            elif result['char_diff_pct'] < 10:
                result['status'] = 'minor'
                result['notes'] = 'Minor differences (likely normalization)'
            else:
                result['status'] = 'major'
                result['notes'] = 'Significant discrepancy - needs investigation'

                # Add specific notes
                if result['missing_chapters']:
                    result['notes'] += f" | Missing {len(result['missing_chapters'])} chapters in DB"
                if result['extra_chapters']:
                    result['notes'] += f" | {len(result['extra_chapters'])} extra chapters in DB"

        except Exception as e:
            result['status'] = 'error'
            result['notes'] = f'Error extracting chapters: {str(e)}'

        return result

    def run_full_audit(self) -> List[Dict]:
        """
        Audit all books in the database.

        Returns:
            List of audit results for each book
        """
        print("Starting full database audit...")
        print(f"Books directory: {self.books_dir}")
        print()

        # Get all books
        books = self.db.get_all_books()
        print(f"Found {len(books)} books in database")
        print()

        results = []
        for i, book in enumerate(books, 1):
            print(f"[{i}/{len(books)}] Auditing: {book['title']} (ID: {book['id']})")
            result = self.audit_book(book)
            results.append(result)

            # Print summary
            if result['source_found']:
                print(f"  Status: {result['status'].upper()}")
                print(f"  DB: {result['db_chapter_count']} chapters, {result['db_total_chars']:,} chars")
                print(f"  Source: {result['source_chapter_count']} chapters, {result['source_total_chars']:,} chars")
                print(f"  Difference: {result['char_diff_pct']:.1f}% chars, {result['word_diff_pct']:.1f}% words")
                if result['notes']:
                    print(f"  Notes: {result['notes']}")
            else:
                print(f"  Status: {result['status'].upper()} - {result['notes']}")
            print()

        return results

    def print_summary(self, results: List[Dict]):
        """Print summary statistics"""
        total = len(results)

        status_counts = {}
        for result in results:
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        print("=" * 80)
        print("AUDIT SUMMARY")
        print("=" * 80)
        print(f"Total books audited: {total}")
        print()
        print("Status breakdown:")
        for status, count in sorted(status_counts.items()):
            pct = (count / total) * 100
            print(f"  {status:12s}: {count:3d} ({pct:5.1f}%)")
        print()

        # Books with sources
        with_sources = [r for r in results if r['source_found']]
        if with_sources:
            print(f"Books with source files: {len(with_sources)}")

            # Calculate aggregate stats
            total_db_chars = sum(r['db_total_chars'] for r in with_sources)
            total_source_chars = sum(r['source_total_chars'] for r in with_sources)

            if total_source_chars > 0:
                overall_diff = abs(total_db_chars - total_source_chars)
                overall_pct = (overall_diff / total_source_chars) * 100
                coverage_pct = (total_db_chars / total_source_chars) * 100

                print(f"  Total DB chars:     {total_db_chars:,}")
                print(f"  Total source chars: {total_source_chars:,}")
                print(f"  Overall coverage:   {coverage_pct:.1f}%")
                print(f"  Overall difference: {overall_pct:.1f}%")

        print()
        print("=" * 80)

    def export_csv(self, results: List[Dict], output_path: str = 'audit_results.csv'):
        """Export results to CSV"""
        fieldnames = [
            'book_id', 'title', 'author', 'gutenberg_id', 'filename', 'is_poetry',
            'source_found', 'status', 'db_chapter_count', 'source_chapter_count',
            'db_total_chars', 'source_total_chars', 'db_total_words', 'source_total_words',
            'char_diff_pct', 'word_diff_pct', 'missing_chapters', 'extra_chapters', 'notes'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                # Convert lists to strings for CSV
                row = result.copy()
                row['missing_chapters'] = ','.join(map(str, result['missing_chapters']))
                row['extra_chapters'] = ','.join(map(str, result['extra_chapters']))
                writer.writerow(row)

        print(f"Results exported to: {output_path}")

    def print_major_issues(self, results: List[Dict]):
        """Print detailed list of books with major discrepancies"""
        major_issues = [r for r in results if r['status'] == 'major']

        if not major_issues:
            print("No major discrepancies found!")
            return

        print("=" * 80)
        print(f"BOOKS WITH MAJOR DISCREPANCIES ({len(major_issues)} books)")
        print("=" * 80)
        print()

        for result in sorted(major_issues, key=lambda r: r['char_diff_pct'], reverse=True):
            print(f"Book ID {result['book_id']}: {result['title']}")
            print(f"  Author: {result['author']}")
            print(f"  Source: {result['filename']} (Gutenberg ID: {result['gutenberg_id']})")
            print(f"  DB chapters:     {result['db_chapter_count']:3d} ({result['db_total_chars']:,} chars)")
            print(f"  Source chapters: {result['source_chapter_count']:3d} ({result['source_total_chars']:,} chars)")
            print(f"  Difference:      {result['char_diff_pct']:.1f}% chars, {result['word_diff_pct']:.1f}% words")

            if result['missing_chapters']:
                print(f"  Missing chapters: {result['missing_chapters'][:10]}" +
                      ("..." if len(result['missing_chapters']) > 10 else ""))
            if result['extra_chapters']:
                print(f"  Extra chapters:   {result['extra_chapters'][:10]}" +
                      ("..." if len(result['extra_chapters']) > 10 else ""))

            print(f"  Notes: {result['notes']}")
            print()


def main():
    """Main entry point"""
    auditor = ChapterTextAuditor()

    # Run full audit
    results = auditor.run_full_audit()

    # Print summary
    auditor.print_summary(results)

    # Print major issues
    auditor.print_major_issues(results)

    # Export to CSV
    auditor.export_csv(results)
    print()


if __name__ == '__main__':
    main()
