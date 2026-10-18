"""Tests for scripts/content/passage_rewrite.py (verse Plain English gate)."""
from scripts.content.passage_rewrite import check_passages

VERSE = "Of Man’s first disobedience, and the fruit\nOf that forbidden tree whose mortal taste\nBrought death into the World, and all our woe."
GOOD = "Sing about how people first disobeyed God, and the fruit of the forbidden tree that brought death and all our sorrow."


def test_matching_passages_pass():
    assert check_passages([VERSE, VERSE], [GOOD, GOOD]) == []


def test_count_mismatch_fails():
    errors = check_passages([VERSE, VERSE], [GOOD])
    assert any("count" in e for e in errors)


def test_missing_terminator_fails():
    errors = check_passages([VERSE], [GOOD[:-1] + " and all our sor"])
    assert errors and "P1" in errors[0]


def test_closing_quote_terminator_passes():
    assert check_passages([VERSE], [GOOD[:-1] + ".”"]) == []


def test_line_break_inside_paragraph_fails():
    errors = check_passages([VERSE], [GOOD.replace(" the fruit", "\nthe fruit")])
    assert any("line break" in e for e in errors)


def test_too_short_passage_fails():
    errors = check_passages([VERSE], ["People disobeyed God."])
    assert any("ratio" in e for e in errors)


def test_summary_language_fails():
    errors = check_passages([VERSE], ["In this passage, the poet asks the Muse to sing of how people first disobeyed God."])
    assert any("summary" in e for e in errors)


def test_empty_rewrite_fails():
    assert check_passages([VERSE], [""])


def test_summary_phrase_present_in_original_passes():
    original = "Homer is the poet of war, and the poet never tires of it."
    plain = "Homer is the poet of war, and the poet never gets tired of it."
    assert check_passages([original], [plain]) == []


def test_chunks_respect_size_and_numbering():
    from scripts.content.passage_rewrite import chunk_paragraphs
    paras = ["a" * 40, "b" * 40, "c" * 40, "d" * 200]
    assert chunk_paragraphs(paras, max_chars=100) == [(1, paras[:2]), (3, [paras[2]]), (4, [paras[3]])]
    assert chunk_paragraphs([], max_chars=100) == []


def test_rules_file_uses_generator_rules():
    from scripts.content.passage_rewrite import build_rules
    rules = build_rules("The Iliad", "Homer")
    assert "PARAGRAPH COUNT MUST MATCH EXACTLY" in rules  # the Gemini generator's own rules
    assert "The Iliad" in rules and "Homer" in rules


def test_chunk_prompt_points_to_rules_and_holds_only_its_paragraphs():
    from scripts.content.passage_rewrite import build_chunk_prompt
    prompt = build_chunk_prompt("Book I", 5, ["First para.", "Second para."], "out/ch1/005.json", "in/RULES.md")
    assert "in/RULES.md" in prompt and "Book I" in prompt
    assert "[P5] First para.\n\n[P6] Second para." in prompt
    assert '"start": 5' in prompt and "out/ch1/005.json" in prompt
    assert "PARAGRAPH COUNT MUST MATCH EXACTLY" not in prompt  # rules are read once, not repeated per chunk


def test_verbatim_heading_without_terminator_passes():
    assert check_passages(["A. POPE", VERSE], ["A. POPE", GOOD]) == []


def test_review_pairs_format():
    from scripts.content.passage_rewrite import format_pairs
    out = format_pairs(["Orig one.", "Orig two."], ["Plain one.", "Plain two."])
    assert out == ("### P1 (ratio 1.11)\nORIGINAL: Orig one.\nPLAIN: Plain one.\n\n"
                   "### P2 (ratio 1.11)\nORIGINAL: Orig two.\nPLAIN: Plain two.\n")
    assert "PLAIN: (missing)" in format_pairs(["Orig one."], [])


def test_summary_phrase_used_elsewhere_in_chapter_passes():
    originals = ["Homer is the poet of war.", "His fancy grows upon himself and others, and becomes on fire."]
    plains = ["Homer is the poet of war.", "His fancy grows in the poet himself and others, and catches fire."]
    assert check_passages(originals, plains) == []


def test_terminator_inside_italics_passes():
    original = "Numa owed his laws to the nymph, as the elegant pen made ideal: _Numa Pompilius._"
    plain = "Numa owed his laws to the nymph, as an elegant writer imagined it: _Numa Pompilius._"
    assert check_passages([original], [plain]) == []


def test_terminator_inside_citation_braces_passes():
    original = "The princes of Germany first became formidable. {See Pfeffel.}"
    plain = "The German princes first became powerful. {See Pfeffel.}"
    assert check_passages([original], [plain]) == []


def test_unterminated_citation_braces_fails():
    original = "The princes of Germany first became formidable. {See Pfeffel.}"
    plain = "The German princes first became powerful. {See Pfeffel}"
    errors = check_passages([original], [plain])
    assert errors and "terminator" in errors[0]


def test_something_filler_fails():
    original = "One of those boys observed that, by tying a string, the valve would open."
    plain = "One of those boys noticed something. If he tied a string, the valve would open."
    errors = check_passages([original], [plain])
    assert errors and "filler" in errors[0]


def test_something_in_original_is_not_filler():
    original = "It might not be worth all it cost, but it would always be worth something. Nobody would lose it."
    plain = "It might not be worth all it cost, but it would always be worth something. Nobody would lose it."
    assert check_passages([original], [plain]) == []


def test_dropped_connective_warns():
    from scripts.content.passage_rewrite import connective_warnings
    original = "The price, therefore, must rise; and it is perhaps not only the rich who feel it."
    plain = "The price must rise, and the rich feel it, along with others."
    warnings = connective_warnings([original], [plain])
    assert len(warnings) == 3 and all(w.startswith("P1:") for w in warnings)


def test_kept_connective_does_not_warn():
    from scripts.content.passage_rewrite import connective_warnings
    original = "The price, therefore, must rise; and it is perhaps not only the rich who feel it."
    plain = "So the price must rise. Maybe it is not just the rich who feel it."
    assert connective_warnings([original], [plain]) == []


def test_rules_state_book_learnings():
    from scripts.content.passage_rewrite import build_rules
    rules = build_rules("A Book", "An Author")
    for rule in ("short parenthetical", "{See", "therefore", "something.", "scanning errors"):
        assert rule in rules, rule
