# Imagen 4 Image Generation (with Provider Abstraction) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the no-longer-free Gemini image generation models with an Imagen 4 fallback chain (Ultra → Standard → Fast), while keeping the existing Gemini code path runnable behind a `--provider gemini` CLI flag for rollback.

**Architecture:** Introduce `ImageGeneratorBase` abstract class in the existing script. Refactor the current `GeminiImageGenerator` to subclass it (zero behavior change). Add a new `ImagenImageGenerator` subclass that loops `imagen-4.0-ultra-generate-001` → `imagen-4.0-generate-001` → `imagen-4.0-fast-generate-001`, with per-image fallback only on retryable errors (429 / 5xx / quota / rate-limit / unavailable). For cross-chapter character consistency (Imagen has no reference-image input), a one-time `gemini-2.5-flash` text call produces a "character brief" per book, cached to disk, and injected into every chapter prompt. Rename `generate_gemini_illustrations.py` → `generate_illustrations.py` via `git mv` (and the matching test file). All Gemini batch helpers stay in place as dormant code.

**Tech Stack:** Python 3, `google-genai` SDK (`client.models.generate_images` for Imagen, `client.models.generate_content` for Gemini), pytest with `unittest.mock.patch`, existing `Database` and `config` modules.

**Spec:** `docs/superpowers/specs/2026-05-30-imagen-fallback-design.md`

---

## Pre-flight: ground rules

- Each task ends with a commit. Tests stay green at every commit.
- TDD: write the failing test first; confirm it fails for the *right reason*; then implement.
- Do not stage or commit unrelated dirty files (the working tree has many). Each `git add` lists explicit paths.
- Backend tests: `python -m pytest tests/test_illustrations.py -v` (after Task 1 rename) or `tests/test_gemini_illustrations.py -v` (before rename).
- Lint: this project has no lint command in CLAUDE.md — skip.

---

## Task 1: Rename script and test file via `git mv`

**Why first:** Subsequent tasks edit `scripts/images/generate_illustrations.py` and `tests/test_illustrations.py` by their new paths. Doing the rename up front means every later patch step uses the final filename and the import path settles immediately. We then fix the broken imports/patches before adding behavior.

**Files:**
- Rename: `scripts/images/generate_gemini_illustrations.py` → `scripts/images/generate_illustrations.py`
- Rename: `tests/test_gemini_illustrations.py` → `tests/test_illustrations.py`
- Modify: `tests/conftest.py` (line 137 patches `scripts.images.generate_gemini_illustrations.BATCH_JOBS_DIR`)
- Modify: `tests/test_illustrations.py` line 25 (import statement) and lines 221, 222, 251, 252, 278, 279, 314, 315, 358, 359, 401, 402, 466, 488 (all `@patch('scripts.images.generate_gemini_illustrations.X')` strings)

- [ ] **Step 1: Confirm existing tests pass before the rename**

```bash
cd /Users/pengyao/Documents/dev/summra
python -m pytest tests/test_gemini_illustrations.py -v 2>&1 | tail -20
```

Expected: all tests pass (record the pass count, e.g. "31 passed"). If anything is already failing, stop and investigate — don't bury a regression under the rename.

- [ ] **Step 2: Perform the rename with `git mv`**

```bash
git mv scripts/images/generate_gemini_illustrations.py scripts/images/generate_illustrations.py
git mv tests/test_gemini_illustrations.py tests/test_illustrations.py
```

- [ ] **Step 3: Fix the import path in the test file**

Edit `tests/test_illustrations.py`, line 25. Change:

```python
from scripts.images.generate_gemini_illustrations import (
```

to:

```python
from scripts.images.generate_illustrations import (
```

- [ ] **Step 4: Fix the `@patch(...)` strings in the test file**

In `tests/test_illustrations.py`, replace every occurrence of `scripts.images.generate_gemini_illustrations.` with `scripts.images.generate_illustrations.` (use Edit with `replace_all=true`).

- [ ] **Step 5: Fix the `@patch(...)` string in conftest**

In `tests/conftest.py` line 137, replace `scripts.images.generate_gemini_illustrations.BATCH_JOBS_DIR` with `scripts.images.generate_illustrations.BATCH_JOBS_DIR`.

- [ ] **Step 6: Run the renamed tests to confirm they still pass**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -20
```

Expected: same pass count as Step 1. Failures here mean an import or patch string still points at the old module path.

- [ ] **Step 7: Commit**

```bash
git add scripts/images/generate_illustrations.py \
        tests/test_illustrations.py \
        tests/conftest.py
git commit -m "$(cat <<'EOF'
Rename generate_gemini_illustrations.py → generate_illustrations.py

Prep for adding the Imagen 4 backend alongside the existing Gemini code.
Filename now describes what the script does, not which provider it uses.
No behavior change — only the module name and import paths move.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Introduce `ImageGeneratorBase` abstract class and reclassify `GeminiImageGenerator`

**Files:**
- Modify: `scripts/images/generate_illustrations.py` (insert base class before line 118, refactor `GeminiImageGenerator` class header and signatures)
- Modify: `tests/test_illustrations.py` (add new test class for base-class contract)

- [ ] **Step 1: Write the failing test for the base-class attributes on `GeminiImageGenerator`**

Add to `tests/test_illustrations.py` (at the bottom of the file, before any `if __name__ == "__main__":` block):

```python
class TestImageGeneratorBaseInterface:
    """ImageGeneratorBase contract — both subclasses must expose name and capability flags."""

    def test_gemini_generator_attributes(self):
        from scripts.images.generate_illustrations import GeminiImageGenerator
        gen = GeminiImageGenerator(api_key="fake-key", model="gemini-3-pro-image-preview")
        assert gen.name == "gemini"
        assert gen.supports_batch is True
        assert gen.supports_reference_image is True

    def test_gemini_chapter_signature_accepts_character_brief(self):
        """Gemini ignores character_brief but accepts the kwarg for interface parity."""
        import inspect
        from scripts.images.generate_illustrations import GeminiImageGenerator
        sig = inspect.signature(GeminiImageGenerator.generate_chapter_illustration)
        assert "character_brief" in sig.parameters
```

- [ ] **Step 2: Run the new tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestImageGeneratorBaseInterface -v 2>&1 | tail -20
```

Expected: both fail. The first with `AttributeError: 'GeminiImageGenerator' object has no attribute 'name'`, the second with `assert "character_brief" in sig.parameters` failing.

- [ ] **Step 3: Add the `ImageGeneratorBase` class**

In `scripts/images/generate_illustrations.py`, insert this block immediately *before* the `class GeminiImageGenerator:` line (currently line 118):

```python
class ImageGeneratorBase:
    """Common interface for image generation backends.

    Subclasses must set the three class-level attributes and implement
    generate_cover_image / generate_chapter_illustration with the signatures
    declared below. The character_brief and reference_image kwargs are
    advisory — backends that don't use them must accept and ignore them
    so the caller doesn't need to branch.
    """

    name: str = ""                          # "gemini" | "imagen"
    supports_batch: bool = False
    supports_reference_image: bool = False

    def generate_cover_image(
        self,
        book_title: str,
        book_author: str,
        medium_summary: str,
        dry_run: bool = False,
    ) -> Tuple[Optional[bytes], str]:
        raise NotImplementedError

    def generate_chapter_illustration(
        self,
        book_title: str,
        book_author: str,
        medium_summary: str,
        chapter: Dict,
        previous_chapter_summary: Optional[str] = None,
        reference_image: Optional[bytes] = None,
        character_brief: Optional[str] = None,
        dry_run: bool = False,
    ) -> Tuple[Optional[bytes], str]:
        raise NotImplementedError
```

- [ ] **Step 4: Reclassify `GeminiImageGenerator` and accept the new kwarg**

In `scripts/images/generate_illustrations.py`:

1. Change `class GeminiImageGenerator:` to `class GeminiImageGenerator(ImageGeneratorBase):`.
2. Add three class-level attribute lines at the top of the class body (right under the docstring):

   ```python
       name = "gemini"
       supports_batch = True
       supports_reference_image = True
   ```

3. Update the signature of `generate_chapter_illustration` (currently starts at line 233). Add `character_brief: Optional[str] = None,` as a new kwarg before `dry_run`. Inside the method body, immediately after the docstring, add:

   ```python
       # character_brief is unused on the Gemini path — reference images carry
       # cross-chapter consistency. Accepted for ImageGeneratorBase interface parity.
       _ = character_brief
   ```

- [ ] **Step 5: Run the new tests to confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestImageGeneratorBaseInterface -v 2>&1 | tail -20
```

Expected: both pass.

