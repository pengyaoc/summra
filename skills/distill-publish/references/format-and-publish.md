# Format and publishing reference

## Format v1

The active checkout's `distill/book_format.py` is authoritative. Minimal article:

```json
{
  "format": 1,
  "slug": "example-research-2026-10-31",
  "title": "Example Research",
  "author": "Author as credited by the source",
  "lang": "en",
  "categories": ["Equity research"],
  "overview": [],
  "parts": [{
    "title": null,
    "chapters": [{
      "title": "Source section title",
      "blocks": [
        {"type": "p", "text": "Complete source paragraph."},
        {"type": "h", "text": "Source subheading"},
        {"type": "ul", "items": ["First item", "Second item"]},
        {"type": "table", "presentation": "grid",
         "header": ["Metric", "Value"], "rows": [["Revenue", "$100 million"]]}
      ]
    }]
  }],
  "sources": [{"type": "p", "text": "Original title, credited author, date, and source URL where available. Published in full; formatting adapted for Distill."}]
}
```

Use actual source attribution, not the example values. `author` and `cover` may be omitted; never guess authorship. `lang` is two lowercase letters. Optional `cover` is an `images/<file>.jpg` or `.png` path. Empty `overview` creates no Overview chapter; nonempty `sources` adds a terminal Source chapter. Preserve the original bibliography in the original text even when adding provenance here.

Block shapes:

| Type | Fields |
| --- | --- |
| `p`, `h`, `quote` | `text`: string |
| `ul`, `ol`, `keypoints` | `items`: list of strings |
| `table` | `header`: list of strings; `rows`: list of lists of strings; optional `presentation`: `grid` |
| `image` | `src`: `images/<filename>.jpg` or `.png`; optional `caption`: string |

All cell values are strings. Check rectangularity yourself; the validator does not enforce equal row lengths. Plain tables without `presentation: "grid"` keep the existing labeled flow presentation. `keypoints` is supported, but not required for a full-content publication. Images are validated by actual file encoding, not extension alone. Inline text accepts `**bold**` and `*italic*`; unbalanced markers, HTML, and Markdown hyperlinks fail validation. Unsupported headings/lists/formulas require a faithful adaptation, not deletion.

## Commands and staging

Run from the repository root with its existing virtual environment. Replace `/path/to/staged-entry` and scratch paths with real task paths:

```bash
venv/bin/python -m distill.scripts.push_book /path/to/staged-entry --dry-run
venv/bin/python -m distill.scripts.push_book /path/to/staged-entry --db /tmp/distill-publish-TASK/content.db
```

The scratch import writes only the selected content DB and its associated media directory. For a preview, run the app with both scratch DB paths and an unused port:

```bash
DISTILL_DB=/tmp/distill-publish-TASK/content.db DISTILL_USER_DB=/tmp/distill-publish-TASK/users.db PORT=5003 venv/bin/python -m distill.app
```

Inspect `/books/<slug>` and its reader; production adds `/distill`. Confirm current app configuration if the preview requires authentication. Do not change production auth to make testing easier.

## Catalog preflight and deployment

Read settings from gitignored `deploy/distill/deploy.local.env`; the shape is documented in `deploy/distill/deploy.local.env.example`. Do not print secrets, commit that file, or invent VM coordinates. The current owner's usual VM is `wordpress-2-vm`, repo `/opt/summra`; trust the current config over this historical hint.

For consistent reads/backups use `sqlite3.Connection.backup()` rather than copying an open SQLite DB with `cp` (WAL can hold committed data). Query local and VM-live content databases read-only. A useful catalog inventory is:

```sql
SELECT id, slug, title, author, lang, sources, categories, content_checksum
FROM books ORDER BY id;
```

Compare deterministic JSON records, not database file hashes (SQLite layout may differ). Before importing into the master, the local/live inventories must agree or be explicitly reconciled. Preserve a pre-import inventory; after import, only the intended entry may change. Check referenced media and cover metadata as well when updating illustrations: `content_checksum` does not cover every metadata/media field. Re-importing a slug preserves the book ID and chapter IDs by ordinal, not by heading text; do not casually reorder an existing entry.

After preflight and local backup:

```bash
venv/bin/python -m distill.scripts.push_book /path/to/staged-entry --deploy
```

This validates, imports into local `data/distill.db`, then uses `distill/scripts/deploy_db.py` to snapshot content, install verified media, back up live databases, upload/hash-check metadata, swap the content DB and restart Distill. Account/progress databases are backed up, not replaced. It is a full-catalog deployment, not a server-side single-article upload. There is no automatic concurrency lock or catalog-divergence guard in this command; perform the preflight yourself.

If import succeeded but deployment failed, local is now ahead. Inspect live state, backup status and service health; do not interpret that expected local difference as permission to discard remote changes. Fix the concrete failure and redeploy the verified content snapshot using the existing `deploy_db` command when appropriate. Stop on unresolved catalog conflicts or missing deployment access and report the actionable blocker.

Expected final link: `https://pengyaochen.com/distill/books/<slug>`. Validate it with the authenticated reader; a sign-in redirect alone does not prove the entry exists. Use the existing reader manifest/segment requests observed in browser or route tests rather than inventing endpoint paths. No separate EPUB export is needed for Distill's Kindle browser mode.
