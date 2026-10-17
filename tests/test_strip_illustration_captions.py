"""Tests for scripts/audits/strip_illustration_captions.py --tags-only."""
from scripts.audits.strip_illustration_captions import strip_captions

TEXT = "\n\n".join([
    "ARGUMENT",
    "THE SIXTH BATTLE, THE ACTS AND DEATH OF PATROCLUS",
    "[Illustration: ] DIANA",
    "So spoke the god.",
    "[Illustration: ] Map, titled “GRÆCIÆ ANTIQUÆ”",
    "END OF THE ILIAD",
])


def test_tags_only_removes_only_illustration_tags():
    new, n_caps, n_trail = strip_captions(TEXT, tags_only=True)
    assert new == "ARGUMENT\n\nTHE SIXTH BATTLE, THE ACTS AND DEATH OF PATROCLUS\n\nSo spoke the god.\n\nEND OF THE ILIAD"
    assert (n_caps, n_trail) == (2, 0)


def test_tags_only_is_idempotent_and_handles_empty():
    once, _, _ = strip_captions(TEXT, tags_only=True)
    assert strip_captions(once, tags_only=True) == (once, 0, 0)
    assert strip_captions("", tags_only=True) == ("", 0, 0)


def test_default_rules_unchanged():
    new, n_caps, _ = strip_captions("[Illustration: ] DIANA\n\nSo spoke the god.")
    assert new == "So spoke the god." and n_caps == 1