- [ ] **Step 6: Run the full test file to confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -20
```

Expected: same pass count as Task 1 Step 6, plus the two new passes.

- [ ] **Step 7: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Add ImageGeneratorBase abstract class; GeminiImageGenerator subclasses it

Establishes the contract subsequent providers will implement. GeminiImageGenerator
gains name/supports_batch/supports_reference_image attributes and a no-op
character_brief kwarg for interface parity. No behavior change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Mark Gemini batch helpers as dormant with header comments

**Files:**
- Modify: `scripts/images/generate_illustrations.py`

**Functions/sections to mark** (line numbers from the current file; verify with grep before editing):

- `create_batch_job` method on `GeminiImageGenerator`
- `poll_batch_job` method on `GeminiImageGenerator`
- `retrieve_batch_results` method on `GeminiImageGenerator`
- `save_batch_job_state` module-level function
- `load_batch_job_state` module-level function
- `update_batch_job_state` module-level function
- `list_pending_batch_jobs` module-level function
- `generate_chapter_illustrations_batch` module-level function
- `generate_book_covers_batch` module-level function
- `resume_batch_job` module-level function

- [ ] **Step 1: Locate each function's `def` line**

```bash
grep -n "def create_batch_job\|def poll_batch_job\|def retrieve_batch_results\|def save_batch_job_state\|def load_batch_job_state\|def update_batch_job_state\|def list_pending_batch_jobs\|def generate_chapter_illustrations_batch\|def generate_book_covers_batch\|def resume_batch_job" scripts/images/generate_illustrations.py
```

Expected: ten line numbers. Record them.

- [ ] **Step 2: Add the dormant-marker comment above each of the ten `def` lines**

For each function, insert this block on the line *above* its `def`:

```python
# ⚠️ DORMANT: Gemini-only batch path. Imagen 4 does not currently support
# the Files-based Batch API. Kept for potential rollback to --provider gemini.
```

Maintain the existing indentation (methods: 4 spaces; module-level functions: 0 spaces).

- [ ] **Step 3: Run the full test file to confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

Expected: same pass count as Task 2 Step 6.

- [ ] **Step 4: Commit**

```bash
git add scripts/images/generate_illustrations.py
git commit -m "$(cat <<'EOF'
Mark Gemini batch helpers as dormant

Adds header comments to the ten batch-related functions noting they are
kept for the --provider gemini rollback path and are unused by the active
Imagen flow.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add `ImagenImageGenerator` constants and `_is_retryable` helper (test-first)

**Files:**
- Modify: `scripts/images/generate_illustrations.py` (add class skeleton + retry helper)
- Modify: `tests/test_illustrations.py` (add `TestImagenIsRetryable` class)

- [ ] **Step 1: Write the failing tests for `_is_retryable`**

Add to `tests/test_illustrations.py`:

```python
class TestImagenIsRetryable:
    """ImagenImageGenerator._is_retryable: per-error-type fallback decisions."""

    @pytest.fixture
    def generator(self):
        from scripts.images.generate_illustrations import ImagenImageGenerator
        return ImagenImageGenerator(api_key="fake-key")

    def test_status_code_429_is_retryable(self, generator):
        exc = Exception("rate limited")
        exc.status_code = 429
        assert generator._is_retryable(exc) is True

    def test_status_code_500_is_retryable(self, generator):
        exc = Exception("server error")
        exc.status_code = 500
        assert generator._is_retryable(exc) is True

    def test_status_code_503_is_retryable(self, generator):
        exc = Exception("service unavailable")
        exc.status_code = 503
        assert generator._is_retryable(exc) is True

    def test_code_attribute_429_is_retryable(self, generator):
        exc = Exception("rate limited")
        exc.code = 429
        assert generator._is_retryable(exc) is True

    @pytest.mark.parametrize("substring", [
        "quota exceeded",
        "rate limit reached",
        "service unavailable",
        "RESOURCE_EXHAUSTED for project",
    ])
    def test_substring_match_is_retryable(self, generator, substring):
        assert generator._is_retryable(Exception(substring)) is True

    def test_invalid_argument_is_not_retryable(self, generator):
        exc = Exception("INVALID_ARGUMENT: bad prompt")
        exc.status_code = 400
        assert generator._is_retryable(exc) is False

    def test_content_policy_is_not_retryable(self, generator):
        assert generator._is_retryable(
            Exception("Image generation blocked by safety policy")
        ) is False

    def test_auth_error_is_not_retryable(self, generator):
        exc = Exception("PERMISSION_DENIED")
        exc.status_code = 403
        assert generator._is_retryable(exc) is False
```

- [ ] **Step 2: Run the new tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestImagenIsRetryable -v 2>&1 | tail -25
```

Expected: all 11 fail at import time with `ImportError: cannot import name 'ImagenImageGenerator'`.

- [ ] **Step 3: Add the `ImagenImageGenerator` skeleton + constants + `_is_retryable`**

In `scripts/images/generate_illustrations.py`, append this *after* the entire `GeminiImageGenerator` class but *before* the `def save_image(...)` module-level function:

```python
# === Imagen 4 backend =========================================================

IMAGEN_MODEL_CHAIN = [
    "imagen-4.0-ultra-generate-001",   # tier 1: highest quality
    "imagen-4.0-generate-001",         # tier 2: standard
    "imagen-4.0-fast-generate-001",    # tier 3: cheapest, lowest latency
]

IMAGEN_ASPECT_RATIO = "3:4"  # closest portrait Imagen 4 supports (was "2:3" on Gemini)

# Errors that mean "try the next tier"; everything else surfaces immediately.
IMAGEN_RETRYABLE_STATUS_CODES = {429, 500, 503}
IMAGEN_RETRYABLE_SUBSTRINGS = (
    "quota",
    "rate limit",
    "unavailable",
    "resource_exhausted",
)


