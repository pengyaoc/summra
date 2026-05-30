# Switch Image Generation from Gemini to Imagen 4 (with provider abstraction)

**Date:** 2026-05-30
**Status:** Approved — ready for implementation planning

## Problem statement

`gemini-3-pro-image-preview` and `gemini-2.5-flash-image` are no longer
available on the Gemini API free tier. The current image generation script
(`scripts/images/generate_gemini_illustrations.py`) hard-codes these models
for both book covers and chapter illustrations and cannot run.

We need to switch to Imagen 4 as the primary image backend, while keeping
the existing Gemini code intact as a rollback path in case Imagen quality,
character consistency, or cost prove unacceptable.

## Goals

- Replace the active image generation backend with Imagen 4.
- Use a fallback chain to maximize the chance of a successful generation:
  `imagen-4.0-ultra-generate-001` → `imagen-4.0-generate-001` → `imagen-4.0-fast-generate-001`.
- Preserve cross-chapter character consistency without reference images
  (Imagen 4 does not support reference-image input).
- Keep the existing Gemini code path runnable behind a single CLI flag for
  rollback. No code deletion.
- Match existing test discipline (TDD, full coverage of new logic).

## Non-goals

- Re-implementing batch / async generation for Imagen. Imagen 4 does not
  currently support the Files-based Batch API the existing code uses.
  The Gemini batch helpers remain dormant.
- Re-processing existing covers / illustrations. Only newly generated
  images get the new aspect ratio.
- Changing user-facing site behavior. Frontend already handles variable
  image dimensions via CSS.
- Renaming the `--model` flag. It stays Gemini-specific.

## Proposed approach

### File layout

Rename (via `git mv` to preserve blame):

- `scripts/images/generate_gemini_illustrations.py` → `scripts/images/generate_illustrations.py`
- `tests/test_gemini_illustrations.py` → `tests/test_illustrations.py`

The renamed script holds both providers and the dormant batch helpers in
one file. Filename describes what it does (generate illustrations), not
its history.

### Provider abstraction

```
ImageGeneratorBase (abstract base in the same file)
├── GeminiImageGenerator   (existing logic, refactored to subclass)
└── ImagenImageGenerator   (new)
```

Shared interface:

```python
class ImageGeneratorBase:
    name: str                          # "gemini" | "imagen"
    supports_batch: bool               # True for gemini, False for imagen
    supports_reference_image: bool     # True for gemini, False for imagen

    def generate_cover_image(
        self,
        book_title: str,
        book_author: str,
        medium_summary: str,
        dry_run: bool = False,
    ) -> Tuple[Optional[bytes], str]: ...

    def generate_chapter_illustration(
        self,
        book_title: str,
        book_author: str,
        medium_summary: str,
        chapter: Dict,
        previous_chapter_summary: Optional[str] = None,
        reference_image: Optional[bytes] = None,   # ignored by Imagen
        character_brief: Optional[str] = None,     # used by Imagen
        dry_run: bool = False,
    ) -> Tuple[Optional[bytes], str]: ...
```

Return value: `(image_bytes_or_None, model_used_or_prompt)`. The second
element identifies which tier produced the result so logs/WORK_LOG can show
e.g. "Book 47 generated with `imagen-4.0-fast-generate-001` after Ultra hit
quota."

### `GeminiImageGenerator` (refactored, behavior unchanged)

- Subclasses `ImageGeneratorBase`.
- Sets `name = "gemini"`, `supports_batch = True`, `supports_reference_image = True`.
- Accepts (and ignores) the new `character_brief` kwarg.
- All existing `generate_content` calls, `image_config` with
  `image_size`/`aspect_ratio`, reference-image plumbing, and batch helpers
  remain unchanged.
- Batch helper functions get a header comment block:

  ```
  # ⚠️ DORMANT: Gemini-only batch path. Imagen 4 does not currently support
  # the Files-based Batch API. Kept for potential rollback to Gemini.
  ```

### `ImagenImageGenerator` (new)

- Subclasses `ImageGeneratorBase`.
- `name = "imagen"`, `supports_batch = False`, `supports_reference_image = False`.

Fallback chain:

```python
IMAGEN_MODEL_CHAIN = [
    "imagen-4.0-ultra-generate-001",
    "imagen-4.0-generate-001",
    "imagen-4.0-fast-generate-001",
]
```

