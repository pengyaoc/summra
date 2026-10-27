"""Distill's reader, described for the shared reader platform."""
from shared.reader.config import KindleOptions, ReaderConfig, ReaderFeatures, ReaderMode

DISTILL_READER = ReaderConfig(
    app_name='Distill',
    cache_db_name='distill-reader-v1',
    cache_visibility='private',
    modes=(ReaderMode('summary', 'Summary'),),
    default_modes=('summary',),
    features=ReaderFeatures(progress=True, illustrations=False, page_turn_hint=True, kindle=True,
                            automatic_completion=False),
    kindle=KindleOptions((('summary', 'Summary'),), 'summary', font_size_max=10, font_size_default=6,
                        font_choices=(('system', '默认'), ('song', '宋体'), ('hei', '黑体')),
                        font_default='song'),
    extra_page_blocks='figure.reader-figure',
    flow_complex_blocks=True,
    inline='strict',
    image_base='',
    hint_keys=frozenset({'reader_swipe_mobile', 'reader_nav_desktop'}),
)