class ImagenImageGenerator(ImageGeneratorBase):
    """Imagen 4 backend with Ultra → Standard → Fast fallback chain.

    Each generation call walks IMAGEN_MODEL_CHAIN top-down. If a tier raises
    a retryable error (quota, rate limit, 5xx), the next tier is tried.
    Non-retryable errors (content policy, INVALID_ARGUMENT, auth) surface
    immediately without burning two more API calls.

    Does not support reference images. Cross-chapter character consistency
    is handled by injecting a per-book character_brief into the prompt;
    see get_or_build_character_brief().
    """

    name = "imagen"
    supports_batch = False
    supports_reference_image = False

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.last_request_time = 0

    def _wait_for_rate_limit(self):
        """Respect the same MAX_REQUESTS_PER_MINUTE budget as GeminiImageGenerator."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < SECONDS_BETWEEN_REQUESTS:
            wait_time = SECONDS_BETWEEN_REQUESTS - elapsed
            print(f"  ⏳ Rate limit: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def _is_retryable(self, exc: Exception) -> bool:
        """True if exc looks like a quota/availability problem worth retrying on the next tier."""
        code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if code in IMAGEN_RETRYABLE_STATUS_CODES:
            return True
        msg = str(exc).lower()
        return any(s in msg for s in IMAGEN_RETRYABLE_SUBSTRINGS)
```

- [ ] **Step 4: Run the retry tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestImagenIsRetryable -v 2>&1 | tail -20
```

Expected: 11 passed.

- [ ] **Step 5: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Add ImagenImageGenerator skeleton with _is_retryable error classifier

Defines the model chain (Ultra → Standard → Fast), aspect ratio constant,
and the per-image fallback rule: only quota/availability/5xx errors fall
through; content-policy and bad-prompt errors surface immediately.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Implement `_generate_with_fallback` (test-first)

**Files:**
- Modify: `scripts/images/generate_illustrations.py` (add private method)
- Modify: `tests/test_illustrations.py` (add `TestImagenFallbackChain` class)

- [ ] **Step 1: Write the failing fallback-chain tests**

Add to `tests/test_illustrations.py`:

```python
class TestImagenFallbackChain:
    """ImagenImageGenerator._generate_with_fallback: per-tier behavior."""

    @pytest.fixture
    def generator(self):
        from scripts.images.generate_illustrations import ImagenImageGenerator
        gen = ImagenImageGenerator(api_key="fake-key")
        # Mock out the actual API client and the rate limiter
        gen.client = MagicMock()
        gen._wait_for_rate_limit = MagicMock()
        return gen

    def _make_success_response(self, image_bytes: bytes = b"fake-png-bytes"):
        """Build a generate_images response with one image."""
        image_obj = MagicMock()
        image_obj.image.image_bytes = image_bytes
        response = MagicMock()
        response.generated_images = [image_obj]
        return response

    def test_first_tier_success_does_not_try_lower_tiers(self, generator):
        generator.client.models.generate_images.return_value = self._make_success_response()
        image, model = generator._generate_with_fallback(prompt="test", aspect_ratio="3:4")
        assert image == b"fake-png-bytes"
        assert model == "imagen-4.0-ultra-generate-001"
        assert generator.client.models.generate_images.call_count == 1

    def test_quota_on_first_tier_falls_through_to_second(self, generator):
        quota_exc = Exception("RESOURCE_EXHAUSTED: quota for ultra")
        generator.client.models.generate_images.side_effect = [
            quota_exc,
            self._make_success_response(b"second-tier-bytes"),
        ]
        image, model = generator._generate_with_fallback(prompt="test", aspect_ratio="3:4")
        assert image == b"second-tier-bytes"
        assert model == "imagen-4.0-generate-001"
        assert generator.client.models.generate_images.call_count == 2

    def test_all_three_tiers_quota_returns_none(self, generator):
        quota_exc = Exception("quota exceeded")
        generator.client.models.generate_images.side_effect = [quota_exc, quota_exc, quota_exc]
        image, model = generator._generate_with_fallback(prompt="test", aspect_ratio="3:4")
        assert image is None
        assert model == "imagen-4.0-fast-generate-001"  # last tier attempted
        assert generator.client.models.generate_images.call_count == 3

    def test_non_retryable_error_stops_at_first_tier(self, generator):
        policy_exc = Exception("Image blocked by safety filter")
        generator.client.models.generate_images.side_effect = [policy_exc]
        image, model = generator._generate_with_fallback(prompt="test", aspect_ratio="3:4")
        assert image is None
        assert model == "imagen-4.0-ultra-generate-001"  # tier that raised
        assert generator.client.models.generate_images.call_count == 1

    def test_empty_response_falls_through(self, generator):
        empty = MagicMock()
        empty.generated_images = []
        generator.client.models.generate_images.side_effect = [
            empty,
            self._make_success_response(b"recovered"),
        ]
        image, model = generator._generate_with_fallback(prompt="test", aspect_ratio="3:4")
        assert image == b"recovered"
        assert model == "imagen-4.0-generate-001"

    def test_aspect_ratio_passed_to_api(self, generator):
        generator.client.models.generate_images.return_value = self._make_success_response()
        generator._generate_with_fallback(prompt="test", aspect_ratio="3:4")
        call_kwargs = generator.client.models.generate_images.call_args.kwargs
        assert call_kwargs["config"].aspect_ratio == "3:4"
        assert call_kwargs["config"].number_of_images == 1
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestImagenFallbackChain -v 2>&1 | tail -30
```

Expected: 6 fail with `AttributeError: 'ImagenImageGenerator' object has no attribute '_generate_with_fallback'`.

- [ ] **Step 3: Implement `_generate_with_fallback`**

In `scripts/images/generate_illustrations.py`, inside the `ImagenImageGenerator` class (immediately after `_is_retryable`), add:

```python
    def _generate_with_fallback(
        self, prompt: str, aspect_ratio: str
    ) -> Tuple[Optional[bytes], str]:
        """Walk IMAGEN_MODEL_CHAIN top-down. Return (image_bytes_or_None, model_used)."""
        last_error_msg = None
        last_model_attempted = IMAGEN_MODEL_CHAIN[-1]
        for model in IMAGEN_MODEL_CHAIN:
            last_model_attempted = model
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
                    print(f"  ✅ Generated with {model}")
                    return response.generated_images[0].image.image_bytes, model
                last_error_msg = f"{model}: empty response"
                print(f"  ⚠️  {model} returned no images; trying next tier...")
                continue
            except Exception as e:  # noqa: BLE001 — surface or fall through based on _is_retryable
                last_error_msg = f"{model}: {e}"
                if not self._is_retryable(e):
                    print(f"  ❌ Non-retryable error from {model}: {e}")
                    return None, model
                print(f"  ⚠️  {model} failed ({e}); trying next tier...")
                continue
        print(f"  ❌ All Imagen tiers failed. Last error: {last_error_msg}")
        return None, last_model_attempted
```

- [ ] **Step 4: Run the fallback tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestImagenFallbackChain -v 2>&1 | tail -20
```

Expected: 6 passed.

- [ ] **Step 5: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Implement Imagen fallback chain (_generate_with_fallback)

Per-image walk over IMAGEN_MODEL_CHAIN. Retryable errors (quota / rate
limit / 5xx) fall through to the next tier; non-retryable errors
(content policy, bad prompt, auth) surface immediately. Returns the
model that actually produced the image so logs can show downgrades.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Implement `ImagenImageGenerator.generate_cover_image` (test-first)

**Files:**
- Modify: `scripts/images/generate_illustrations.py`
- Modify: `tests/test_illustrations.py`

- [ ] **Step 1: Write the failing cover-generation tests**

Add to `tests/test_illustrations.py`:

```python
class TestImagenCoverGeneration:
    """ImagenImageGenerator.generate_cover_image: prompt building + delegate to fallback."""

    @pytest.fixture
    def generator(self):
        from scripts.images.generate_illustrations import ImagenImageGenerator
        gen = ImagenImageGenerator(api_key="fake-key")
        gen._generate_with_fallback = MagicMock(
            return_value=(b"cover-bytes", "imagen-4.0-ultra-generate-001")
        )
        return gen

    def test_cover_returns_image_bytes_on_success(self, generator):
        image, model = generator.generate_cover_image(
            book_title="The Trial",
            book_author="Franz Kafka",
            medium_summary="Josef K. is arrested without explanation...",
        )
        assert image == b"cover-bytes"
        assert model == "imagen-4.0-ultra-generate-001"

    def test_cover_prompt_includes_title_and_author(self, generator):
        generator.generate_cover_image(
            book_title="The Trial",
            book_author="Franz Kafka",
            medium_summary="Josef K. is arrested without explanation...",
        )
        prompt_arg = generator._generate_with_fallback.call_args.kwargs["prompt"]
        assert "The Trial" in prompt_arg
        assert "Franz Kafka" in prompt_arg

    def test_cover_uses_3_4_aspect_ratio(self, generator):
        generator.generate_cover_image(
            book_title="Test", book_author="Test", medium_summary="...",
        )
        assert generator._generate_with_fallback.call_args.kwargs["aspect_ratio"] == "3:4"

    def test_cover_dry_run_does_not_call_api(self, generator):
        image, _ = generator.generate_cover_image(
            book_title="Test", book_author="Test", medium_summary="...",
            dry_run=True,
        )
        assert image is None
        generator._generate_with_fallback.assert_not_called()
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestImagenCoverGeneration -v 2>&1 | tail -20
```

Expected: 4 fail with `AttributeError: 'ImagenImageGenerator' object has no attribute 'generate_cover_image'` (or the inherited `NotImplementedError`).

- [ ] **Step 3: Implement `generate_cover_image`**

In `scripts/images/generate_illustrations.py`, inside the `ImagenImageGenerator` class, add:

```python
    def generate_cover_image(
        self,
        book_title: str,
        book_author: str,
        medium_summary: str,
        dry_run: bool = False,
    ) -> Tuple[Optional[bytes], str]:
        clean_title = clean_title_for_prompt(book_title)
        prompt = f"""Generate book cover art for "{clean_title}" by {book_author}. Your main focus is accurate visual storytelling — the cover should vividly capture the essence, tone, and meaning of the book's content.

Your process:
1. Interpret the book summary below to understand its mood, symbolism, and key imagery.
2. Ensure the cover adheres to the following layout rules:
   - The title "{clean_title}" must appear at the top, complete and correctly spelled.
   - The author name "{book_author}" must appear at the bottom.
   - The illustration must cover the full page, edge-to-edge, with no borders.
   - The art must visually reflect the book's actual story and tone, not just literal elements from the title.
3. Create a composition with appropriate lighting, color palette, artistic style, and mood — all tied to the story's themes.
4. Place the title at the top and author at the bottom, with art that has no visible borders or frames.

Guidelines:
- Prioritize storytelling accuracy: symbolism, color, and imagery should represent the narrative truth of the book.
- Avoid generic visuals or irrelevant symbolism.
- Use appropriate artwork and color scheme for the genre and time period.
- Professional, publishable quality suitable for a book cover.

Book Summary:
{medium_summary}

