"""The one registry of reader mode ids. These are storage vocabulary: the
SQL CHECK lists in the reader tables and in reader_mode_state spell the
same ids, and tests pin the two together."""

ALL_MODES = ('summary', 'original', 'plain', 'side_by_side')
SINGLE_MODES = ('summary', 'original', 'plain')
SIDE_BY_SIDE_MEMBERS = ('original', 'plain')
