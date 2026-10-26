"""Distill's reader, described for the shared reader platform."""
from shared.reader.config import KindleOptions, ReaderConfig, ReaderFeatures, ReaderMode

DISTILL_READER = ReaderConfig(
    app_name='Distill',
    cache_db_name='distill-reader-v1',
    cache_visibility='private',
    modes=(ReaderMode('summary', 'Summary'),),
    default_modes=('summary',),
    features=ReaderFeatures(progress=True, illustrations=False, page_turn_hint=True, kindle=True),
    kindle=KindleOptions((('summary', 'Summary'),), 'summary'),
    extra_page_blocks='table.reader-table, figure.reader-figure',
    inline='strict',
    image_base='',
    hint_keys=frozenset({'reader_swipe_mobile', 'reader_nav_desktop'}),
)