Generate ONE high-quality, professional book cover."""

        print(f"\n{'='*80}\nCOVER IMAGE PROMPT (Imagen):\n{'='*80}\n{prompt}\n{'='*80}\n")

        if dry_run:
            print(f"  [DRY RUN] Skipping actual image generation")
            return (None, "")

        return self._generate_with_fallback(prompt=prompt, aspect_ratio=IMAGEN_ASPECT_RATIO)
```

- [ ] **Step 4: Run the cover tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestImagenCoverGeneration -v 2>&1 | tail -15
```

Expected: 4 passed.

- [ ] **Step 5: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Implement ImagenImageGenerator.generate_cover_image

Reuses the existing cover prompt (storytelling-first composition rules);
delegates the actual API call to _generate_with_fallback so Imagen 4 tiers
are walked Ultra → Standard → Fast on quota errors. Aspect ratio "3:4".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Extend `build_chapter_illustration_prompt` to accept `character_brief` (test-first)

**Files:**
- Modify: `scripts/images/generate_illustrations.py` (extend the existing function at lines 567-620)
- Modify: `tests/test_illustrations.py` (add `TestBuildChapterPromptCharacterBrief` class)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_illustrations.py`:

```python
class TestBuildChapterPromptCharacterBrief:
    """build_chapter_illustration_prompt: optional character_brief injection."""

    def _chapter(self):
        return {
            "chapter_number": 3,
            "chapter_title": "The Storm",
            "summary": "The crew battles a hurricane.",
            "word_count": 1200,
        }

    def test_brief_none_omits_style_guide_header(self):
        from scripts.images.generate_illustrations import build_chapter_illustration_prompt
        prompt = build_chapter_illustration_prompt(
            book_title="Moby-Dick",
            book_author="Herman Melville",
            medium_summary="A whaling voyage...",
            chapter=self._chapter(),
            previous_chapter_summary=None,
            character_brief=None,
        )
        assert "VISUAL STYLE GUIDE" not in prompt

    def test_brief_empty_string_omits_header(self):
        from scripts.images.generate_illustrations import build_chapter_illustration_prompt
        prompt = build_chapter_illustration_prompt(
            book_title="Moby-Dick",
            book_author="Herman Melville",
            medium_summary="A whaling voyage...",
            chapter=self._chapter(),
            character_brief="",
        )
        assert "VISUAL STYLE GUIDE" not in prompt

    def test_brief_present_includes_header_and_brief_text(self):
        from scripts.images.generate_illustrations import build_chapter_illustration_prompt
        brief = "ART STYLE: moody oil painting.\nCHARACTERS: Ahab — peg-legged captain..."
        prompt = build_chapter_illustration_prompt(
            book_title="Moby-Dick",
            book_author="Herman Melville",
            medium_summary="A whaling voyage...",
            chapter=self._chapter(),
            character_brief=brief,
        )
        assert "=== VISUAL STYLE GUIDE (apply to every illustration in this book) ===" in prompt
        assert "moody oil painting" in prompt
        assert "peg-legged captain" in prompt

    def test_brief_is_inserted_before_overall_summary(self):
        """Style guide should come before the per-book summary so the model
        weighs visual style ahead of plot context."""
        from scripts.images.generate_illustrations import build_chapter_illustration_prompt
        brief = "ART STYLE: watercolor"
        prompt = build_chapter_illustration_prompt(
            book_title="A", book_author="B",
            medium_summary="OVERALL_BOOK_SUMMARY_MARKER",
            chapter=self._chapter(),
            character_brief=brief,
        )
        brief_idx = prompt.index("VISUAL STYLE GUIDE")
        summary_idx = prompt.index("OVERALL_BOOK_SUMMARY_MARKER")
        assert brief_idx < summary_idx
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestBuildChapterPromptCharacterBrief -v 2>&1 | tail -25
```

Expected: 4 fail. First three: `TypeError: build_chapter_illustration_prompt() got an unexpected keyword argument 'character_brief'`. Fourth: same.

- [ ] **Step 3: Extend `build_chapter_illustration_prompt`**

In `scripts/images/generate_illustrations.py`, replace the existing function (`def build_chapter_illustration_prompt(...)` starting around line 567) with:

```python
def build_chapter_illustration_prompt(book_title: str, book_author: str,
                                     medium_summary: str, chapter: Dict,
                                     previous_chapter_summary: Optional[str] = None,
                                     character_brief: Optional[str] = None) -> str:
    """Build the prompt for chapter illustration generation.

    character_brief, when non-empty, is injected under a VISUAL STYLE GUIDE
    header between the "Book:" line and the overall book summary. Used by
    ImagenImageGenerator for cross-chapter character consistency; the Gemini
    path passes None.
    """
    chapter_num = chapter['chapter_number']
    chapter_title = chapter.get('chapter_title', '')
    chapter_summary = chapter['summary']

    title_part = f" - {chapter_title}" if chapter_title else ""

    prev_context = ""
    if previous_chapter_summary:
        prev_context = f"""
Summary of previous chapter for reference:
{previous_chapter_summary}

"""

    style_guide_section = ""
    if character_brief:
        style_guide_section = f"""=== VISUAL STYLE GUIDE (apply to every illustration in this book) ===
{character_brief}

"""

    prompt = f"""Create a full page illustration for the following chapter.

The illustration can have multiple panels describing the key plot of the chapter. Consider the art style of previous generations. Maintain consistency of key characters in terms of art style and appearance.

CRITICAL RULES - MUST FOLLOW:
- NO TEXT OF ANY KIND on the image
- NO dialog bubbles or speech
- NO narration or captions
- NO chapter numbers or citations
- NO words, letters, or written language visible anywhere
- ONLY visual storytelling through pictures

The image must be completely text-free. Any text, dialog, or words will make the illustration unusable.

Book: {book_title} by {book_author}

{style_guide_section}Summary of the overall book (for reference):
{medium_summary}

