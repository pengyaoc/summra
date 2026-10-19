# Agent Plain English: Learnings

What each Plain English run taught us, and why `docs/agent_plain_english_workflow.md` has the rules it has. The workflow doc is the process; this doc is the evidence. Add a section per book.

## Lessons across books

| Book | Writer | Paragraphs | Verifier fixes | Rate |
|---|---|---|---|---|
| The Iliad (66), Pope's verse | Haiku | 1,524 | 317 | 21% |
| The Happy Prince (105) | Sonnet | 397 | 7 | 2% |
| The Wealth of Nations (3) | Sonnet | 2,271 | 109 | 5% |
| Life on the Mississippi (112) | Sonnet (effort low) | 1,974 | 26 | 1.3% |
| Grimms' Fairy Tales (62) | Sonnet (effort low) | 908 | 17 | 1.9% |

1. **Sonnet writes; a fresh Sonnet verifies.** Haiku drafts pass the gate but carry many meaning errors. The verifier is never optional: every chapter passed the gate on every book, and verifiers still found real errors.
2. **The errors depend on the prose.**
   - Verse (Pope) fails on *who did what*: swapped speakers and reversed meanings.
   - Argument (Smith) fails on *logic*: dropped connectives and hedges, reversed conclusions, invented framing.
   - Simple stories (Wilde) barely fail at all.
   Tune the verifier brief to the book.
3. **The gate should catch what it can.** Each repeated, mechanical error became a gate rule:
   - the `{See …}` terminator;
   - "…something." filler as a FAIL;
   - dropped connectives as a WARN.
   Rules that need judgment stay in the briefs.
4. **Writers' doubt lists are accurate.** They flag almost every risky spot: source typos, compressed passages, odd figures. Always paste them into the verifier's brief.
5. **Verifiers can be wrong too.** Check unresolved items and source-typo calls yourself before accepting them. On Wealth of Nations, "usurers" → "insurers" looked wrong but was right in context.
6. **Usage limits set the pace.** A limit hit stops every running agent; `SendMessage` resumes them with no lost work. Plan big books as several sittings.
7. **Fix structure before writing.** Headings and introductions stranded at chapter ends, and Book/Part levels encoded in chapter numbers, are cheap to fix at ingest. They are expensive once two columns must move together.

## Token efficiency (from the Wealth of Nations run)

Where the tokens went, about 100 agents in all:
- **Fixed startup cost per agent dominated.** That is the system prompt, tool definitions and project instructions. A writer with one 9K-character chunk used ~82K tokens, and a writer with five chunks ~110–120K. So most of each agent's tokens were overhead, paid 97 times.
- **The rules repeated in every chunk.** Each chunk file carried the full 7.4K-character rules: 39% of all prompt text (211 chunks, ~1.6M characters).
- **The coordinator's context grew with every report.** Some reports ran 20–30 lines.

Changes made:
1. **One `RULES.md` per book.** Chunk files hold only their paragraphs, and agents read the rules once.
2. **Agent types `plain-english-writer` and `plain-english-verifier`.** Each has only Read, Write and Bash, with the brief built in and reports capped at 6–8 lines. Launch prompts shrink to the assignment, and each agent loads less.
3. **Bigger assignments: ~60–80K characters of text per agent.** Short chapters are batched, so the fixed cost is paid about half as often. Wealth of Nations would have needed ~30 writers and ~30 verifiers instead of 48 + 49.

First exercised on the Origin of Species continuation below. Agent token totals were unavailable from the collaboration tool, so the expected token savings have not been measured.

4. **Effort:** writer `low`, verifier `medium` (set in the agent files).
5. **Coordinator:** a fresh Sonnet session per sitting instead of one long Opus session.

Check 4 on the next book against the 5% fix rate.

Not changed: the fresh verifier per range. It is the most expensive step, but it found 109 real errors that no gate could. Chapters that came back with 0 fixes were simple prose, and nothing tells you that in advance.

