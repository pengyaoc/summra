"""Tests for scripts/audits/strip_footnotes.py."""
from scripts.audits.strip_footnotes import strip_footnotes

BODY = "Such was the sovereign doom, and such the will of Jove![42]"


def test_inline_marker_removed():
    text, markers, dropped = strip_footnotes(BODY)
    assert text == "Such was the sovereign doom, and such the will of Jove!"
    assert (markers, dropped) == (1, 0)


def test_marker_after_space_leaves_single_space():
    text, markers, _ = strip_footnotes("Declare, O Muse! [43] in what ill-fated hour[44] Sprung")
    assert text == "Declare, O Muse! in what ill-fated hour Sprung"
    assert markers == 2


def test_trailing_footnotes_block_dropped():
    src = f"{BODY}\n\nAnd Juno slumber’d.\n\nFootnotes\n\n[1] A note.\n\n[2] Another note."
    text, markers, dropped = strip_footnotes(src)
    assert text == "Such was the sovereign doom, and such the will of Jove!\n\nAnd Juno slumber’d."
    assert dropped == 3


def test_illustration_brackets_untouched():
    src = "[Illustration: ] MARS"
    assert strip_footnotes(src) == (src, 0, 0)


def test_word_footnotes_in_prose_is_not_a_block():
    src = "He read the Footnotes carefully.\n\nThen he slept."
    assert strip_footnotes(src) == (src, 0, 0)


def test_idempotent_and_empty():
    once, _, _ = strip_footnotes(f"{BODY}\n\nFootnotes\n\n[1] A note.")
    assert strip_footnotes(once) == (once, 0, 0)
    assert strip_footnotes("") == ("", 0, 0)