{prev_context}Chapter to be illustrated:
=== Chapter {chapter_num}{title_part} ===
{chapter_summary}"""

    return prompt
```

- [ ] **Step 4: Run the new tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestBuildChapterPromptCharacterBrief -v 2>&1 | tail -15
```

Expected: 4 passed.

- [ ] **Step 5: Confirm no regression of existing prompt tests**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

Expected: pass count = previous count + 4. (If prior tests asserted exact prompt strings, they may break — fix them by passing `character_brief=None` explicitly OR by leaving the optional default in place; the function already defaults to None so unchanged calls should still pass.)

- [ ] **Step 6: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Add optional character_brief to build_chapter_illustration_prompt

When provided, the brief is injected under a VISUAL STYLE GUIDE header
between the book metadata and the overall summary. Used by Imagen to
maintain cross-chapter character consistency (Imagen has no
reference-image input). Default None keeps existing Gemini call sites
unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Implement `ImagenImageGenerator.generate_chapter_illustration` (test-first)

**Files:**
- Modify: `scripts/images/generate_illustrations.py`
- Modify: `tests/test_illustrations.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_illustrations.py`:

```python
class TestImagenChapterGeneration:
    """ImagenImageGenerator.generate_chapter_illustration: prompt + brief + ignore reference."""

    @pytest.fixture
    def generator(self):
        from scripts.images.generate_illustrations import ImagenImageGenerator
        gen = ImagenImageGenerator(api_key="fake-key")
        gen._generate_with_fallback = MagicMock(
            return_value=(b"chapter-bytes", "imagen-4.0-generate-001")
        )
        return gen

    def _chapter(self):
        return {
            "chapter_number": 5,
            "chapter_title": "The Reckoning",
            "summary": "The protagonist confronts the villain.",
            "word_count": 1500,
        }

    def test_chapter_returns_bytes_on_success(self, generator):
        image, model = generator.generate_chapter_illustration(
            book_title="Test Book", book_author="Test Author",
            medium_summary="A summary.",
            chapter=self._chapter(),
        )
        assert image == b"chapter-bytes"
        assert model == "imagen-4.0-generate-001"

    def test_chapter_uses_3_4_aspect_ratio(self, generator):
        generator.generate_chapter_illustration(
            book_title="Test", book_author="Test",
            medium_summary="...", chapter=self._chapter(),
        )
        assert generator._generate_with_fallback.call_args.kwargs["aspect_ratio"] == "3:4"

    def test_chapter_brief_injected_into_prompt(self, generator):
        generator.generate_chapter_illustration(
            book_title="Test", book_author="Test",
            medium_summary="A summary.", chapter=self._chapter(),
            character_brief="ART STYLE: charcoal sketch",
        )
        prompt = generator._generate_with_fallback.call_args.kwargs["prompt"]
        assert "VISUAL STYLE GUIDE" in prompt
        assert "charcoal sketch" in prompt

    def test_chapter_ignores_reference_image_without_crashing(self, generator):
        # Should not raise, should still produce output
        image, _ = generator.generate_chapter_illustration(
            book_title="Test", book_author="Test",
            medium_summary="A summary.", chapter=self._chapter(),
            reference_image=b"some_image_bytes",
        )
        assert image == b"chapter-bytes"

    def test_chapter_dry_run_does_not_call_api(self, generator):
        image, _ = generator.generate_chapter_illustration(
            book_title="Test", book_author="Test",
            medium_summary="...", chapter=self._chapter(),
            dry_run=True,
        )
        assert image is None
        generator._generate_with_fallback.assert_not_called()
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestImagenChapterGeneration -v 2>&1 | tail -25
```

Expected: 5 fail with `NotImplementedError` from the base class.

- [ ] **Step 3: Implement `generate_chapter_illustration`**

In `scripts/images/generate_illustrations.py`, inside the `ImagenImageGenerator` class (after `generate_cover_image`), add:

```python
    def generate_chapter_illustration(
        self,
        book_title: str,
        book_author: str,
        medium_summary: str,
        chapter: Dict,
        previous_chapter_summary: Optional[str] = None,
        reference_image: Optional[bytes] = None,
        character_brief: Optional[str] = None,
        dry_run: bool = False,
    ) -> Tuple[Optional[bytes], str]:
        chapter_num = chapter['chapter_number']

        if reference_image is not None:
            print(f"  ℹ️  Imagen does not support reference images; ignoring (chapter {chapter_num})")

        prompt = build_chapter_illustration_prompt(
            book_title=book_title,
            book_author=book_author,
            medium_summary=medium_summary,
            chapter=chapter,
            previous_chapter_summary=previous_chapter_summary,
            character_brief=character_brief,
        )

        print(f"\n{'='*80}\nCHAPTER ILLUSTRATION PROMPT (Imagen, Chapter {chapter_num}):\n{'='*80}\n{prompt}\n{'='*80}\n")

        if dry_run:
            print(f"  [DRY RUN] Skipping actual image generation")
            return (None, "")

        return self._generate_with_fallback(prompt=prompt, aspect_ratio=IMAGEN_ASPECT_RATIO)
```

- [ ] **Step 4: Run the chapter tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestImagenChapterGeneration -v 2>&1 | tail -15
```

Expected: 5 passed.

- [ ] **Step 5: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Implement ImagenImageGenerator.generate_chapter_illustration

Builds the chapter prompt via the shared builder (now with character_brief
injection), delegates to _generate_with_fallback. Accepts and ignores
reference_image with a one-line log. Aspect ratio "3:4".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Implement `get_or_build_character_brief` helper (test-first)

**Files:**
- Modify: `scripts/images/generate_illustrations.py` (add module-level function)
- Modify: `tests/test_illustrations.py` (add `TestGetOrBuildCharacterBrief` class)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_illustrations.py`:

```python
class TestGetOrBuildCharacterBrief:
    """get_or_build_character_brief: cache to disk, fallback on LLM failure."""

    @pytest.fixture
    def tmp_briefs_dir(self, tmp_path, monkeypatch):
        d = tmp_path / "character_briefs"
        d.mkdir()
        from scripts.images import generate_illustrations
        monkeypatch.setattr(generate_illustrations, "CHARACTER_BRIEFS_DIR", d)
        return d

    @patch("scripts.images.generate_illustrations._call_brief_llm")
    def test_first_call_invokes_llm_and_writes_cache(self, mock_llm, tmp_briefs_dir):
        from scripts.images.generate_illustrations import get_or_build_character_brief
        mock_llm.return_value = "ART STYLE: oil painting"
        result = get_or_build_character_brief(book_id=42, medium_summary="A summary")
        assert result == "ART STYLE: oil painting"
        mock_llm.assert_called_once_with("A summary")
        cache_file = tmp_briefs_dir / "42.txt"
        assert cache_file.exists()
        assert cache_file.read_text() == "ART STYLE: oil painting"

    @patch("scripts.images.generate_illustrations._call_brief_llm")
    def test_second_call_uses_cache_and_skips_llm(self, mock_llm, tmp_briefs_dir):
        from scripts.images.generate_illustrations import get_or_build_character_brief
        (tmp_briefs_dir / "42.txt").write_text("CACHED BRIEF")
        result = get_or_build_character_brief(book_id=42, medium_summary="A summary")
        assert result == "CACHED BRIEF"
        mock_llm.assert_not_called()

    @patch("scripts.images.generate_illustrations._call_brief_llm")
    def test_llm_failure_returns_empty_string(self, mock_llm, tmp_briefs_dir):
        from scripts.images.generate_illustrations import get_or_build_character_brief
        mock_llm.side_effect = Exception("API down")
        result = get_or_build_character_brief(book_id=42, medium_summary="A summary")
        assert result == ""
        # Should NOT write a cache file on failure
        assert not (tmp_briefs_dir / "42.txt").exists()

    @patch("scripts.images.generate_illustrations._call_brief_llm")
    def test_llm_empty_response_returns_empty_string(self, mock_llm, tmp_briefs_dir):
        from scripts.images.generate_illustrations import get_or_build_character_brief
        mock_llm.return_value = ""
        result = get_or_build_character_brief(book_id=42, medium_summary="A summary")
        assert result == ""
        assert not (tmp_briefs_dir / "42.txt").exists()
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestGetOrBuildCharacterBrief -v 2>&1 | tail -25
```

Expected: 4 fail with `AttributeError: module 'scripts.images.generate_illustrations' has no attribute 'CHARACTER_BRIEFS_DIR'` (or `get_or_build_character_brief`).

- [ ] **Step 3: Implement the helper**

In `scripts/images/generate_illustrations.py`, add near the top (after the existing `BATCH_JOBS_DIR` constant around line 115):

```python
CHARACTER_BRIEFS_DIR = Path(__file__).parent.parent.parent / "data" / "character_briefs"
CHARACTER_BRIEF_MODEL = "gemini-2.5-flash"  # cheap text-only model
```

Then add these two module-level functions (e.g. immediately after `build_chapter_illustration_prompt`):

```python
def _call_brief_llm(medium_summary: str) -> str:
    """Call the brief-builder LLM. Separated so tests can patch it cleanly."""
    prompt = f"""You are preparing a visual style guide for a book illustrator who will draw
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
{medium_summary}"""

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(model=CHARACTER_BRIEF_MODEL, contents=prompt)
    return (response.text or "").strip()


def get_or_build_character_brief(book_id: int, medium_summary: str) -> str:
    """Return the cached character brief for `book_id`, generating it once if missing.

    On LLM failure or empty response, returns "" and does NOT write a cache file
    (so the next run gets a chance to retry). Manual cache invalidation =
    delete data/character_briefs/{book_id}.txt.
    """
    CHARACTER_BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CHARACTER_BRIEFS_DIR / f"{book_id}.txt"
    if cache_file.exists():
        return cache_file.read_text()
    try:
        brief = _call_brief_llm(medium_summary)
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️  Character brief LLM failed for book {book_id}: {e}")
        return ""
    if not brief:
        print(f"  ⚠️  Character brief LLM returned empty for book {book_id}")
        return ""
    cache_file.write_text(brief)
    print(f"  💾 Cached character brief for book {book_id}: {cache_file}")
    return brief
```

- [ ] **Step 4: Run the brief tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestGetOrBuildCharacterBrief -v 2>&1 | tail -15
```

Expected: 4 passed.

- [ ] **Step 5: Add a `.gitignore` for the brief cache directory**

```bash
mkdir -p /Users/pengyao/Documents/dev/summra/data/character_briefs
printf '*\n!.gitignore\n' > /Users/pengyao/Documents/dev/summra/data/character_briefs/.gitignore
```

- [ ] **Step 6: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add scripts/images/generate_illustrations.py \
        tests/test_illustrations.py \
        data/character_briefs/.gitignore
git commit -m "$(cat <<'EOF'
Add get_or_build_character_brief helper for Imagen consistency

One-time gemini-2.5-flash text call per book produces a structured visual
style guide (art style / palette / recurring characters / setting), cached
to data/character_briefs/{book_id}.txt. Manual delete to invalidate.
LLM failures or empty responses return "" without writing the cache so
the next run can retry.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Wire `character_brief` into the sync chapter-loop call site

**Files:**
- Modify: `scripts/images/generate_illustrations.py` — the `generate_chapter_illustrations_for_book` function (~lines 965-1096).
- Modify: `tests/test_illustrations.py` — verify the brief is fetched once and passed through.

Tests for this are an integration-style check using a mocked generator + DB. We're verifying the call site, not the helper.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_illustrations.py`:

```python
class TestChapterLoopUsesCharacterBrief:
    """generate_chapter_illustrations_for_book passes character_brief to the generator."""

    @patch("scripts.images.generate_illustrations.auto_optimize_illustrations")
    @patch("scripts.images.generate_illustrations.save_image", return_value=True)
    @patch("scripts.images.generate_illustrations.get_or_build_character_brief")
    def test_brief_fetched_once_per_book_and_passed_to_every_chapter(
        self, mock_brief, mock_save, mock_optimize, tmp_path, monkeypatch
    ):
        from scripts.images import generate_illustrations
        from scripts.images.generate_illustrations import (
            generate_chapter_illustrations_for_book, ImagenImageGenerator,
        )

        # Redirect illustration_originals into tmp_path so the test doesn't touch the real tree
        monkeypatch.setattr(
            generate_illustrations,
            "project_root",
            tmp_path,
            raising=False,
        )

        mock_brief.return_value = "ART STYLE: ink wash"
        db = MagicMock()
        db.get_book.return_value = {"id": 1, "title": "T", "author": "A"}
        db.get_summary.return_value = {"content": "A summary"}
        db.get_chapters.return_value = [
            {"chapter_number": n, "chapter_title": "", "summary": "s", "word_count": 1000}
            for n in (1, 2)
        ]
        db.get_chapter.return_value = {"summary": "prev"}

        generator = ImagenImageGenerator(api_key="fake")
        generator.generate_chapter_illustration = MagicMock(
            return_value=(b"img", "imagen-4.0-generate-001")
        )

        generate_chapter_illustrations_for_book(db, generator, book_id=1, dry_run=False)

        # Brief fetched exactly once
        mock_brief.assert_called_once()
        # Passed to every chapter call
        for call in generator.generate_chapter_illustration.call_args_list:
            assert call.kwargs["character_brief"] == "ART STYLE: ink wash"

    @patch("scripts.images.generate_illustrations.auto_optimize_illustrations")
    @patch("scripts.images.generate_illustrations.save_image", return_value=True)
    @patch("scripts.images.generate_illustrations.get_or_build_character_brief")
    def test_brief_not_fetched_for_gemini_generator(
        self, mock_brief, mock_save, mock_optimize, tmp_path, monkeypatch
    ):
        from scripts.images import generate_illustrations
        from scripts.images.generate_illustrations import (
            generate_chapter_illustrations_for_book, GeminiImageGenerator,
        )
        monkeypatch.setattr(generate_illustrations, "project_root", tmp_path, raising=False)

        db = MagicMock()
        db.get_book.return_value = {"id": 1, "title": "T", "author": "A"}
        db.get_summary.return_value = {"content": "A summary"}
        db.get_chapters.return_value = [
            {"chapter_number": 1, "chapter_title": "", "summary": "s", "word_count": 1000},
        ]
        db.get_chapter.return_value = None

        generator = GeminiImageGenerator(api_key="fake", model="gemini-3-pro-image-preview")
        generator.generate_chapter_illustration = MagicMock(
            return_value=(b"img", "")
        )

        generate_chapter_illustrations_for_book(db, generator, book_id=1, dry_run=False)
        mock_brief.assert_not_called()
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestChapterLoopUsesCharacterBrief -v 2>&1 | tail -20
```

Expected: 2 fail. First: `mock_brief.assert_called_once()` fails (not called at all yet). Second already passes — if so, that's OK; the assertion is conservative.

- [ ] **Step 3: Wire `character_brief` into the chapter loop**

In `scripts/images/generate_illustrations.py`, locate `generate_chapter_illustrations_for_book` (~line 965). Inside the function, right after the existing `chapters = filter_eligible_chapters(...)` call and the empty-chapters early return, but BEFORE the `for i, chapter in enumerate(chapters):` loop, add:

```python
    # Imagen needs cross-chapter consistency via prompt text (no reference-image input).
    # Gemini uses the previous-chapter PNG as reference instead.
    character_brief = ""
    if generator.name == "imagen":
        character_brief = get_or_build_character_brief(book_id, summary['content'])
```

Then, inside the loop, find the existing call:

```python
        image_data, chapter_prompt = generator.generate_chapter_illustration(
            book_title=book['title'],
            book_author=book['author'],
            medium_summary=summary['content'],
            chapter=chapter,
            previous_chapter_summary=previous_chapter_summary,
            reference_image=reference_image,
            dry_run=dry_run
        )
```

And add the new kwarg:

```python
        image_data, chapter_prompt = generator.generate_chapter_illustration(
            book_title=book['title'],
            book_author=book['author'],
            medium_summary=summary['content'],
            chapter=chapter,
            previous_chapter_summary=previous_chapter_summary,
            reference_image=reference_image,
            character_brief=character_brief,
            dry_run=dry_run
        )
```

Note: even when `character_brief == ""`, passing it is harmless — both backends already handle empty/None.

- [ ] **Step 4: Run the new tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestChapterLoopUsesCharacterBrief -v 2>&1 | tail -15
```

Expected: 2 passed.

- [ ] **Step 5: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Wire character_brief into the sync chapter loop for Imagen

generate_chapter_illustrations_for_book fetches the brief once per book
(only when the generator is Imagen) and passes it into every chapter
illustration call. Gemini path is untouched — it gets character
consistency via reference images instead.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Add `--provider` CLI flag with `build_generator` factory and flag-guard tests

**Files:**
- Modify: `scripts/images/generate_illustrations.py` — `main()` and a new `build_generator` helper.
- Modify: `tests/test_illustrations.py` — new `TestProviderSelection` class.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_illustrations.py`:

```python
class TestProviderSelection:
    """build_generator factory + main() flag-guard behavior."""

    def test_build_generator_default_provider_is_imagen(self):
        from scripts.images.generate_illustrations import (
            build_generator, ImagenImageGenerator,
        )
        gen = build_generator(provider="imagen", api_key="fake", model=None)
        assert isinstance(gen, ImagenImageGenerator)

    def test_build_generator_gemini_explicit(self):
        from scripts.images.generate_illustrations import (
            build_generator, GeminiImageGenerator,
        )
        gen = build_generator(provider="gemini", api_key="fake", model="gemini-3-pro-image-preview")
        assert isinstance(gen, GeminiImageGenerator)
        assert gen.model == "gemini-3-pro-image-preview"

    def test_build_generator_gemini_default_model(self):
        from scripts.images.generate_illustrations import build_generator
        gen = build_generator(provider="gemini", api_key="fake", model=None)
        assert gen.model == "gemini-3-pro-image-preview"

    def test_build_generator_unknown_provider_raises(self):
        from scripts.images.generate_illustrations import build_generator
        with pytest.raises(ValueError, match="Unknown provider"):
            build_generator(provider="dall-e", api_key="fake", model=None)

    @patch("scripts.images.generate_illustrations.config")
    def test_imagen_with_sync_mode_exits_non_zero(self, mock_config, capsys, monkeypatch):
        """--provider imagen + --sync-mode should error out, not silently fall back."""
        mock_config.GEMINI_API_KEY = "fake"
        from scripts.images.generate_illustrations import main
        monkeypatch.setattr(
            "sys.argv",
            ["generate_illustrations.py", "--book-id", "1", "--sync-mode"],
        )
        rc = main()
        assert rc != 0
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "imagen" in combined.lower()
        assert "batch" in combined.lower() or "sync" in combined.lower()

    @patch("scripts.images.generate_illustrations.config")
    def test_imagen_with_list_jobs_exits_non_zero(self, mock_config, capsys, monkeypatch):
        mock_config.GEMINI_API_KEY = "fake"
        from scripts.images.generate_illustrations import main
        monkeypatch.setattr(
            "sys.argv",
            ["generate_illustrations.py", "--list-jobs"],
        )
        rc = main()
        # --list-jobs is still allowed under --provider gemini default. With imagen, it errors.
        # Provider defaults to imagen, so this MUST error.
        assert rc != 0

    @patch("scripts.images.generate_illustrations.config")
    def test_imagen_with_model_flag_prints_warning(self, mock_config, capsys, monkeypatch):
        """--provider imagen --model X should warn and ignore the model flag, not crash."""
        mock_config.GEMINI_API_KEY = "fake"
        from scripts.images.generate_illustrations import main
        # Use --dry-run so we don't actually invoke the API
        monkeypatch.setattr(
            "sys.argv",
            ["generate_illustrations.py", "--book-id", "1", "--model",
             "gemini-2.5-flash-image", "--dry-run"],
        )
        # Don't care about return code (DB may be missing); we want the warning text.
        try:
            main()
        except SystemExit:
            pass
        except Exception:
            pass
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "--model" in combined or "ignored" in combined.lower()
```

- [ ] **Step 2: Run the tests, confirm they fail**

```bash
python -m pytest tests/test_illustrations.py::TestProviderSelection -v 2>&1 | tail -30
```

Expected: 7 fail (no `build_generator`, no `--provider` flag, no guards).

- [ ] **Step 3: Add `build_generator` factory**

In `scripts/images/generate_illustrations.py`, add a module-level function (before `main()`):

```python
def build_generator(provider: str, api_key: str, model: Optional[str]) -> ImageGeneratorBase:
    """Construct the requested image generation backend."""
    if provider == "imagen":
        return ImagenImageGenerator(api_key)
    if provider == "gemini":
        return GeminiImageGenerator(api_key, model=model or DEFAULT_IMAGE_MODEL)
    raise ValueError(f"Unknown provider: {provider}")
```

- [ ] **Step 4: Add the `--provider` argparse flag and the guard logic in `main()`**

In `main()`:

1. Add the `--provider` argument alongside the existing flags:

   ```python
       parser.add_argument(
           "--provider",
           choices=["imagen", "gemini"],
           default="imagen",
           help="Image generation backend. 'imagen' (default) uses Imagen 4 "
                "fallback chain (Ultra → Standard → Fast). 'gemini' uses the "
                "legacy Gemini 3 Pro / 2.5 Flash Image path (kept for rollback).",
       )
   ```

2. After `args = parser.parse_args()` but BEFORE the existing `if args.list_jobs:` block, add the guard:

   ```python
       # Guard: Imagen does not support batch / sync-mode / resume / list-jobs.
       if args.provider == "imagen":
           batch_flag_used = (
               args.sync_mode or args.resume or args.list_jobs
               or args.batch_poll_interval != BATCH_POLL_INTERVAL_SECONDS
           )
           if batch_flag_used:
               print(
                   "❌ --provider imagen does not support batch/sync-mode/resume/"
                   "list-jobs (Imagen 4 has no Files-based Batch API). "
                   "Use --provider gemini for the legacy batch path."
               )
               return 1
           if args.model and args.model != DEFAULT_IMAGE_MODEL:
               print(
                   f"⚠️  --model {args.model} is ignored under --provider imagen "
                   "(Imagen picks its tier via fallback chain)."
               )
   ```

3. Replace the existing two lines that construct the generator (the `generator = GeminiImageGenerator(...)` line) with:

   ```python
       generator = build_generator(args.provider, config.GEMINI_API_KEY, args.model)
   ```

   And update the `print(f"Using model: {args.model}")` block to:

   ```python
       print(f"Using provider: {args.provider}")
       if args.provider == "gemini":
           print(f"Using model: {args.model}")
           if "gemini-3-pro-image" in args.model:
               print(f"Resolution: {COVER_IMAGE_SIZE} for covers, {IMAGE_SIZE} for chapters at {ASPECT_RATIO} aspect ratio")
           else:
               print(f"Aspect ratio: {ASPECT_RATIO} (resolution auto-determined by model)")
       else:
           print(f"Imagen aspect ratio: {IMAGEN_ASPECT_RATIO}; model chain: {IMAGEN_MODEL_CHAIN}")
   ```

4. **Block batch entry points for Imagen** inside `main()`. The script has `--sync-mode` default-False semantics: by *default* it tries the batch path. With Imagen this MUST go to sync. The cleanest fix: invert the default check by provider. Find the existing single-book `if args.sync_mode:` blocks (and the `--book-ids` and `--batch-all` blocks) and change every line that currently reads:

   ```python
           if args.sync_mode:
   ```

   to:

   ```python
           if args.sync_mode or args.provider == "imagen":
   ```

   This routes Imagen runs into the sync code path (`generate_book_cover`, `generate_chapter_illustrations_for_book`) which now supports both providers. Imagen never hits the batch entry points.

- [ ] **Step 5: Run the provider-selection tests, confirm they pass**

```bash
python -m pytest tests/test_illustrations.py::TestProviderSelection -v 2>&1 | tail -15
```

Expected: 7 passed.

- [ ] **Step 6: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add scripts/images/generate_illustrations.py tests/test_illustrations.py
git commit -m "$(cat <<'EOF'
Add --provider {imagen,gemini} flag (default imagen)

build_generator factory chooses the backend. main() routes Imagen runs
through the sync code path (the batch entry points are Gemini-only). When
batch/sync-mode/resume/list-jobs is requested with --provider imagen, exit
non-zero with a clear message. --model is ignored under Imagen with a
warning.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Skip reference-image loading when the generator doesn't support it

**Why:** the sync chapter loop currently loads the previous chapter's PNG from disk into `reference_image` unconditionally. For Imagen that's wasted disk I/O on every chapter. Tiny perf win, but mostly it removes confusing noise from logs and prevents accidental "loaded reference image" messages on the Imagen path.

**Files:**
- Modify: `scripts/images/generate_illustrations.py` — inside `generate_chapter_illustrations_for_book`, gate the reference-image load on `generator.supports_reference_image`.

- [ ] **Step 1: Modify the chapter loop**

In `generate_chapter_illustrations_for_book`, find the existing block (around line 1036):

```python
        # Try to load previous illustration from filesystem if this isn't the first chapter
        if chapter_num > 1 and reference_image is None:
```

Change the condition to:

```python
        # Try to load previous illustration from filesystem if this isn't the first chapter
        # (skip for backends that don't use reference images)
        if generator.supports_reference_image and chapter_num > 1 and reference_image is None:
```

Also change the very last line inside the success branch where we save the generated image for next-chapter reference:

```python
            # Save the generated image as reference for next chapter
            reference_image = image_data
```

to:

```python
            # Save the generated image as reference for next chapter (no-op for Imagen)
            if generator.supports_reference_image:
                reference_image = image_data
```

- [ ] **Step 2: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

Expected: same pass count.

- [ ] **Step 3: Commit**

```bash
git add scripts/images/generate_illustrations.py
git commit -m "$(cat <<'EOF'
Skip reference-image loading on backends that don't use them

The sync chapter loop now reads/sets reference_image only when
generator.supports_reference_image is True. Avoids confusing
'loaded reference image' log lines on the Imagen path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Update the script docstring + the `--help` examples

**Why:** the top-of-file docstring (lines 1-66) still talks exclusively about Gemini models and batch mode. After Task 11, the default behavior is Imagen sync. The docstring must match reality so anyone reading the file (or `--help`) knows the current entry point.

**Files:**
- Modify: `scripts/images/generate_illustrations.py` — replace the module docstring at lines 1-66.

- [ ] **Step 1: Rewrite the module docstring**

Replace the entire opening docstring block (the `"""..."""` from line 1 to line 66) with:

```python
#!/usr/bin/env python3
"""Batch generate book covers and chapter illustrations.

