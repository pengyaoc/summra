"""Plainly's reader, described for the shared reader platform."""
from plainly import config
from shared.reader.config import (
    KindleOptions, ReaderConfig, ReaderFeatures, ReaderMember, ReaderMode,
)

PLAINLY_READER = ReaderConfig(
    app_name='Plainly',
    cache_db_name='summra-reader-v2',
    cache_visibility='public',
    modes=(
        ReaderMode('summary', 'Summary'),
        ReaderMode('original', 'Original'),
        ReaderMode('plain', 'Plain English'),
        ReaderMode(
            'side_by_side', 'Side-by-Side',
            layout='side_by_side',
            members=(
                ReaderMember('original', 'Original', 'original'),
                ReaderMember('plain', 'Plain English', 'modern'),
            ),
            library_label='Side by side',
            min_width=1024,
            narrow_fallback=('plain', 'original'),
        ),
    ),
    default_modes=('plain', 'original'),
    features=ReaderFeatures(
        progress=config.FEATURE_AUTH, illustrations=True, page_turn_hint=True, kindle=True,
    ),
    kindle=KindleOptions((('plain', 'Plain English'), ('original', 'Original')), 'plain'),
    hint_keys=config.READER_HINTS,
)
