"""
Analyze chapter names across all books to identify anomalies.
Anomalies include:
- Case inconsistencies (camelCase vs ALL CAPS vs Title Case)
- Length outliers (one very long/short compared to others)
"""

import sqlite3
from collections import defaultdict
import statistics

def analyze_chapter_names():
    conn = sqlite3.connect('data/database.db')
    cursor = conn.cursor()

    # Get all books with their chapters
    cursor.execute("""
        SELECT b.id, b.title, c.chapter_number, c.chapter_title
        FROM books b
        JOIN chapters c ON b.id = c.book_id
        ORDER BY b.id, c.chapter_number
    """)

    books = defaultdict(list)
    for book_id, book_title, chapter_num, chapter_title in cursor.fetchall():
        books[(book_id, book_title)].append({
            'number': chapter_num,
            'title': chapter_title
        })

    conn.close()

    anomalies = []

    for (book_id, book_title), chapters in books.items():
        if len(chapters) < 2:
            continue

        chapter_titles = [ch['title'] for ch in chapters]

        # Check for case inconsistencies
        case_patterns = []
        for title in chapter_titles:
            if not title or not title.strip():
                case_patterns.append('Empty')
            elif title.isupper():
                case_patterns.append('UPPER')
            elif title.islower():
                case_patterns.append('lower')
            elif title[0].isupper() and not title.isupper():
                # Check if it's Title Case
                words = title.split()
                if all(w[0].isupper() if w else False for w in words if w):
                    case_patterns.append('Title Case')
                else:
                    case_patterns.append('Mixed')
            else:
                case_patterns.append('Mixed')

        # Find outliers in case patterns
        from collections import Counter
        case_counts = Counter(case_patterns)
        most_common_case = case_counts.most_common(1)[0][0]

        for i, (title, case) in enumerate(zip(chapter_titles, case_patterns)):
            if case != most_common_case and len(case_counts) > 1:
                anomalies.append({
                    'book_id': book_id,
                    'book_title': book_title,
                    'chapter_num': chapters[i]['number'],
                    'chapter_title': title,
                    'issue': f'Case mismatch: "{case}" vs majority "{most_common_case}"',
                    'type': 'case'
                })

        # Check for length anomalies
        lengths = [len(title) for title in chapter_titles]
        if len(lengths) > 2:
            mean_length = statistics.mean(lengths)
            stdev_length = statistics.stdev(lengths) if len(lengths) > 1 else 0

            for i, length in enumerate(lengths):
                # Flag if more than 2 standard deviations away OR if very different ratio
                if stdev_length > 0 and abs(length - mean_length) > 2 * stdev_length:
                    anomalies.append({
                        'book_id': book_id,
                        'book_title': book_title,
                        'chapter_num': chapters[i]['number'],
                        'chapter_title': chapter_titles[i],
                        'issue': f'Length outlier: {length} chars (avg: {mean_length:.1f}, stdev: {stdev_length:.1f})',
                        'type': 'length'
                    })
                elif length > mean_length * 3 or (mean_length > 20 and length < mean_length / 3):
                    anomalies.append({
                        'book_id': book_id,
                        'book_title': book_title,
                        'chapter_num': chapters[i]['number'],
                        'chapter_title': chapter_titles[i],
                        'issue': f'Length ratio outlier: {length} chars vs avg {mean_length:.1f}',
                        'type': 'length'
                    })

    return anomalies

def main():
    print("Analyzing chapter names across all books...\n")
    anomalies = analyze_chapter_names()

    if not anomalies:
        print("No anomalies found!")
        return

    # Group by book
    from collections import defaultdict
    by_book = defaultdict(list)
    for anomaly in anomalies:
        by_book[anomaly['book_title']].append(anomaly)

    print(f"Found {len(anomalies)} anomalies across {len(by_book)} books:\n")
    print("=" * 100)

    for book_title, book_anomalies in sorted(by_book.items()):
        print(f"\n📚 {book_title} (Book ID: {book_anomalies[0]['book_id']})")
        print("-" * 100)

        for anomaly in sorted(book_anomalies, key=lambda x: x['chapter_num']):
            print(f"  Chapter {anomaly['chapter_num']}: {anomaly['chapter_title'][:80]}")
            print(f"  ⚠️  {anomaly['issue']}")
            print()

if __name__ == '__main__':
    main()
