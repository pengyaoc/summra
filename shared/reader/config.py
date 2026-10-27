"""Declarative description of one app's reader. Each app builds a single
ReaderConfig; the shared reader server and client read it instead of
hard-coding Plainly's modes, labels and cache names."""
from dataclasses import dataclass
from typing import Optional

from shared.reader.modes import ALL_MODES, SIDE_BY_SIDE_MEMBERS

LAYOUTS = ('single', 'side_by_side')
CACHE_VISIBILITIES = ('public', 'private')
# Inline markup in reader blocks (shared/static/js/blocks.js formatInline).
INLINE_MODES = ('markdown', 'strict')


@dataclass(frozen=True)
class ReaderMember:
    id: str
    label: str
    cell_class: str


@dataclass(frozen=True)
class ReaderMode:
    id: str
    label: str
    layout: str = 'single'
    members: tuple[ReaderMember, ...] = ()
    library_label: Optional[str] = None
    min_width: Optional[int] = None
    narrow_fallback: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReaderFeatures:
    progress: bool = True
    illustrations: bool = False
    page_turn_hint: bool = True
    kindle: bool = True
    automatic_completion: bool = True


@dataclass(frozen=True)
class ReaderSettings:
    fonts: tuple[tuple[str, str], ...]
    font_default: str
    size_min: int
    size_max: int
    size_default: int
    themes: tuple[tuple[str, str], ...]
    theme_default: str


DEFAULT_SETTINGS = ReaderSettings(
    (('georgia', 'Reader Serif'), ('system', 'System'), ('figtree', 'Figtree')),
    'georgia', 12, 24, 16,
    (('light', 'Light'), ('dark', 'Dark')), 'light',
)


@dataclass(frozen=True)
class KindleOptions:
    text_modes: tuple[tuple[str, str], ...]
    default_text: str
    font_size_max: int = 5
    font_size_default: int = 3
    font_choices: tuple[tuple[str, str], ...] = ()
    font_default: str = 'system'

    def __post_init__(self):
        if not 1 <= self.font_size_default <= self.font_size_max <= 10:
            raise ValueError('Kindle font size range must be within 1–10')
        choices = [key for key, _ in self.font_choices]
        if any(key not in ('system', 'song', 'hei') for key in choices) or len(set(choices)) != len(choices):
            raise ValueError('Unknown or duplicate Kindle font choice')
        if choices and self.font_default not in choices:
            raise ValueError('Kindle default font is not among choices')


@dataclass(frozen=True)
class ReaderConfig:
    app_name: str
    cache_db_name: str
    cache_visibility: str
    modes: tuple[ReaderMode, ...]
    default_modes: tuple[str, ...]
    features: ReaderFeatures
    settings: ReaderSettings = DEFAULT_SETTINGS
    kindle: Optional[KindleOptions] = None
    api_base: str = '/api'
    extra_page_blocks: str = ''
    hint_keys: frozenset[str] = frozenset()
    inline: str = 'markdown'
    image_base: str = ''
    flow_complex_blocks: bool = False

    def __post_init__(self):
        ids = [mode.id for mode in self.modes]
        for mode_id in ids:
            if mode_id not in ALL_MODES:
                raise ValueError(f'unknown reader mode id {mode_id!r}')
        if len(set(ids)) != len(ids):
            raise ValueError('duplicate reader mode ids')
        for mode in self.modes:
            if mode.layout not in LAYOUTS:
                raise ValueError(f'unknown layout {mode.layout!r} for mode {mode.id!r}')
            if (mode.layout == 'side_by_side') != (mode.id == 'side_by_side'):
                raise ValueError("layout 'side_by_side' and mode id 'side_by_side' go together")
            if mode.layout == 'side_by_side' and tuple(m.id for m in mode.members) != SIDE_BY_SIDE_MEMBERS:
                raise ValueError(f'side_by_side members of {mode.id!r} must be {SIDE_BY_SIDE_MEMBERS}')
            self._require_configured(mode.narrow_fallback, f'narrow_fallback of {mode.id!r}')
        self._require_configured(self.default_modes, 'default_modes')
        if self.cache_visibility not in CACHE_VISIBILITIES:
            raise ValueError(f'cache_visibility must be one of {CACHE_VISIBILITIES}')
        if self.inline not in INLINE_MODES:
            raise ValueError(f'inline must be one of {INLINE_MODES}')
        if self.features.kindle:
            if self.kindle is None:
                raise ValueError('features.kindle requires kindle options')
            self._require_configured(tuple(m for m, _ in self.kindle.text_modes), 'kindle text_modes')
            if self.kindle.default_text not in [m for m, _ in self.kindle.text_modes]:
                raise ValueError('kindle default_text is not among text_modes')
        settings = self.settings
        if settings.font_default not in [f for f, _ in settings.fonts]:
            raise ValueError('font_default is not among fonts')
        if settings.theme_default not in [t for t, _ in settings.themes]:
            raise ValueError('theme_default is not among themes')
        if not settings.size_min <= settings.size_default <= settings.size_max:
            raise ValueError('size_default is outside the size range')

    def _require_configured(self, mode_ids, what):
        configured = {mode.id for mode in self.modes}
        for mode_id in mode_ids:
            if mode_id not in configured:
                raise ValueError(f'{what} names mode {mode_id!r}, which is not configured')

    def mode(self, mode_id: str) -> Optional[ReaderMode]:
        return next((mode for mode in self.modes if mode.id == mode_id), None)

    def to_client(self) -> dict:
        settings = self.settings
        return {
            'app_name': self.app_name,
            'cache_db_name': self.cache_db_name,
            'api_base': self.api_base,
            'extra_page_blocks': self.extra_page_blocks,
            'inline': self.inline,
            'image_base': self.image_base,
            'flow_complex_blocks': self.flow_complex_blocks,
            'default_modes': list(self.default_modes),
            'modes': [
                {
                    'id': mode.id,
                    'label': mode.label,
                    'layout': mode.layout,
                    'members': [
                        {'id': m.id, 'label': m.label, 'cell_class': m.cell_class}
                        for m in mode.members
                    ],
                    'library_label': mode.library_label or mode.label,
                    'min_width': mode.min_width,
                    'narrow_fallback': list(mode.narrow_fallback),
                }
                for mode in self.modes
            ],
            'features': {
                'progress': self.features.progress,
                'illustrations': self.features.illustrations,
                'page_turn_hint': self.features.page_turn_hint,
                'kindle': self.features.kindle,
                'automatic_completion': self.features.automatic_completion,
            },
            'settings': {
                'fonts': [list(f) for f in settings.fonts],
                'font_default': settings.font_default,
                'size_min': settings.size_min,
                'size_max': settings.size_max,
                'size_default': settings.size_default,
                'themes': [list(t) for t in settings.themes],
                'theme_default': settings.theme_default,
            },
        }