Default backend (--provider imagen):
    Imagen 4 fallback chain — imagen-4.0-ultra-generate-001 → imagen-4.0-generate-001
    → imagen-4.0-fast-generate-001. Each image attempts Ultra first and falls
    through to the next tier only on quota / rate-limit / 5xx errors. Content-policy
    and bad-prompt errors surface immediately. Aspect ratio "3:4". Cross-chapter
    character consistency comes from a per-book "character brief" cached under
    data/character_briefs/{book_id}.txt (auto-built on first use via gemini-2.5-flash).

Legacy backend (--provider gemini):
    Original Gemini 3 Pro Image / 2.5 Flash Image path. Supports reference-image
    character consistency and an async Batch API (50% cost reduction). Kept for
    rollback now that the Gemini image models are no longer available on the free
    tier. The Gemini batch helpers remain in this file but are dormant unless
    --provider gemini is set.

Usage:
    # Default (Imagen 4 sync, with fallback chain)
    python scripts/images/generate_illustrations.py --book-id 53
    python scripts/images/generate_illustrations.py --book-id 53 --with-chapters
    python scripts/images/generate_illustrations.py --book-id 53 --chapters-only --chapter-range 2-50
    python scripts/images/generate_illustrations.py --book-ids 53,54,55
    python scripts/images/generate_illustrations.py --batch-all

    # Rollback to Gemini (async batch is the default for Gemini)
    python scripts/images/generate_illustrations.py --book-id 53 --provider gemini
    python scripts/images/generate_illustrations.py --book-id 53 --provider gemini --sync-mode
    python scripts/images/generate_illustrations.py --book-id 53 --provider gemini --model gemini-2.5-flash-image
    python scripts/images/generate_illustrations.py --provider gemini --list-jobs
    python scripts/images/generate_illustrations.py --provider gemini --resume data/batch_jobs/book_47_*.json

    # Dry run
    python scripts/images/generate_illustrations.py --book-id 53 --dry-run

