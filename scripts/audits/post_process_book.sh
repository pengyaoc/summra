#!/usr/bin/env bash
# Runs steps 2-4 of the Plain English workflow for a single book and emits
# an audit table on stdout. Idempotent. No LLM calls.
#
# Usage:  scripts/audits/post_process_book.sh <book_id>
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <book_id>" >&2
  exit 2
fi
BOOK_ID="$1"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "=== Book $BOOK_ID: step 2 reformat (chapter_text) ==="
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id "$BOOK_ID" || true

echo "=== Book $BOOK_ID: step 2 reformat (modern_english_text) ==="
PYTHONPATH=backend venv/bin/python scripts/audits/reformat_paragraphs.py --book-id "$BOOK_ID" --column modern_english_text || true

echo "=== Book $BOOK_ID: step 3 strip decorative dividers ==="
PYTHONPATH=backend venv/bin/python scripts/audits/strip_decorative_dividers.py --book-id "$BOOK_ID" || true

echo "=== Book $BOOK_ID: step 4 audit ==="
PYTHONPATH=backend venv/bin/python3 -c "
import sqlite3, sys
bid = $BOOK_ID
db = sqlite3.connect('data/database.db')
def c(t): return len(t.strip().split(chr(10)*2)) if t and t.strip() else 0
exact = 0; small = 0; large = 0; missing = 0; truncated = 0; total = 0
rows = list(db.execute('SELECT chapter_number, chapter_text, modern_english_text FROM chapters WHERE book_id=? ORDER BY chapter_number', (bid,)))
for n, ot, mt in rows:
    total += 1
    if mt is None or mt == '':
        print(f'  ch.{n:>3}: NULL')
        missing += 1
        continue
    o = c(ot); m = c(mt)
    ratio = len(mt) / max(1, len(ot)) * 100
    end = mt.rstrip()[-1] if mt.rstrip() else ''
    diff = o - m
    if diff == 0:
        flag = 'EXACT'
        exact += 1
    elif abs(diff) <= 5:
        flag = 'SMALL_DIFF'
        small += 1
    else:
        flag = 'LARGE_DIFF'
        large += 1
    trunc_flag = ''
    if ratio < 50 or (end and end not in '.!?\"\\')]”’'):
        trunc_flag = ' TRUNC?'
        truncated += 1
    print(f'  ch.{n:>3}: orig={o:>4} mod={m:>4} diff={diff:+d} ratio={ratio:>5.0f}% ends={end!r:>5} {flag}{trunc_flag}')
print(f'  --- SUMMARY book={bid}: total={total} exact={exact} small_diff={small} large_diff={large} truncated={truncated} missing={missing} ---')
"
