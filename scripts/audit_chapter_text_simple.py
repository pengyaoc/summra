#!/usr/bin/env python3
"""
Simple database audit - compare total chapter text with source file size.
Much faster than re-parsing chapters, just validates rough character counts.
"""

import sys
import os
from pathlib import Path
import csv
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from backend import models
import config


class SimpleChapterAuditor:
    """Simple auditor that compares total character counts"""

    def __init__(self):
        self.db = models.Database()
        self.books_dir = Path(config.BOOKS_DIR)

    def get_source_file_path(self, filename: str, gutenberg_id: Optional[int]) -> Optional[Path]:
        """Find the source file for a book."""
        if not filename:
            if gutenberg_id:
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

    def extract_gutenberg_content(self, text: str) -> str:
        """
        Extract the actual book content, removing Gutenberg headers/footers.
        Uses same logic as generate_summaries.py for consistency.
        """
        # Look for standard Project Gutenberg markers
        start_markers = [
            '*** START OF THE PROJECT GUTENBERG EBOOK',
            '*** START OF THIS PROJECT GUTENBERG EBOOK',
            '***START OF THE PROJECT GUTENBERG EBOOK'
        ]

        end_markers = [
            '*** END OF THE PROJECT GUTENBERG EBOOK',
            '*** END OF THIS PROJECT GUTENBERG EBOOK',
            '***END OF THE PROJECT GUTENBERG EBOOK'
        ]

        # Find start position
        start_pos = 0
        for marker in start_markers:
            pos = text.upper().find(marker)
            if pos != -1:
                # Find the end of the line after the marker
                start_pos = text.find('\n', pos) + 1
                break

        # Find end position
        end_pos = len(text)
        for marker in end_markers:
            pos = text.upper().find(marker)
            if pos != -1:
                end_pos = pos
                break

        # Extract content
        if start_pos > 0 or end_pos < len(text):
            content = text[start_pos:end_pos]
            # Remove excessive leading/trailing newlines
            content = content.strip()
            return content

        return text

    def get_source_content_size(self, source_path: Path) -> int:
        """
        Get content size from source file after removing Gutenberg header/footer.
        """
        with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

        # Extract content (removes headers/footers)
        content = self.extract_gutenberg_content(text)

        return len(content)

    def audit_book(self, book: Dict) -> Dict:
        """
        Simple audit: compare DB total chars with source file size.

        Returns:
            Dictionary with audit results
        """
        result = {
            'book_id': book['id'],
            'title': book['title'],
            'author': book['author'],
            'gutenberg_id': book.get('gutenberg_id'),
            'filename': book.get('filename'),
            'source_found': False,
            'db_chapter_count': 0,
            'db_total_chars': 0,
            'source_total_chars': 0,
            'char_diff_pct': 0.0,
            'coverage_pct': 0.0,
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
                result['db_total_chars'] += len(chapter['chapter_text'])

        # Get source file size (with Gutenberg header/footer removed)
        try:
            result['source_total_chars'] = self.get_source_content_size(source_path)

            # Calculate metrics
            if result['source_total_chars'] > 0:
                result['coverage_pct'] = (result['db_total_chars'] / result['source_total_chars']) * 100
                char_diff = abs(result['db_total_chars'] - result['source_total_chars'])
                result['char_diff_pct'] = (char_diff / result['source_total_chars']) * 100

            # Determine status
            if result['db_total_chars'] == 0:
                result['status'] = 'empty_db'
                result['notes'] = 'No chapter_text in database'
            elif result['char_diff_pct'] < 5:
                result['status'] = 'perfect'
                result['notes'] = 'Excellent match'
            elif result['char_diff_pct'] < 15:
                result['status'] = 'good'
                result['notes'] = 'Good match (minor differences)'
            elif result['char_diff_pct'] < 30:
                result['status'] = 'fair'
                result['notes'] = 'Fair match (may need review)'
            else:
                result['status'] = 'poor'
                result['notes'] = 'Significant difference (needs investigation)'

        except Exception as e:
            result['status'] = 'error'
            result['notes'] = f'Error reading source: {str(e)}'

        return result

    def run_full_audit(self) -> List[Dict]:
        """Audit all books in the database."""
        print("Starting simple database audit (character count comparison)...")
        print(f"Books directory: {self.books_dir}")
        print()

        books = self.db.get_all_books()
        print(f"Found {len(books)} books in database")
        print()

        results = []
        for i, book in enumerate(books, 1):
            print(f"[{i}/{len(books)}] {book['title'][:60]:<60} ", end='')
            result = self.audit_book(book)
            results.append(result)

            if result['source_found']:
                coverage = result['coverage_pct']
                diff = result['char_diff_pct']
                status_icon = {
                    'perfect': '✓',
                    'good': '✓',
                    'fair': '⚠',
                    'poor': '✗',
                    'empty_db': '✗'
                }.get(result['status'], '?')

                print(f"{status_icon} {coverage:5.1f}% ({diff:4.1f}% diff)")
            else:
                print(f"✗ No source")

        return results

    def print_summary(self, results: List[Dict]):
        """Print summary statistics"""
        total = len(results)

        status_counts = {}
        for result in results:
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        print()
        print("=" * 80)
        print("AUDIT SUMMARY")
        print("=" * 80)
        print(f"Total books audited: {total}")
        print()
        print("Status breakdown:")
        for status in ['perfect', 'good', 'fair', 'poor', 'empty_db', 'no_source', 'error']:
            if status in status_counts:
                count = status_counts[status]
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
                overall_coverage = (total_db_chars / total_source_chars) * 100
                overall_diff = abs(total_db_chars - total_source_chars)
                overall_diff_pct = (overall_diff / total_source_chars) * 100

                print(f"  Total DB chars:     {total_db_chars:,}")
                print(f"  Total source chars: {total_source_chars:,}")
                print(f"  Overall coverage:   {overall_coverage:.1f}%")
                print(f"  Overall difference: {overall_diff_pct:.1f}%")

        print()
        print("=" * 80)

    def print_issues(self, results: List[Dict]):
        """Print books that need attention"""
        issues = [r for r in results if r['status'] in ['fair', 'poor', 'empty_db']]

        if not issues:
            print()
            print("No issues found! All books have good coverage.")
            return

        print()
        print("=" * 80)
        print(f"BOOKS NEEDING ATTENTION ({len(issues)} books)")
        print("=" * 80)
        print()

        for result in sorted(issues, key=lambda r: r['char_diff_pct'], reverse=True):
            print(f"Book ID {result['book_id']}: {result['title']}")
            print(f"  Status: {result['status'].upper()}")
            print(f"  DB: {result['db_chapter_count']} chapters, {result['db_total_chars']:,} chars")
            print(f"  Source: {result['source_total_chars']:,} chars")
            print(f"  Coverage: {result['coverage_pct']:.1f}% (difference: {result['char_diff_pct']:.1f}%)")
            print(f"  Notes: {result['notes']}")
            print()

    def export_csv(self, results: List[Dict], output_path: str = 'audit_results_simple.csv'):
        """Export results to CSV"""
        fieldnames = [
            'book_id', 'title', 'author', 'gutenberg_id', 'filename',
            'source_found', 'status', 'db_chapter_count',
            'db_total_chars', 'source_total_chars',
            'coverage_pct', 'char_diff_pct', 'notes'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"Results exported to: {output_path}")


def main():
    """Main entry point"""
    auditor = SimpleChapterAuditor()

    # Run full audit
    results = auditor.run_full_audit()

    # Print summary
    auditor.print_summary(results)

    # Print issues
    auditor.print_issues(results)

    # Export to CSV
    auditor.export_csv(results)
    print()


if __name__ == '__main__':
    main()
