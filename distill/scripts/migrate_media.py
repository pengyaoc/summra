"""Extract/verify legacy image BLOBs, optionally compacting the content database.

Stop the app/import writers and take a consistent backup before --compact.
Existing image URLs and IDs stay unchanged. Re-running is safe.
"""
import argparse
import json
from pathlib import Path

from distill import config
from distill.models import DistillDatabase


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=config.DATABASE_PATH)
    parser.add_argument('--media-dir', type=Path)
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args(argv)
    if not args.db.is_file():
        parser.error('database does not exist')
    before = args.db.stat().st_size
    db = DistillDatabase(args.db, media_dir=args.media_dir)
    count = db.verify_media()
    if args.compact:
        db.compact()
    print(json.dumps({'verified_files': count, 'media_dir': str(db.media.root),
                      'database_bytes_before': before, 'database_bytes_after': args.db.stat().st_size}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
