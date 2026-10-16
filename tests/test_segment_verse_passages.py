"""Tests for scripts/content/segment_verse_passages.py."""
from scripts.content.segment_verse_passages import segment_verse


def _lines(n, end_every=None, terminal="."):
    """n verse lines; every `end_every`-th line ends a sentence."""
    out = []
    for i in range(1, n + 1):
        ends = end_every and i % end_every == 0
        out.append(f"line {i} of the verse{terminal if ends else ','}")
    return out


def _passages(text):
    return [p.split("\n") for p in text.split("\n\n")]


def test_breaks_at_sentence_ends_near_target():
    text = "\n".join(_lines(80, end_every=10))
    passages = _passages(segment_verse(text, target=20, min_lines=12, max_lines=30))
    assert [len(p) for p in passages] == [20, 20, 20, 20]
    for p in passages:
        assert p[-1].endswith(".")


def test_preserves_every_line_in_order():
    lines = _lines(97, end_every=7)
    out = segment_verse("\n".join(lines), target=20, min_lines=12, max_lines=30)
    assert out.replace("\n\n", "\n").split("\n") == lines


def test_falls_back_to_semicolon_when_no_sentence_end_in_range():
    lines = _lines(60)
    lines[24] = lines[24][:-1] + ";"
    lines[59] = lines[59][:-1] + "."
    passages = _passages(segment_verse("\n".join(lines), target=20, min_lines=12, max_lines=30))
    assert len(passages[0]) == 25
    assert passages[0][-1].endswith(";")


def test_long_sentence_extends_past_max_to_next_sentence_end():
    lines = _lines(60)
    lines[37] = lines[37][:-1] + "."
    lines[59] = lines[59][:-1] + "."
    passages = _passages(segment_verse("\n".join(lines), target=20, min_lines=12, max_lines=30))
    assert [len(p) for p in passages] == [38, 22]


def test_short_tail_merges_into_previous_passage():
    lines = _lines(25, end_every=20)
    lines[-1] = lines[-1][:-1] + "."
    passages = _passages(segment_verse("\n".join(lines), target=20, min_lines=12, max_lines=30))
    assert [len(p) for p in passages] == [25]


def test_closing_quote_after_terminator_counts_as_sentence_end():
    lines = _lines(40)
    lines[19] = "and so he spoke.’"
    lines[39] = "the end.”"
    passages = _passages(segment_verse("\n".join(lines), target=20, min_lines=12, max_lines=30))
    assert [len(p) for p in passages] == [20, 20]


def test_idempotent_on_already_segmented_text():
    text = "\n".join(_lines(80, end_every=10))
    once = segment_verse(text, target=20, min_lines=12, max_lines=30)
    assert segment_verse(once, target=20, min_lines=12, max_lines=30) == once


def test_empty_text():
    assert segment_verse("") == ""