## Iliad notes (book 66, 2026-10-16)

**Source.** Pope's translation (pg6130), `is_poetry=0`. Ingest had flattened each verse paragraph onto one line, so paragraphs were single-`\n` lines, which the reader already treats as paragraphs. We left the original as flattened couplets (prose workflow) rather than restoring verse lines.

**Cleanup.**
- `reformat_paragraphs.py` changed all 25 chapters to `\n\n` paragraphs.
- `strip_footnotes.py` removed about 300 inline `[n]` markers, plus 461 endnote paragraphs that had been appended to Book XXIV.
- `strip_illustration_captions.py --tags-only` removed 71 `[Illustration: ]` lines. The default rules would also have deleted the headings `ARGUMENT`, `END OF THE ILIAD`, `A. POPE` and `POPE’S PREFACE TO THE ILIAD OF HOMER`.

**Size.** 25 chapters (the Introduction and Pope's Preface, then Books I–XXIV), 1,524 paragraphs, 987K characters, cut into 98 chunks of about 12K characters. 26 Haiku writers and 26 Sonnet verifiers, with the Introduction split in two for both steps.

**Result.**
- All 25 chapters are EXACT, with ratios of 94–107%.
- Side by Side has 1,524 paired rows. `agent_plain_english_side_by_side.mjs` passes, and 40 consecutive pages show no clipping.

**What Sonnet QC caught (317 paragraphs fixed across the 25 chapters).**
- Haiku's errors on Pope's compressed, inverted verse are mostly about *who did what*:
  - swapped speakers or agents (Book IV: Atrides and Nestor reversed; Book XIII: Menelaus and Helenus swapped; Book XX: wrong spear-thrower);
  - reversed meanings (Book III: a curse inverted; the Preface: "I doubt not" became "I doubt that"; Book IX: Achilles made the giver instead of the receiver);
  - wrong genealogy (Book XIII: Medon; Book XIV: Diomed's ancestry);
  - invented details (a cliff, a chariot, "of gold");
  - spots where the writer admitted it compressed text.
- Plain prose chapters such as the Introduction needed far fewer fixes (7 in 123 paragraphs).

**Gate adjustments made during the run.**
- A paragraph kept verbatim (a heading such as `A. POPE`) may end without a terminator.
- A terminator inside italics (`_Numa Pompilius._`) counts.
- A summary phrase ("the poet") is allowed when the chapter's original uses it, as in the Preface, which is commentary.

**Operational lessons.**
- Running ~26 agents at once hit the account's usage limit partway through. The stopped agents kept their work and were resumed with `SendMessage` after the reset ("continue from where you stopped; re-read the JSON files first"). Expect this on a whole book, and keep about 10 agents running at a time.
- Several reviewers wrote helper scripts named `fix.py` in the shared scratchpad and overwrote each other's. Their exact-string asserts failed before any write, so no chapter was damaged, but the brief now requires unique script names. Afterwards, check that each reported fix landed in its own chapter (`grep -l "<new text>" $DIR/out/ch*/*.json`).
- One reviewer returned "pending" instead of a report. Ask it again before counting the chapter as done.

## The Happy Prince notes (book 105, 2026-10-17): first run with Sonnet writers

**Cleanup.**
- `reformat_paragraphs.py` split the text into paragraphs.
- `strip_illustration_captions.py --tags-only` removed 12 `[Picture: …]` tags and the trailing "Printed by BALLANTYNE…" line. The option now also covers `[Picture` tags and printer lines.
- `strip_decorative_dividers.py` removed one `* * * * *`.
- The Giant's notice board is three verbatim one-line paragraphs.
- Result: 5 tales, 397 paragraphs, 85K characters, 8 chunks.

**Writing.** 5 Sonnet writers, one per tale, each took under a minute and passed the gate (three on the first run). They followed the source's curly quotes, so no apostrophe fix was needed.

**Verification.** 5 fresh Sonnet verifiers made **7 fixes in 397 paragraphs**:
- one invented detail;
- one dropped word ("lips");
- a lost pun ("affected");
- a quote mark that closed a story-within-a-story early;
- three wording or archaism fixes.

The Iliad's Haiku drafts needed 317. Wilde is easier than Pope, so not all of that gap is the model, but the writers' own doubt lists were also short and accurate.

**Result.** All 5 tales are EXACT, with ratios of 96–99%. `agent_plain_english_side_by_side.mjs` passes for both books.

**Operational.** The usage limit stopped all five verifiers once. They were resumed with `SendMessage` after the reset, with no lost work.


## The Wealth of Nations notes (book 3, 2026-10-17/18): a 2.3M-character book

**Size.**
- 32 chapters (34 after the restructure), 2,271 paragraphs, 211 chunks.
- 48 Sonnet writers and 49 verifier ranges. Chapters over 6 chunks were split 2–5 ways, with disjoint file lists for both writers and verifiers.

**Shared briefs.** Put the writer and verifier briefs in files (`$DIR/WRITER_BRIEF.md`, `$DIR/VERIFIER_BRIEF.md`) and keep each agent's prompt to the assignment: the chapter, the files or paragraph range, and the writer's doubts. This keeps the coordinator's context small across about 100 launches.

**Usage limits.** The session limit hit twice. Both times every running agent stopped at once, and `SendMessage` resumed them after the reset with no lost work. Expect this on any book this size.

**Gate change.** A terminator followed by a closing `}` now passes. Smith's paragraphs often end with a citation like `{See Pfeffel.}`.

**What verifiers caught (109 fixes).**
- Mostly lost logical connectives ("therefore", "not only… but", "perhaps"/"seem").
- A few reversals and invented framings.
- OCR names left as printed.
- Unglossed false friends: "undertaker", "workhouse", "police".

**Writer tic.** Sonnet sometimes turns a "that"-clause into filler: "…noticed something. If he…". Grep for `something\. [A-Z]` before applying.

**Structure.** If a book encodes Book/Chapter as chapter numbers (101, 201…), move it to `book_sections` with chapters numbered 1..N. Book introductions that ingest attached to the previous Book's last chapter become their own "Introduction" chapters. Both text columns must move together.

**Follow-up changes (2026-10-18).**
- **Gate:** now fails "…something. If he…" filler unless the original says "something". It also warns when "therefore", "perhaps" or "not only" has no plain-English equivalent. On the Iliad's finished output the warning fires on 3 of 1,524 paragraphs.
- **Exported prompts:** now carry the rules that emerged mid-run on this book: connectives, short parenthetical glosses, braces, no filler, and scanning-error names.
- **Workflow doc:** gained the structure check, sitting planning, and shared brief files.


## The Origin of Species notes (book 2, 2026-10-17/18): Sol writers and verifiers

- Initial sitting completed chapters 1–10; the resumed sitting completed 11–14. All 14 chapters now have 1,264 paired paragraphs, including 565 verbatim index entries. Sol (`gpt-6-sol`) wrote and independently verified the prose; no Gemini calls.
- Initial fresh verification corrected 69 paragraphs in chapters 1–10. The continuation corrected 18 paragraphs in chapters 11–14, plus seven earlier paragraphs found by the new gate's focused review. These are correction events across two passes, not a count of distinct paragraphs across the entire book.
- Darwin's errors concentrate on scientific distinctions, causal direction and qualifications: geographic range versus abundance, first crosses versus hybrids, inherited structure versus common use, conditional migration and future possibilities. Preserve the historical claims and first-person voice; do not insert modern editorial commentary.
- The continuation exercised the shared RULES.md prompts and updated gate on real content. All 23 earlier gate flags were independently reviewed; 19 warnings remained as faithful equivalents (“may”, “as well as”, or paired claims) rather than genuine omissions. Do not force keyword matches where the argument is already intact.
- Four remaining-chapter writers and four fresh verifiers were used; the short chapter 12 review was batched with the earlier flagged pairs. Agent token totals were not exposed by the collaboration tool, so no token-efficiency comparison is claimed.
- Full-book pairing, index equality, desktop/mobile reader checks, smoke and reader regressions passed. The result is local, not deployed.


## Life on the Mississippi notes (book 112, 2026-10-18): first run with `effort: low` writers

**Size.** 61 chapters, 1,974 paragraphs, 867K characters, 98 chunks. 13 writers (about 70K characters each; ch60's appendices split in two) and 13 verifiers. One session limit hit, right after the first launch: all 10 running writers had saved nothing yet, and `SendMessage` restarted them cleanly.

**Result.** Verifiers made 26 fixes (1.3%), against 5% on Wealth of Nations. `effort: low` for writers is fine on clear prose; keep it. The errors were few and typical: lost "not only … but", invented numbers ("three months" for "months"), unglossed words (undertaker, chute, Sandwich Islands), wrong glosses (quarter less twain, doughface, "come up to blow").

**Brief mistake to avoid.** Telling a writer to "keep dialect faithful" made it copy a 110-paragraph Huck Finn passage word for word. Say "rewrite dialect spelling into standard English, keep the speaker's attitude and the joke".

**Slurs.** Writers replaced the period slur with "Black man" or similar, as earlier books did. Put this in every brief; verifiers need it too so they do not "restore" it.

**Gate vs. dashes.** The terminator rule fails speech lead-ins that end in `--`, `:` or `,`. Writers changed them to a period or "said this." (about 120 paragraphs). It reads a little oddly but is accepted. If this repeats, consider letting the gate accept a trailing colon, comma or dash when the next original paragraph is a quotation.

**Footnotes.** This Gutenberg text has inline `{footnote [...]}` paragraphs. `strip_footnotes.py` does not touch them, and they stay as paired rows. The E2E footnote check was narrowed so "[Illustrations of it…" is not flagged.

**Verifier speed.** Verifiers finished in 20–50 seconds each with few fixes. A spot check of six random pairs and a number-by-number comparison of ch14–17 found no misses.


## Grimms' Fairy Tales notes (book 62, 2026-10-18): fairy tales with embedded rhymes

**Size.** 61 tales, 908 paragraphs, 516K characters, 9 writers and 9 verifiers (each about two minutes). 17 verifier fixes (1.9%); six of nine ranges needed none.

**Run the paragraph-level cleanup scripts after `reformat_paragraphs.py`, never before.** The footnote, caption and divider scripts work on `\n\n` paragraphs. Run on hard-wrapped text they report "0 changes" and look clean. Here a `*****` divider and a `[*] Simpleton` footnote slipped through to the writers and had to be removed from both columns afterwards. Re-run all dry-runs after the reformat.

**Do not run the caption script's default rules on verse-bearing prose.** Short unpunctuated lines are real content in fairy tales (the Juniper-tree bird's song, ch40, 16 lines; `FIRST STORY` headings). Use `--tags-only`.

**Rhyme lead-ins hit the terminator rule.** "…and sang:" before a rhyme fails the gate, so writers wrote "…and sang this song." (about 70 paragraphs). Accepted by verifiers. This is the same issue as the Mississippi speech lead-ins; the gate could accept a trailing colon when the next original paragraph is a quotation or verse.

**Verifier errors in this book were archaic words left in place** ("rue", "thee", "desert", "sexton", "slut" in its old sense) and one or two reversals ("my own amusement" for "your amusement"). Fairy-tale prose is simple, so the rate was low.

**Quotes.** Briefs that say "use curly quotes ‘ ’ “ ” as the source does" worked; the one batch launched before that note used straight quotes, and a smart-quote pass over the JSON fixed it.