Notes:
    - --sync-mode / --resume / --list-jobs / non-default --batch-poll-interval require
      --provider gemini and will error out under --provider imagen.
    - --model is ignored (with a warning) under --provider imagen.
"""
```

- [ ] **Step 2: Confirm no regression**

```bash
python -m pytest tests/test_illustrations.py -v 2>&1 | tail -5
```

- [ ] **Step 3: Verify the `--help` output looks sane**

```bash
python scripts/images/generate_illustrations.py --help 2>&1 | head -40
```

Expected: see `--provider` listed; usage examples mention Imagen.

- [ ] **Step 4: Commit**

```bash
git add scripts/images/generate_illustrations.py
git commit -m "$(cat <<'EOF'
Rewrite module docstring to reflect Imagen-default behavior

Describes both providers, the fallback chain, the character-brief
consistency mechanism, and the flag combinations that work under each
provider.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Update `docs/ERD.md` image-generation section

**Files:**
- Modify: `docs/ERD.md` — replace the image-generation section (~lines 7320-8500 contain the existing description; we update the active content, leave historical work-log entries alone).

- [ ] **Step 1: Locate the section header**

```bash
grep -n "^##\|^###\|generate_gemini_illustrations\|Image Generation" docs/ERD.md | head -40
```

Find the section that currently describes the image-generation pipeline (likely `### Image Generation` or similar near line 7326).

- [ ] **Step 2: Update the section body**

In `docs/ERD.md`, find every reference to `generate_gemini_illustrations.py` inside the **forward-facing engineering reference** (NOT inside dated work-log entries). Replace with `generate_illustrations.py`. Then add a new subsection right after the current "Location:" line:

```markdown
**Backends:** the script supports two image-generation providers via `--provider`:

- **`imagen` (default)** — Imagen 4 fallback chain: `imagen-4.0-ultra-generate-001` →
  `imagen-4.0-generate-001` → `imagen-4.0-fast-generate-001`. Each image attempts Ultra
  first and falls through to the next tier only on quota / rate-limit / 5xx errors.
  Aspect ratio `3:4`. No reference-image support — character consistency comes from a
  per-book "character brief" (cached at `data/character_briefs/{book_id}.txt`,
  auto-built on first use via `gemini-2.5-flash`).
- **`gemini` (rollback)** — original Gemini 3 Pro Image / 2.5 Flash Image path. Kept
  for rollback now that the Gemini image models are no longer available on the free
  tier. Supports reference-image consistency and the async Batch API (50% cost
  reduction); these features remain available only under `--provider gemini`.

**Flag interactions** (Imagen has no Files-based Batch API):

| Flag | `--provider imagen` (default) | `--provider gemini` |
|------|------------------------------|---------------------|
| `--sync-mode` | Errors: not supported | Works as legacy |
| `--resume` | Errors: not supported | Works as legacy |
| `--list-jobs` | Errors: not supported | Works as legacy |
| `--batch-poll-interval` (non-default) | Errors: not supported | Works as legacy |
| `--model` | Ignored with a warning | Works as legacy |
```

Update the existing usage examples in the same section to show `--provider gemini` for any command that uses `--list-jobs`, `--resume`, `--sync-mode`, or `--batch-mode`.

- [ ] **Step 3: Commit**

```bash
git add docs/ERD.md
git commit -m "$(cat <<'EOF'
Update ERD: document --provider {imagen,gemini} and flag interactions

Describes the new Imagen 4 fallback chain as the active backend, the
character-brief consistency mechanism, and which flags work under each
provider. Historical work-log entries are left as-is.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Grep & update deploy / scripts docs for the old filename

**Files:**
- Modify: `deploy/README.md`, `deploy/setup-e2small.sh`, any `scripts/**/README.md` that reference `generate_gemini_illustrations.py` in active commands. WORK_LOG.md historical entries are NOT updated.

- [ ] **Step 1: Find all remaining references**

```bash
grep -rn "generate_gemini_illustrations" \
    /Users/pengyao/Documents/dev/summra \
    --include="*.md" --include="*.sh" --include="*.py" 2>/dev/null \
    | grep -v __pycache__ \
    | grep -v node_modules \
    | grep -v "/WORK_LOG.md" \
    | grep -v "/docs/superpowers/"
```

Expected: a small list. Each hit (except WORK_LOG.md and the spec/plan files we just wrote) needs updating.

- [ ] **Step 2: Edit each remaining file**

For each file from Step 1, replace `generate_gemini_illustrations.py` with `generate_illustrations.py`. If the same file also references `--sync-mode`, `--resume`, `--list-jobs`, or other batch flags as part of an active command, prepend `--provider gemini` to that command line.

- [ ] **Step 3: Verify no remaining active references**

```bash
grep -rn "generate_gemini_illustrations" \
    /Users/pengyao/Documents/dev/summra \
    --include="*.md" --include="*.sh" --include="*.py" 2>/dev/null \
    | grep -v __pycache__ \
    | grep -v node_modules \
    | grep -v "/WORK_LOG.md" \
    | grep -v "/docs/superpowers/"
```

Expected: empty output.

- [ ] **Step 4: Commit**

```bash
git add deploy/README.md deploy/setup-e2small.sh scripts/  # adjust to actual paths touched
git commit -m "$(cat <<'EOF'
Update deploy + scripts docs for renamed illustration script

References to scripts/images/generate_gemini_illustrations.py become
scripts/images/generate_illustrations.py. Where batch flags are used,
prefix the command with --provider gemini so the example continues to
work. Historical WORK_LOG entries are left intact.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Add the WORK_LOG entry

**Files:**
- Modify: `WORK_LOG.md` — add a new dated entry at the TOP of the file (preserving everything below).

- [ ] **Step 1: Determine the date and prepend the entry**

Use today's date (2026-05-30 at the time of this plan's writing; substitute the actual date at execution time).

Open `WORK_LOG.md` and insert this block at the top, immediately under the file's top-level heading (or as the first entry under whatever heading the work log uses for new entries):

```markdown
## 2026-05-30: Switch image generation from Gemini to Imagen 4 with provider abstraction

**Why:** `gemini-3-pro-image-preview` and `gemini-2.5-flash-image` are no longer available on the Gemini API free tier; the existing script could not run.

**What changed:**
- Renamed `scripts/images/generate_gemini_illustrations.py` → `scripts/images/generate_illustrations.py`. Same for the test file.
- Added `ImageGeneratorBase` abstract class. Existing Gemini logic refactored into `GeminiImageGenerator` (subclass, zero behavior change). New `ImagenImageGenerator` subclass added.
- New `--provider {imagen,gemini}` CLI flag, default `imagen`.
- Imagen path uses the fallback chain `imagen-4.0-ultra-generate-001` → `imagen-4.0-generate-001` → `imagen-4.0-fast-generate-001`. Per-image fallback, only on retryable errors (429, 500, 503, "quota", "rate limit", "unavailable", "resource_exhausted"). Non-retryable errors (content policy, INVALID_ARGUMENT, auth) surface immediately without retrying lower tiers.
- Aspect ratio for Imagen is `"3:4"` (closest portrait Imagen 4 supports; was `"2:3"` for Gemini). Existing covers/illustrations on disk are unchanged.
- Cross-chapter character consistency for Imagen: one-time `gemini-2.5-flash` text call per book extracts a "character brief" (art style, color palette, recurring characters, setting). Cached at `data/character_briefs/{book_id}.txt`. Brief is injected into every chapter prompt under a `=== VISUAL STYLE GUIDE ===` header. LLM failures fall back to an empty brief; chapters still generate.
- Gemini batch helpers (~600 lines: `create_batch_job`, `poll_batch_job`, `retrieve_batch_results`, `generate_chapter_illustrations_batch`, `generate_book_covers_batch`, `resume_batch_job`, batch state helpers, `list_pending_batch_jobs`) are kept in place with `⚠️ DORMANT` header comments. CLI flags `--sync-mode`, `--resume`, `--list-jobs`, and non-default `--batch-poll-interval` work only under `--provider gemini`; they error out cleanly under `--provider imagen`.
- The legacy `--model` flag is now Gemini-only; ignored with a warning under `--provider imagen`.

**How to roll back:**
```
python scripts/images/generate_illustrations.py --provider gemini ...
```
Behaves identically to the old script (subject to Gemini free-tier availability).

**Files:**
- `scripts/images/generate_illustrations.py` (renamed from `generate_gemini_illustrations.py`)
- `tests/test_illustrations.py` (renamed from `test_gemini_illustrations.py`)
- `tests/conftest.py` (patch path updated)
- `data/character_briefs/.gitignore` (new)
- `docs/ERD.md` (image-generation section updated)
- `docs/superpowers/specs/2026-05-30-imagen-fallback-design.md`
- `docs/superpowers/plans/2026-05-30-imagen-fallback-impl.md`
- `deploy/README.md`, `deploy/setup-e2small.sh` (path/flag updates)
```

- [ ] **Step 2: Commit**

```bash
git add WORK_LOG.md
git commit -m "$(cat <<'EOF'
WORK_LOG: document Imagen 4 backend + provider abstraction

Captures the why (free-tier loss), the what (rename, provider class
hierarchy, fallback chain, character-brief mechanism), and the rollback
path (--provider gemini).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Final full-suite test run + manual smoke prep

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass. If anything outside `tests/test_illustrations.py` fails, investigate before claiming done — the rename + signature changes may have rippled.

- [ ] **Step 2: Record the manual smoke procedure**

The plan does not run the smoke itself (it needs real API keys and visual judgment). Document the next steps for the operator at the end of WORK_LOG.md's new entry. Add this block to `WORK_LOG.md` under the "What changed" entry from Task 16:

```markdown
**Manual smoke (operator):**
1. Pick a small book with existing Gemini illustrations (for A/B comparison): `SMOKE_BOOK_ID=<id>`.
2. Cover: `python scripts/images/generate_illustrations.py --book-id $SMOKE_BOOK_ID`
3. First three chapters: `python scripts/images/generate_illustrations.py --book-id $SMOKE_BOOK_ID --chapters-only --chapter-range 1-3`
4. Compare new outputs in `frontend/static/illustrations/$SMOKE_BOOK_ID/` against the prior Gemini versions: look for aspect-ratio sanity, character consistency across chapters 1-3, no text artifacts.
5. Rollback dry-run: `python scripts/images/generate_illustrations.py --book-id $SMOKE_BOOK_ID --provider gemini --dry-run` — verify it exits cleanly and shows the Gemini prompt path.
```

- [ ] **Step 3: Commit the smoke procedure**

```bash
git add WORK_LOG.md
git commit -m "$(cat <<'EOF'
WORK_LOG: add manual smoke procedure for Imagen rollout

Operator runs the smoke (needs API keys + visual A/B) after merging.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done

After Task 17:
- The active image generation path is Imagen 4 with the Ultra → Standard → Fast fallback chain.
- Character consistency for chapters is preserved via cached per-book briefs.
- The Gemini code path is one flag (`--provider gemini`) away.
- Tests cover both providers, the fallback chain, retry-classification, the prompt builder's optional brief, the CLI guards, and the character-brief cache.
- Docs (`WORK_LOG.md`, `docs/ERD.md`, deploy READMEs, in-file docstring) match reality.
- Historical WORK_LOG entries are intentionally not rewritten.