Per-image fallback with error-type filtering:

```python
RETRYABLE_ERROR_CODES = {429, 500, 503}
RETRYABLE_ERROR_SUBSTRINGS = (
    "quota",
    "rate limit",
    "unavailable",
    "resource_exhausted",
)

def _generate_with_fallback(
    self, prompt: str, aspect_ratio: str
) -> Tuple[Optional[bytes], str]:
    last_error = None
    for model in IMAGEN_MODEL_CHAIN:
        try:
            self._wait_for_rate_limit()
            response = self.client.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    person_generation="allow_adult",
                ),
            )
            if response.generated_images:
                return response.generated_images[0].image.image_bytes, model
            last_error = f"{model}: empty response"
        except Exception as e:
            last_error = f"{model}: {e}"
            if not self._is_retryable(e):
                return None, model
            continue
    return None, IMAGEN_MODEL_CHAIN[-1]

def _is_retryable(self, exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in RETRYABLE_ERROR_CODES:
        return True
    msg = str(exc).lower()
    return any(s in msg for s in RETRYABLE_ERROR_SUBSTRINGS)
```

Other Imagen specifics:

- Aspect ratio: `"3:4"` for both covers and chapters (closest portrait
  Imagen 4 supports; was `"2:3"` for Gemini). `COVER_IMAGE_SIZE` / `IMAGE_SIZE`
  (2K/4K) constants are no longer used on the Imagen path — Imagen 4 does
  not expose a size knob; Ultra/Generate output ~2K, Fast outputs ~1K.
- Rate limiting: unchanged (`MAX_REQUESTS_PER_MINUTE = 2`).
- `reference_image` kwarg: accepted, ignored, logs a one-line note if
  provided.

### Character consistency (Q2 — prompt enrichment)

Imagen has no reference-image input, so consistency comes from prompt text.

New helper:

```python
def get_or_build_character_brief(
    db: Database, book_id: int, medium_summary: str
) -> str:
    """Generate (or load from cache) a visual style guide for a book.

    Cached at data/character_briefs/{book_id}.txt. Manual delete to invalidate.
    Uses gemini-2.5-flash for the text generation (cheap, text-only).
    On LLM failure, returns "" and logs a warning.
    """
```

Builder prompt:

```
You are preparing a visual style guide for a book illustrator who will draw
one illustration per chapter and must keep characters looking consistent
across all illustrations.

Read the book summary below and produce a CONCISE visual brief (under 200 words)
describing:

1. ART STYLE — overall artistic style appropriate to the book's tone and era
   (e.g., "moody oil painting", "watercolor children's book illustration",
   "stark Victorian engraving").

2. COLOR PALETTE — 3-5 dominant colors that should appear throughout.

3. RECURRING CHARACTERS — for each main character, give:
   - Name
   - Approximate age, build, hair color/style, distinctive clothing or props
   - One defining visual feature (a scar, a hat, a coat, etc.)

4. SETTING — the dominant environment / time period in 1-2 sentences.

Do NOT include plot details, dialogue, or anything not visually relevant.
Output as plain text, not JSON. Keep each section short.

Book summary:
{medium_summary}
```

Wiring:

- `generate_chapter_illustrations_for_book(...)` calls
  `get_or_build_character_brief()` once per book before the chapter loop,
  then passes the brief into every
  `generator.generate_chapter_illustration(..., character_brief=...)` call.
- `build_chapter_illustration_prompt(...)` gains a `character_brief`
  parameter. When non-empty, it inserts the brief between the "Book:" line
  and "Summary of the overall book:" section under a header:

  ```
  === VISUAL STYLE GUIDE (apply to every illustration in this book) ===
  {brief}
  ```

- `GeminiImageGenerator` accepts the kwarg but does not inject it (Gemini
  uses reference images).
- Covers do **not** get the brief — only one cover per book, no consistency
  problem.

Cache directory:

- `data/character_briefs/` — created on first use.
- `.gitignore` matches existing convention used by `data/batch_jobs/` and
  `data/cover_originals/` (verified during implementation).

### CLI changes

New flag:

```python
parser.add_argument(
    "--provider",
    choices=["imagen", "gemini"],
    default="imagen",
    help="Image generation backend. 'imagen' (default) uses Imagen 4 "
         "fallback chain. 'gemini' uses the legacy Gemini 3 Pro / 2.5 "
         "Flash Image path (kept for rollback).",
)
```

Existing flag interactions:

| Flag | `--provider imagen` (default) | `--provider gemini` |
|------|------------------------------|---------------------|
| `--model` | Ignored, prints warning | Works as today |
| `--sync-mode` | Errors: "Imagen does not support batch — use --provider gemini" | Works as today |
| `--resume` | Errors (same) | Works as today |
| `--list-jobs` | Errors (same) | Works as today |
| `--batch-poll-interval` | Ignored silently if user kept the default; warns if user explicitly set a non-default value | Works as today |

Provider construction helper:

```python
def build_generator(
    provider: str, api_key: str, model: Optional[str]
) -> ImageGeneratorBase:
    if provider == "imagen":
        return ImagenImageGenerator(api_key)
    elif provider == "gemini":
        return GeminiImageGenerator(
            api_key, model=model or "gemini-3-pro-image-preview"
        )
    raise ValueError(f"Unknown provider: {provider}")
```

### Caller code

The top-level functions (`generate_book_cover`,
`generate_chapter_illustrations_for_book`, `generate_book_covers_batch`,
`generate_chapter_illustrations_batch`, `resume_batch_job`) accept an
`ImageGeneratorBase` instead of `GeminiImageGenerator`. Branch on
`generator.supports_batch` / `generator.supports_reference_image` where
needed:

- Sync chapter generation: only loads previous-chapter PNG as
  `reference_image` if `generator.supports_reference_image`.
- Sync chapter generation: only calls `get_or_build_character_brief()` if
  generator is Imagen (or just always — the Gemini class ignores the brief).
- Batch entry points (`generate_*_batch`, `resume_batch_job`,
  `list_pending_batch_jobs`) refuse to run with an Imagen generator.

## Alternatives considered

1. **Delete Gemini batch code entirely.** Cleaner, matches CLAUDE.md
   simplicity principle. Rejected because the user explicitly wants the
   option to roll back to Gemini ("might use old nano banana API if this
   doesn't work out").
2. **Extract batch helpers to a separate `_legacy.py` file.** Isolates
   dormant code. Rejected: user preferred inline retention with marker
   comments so the rollback path stays a single-file mental model.
3. **Drop character consistency entirely (rely on art-style hint in
   prompt).** Simpler but produces visibly inconsistent characters across
   chapters. Rejected in favor of prompt enrichment.
4. **Crop/pad Imagen `"3:4"` output to `"2:3"` to match existing covers.**
   Adds image post-processing complexity for a small shape change.
   Rejected — frontend already handles variable image dimensions.
5. **Global tier fallback (whole batch downgrades to next tier on first
   quota hit) instead of per-image.** Simpler bookkeeping. Rejected:
   per-image fallback means each image gets the best tier currently
   available, maximizing quality.

## Tests

Renamed file `tests/test_illustrations.py`. TDD order during
implementation: write each failing test first, confirm red for the right
reason, then implement to green.

### Existing tests (kept, possibly tweaked)

- `test_filter_eligible_chapters_*` — unchanged.
- `test_build_chapter_illustration_prompt_*` — keep existing happy-path
  tests; add new cases for the `character_brief` parameter.
- `test_clean_title_for_prompt` — unchanged.
- All `GeminiImageGenerator` constructor / generation tests — keep, add
  assertions that the constructor sets `name="gemini"`,
  `supports_batch=True`, `supports_reference_image=True`.
- All batch flow tests — keep. They protect the rollback path.

### New Gemini-side tests

- `test_gemini_ignores_character_brief` — pass a brief, assert the
  generated prompt does not contain it.

### New Imagen-side tests

- `test_imagen_generator_attributes` — `name == "imagen"`,
  `supports_batch is False`, `supports_reference_image is False`.
- `test_imagen_fallback_chain_success_first_tier` — Ultra succeeds; assert
  Generate / Fast never called.
- `test_imagen_fallback_chain_quota_then_success` — Ultra raises 429;
  Generate succeeds; assert Fast not called; assert returned
  `model_used == "imagen-4.0-generate-001"`.
- `test_imagen_fallback_chain_all_tiers_quota` — all three raise quota
  errors; assert `(None, last_model)` returned.
- `test_imagen_fallback_non_retryable_stops_immediately` — Ultra raises
  content-policy error; assert Generate / Fast never called.
- `test_imagen_is_retryable_*` — parameterized unit tests on
  `_is_retryable()` covering each code, each substring, and at least one
  counter-example (e.g. `INVALID_ARGUMENT`).
- `test_imagen_cover_prompt_excludes_character_brief` — covers don't get
  the brief header.
- `test_imagen_chapter_prompt_includes_character_brief_when_provided` —
  brief header appears under `=== VISUAL STYLE GUIDE ===`.
- `test_imagen_ignores_reference_image` — passing `reference_image=b"..."`
  doesn't crash; one-line warning logged.
- `test_imagen_aspect_ratio_is_3_4` — assert `GenerateImagesConfig` called
  with `aspect_ratio="3:4"` for both cover and chapter calls.

### CLI / provider-selection tests

- `test_build_generator_default_is_imagen`
- `test_build_generator_gemini_explicit`
- `test_imagen_provider_rejects_batch_flags` — `--provider imagen
  --sync-mode` exits non-zero with the dormant-path message; same for
  `--resume`, `--list-jobs`. `--batch-poll-interval` set explicitly to a
  non-default value warns; left at default is silent.
- `test_imagen_provider_warns_on_model_flag` — `--provider imagen --model
  gemini-2.5-flash-image` prints warning, ignores the flag, proceeds.

### Character-brief tests

- `test_get_or_build_character_brief_caches_to_disk` — first call hits LLM
  (mocked), writes file; second call reads file, LLM not called.
- `test_get_or_build_character_brief_handles_llm_failure` — LLM raises;
  function returns `""` and logs warning, no crash.

### Manual smoke verification (post-tests)

Not automated (needs API keys + visual judgment). Run against a small book
that already has Gemini-generated illustrations as a visual A/B reference:

```bash
# Cover only, default provider (imagen)
python scripts/images/generate_illustrations.py --book-id <SMALL_BOOK_ID>

# A few chapter illustrations
python scripts/images/generate_illustrations.py --book-id <SMALL_BOOK_ID> \
  --chapters-only --chapter-range 1-3

# Visual A/B against frontend/static/illustrations/<id>/

# Confirm rollback path still works
python scripts/images/generate_illustrations.py --book-id <SMALL_BOOK_ID> \
  --provider gemini --dry-run
```

## Documentation updates

- `WORK_LOG.md` — new entry at the top describing the change, the
  rationale, and the rollback path (one-line: `--provider gemini`).
- `docs/ERD.md` — update the image-generation section: provider
  abstraction, Imagen fallback chain, character-brief enrichment, aspect
  ratio change, dormant batch path, rollback path.
- `docs/PRD.md` — no change (internal infrastructure, no user-facing
  behavior change).
- `deploy/README.md`, `deploy/setup-e2small.sh`, and any cron scripts —
  grep for the old filename `generate_gemini_illustrations.py` and update
  references.
- `scripts/images/` READMEs — same grep + update.

## Success metrics

- `pytest tests/ -v` is fully green, with new tests covering every branch
  of the Imagen path and the provider-selection logic.
- Manual smoke generates a usable cover and three usable chapter
  illustrations for a sample book, with visually consistent characters
  across chapters 1–3.
- Rollback works: `--provider gemini` against the same script produces an
  image (or surfaces the upstream "not available on free tier" error
  cleanly, depending on Gemini availability).
- WORK_LOG entry, ERD section, and deploy doc references are updated.

## Open questions

None — all five clarifying questions resolved during brainstorming:

- Q1 (replacement scope): full replacement for both covers and chapters.
- Q2 (character consistency): prompt enrichment via per-book character brief.
- Q3 (fallback trigger): per-image fallback, only on retryable errors.
- Q4 (batch API): Imagen sync only; Gemini batch code kept dormant.
- Q5 (aspect ratio): `"3:4"` for both covers and chapters on Imagen path.
- Q6 (architecture): provider abstraction with both backends ready to use,
  `--provider` flag, default imagen.
