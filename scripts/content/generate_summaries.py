#!/usr/bin/env python3
"""
Summra - Book Summary Generation Script

This script processes book text files and generates three types of summaries
using Google's Gemini API:
1. Concise (500 words, no spoilers for fiction)
2. Medium (2000-3000 words)
3. Comprehensive (chapter-by-chapter summaries using bulk processing)

Processing Modes:
1. Async Batch Mode (default): Uses Gemini Batch API for 50% cost savings
   - All API calls submitted as one batch job
   - Target completion: ~1-4 hours (can take up to 24 hours)
   - Supports resumption if interrupted
2. Sync Mode (--sync): Real-time API calls with immediate results

Chapter summaries are generated using bulk processing, where consecutive chapters
are processed in a single API call for improved efficiency and context.

Book Metadata Extraction:
- Title and author are extracted from the text file itself (supports multiple formats)
- For Project Gutenberg books: cover images can be automatically downloaded
- For non-Gutenberg books: metadata is extracted from simple "Title\n\nby Author" format
- You can also manually specify title/author via command-line arguments

Usage:
    # Generate all summaries for a book (async batch mode, 50% cost savings)
    python generate_summaries.py <book_file.txt>

    # Use synchronous mode for immediate results
    python generate_summaries.py <book_file.txt> --sync

    # Preview chapter detection without making API calls
    python generate_summaries.py <book_file.txt> --dry-run

    # Parse book and store to database without LLM calls
    python generate_summaries.py <book_file.txt> --parse-only

    # Test mode: generate only concise + medium + first 3 chapters
    python generate_summaries.py <book_file.txt> --partial-run

    # Regenerate specific consecutive chapters (comma-separated)
    python generate_summaries.py <book_file.txt> --regenerate-chapters "1,2,3"

    # Regenerate only concise and medium overall summaries
    python generate_summaries.py <book_file.txt> --regenerate-overall

    # Process all .txt files in a directory
    python generate_summaries.py --batch <directory>

    # List pending batch jobs
    python generate_summaries.py --list-jobs

    # Resume an interrupted batch job
    python generate_summaries.py --resume data/batch_jobs/book_99_1234567890.json

Note: --regenerate-chapters requires consecutive chapter numbers (e.g., "1,2,3" works, "1,3,5" fails)
"""


def normalize_book_title(title):
    """
    Normalize book title to follow consistent formatting rules:
    1. Title Case (capitalize first letter of each word, except articles/prepositions)
    2. Truncate at first colon (:) or semicolon (;)

    Examples:
        "jane eyre: an autobiography" -> "Jane Eyre"
        "MOBY DICK; Or, The Whale" -> "Moby Dick"
        "the great gatsby" -> "The Great Gatsby"

    Args:
        title: Raw book title string

    Returns:
        Normalized title string
    """
    if not title or not title.strip():
        return title

    # Step 1: Truncate at first colon or semicolon
    # Find first occurrence of : or ;
    colon_pos = title.find(':')
    semicolon_pos = title.find(';')

    # Determine which comes first
    if colon_pos != -1 and semicolon_pos != -1:
        truncate_pos = min(colon_pos, semicolon_pos)
    elif colon_pos != -1:
        truncate_pos = colon_pos
    elif semicolon_pos != -1:
        truncate_pos = semicolon_pos
    else:
        truncate_pos = len(title)

    # Truncate title
    title = title[:truncate_pos].strip()

    # Step 2: Apply Title Case
    # Words that should remain lowercase (unless first word)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from',
        'in', 'into', 'nor', 'of', 'on', 'or', 'so', 'the', 'to',
        'up', 'with', 'yet'
    }

    words = title.split()
    result = []

    for i, word in enumerate(words):
        # Handle hyphenated words - capitalize each part
        if '-' in word:
            parts = word.split('-')
            capitalized_parts = []
            for j, part in enumerate(parts):
                # First part or parts that aren't lowercase words
                if j == 0 or part.lower() not in lowercase_words:
                    capitalized_parts.append(part.capitalize())
                else:
                    capitalized_parts.append(part.lower())
            result.append('-'.join(capitalized_parts))
        # Always capitalize first word
        elif i == 0:
            result.append(word.capitalize())
        # Keep lowercase words as lowercase (unless after colon/period)
        elif word.lower() in lowercase_words:
            result.append(word.lower())
        # Otherwise capitalize
        else:
            result.append(word.capitalize())

    return ' '.join(result)


def fix_roman_numerals_in_text(text):
    """Convert all title-cased Roman numerals in text to uppercase.

    Delegates to scripts.lib.text — see there for the full docstring.
    """
    from scripts.lib.text import fix_roman_numerals_in_text as _fix
    return _fix(text)


import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import re
import requests
from urllib.parse import quote

from google import genai
from dotenv import load_dotenv

from backend import config
from backend import models
from scripts.lib import text as text_lib
try:
    from scripts.categorization import categorization
except ModuleNotFoundError:
    categorization = None


# ============================================================================
# CONSTANTS - moved to scripts/content/constants.py; re-exported here so
# existing `from scripts.content.generate_summaries import X` call sites
# (30+ across scripts/ and tests/) keep working unchanged.
# ============================================================================
from scripts.content.constants import (
    SummaryConstants,
    APIConstants,
    ContentThresholds,
    ChapterDetectionConstants,
    DisplayConstants,
    BATCH_POLL_INTERVAL_SECONDS,
    BATCH_MAX_WAIT_HOURS,
    BATCH_JOBS_DIR,
)
from scripts.content.rate_limiter import RateLimiter
from scripts.content.batch_state import (
    save_batch_job_state,
    load_batch_job_state,
    update_batch_job_state,
    list_pending_batch_jobs,
)


class SummaryGenerator:
    """Generate book summaries using Gemini API"""

    # Use constants from APIConstants class
    MAX_CHARS_PER_CALL = APIConstants.MAX_CHARS_PER_CALL
    MAX_TOKENS_PER_CALL = APIConstants.MAX_TOKENS_PER_CALL
    LARGE_CALL_THRESHOLD = APIConstants.LARGE_CALL_THRESHOLD_TOKENS
    LARGE_CALL_WAIT_SECONDS = APIConstants.LARGE_CALL_WAIT_SECONDS

    def __init__(self, api_key: str):
        # Initialize Gemini client with API key
        self.client = genai.Client(api_key=api_key)
        self.db = models.Database()
        self.rate_limiter = RateLimiter(
            config.MAX_REQUESTS_PER_MINUTE,
            config.MAX_TOKENS_PER_MINUTE
        )
        self.last_large_call_time = None  # Track last large API call

    @staticmethod
    def _is_retriable_error(error_message: str) -> bool:
        """Predicate matching the same retriable signatures all 4 summary call
        sites used: 503 / overloaded / UNAVAILABLE / 429 / RESOURCE_EXHAUSTED."""
        msg = error_message
        return (
            '503' in msg
            or 'overloaded' in msg.lower()
            or 'UNAVAILABLE' in msg
            or '429' in msg
            or 'RESOURCE_EXHAUSTED' in msg
        )

    @staticmethod
    def _retry_wait_seconds_from_error(error_message: str) -> int:
        """Honour any 'Please retry in Ns' / 'Please retry in Nms' suggestion
        in a 429/RESOURCE_EXHAUSTED message; otherwise fall back to defaults."""
        if '429' in error_message or 'RESOURCE_EXHAUSTED' in error_message:
            m = re.search(r'Please retry in ([\d.]+)([ms]?s?)', error_message)
            if m:
                value = float(m.group(1))
                unit = m.group(2)
                return int(value / 1000) + 1 if unit == 'ms' else int(value) + 1
            return APIConstants.RATE_LIMIT_RETRY_WAIT_SECONDS
        return APIConstants.DEFAULT_RETRY_WAIT_SECONDS

    def _generate_with_retries(self, model_name: str, contents, *, gen_config=None,
                               log_label: str = "API call"):
        """Single-model retry loop. Returns the SDK response on success; raises
        the last exception on terminal failure (non-retriable or retries exhausted).
        """
        max_retries = APIConstants.MAX_RETRIES
        for attempt in range(max_retries + 1):
            try:
                if gen_config is not None:
                    return self.client.models.generate_content(
                        model=model_name, contents=contents, config=gen_config
                    )
                return self.client.models.generate_content(
                    model=model_name, contents=contents
                )
            except Exception as e:
                error_message = str(e)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {log_label} failed on {model_name}: {type(e).__name__}")
                if '429' in error_message:
                    print(f"  → Error type: Rate limit exceeded (429)")
                elif 'RESOURCE_EXHAUSTED' in error_message:
                    print(f"  → Error type: Resource exhausted")
                elif '503' in error_message:
                    print(f"  → Error type: Service unavailable (503)")
                else:
                    print(f"  → Error type: {error_message[:100]}")

                if self._is_retriable_error(error_message) and attempt < max_retries:
                    wait_time = self._retry_wait_seconds_from_error(error_message)
                    print(f"  ⏳ Retrying in {wait_time}s on {model_name} (attempt {attempt + 2}/{max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                if attempt > 0:
                    print(f"  ❌ Max retries exceeded on {model_name}")
                raise

    def _llm_log_dir(self) -> Path:
        """Directory where LLM call audit logs are written. Overridable in
        tests via monkeypatch."""
        project_root = Path(__file__).resolve().parents[2]
        return project_root / "data" / "llm_responses"

    def _serialize_contents(self, contents) -> object:
        """Make `contents` faithfully inspectable in the audit log.
        Strings pass through; lists/dicts (multimodal) are kept as-is so
        json.dump renders nested structure; other objects fall back to repr."""
        if isinstance(contents, (str, list, dict, int, float, bool)) or contents is None:
            return contents
        return repr(contents)

    def _serialize_gen_config(self, gen_config) -> object:
        """Render gen_config for the audit log. dict passes through; SDK
        config objects (google.genai.types.GenerateContentConfig) are
        converted via model_dump() when available, else repr()."""
        return self._serialize_sdk_obj(gen_config)

    def _serialize_sdk_obj(self, obj) -> object:
        """Best-effort: convert a google-genai SDK pydantic object to a dict
        for json.dump. Pass through primitives and None."""
        if obj is None or isinstance(obj, (str, dict, list, int, float, bool)):
            return obj
        dump = getattr(obj, "model_dump", None)
        if callable(dump):
            try:
                return dump()
            except Exception:
                pass
        return repr(obj)

    def _persist_raw_llm_response(self, response, *, used_model: str, contents,
                                  log_label: str, gen_config=None,
                                  config_key: str = None) -> None:
        """Write a successful Gemini call to data/llm_responses/. Captures
        input (prompt + gen_config + config_key) and output (raw text +
        finish_reason + safety + token usage) so the call can be audited
        and replayed without re-spending on the API.

        Best-effort: any persistence failure is logged but does not raise."""
        try:
            out_dir = self._llm_log_dir()
            out_dir.mkdir(parents=True, exist_ok=True)

            slug = re.sub(r'[^\w-]+', '_', log_label).strip('_') or "llm"
            ts = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
            out_path = out_dir / f"{ts}_{slug}.json"

            finish_reason = None
            safety_ratings = None
            if getattr(response, "candidates", None):
                cand = response.candidates[0]
                finish_reason = getattr(cand, "finish_reason", None)
                safety_ratings = getattr(cand, "safety_ratings", None)

            usage = getattr(response, "usage_metadata", None)

            payload = {
                "timestamp": datetime.now().isoformat(),
                "status": "ok",
                "log_label": log_label,
                "config_key": config_key,
                "used_model": used_model,
                "gen_config": self._serialize_gen_config(gen_config),
                "prompt": self._serialize_contents(contents),
                "raw_text": getattr(response, "text", None),
                "raw_len_chars": len(getattr(response, "text", "") or ""),
                "raw_len_words": len((getattr(response, "text", "") or "").split()),
                "finish_reason": str(finish_reason) if finish_reason is not None else None,
                "safety_ratings": self._serialize_sdk_obj(safety_ratings),
                "usage_metadata": self._serialize_sdk_obj(usage),
            }
            out_path.write_text(json.dumps(payload, indent=2, default=str))
        except Exception as e:
            print(f"  ⚠ Failed to persist raw LLM response: {e}")

    def _persist_raw_llm_error(self, error, *, attempted_models, contents,
                               log_label: str, gen_config=None,
                               config_key: str = None) -> None:
        """Write a failed Gemini call to data/llm_responses/. Captures the
        same input metadata as the success path plus exception details and
        the list of models tried before giving up — so failures are auditable
        and replayable."""
        try:
            out_dir = self._llm_log_dir()
            out_dir.mkdir(parents=True, exist_ok=True)

            slug = re.sub(r'[^\w-]+', '_', log_label).strip('_') or "llm"
            ts = datetime.now().strftime("%Y%m%dT%H%M%S_%f")
            out_path = out_dir / f"{ts}_{slug}_ERROR.json"

            payload = {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "log_label": log_label,
                "config_key": config_key,
                "attempted_models": list(attempted_models),
                "gen_config": self._serialize_gen_config(gen_config),
                "prompt": self._serialize_contents(contents),
                "error_class": type(error).__name__,
                "error_message": str(error),
            }
            out_path.write_text(json.dumps(payload, indent=2, default=str))
        except Exception as e:
            print(f"  ⚠ Failed to persist LLM error: {e}")

    def _generate_content_with_fallback(self, config_key: str, contents, *,
                                        gen_config=None, log_label: str = "API call"):
        """Try the primary model for `config_key`, then each fallback in order,
        on retriable failure. Non-retriable errors propagate immediately so we
        don't waste fallback budget on prompt/auth bugs.

        Every call — success or failure — is persisted to
        data/llm_responses/ for audit and replay."""
        cfg = config.SUMMARY_CONFIGS[config_key]
        chain = [cfg['model']] + list(cfg.get('model_fallbacks', []))
        attempted = []
        last_error = None
        for idx, model_name in enumerate(chain):
            attempted.append(model_name)
            try:
                response = self._generate_with_retries(
                    model_name, contents, gen_config=gen_config, log_label=log_label
                )
                if idx > 0:
                    print(f"  ✓ Succeeded on fallback model: {model_name}")
                self._persist_raw_llm_response(
                    response, used_model=model_name, contents=contents,
                    log_label=log_label, gen_config=gen_config,
                    config_key=config_key,
                )
                return response, model_name
            except Exception as e:
                last_error = e
                if not self._is_retriable_error(str(e)):
                    self._persist_raw_llm_error(
                        e, attempted_models=attempted, contents=contents,
                        log_label=log_label, gen_config=gen_config,
                        config_key=config_key,
                    )
                    raise
                if idx < len(chain) - 1:
                    next_model = chain[idx + 1]
                    print(f"  ⤳ Falling back from {model_name} to {next_model}")
        self._persist_raw_llm_error(
            last_error, attempted_models=attempted, contents=contents,
            log_label=log_label, gen_config=gen_config, config_key=config_key,
        )
        raise last_error

    def submit_batch_job(self, requests: List[Dict], model_name: str, display_name: str) -> str:
        """
        Submit a batch job to Gemini Batch API.

        Args:
            requests: List of request dictionaries with 'contents' key
            model_name: Model to use (e.g., 'gemini-2.5-flash')
            display_name: Display name for the batch job

        Returns:
            Batch job name for polling
        """
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Submitting batch job: {display_name}")
        print(f"  → {len(requests)} request(s) at 50% cost savings")

        batch_job = self.client.batches.create(
            model=model_name,
            src=requests,
            config={'display_name': display_name}
        )

        print(f"  ✓ Batch job submitted: {batch_job.name}")
        print(f"  → Target completion: ~24 hours (usually much faster)")

        return batch_job.name

    def poll_batch_job(self, job_name: str, poll_interval_seconds: int = 30) -> Dict:
        """
        Poll a batch job until completion.

        Args:
            job_name: Batch job name from submit_batch_job()
            poll_interval_seconds: How often to poll (default 30s)

        Returns:
            Completed batch job object
        """
        completed_states = {'JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED',
                           'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED'}

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Polling batch job: {job_name}")

        batch_job = self.client.batches.get(name=job_name)
        start_time = time.time()

        while batch_job.state.name not in completed_states:
            elapsed = time.time() - start_time
            elapsed_str = time.strftime('%H:%M:%S', time.gmtime(elapsed))
            print(f"  [{elapsed_str}] State: {batch_job.state.name} - waiting {poll_interval_seconds}s...")
            time.sleep(poll_interval_seconds)
            batch_job = self.client.batches.get(name=job_name)

        total_time = time.time() - start_time
        total_time_str = time.strftime('%H:%M:%S', time.gmtime(total_time))
        print(f"  ✓ Job completed in {total_time_str}: {batch_job.state.name}")

        return batch_job

    def retrieve_batch_results(self, batch_job: Dict) -> List[Dict]:
        """
        Retrieve results from a completed batch job.

        Args:
            batch_job: Completed batch job object from poll_batch_job()

        Returns:
            List of responses (text or error for each request)
        """
        if batch_job.state.name != 'JOB_STATE_SUCCEEDED':
            raise ValueError(f"Batch job failed: {batch_job.error if hasattr(batch_job, 'error') else 'Unknown error'}")

        results = []

        # Check for inline responses (for small batches)
        if batch_job.dest and batch_job.dest.inlined_responses:
            for inline_response in batch_job.dest.inlined_responses:
                if inline_response.response:
                    results.append({'text': inline_response.response.text})
                elif inline_response.error:
                    results.append({'error': str(inline_response.error)})

        # Check for file-based results (for larger batches)
        elif batch_job.dest and batch_job.dest.file_name:
            result_file_name = batch_job.dest.file_name
            file_content = self.client.files.download(file=result_file_name)

            # Parse JSONL results
            for line in file_content.decode('utf-8').strip().split('\n'):
                result_json = json.loads(line)
                if 'response' in result_json and result_json['response']:
                    text = result_json['response'].get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    results.append({'text': text})
                elif 'error' in result_json:
                    results.append({'error': str(result_json['error'])})

        print(f"  ✓ Retrieved {len(results)} result(s)")
        return results

    def build_batch_request(self, prompt: str) -> Dict:
        """
        Build a batch API request object from a prompt string.

        Args:
            prompt: The prompt text

        Returns:
            Dictionary in Gemini Batch API request format
        """
        return {
            'contents': [{
                'parts': [{'text': prompt}],
                'role': 'user'
            }]
        }

    def wait_if_needed_for_large_call(self, estimated_tokens: int):
        """
        Wait if a large API call was recently made to avoid rate limits.

        Args:
            estimated_tokens: Estimated tokens for the upcoming call
        """
        if estimated_tokens < self.LARGE_CALL_THRESHOLD:
            return  # Small call, no wait needed

        if self.last_large_call_time is None:
            # First large call, just record the time
            self.last_large_call_time = time.time()
            return

        # Calculate time since last large call
        elapsed = time.time() - self.last_large_call_time
        wait_needed = self.LARGE_CALL_WAIT_SECONDS - elapsed

        if wait_needed > 0:
            print(f"\n⏱️  Large API call detected ({estimated_tokens:,} tokens)")
            print(f"   Waiting {wait_needed:.1f}s to avoid rate limits...")
            time.sleep(wait_needed)

        # Update last large call time
        self.last_large_call_time = time.time()

    def clean_llm_response(self, text: str) -> str:
        """
        Remove common LLM preamble phrases and clean up the response.
        Removes phrases like "Of course. Here is..." and leading whitespace.
        """
        # Common preamble patterns to remove
        preamble_patterns = [
            r'^Of course[.!]?\s*',
            r'^Certainly[.!]?\s*',
            r'^Sure[.!]?\s*',
            r'^Here is\s+',
            r'^Here\'s\s+',
            r"^Here is a.*?summary.*?[:\n]",
            r"^Here's a.*?summary.*?[:\n]",
            r"^I'll provide.*?[:\n]",
            r"^I will provide.*?[:\n]",
            r"^This is.*?summary.*?[:\n]",
            r"^a\s+(comprehensive|detailed|complete|thorough)\s+summary\s+and\s+analysis\s+of.*?[:\n]",
        ]

        cleaned = text
        for pattern in preamble_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)

        # Strip leading/trailing whitespace and newlines
        cleaned = cleaned.strip()

        # Remove leading asterisks and separator lines
        cleaned = re.sub(r'^\*+\s*\n*', '', cleaned)

        # Remove excessive leading newlines (keep max 1)
        cleaned = re.sub(r'^\n+', '', cleaned)

        return cleaned

    def parse_combined_summaries_response(self, response_text: str, title: str, author: str) -> Dict:
        """
        Parse the combined summaries response from the API.
        Extracts about_text, concise_summary, medium_summary, and relevance_now.

        Args:
            response_text: The raw response text from the API
            title: Book title (for logging)
            author: Book author (for logging)

        Returns:
            Dictionary with parsed sections
        """
        # Extract each section using regex
        about_text = ""
        concise_summary = ""
        medium_summary = ""
        relevance_now = ""

        # Section terminator: start-of-line "### " (exactly three #'s, NOT ####),
        # or end of string. The negative lookahead `(?!#)` prevents matching
        # `####` (h4) subheadings the model uses inside the medium summary
        # (e.g. "#### Part I: ..."), which previously caused the section
        # capture to collapse to empty.
        section_terminator = r'(?=^###(?!#)\s|\Z)'
        flags = re.DOTALL | re.IGNORECASE | re.MULTILINE

        # About the Book (75-100 words)
        about_match = re.search(r'### ABOUT THE BOOK.*?\n(.*?)' + section_terminator, response_text, flags)
        if about_match:
            about_text = about_match.group(1).strip()
            about_text = re.sub(r'^\[.*?\]', '', about_text).strip()  # Remove template text

        # Concise Summary (500 words)
        concise_match = re.search(r'### CONCISE SUMMARY.*?\n(.*?)' + section_terminator, response_text, flags)
        if concise_match:
            concise_summary = concise_match.group(1).strip()
            concise_summary = re.sub(r'^\[.*?\]', '', concise_summary).strip()

        # Medium Summary (2000-3000 words)
        medium_match = re.search(r'### MEDIUM SUMMARY.*?\n(.*?)' + section_terminator, response_text, flags)
        if medium_match:
            medium_summary = medium_match.group(1).strip()
            medium_summary = re.sub(r'^\[.*?\]', '', medium_summary).strip()

        # Relevance Now (75-100 words)
        relevance_match = re.search(r'### RELEVANCE NOW.*?\n(.*?)' + section_terminator, response_text, flags)
        if relevance_match:
            relevance_now = relevance_match.group(1).strip()
            relevance_now = re.sub(r'^\[.*?\]', '', relevance_now).strip()

        # Calculate word counts
        about_words = len(about_text.split()) if about_text else 0
        concise_words = len(concise_summary.split())
        medium_words = len(medium_summary.split())
        relevance_words = len(relevance_now.split()) if relevance_now else 0
        total_words = about_words + concise_words + medium_words + relevance_words

        print(f"  ← Output: {total_words:,} words total")
        print(f"     About: {about_words:,} words")
        print(f"     Concise: {concise_words:,} words")
        print(f"     Medium: {medium_words:,} words")
        print(f"     Relevance: {relevance_words:,} words")

        # Return all parsed data as a dictionary
        return {
            'about_text': about_text,
            'concise_summary': concise_summary,
            'medium_summary': medium_summary,
            'relevance_now': relevance_now
        }

    def generate_combined_summaries(self, text: str, title: str, author: str, dry_run: bool = False, return_prompt_only: bool = False) -> Dict | str:
        """
        Generate summaries and metadata in a single API call.
        Returns dictionary with: about_text, concise_summary, medium_summary,
        relevance_now, author_country, similar_books, other_books_by_author

        Note: This method does NOT include book content in the prompt - it relies on
        the LLM's training data knowledge of classic books.
        """
        model_name = config.SUMMARY_CONFIGS['combined']['model']

        # Estimate tokens for prompt only (no book content)
        estimated_tokens = 500 + 3000  # prompt + output

        prompt = f"""Analyze "{title}" by {author} and provide the following information. Follow the format exactly with each section clearly marked:

### ABOUT THE BOOK ({SummaryConstants.ABOUT_MIN_WORDS}-{SummaryConstants.ABOUT_MAX_WORDS} words)
[Generate a short, engaging summary for the "About the Book" section - {SummaryConstants.ABOUT_MIN_WORDS}-{SummaryConstants.ABOUT_MAX_WORDS} words]

This should be concise but compelling, suitable for a book overview page. **ABSOLUTELY NO SPOILERS** - do not reveal plot twists, endings, character fates, or major reveals. Focus only on the premise, themes, and setting.

### CONCISE SUMMARY ({SummaryConstants.CONCISE_TARGET_WORDS} words)
[Generate a concise {SummaryConstants.CONCISE_TARGET_WORDS}-word summary here]

Focus on the main theme, setting, and central conflict. For fiction, avoid spoilers (no plot twists, endings, or major reveals). For non-fiction, cover main arguments and key takeaways. Write in an engaging, accessible style.

### MEDIUM SUMMARY ({SummaryConstants.MEDIUM_MIN_WORDS}-{SummaryConstants.MEDIUM_MAX_WORDS} words)
[Generate a comprehensive {SummaryConstants.MEDIUM_MIN_WORDS}-{SummaryConstants.MEDIUM_MAX_WORDS} word summary here]

Cover all major plot points, themes, and character developments in chronological order. Discuss the author's writing style and analyze major themes. Spoilers are acceptable. For non-fiction, cover all main arguments, evidence, and conclusions.

### RELEVANCE NOW ({SummaryConstants.RELEVANCE_MIN_WORDS}-{SummaryConstants.RELEVANCE_MAX_WORDS} words)
[Explain why this book is relevant to modern audiences - {SummaryConstants.RELEVANCE_MIN_WORDS}-{SummaryConstants.RELEVANCE_MAX_WORDS} words]

Focus on contemporary themes, timeless insights, or how it speaks to current issues."""

        # Return prompt only for batch mode
        if return_prompt_only:
            return prompt

        if dry_run:
            print(f"\n[DRY RUN] Would generate combined summaries using {model_name}")
            print(f"[DRY RUN] Prompt ({len(prompt)} chars):")
            print("-" * DisplayConstants.SEPARATOR_WIDTH)
            print(prompt[:DisplayConstants.MAX_PROMPT_PREVIEW_CHARS] + f"\n... [truncated, {len(prompt) - DisplayConstants.MAX_PROMPT_PREVIEW_CHARS} chars omitted]" if len(prompt) > DisplayConstants.MAX_PROMPT_PREVIEW_CHARS else prompt)
            print("-" * DisplayConstants.SEPARATOR_WIDTH)
            return {
                'about_text': f'[DRY RUN] About the Book ({SummaryConstants.ABOUT_MIN_WORDS}-{SummaryConstants.ABOUT_MAX_WORDS} words): This would contain a concise, engaging summary suitable for the book overview page with absolutely no spoilers.',
                'concise_summary': f'[DRY RUN] Concise summary ({SummaryConstants.CONCISE_TARGET_WORDS} words): This would contain the spoiler-free summary with main themes and central conflict.',
                'medium_summary': f'[DRY RUN] Medium summary ({SummaryConstants.MEDIUM_MIN_WORDS}-{SummaryConstants.MEDIUM_MAX_WORDS} words): This would contain the comprehensive analysis with all major plot points and themes.',
                'relevance_now': f'[DRY RUN] Relevance Now ({SummaryConstants.RELEVANCE_MIN_WORDS}-{SummaryConstants.RELEVANCE_MAX_WORDS} words): This would explain why the book is relevant to modern audiences.'
            }

        # Wait if needed for large API calls
        self.wait_if_needed_for_large_call(estimated_tokens)
        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input word count
        input_words = len(prompt.split())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating combined summaries using {model_name} (fallback chain enabled)...")
        print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

        response, used_model = self._generate_content_with_fallback(
            'combined', prompt, log_label="combined-summary API call"
        )
        result = self.clean_llm_response(response.text)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ API call successful on {used_model}")

        # Parse the response using the shared parsing method
        return self.parse_combined_summaries_response(result, title, author)

    def read_book(self, file_path: Path) -> str:
        """Read book text from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()

    def extract_metadata(self, text: str, filename: str) -> Tuple[str, str]:
        """
        Extract title and author from book text
        Supports multiple formats:
        1. Simple format (title on first line, "by Author" on line 3)
        2. Project Gutenberg format ("Title:" and "Author:" labels)
        3. Fallback to filename if not found

        Returns (title, author)
        """
        lines = text.split('\n')[:50]  # Check first 50 lines

        title = None
        author = None

        # First try simple format: title on line 1, "by Author" on line 3
        if len(lines) >= 3:
            # Check if line 3 starts with "by" (common pattern)
            line_3 = lines[2].strip()
            if line_3.lower().startswith('by '):
                potential_title = lines[0].strip()
                potential_author = line_3[3:].strip()  # Remove "by " prefix

                # Validate: title and author should be non-empty and reasonable length
                if potential_title and potential_author and len(potential_title) > 0 and len(potential_author) > 0:
                    title = potential_title
                    author = potential_author

        # If simple format didn't work, try Project Gutenberg format
        if not title or not author:
            for line in lines:
                line = line.strip()
                if line.startswith('Title:'):
                    title = line.replace('Title:', '').strip()
                elif line.startswith('Author:'):
                    author = line.replace('Author:', '').strip()

        # Fallback to filename if not found
        if not title:
            title = filename.replace('.txt', '').replace('_', ' ').title()
        if not author:
            author = "Unknown"

        # Normalize title: Title Case and truncate at colon/semicolon
        title = normalize_book_title(title)

        return title, author

    def extract_gutenberg_id(self, text: str) -> int:
        """
        Extract Project Gutenberg ID from the book text header
        Returns Gutenberg ID or None
        """
        lines = text.split('\n')[:100]  # Check first 100 lines

        for line in lines:
            line = line.strip()
            # Look for patterns like "Release Date: ... [EBook #11]" or "eBook #11"
            # Case-insensitive search for both "EBook" and "eBook"
            if 'ebook' in line.lower() and '#' in line:
                match = re.search(r'#(\d+)', line)
                if match:
                    return int(match.group(1))

        return None

    def get_gutenberg_cover_url(self, gutenberg_id: int) -> str:
        """
        Get the cover image URL for a Project Gutenberg book
        Returns cover image URL or None
        """
        # Try multiple cover image formats
        formats = [
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.medium.jpg",
            f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.cover.small.jpg",
            f"https://www.gutenberg.org/files/{gutenberg_id}/{gutenberg_id}-h/images/cover.jpg",
        ]

        for url in formats:
            try:
                response = requests.head(url, timeout=5)
                if response.status_code == 200:
                    print(f"Found cover image: {url}")
                    return url
            except Exception:
                continue

        return None

    def download_gutenberg_cover(self, gutenberg_id: int, dry_run: bool = False) -> str:
        """
        Download and save the cover image for a Project Gutenberg book
        Returns local file path relative to static directory, or None if download fails

        Example return: 'covers/pg11.jpg' (relative to frontend/static/)
        """
        # Get the cover image URL
        cover_url = self.get_gutenberg_cover_url(gutenberg_id)

        if not cover_url:
            print(f"No cover image found for Gutenberg ID {gutenberg_id}")
            return None

        if dry_run:
            print(f"[DRY RUN] Would download cover image from: {cover_url}")
            return f"covers/pg{gutenberg_id}.jpg"

        try:
            # Create covers directory if it doesn't exist
            config.COVERS_DIR.mkdir(parents=True, exist_ok=True)

            # Determine file extension from URL
            file_ext = '.jpg'  # Default to jpg
            if cover_url.endswith('.png'):
                file_ext = '.png'
            elif cover_url.endswith('.gif'):
                file_ext = '.gif'

            # Create local filename
            local_filename = f"pg{gutenberg_id}{file_ext}"
            local_path = config.COVERS_DIR / local_filename

            # Check if image already exists
            if local_path.exists():
                print(f"Cover image already exists: {local_path}")
                # Return path relative to static directory
                return f"covers/{local_filename}"

            # Download the image
            print(f"Downloading cover image from: {cover_url}")
            response = requests.get(cover_url, timeout=10)
            response.raise_for_status()

            # Save the image
            with open(local_path, 'wb') as f:
                f.write(response.content)

            print(f"✓ Saved cover image to: {local_path}")

            # Return path relative to static directory (for serving via web)
            return f"covers/{local_filename}"

        except Exception as e:
            print(f"Error downloading cover image: {e}")
            return None

    def process_cover_image(self, gutenberg_id: int, book_id: int, dry_run: bool = False) -> str:
        """
        Process cover image: rename from pg{gutenberg_id} to {book_id} and create WebP version

        Args:
            gutenberg_id: Project Gutenberg ID
            book_id: Database book ID
            dry_run: If True, only simulate the operation

        Returns:
            Updated cover path relative to static directory (e.g., 'covers/81.jpg')
        """
        if dry_run:
            print(f"[DRY RUN] Would process cover: pg{gutenberg_id}.jpg -> {book_id}.jpg and create WebP")
            return f"covers/{book_id}.jpg"

        try:
            # Find the original cover file
            covers_dir = config.COVERS_DIR
            original_files = list(covers_dir.glob(f"pg{gutenberg_id}.*"))

            if not original_files:
                print(f"Warning: No cover file found for pg{gutenberg_id}")
                return None

            original_file = original_files[0]
            file_ext = original_file.suffix  # .jpg, .png, etc.

            # New filenames
            new_jpg_path = covers_dir / f"{book_id}.jpg"
            new_webp_path = covers_dir / f"{book_id}.webp"

            # Rename the original file
            print(f"Renaming cover: {original_file.name} -> {book_id}{file_ext}")
            original_file.rename(new_jpg_path)

            # Create optimized WebP version using cwebp
            print(f"Creating optimized WebP version...")
            import subprocess
            result = subprocess.run(
                ['cwebp', '-q', '85', str(new_jpg_path), '-o', str(new_webp_path)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                jpg_size = new_jpg_path.stat().st_size / 1024
                webp_size = new_webp_path.stat().st_size / 1024
                savings = ((jpg_size - webp_size) / jpg_size) * 100
                print(f"✓ Created {book_id}.webp ({webp_size:.1f} KB, {savings:.1f}% smaller than JPG)")
            else:
                print(f"Warning: Failed to create WebP version: {result.stderr}")

            return f"covers/{book_id}.jpg"

        except Exception as e:
            print(f"Error processing cover image: {e}")
            return f"covers/pg{gutenberg_id}.jpg"  # Fall back to original naming

    def roman_to_int(self, s: str) -> int:
        """Convert Roman numeral to integer"""
        if not s:
            return 0

        roman_map = {
            'I': 1, 'V': 5, 'X': 10, 'L': 50,
            'C': 100, 'D': 500, 'M': 1000
        }

        s = s.upper()
        result = 0
        prev_value = 0

        for char in reversed(s):
            value = roman_map.get(char, 0)
            if value < prev_value:
                result -= value
            else:
                result += value
            prev_value = value

        return result

    def word_to_int(self, s: str) -> int:
        """Convert spelled-out number to integer (e.g., 'ONE' -> 1, 'FIRST' -> 1, 'First' -> 1, 'TWENTY-TWO' -> 22)"""
        # Map for cardinal and ordinal numbers (uppercase and title case)
        word_map = {
            'ONE': 1, 'FIRST': 1, 'TWO': 2, 'SECOND': 2, 'THREE': 3, 'THIRD': 3,
            'FOUR': 4, 'FOURTH': 4, 'FIVE': 5, 'FIFTH': 5,
            'SIX': 6, 'SIXTH': 6, 'SEVEN': 7, 'SEVENTH': 7, 'EIGHT': 8, 'EIGHTH': 8,
            'NINE': 9, 'NINTH': 9, 'TEN': 10, 'TENTH': 10,
            'ELEVEN': 11, 'ELEVENTH': 11, 'TWELVE': 12, 'TWELFTH': 12,
            'THIRTEEN': 13, 'THIRTEENTH': 13, 'FOURTEEN': 14, 'FOURTEENTH': 14, 'FIFTEEN': 15, 'FIFTEENTH': 15,
            'SIXTEEN': 16, 'SIXTEENTH': 16, 'SEVENTEEN': 17, 'SEVENTEENTH': 17,
            'EIGHTEEN': 18, 'EIGHTEENTH': 18, 'NINETEEN': 19, 'NINETEENTH': 19, 'TWENTY': 20, 'TWENTIETH': 20,
            'TWENTY-ONE': 21, 'TWENTY-FIRST': 21, 'TWENTY-TWO': 22, 'TWENTY-SECOND': 22,
            'TWENTY-THREE': 23, 'TWENTY-THIRD': 23, 'TWENTY-FOUR': 24, 'TWENTY-FOURTH': 24,
            'TWENTY-FIVE': 25, 'TWENTY-FIFTH': 25, 'TWENTY-SIX': 26, 'TWENTY-SIXTH': 26,
            'TWENTY-SEVEN': 27, 'TWENTY-SEVENTH': 27, 'TWENTY-EIGHT': 28, 'TWENTY-EIGHTH': 28,
            'TWENTY-NINE': 29, 'TWENTY-NINTH': 29, 'THIRTY': 30, 'THIRTIETH': 30,
            'THIRTY-ONE': 31, 'THIRTY-FIRST': 31, 'THIRTY-TWO': 32, 'THIRTY-SECOND': 32,
            'THIRTY-THREE': 33, 'THIRTY-THIRD': 33, 'THIRTY-FOUR': 34, 'THIRTY-FOURTH': 34,
            'THIRTY-FIVE': 35, 'THIRTY-FIFTH': 35, 'THIRTY-SIX': 36, 'THIRTY-SIXTH': 36,
            'THIRTY-SEVEN': 37, 'THIRTY-SEVENTH': 37, 'THIRTY-EIGHT': 38, 'THIRTY-EIGHTH': 38,
            'THIRTY-NINE': 39, 'THIRTY-NINTH': 39, 'FORTY': 40, 'FORTIETH': 40,
            'FORTY-ONE': 41, 'FORTY-FIRST': 41, 'FORTY-TWO': 42, 'FORTY-SECOND': 42,
            'FORTY-THREE': 43, 'FORTY-THIRD': 43, 'FORTY-FOUR': 44, 'FORTY-FOURTH': 44,
            'FORTY-FIVE': 45, 'FORTY-FIFTH': 45, 'FORTY-SIX': 46, 'FORTY-SIXTH': 46,
            'FORTY-SEVEN': 47, 'FORTY-SEVENTH': 47, 'FORTY-EIGHT': 48, 'FORTY-EIGHTH': 48,
            'FORTY-NINE': 49, 'FORTY-NINTH': 49, 'FIFTY': 50, 'FIFTIETH': 50,
            'FIFTY-ONE': 51, 'FIFTY-FIRST': 51, 'FIFTY-TWO': 52, 'FIFTY-SECOND': 52,
            'FIFTY-THREE': 53, 'FIFTY-THIRD': 53, 'FIFTY-FOUR': 54, 'FIFTY-FOURTH': 54,
            'FIFTY-FIVE': 55, 'FIFTY-FIFTH': 55, 'FIFTY-SIX': 56, 'FIFTY-SIXTH': 56,
            'FIFTY-SEVEN': 57, 'FIFTY-SEVENTH': 57, 'FIFTY-EIGHT': 58, 'FIFTY-EIGHTH': 58,
            'FIFTY-NINE': 59, 'FIFTY-NINTH': 59, 'SIXTY': 60, 'SIXTIETH': 60,
            'SIXTY-ONE': 61, 'SIXTY-FIRST': 61, 'SIXTY-TWO': 62, 'SIXTY-SECOND': 62,
            'SIXTY-THREE': 63, 'SIXTY-THIRD': 63, 'SIXTY-FOUR': 64, 'SIXTY-FOURTH': 64,
            'SIXTY-FIVE': 65, 'SIXTY-FIFTH': 65, 'SIXTY-SIX': 66, 'SIXTY-SIXTH': 66,
            'SIXTY-SEVEN': 67, 'SIXTY-SEVENTH': 67, 'SIXTY-EIGHT': 68, 'SIXTY-EIGHTH': 68,
            'SIXTY-NINE': 69, 'SIXTY-NINTH': 69, 'SEVENTY': 70, 'SEVENTIETH': 70,
            # Title case variants (for "Book the First", "Book the Second", etc.)
            'First': 1, 'Second': 2, 'Third': 3, 'Fourth': 4, 'Fifth': 5,
            'Sixth': 6, 'Seventh': 7, 'Eighth': 8, 'Ninth': 9, 'Tenth': 10,
            'Eleventh': 11, 'Twelfth': 12, 'Thirteenth': 13, 'Fourteenth': 14, 'Fifteenth': 15
        }
        return word_map.get(s.upper(), word_map.get(s, 0))

    def _int_to_roman(self, num: int) -> str:
        """Convert positive integer to a Roman numeral string."""
        if num <= 0:
            return ""
        val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        syms = ['M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I']
        roman = ''
        i = 0
        while num > 0:
            for _ in range(num // val[i]):
                roman += syms[i]
                num -= val[i]
            i += 1
        return roman

    def _build_numeral_alternation(self, number: int, observed_numeral: str = "") -> str:
        """Build a regex alternation of all equivalent numeral forms for a given integer.

        Used when matching section/chapter markers where the TOC and body may use
        different numeral systems (e.g. TOC 'VOLUME I' but body 'VOLUME 1'). The
        alternation accepts any equivalent form: Arabic ('1'), Roman ('I'), and the
        original observed string from the TOC.

        Args:
            number: Integer value of the numeral (e.g. 1, 2, 14).
            observed_numeral: The original numeral string from the TOC (kept as
                a fallback so spelled-out forms like 'ONE' still match).

        Returns:
            Regex alternation string like '14|XIV' suitable for embedding in
            an `f`-string regex. Forms are sorted by length descending to avoid
            shorter prefixes shadowing longer ones (e.g. 'I' shadowing 'II').
        """
        forms = set()
        if number > 0:
            forms.add(str(number))
            roman = self._int_to_roman(number)
            if roman:
                forms.add(roman)
        if observed_numeral:
            forms.add(observed_numeral)
        forms = {f for f in forms if f}
        sorted_forms = sorted(forms, key=lambda s: -len(s))
        return '|'.join(re.escape(f) for f in sorted_forms)

    def extract_gutenberg_content(self, text: str) -> str:
        """
        Extract the actual book content, removing Gutenberg headers/footers if present.

        For Project Gutenberg books: Removes headers, footers, and license information.
        Preserves prefaces, introductions, and translator's notes that appear
        after the title/author but before the main content.

        For non-Gutenberg books: Returns the text unchanged.
        """
        # Look for standard Project Gutenberg markers
        start_markers = [
            '*** START OF THE PROJECT GUTENBERG EBOOK',
            '*** START OF THIS PROJECT GUTENBERG EBOOK',
            '***START OF THE PROJECT GUTENBERG EBOOK'
        ]

        end_markers = [
            '*** END OF THE PROJECT GUTENBERG EBOOK',
            '*** END OF THIS PROJECT GUTENBERG EBOOK',
            '***END OF THE PROJECT GUTENBERG EBOOK'
        ]

        # Find start position
        start_pos = 0
        for marker in start_markers:
            pos = text.upper().find(marker)
            if pos != -1:
                # Find the end of the line after the marker
                start_pos = text.find('\n', pos) + 1
                break

        # Find end position
        end_pos = len(text)
        for marker in end_markers:
            pos = text.upper().find(marker)
            if pos != -1:
                end_pos = pos
                break

        # Extract content
        if start_pos > 0 or end_pos < len(text):
            content = text[start_pos:end_pos]

            # Only remove excessive leading/trailing newlines, preserve paragraph spacing
            while content.startswith('\n'):
                content = content[1:]
            while content.endswith('\n'):
                content = content[:-1]

            print(f"Extracted Project Gutenberg content: {len(content)} characters (original: {len(text)})")

            return content

        return text

    def normalize_chapter_title(self, title: str) -> str:
        """Normalize chapter title to use consistent title case.

        Delegates to scripts.lib.text — see there for the full docstring.
        """
        return text_lib.normalize_chapter_title(title)

    def normalize_chapter_text(self, text: str, is_poetry: bool = False) -> str:
        """
        Normalize chapter text by removing single newlines but keeping paragraph breaks
        Also removes leading/trailing spaces from each line
        Uses single newline between paragraphs

        Args:
            text: The text to normalize
            is_poetry: If True, preserves line breaks (for poetry). If False, joins lines within paragraphs.
        """
        import re

        # Replace any Windows-style line endings with Unix-style
        text = text.replace('\r\n', '\n')

        # If poetry, preserve all line breaks - just trim whitespace from each line
        if is_poetry:
            lines = text.split('\n')
            # Trim each line but preserve empty lines
            trimmed_lines = [line.strip() for line in lines]
            # Remove leading/trailing empty lines
            while trimmed_lines and not trimmed_lines[0]:
                trimmed_lines.pop(0)
            while trimmed_lines and not trimmed_lines[-1]:
                trimmed_lines.pop()
            # Join with newlines, preserving structure
            result = '\n'.join(trimmed_lines)
            return result

        # For prose: normalize as before
        # Replace multiple consecutive newlines (3+) with exactly 2 newlines (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Split into paragraphs (separated by double newlines)
        paragraphs = text.split('\n\n')

        # For each paragraph: split lines, trim each line, join with space
        normalized_paragraphs = []
        for paragraph in paragraphs:
            # Split on single newlines
            lines = paragraph.split('\n')
            # Trim each line and filter out empty lines
            trimmed_lines = [line.strip() for line in lines if line.strip()]
            # Join lines within paragraph with space
            normalized_paragraph = ' '.join(trimmed_lines)
            if normalized_paragraph:
                normalized_paragraphs.append(normalized_paragraph)

        # Join paragraphs with single newline
        result = '\n'.join(normalized_paragraphs)

        # Clean up multiple spaces (in case any slipped through)
        result = re.sub(r' {2,}', ' ', result)

        return result

    def clean_page_numbers_from_title(self, title: str) -> str:
        """
        Remove page numbers from chapter titles.
        Page numbers typically appear at the end, possibly with leading dots/spaces.
        Examples:
            "THE PRISON-DOOR                                51" -> "THE PRISON-DOOR"
            "The Market Place . . . . . . . . . . . . . 54" -> "The Market Place"
            "Chapter Title                              123" -> "Chapter Title"
        """
        # Remove trailing page numbers (digits possibly preceded by dots, spaces, etc.)
        # Look for patterns like "  123", "....123", ". . . .123", "     51"
        cleaned = re.sub(r'[\s\.]+\d+\s*$', '', title)
        return cleaned.strip()

    def extract_toc(self, text: str) -> Tuple[Dict[str, str], int]:
        """
        Extract table of contents from the text.
        Returns tuple of (toc_dict, toc_end_line):
        - toc_dict: mapping of chapter markers to expected chapter titles
        - toc_end_line: line number where TOC LISTING ended (0 if no TOC found)
          This is the last line in the TOC listing section, NOT where actual chapters begin
        Supports both Roman numerals (I, II, III) and Arabic numerals (1, 2, 3).
        Also supports patterns like "Chapter 1", "Letter 1", etc.
        """
        toc = {}
        lines = text.split('\n')

        # Look for CONTENTS section
        in_toc = False
        toc_start_line = 0  # Track where TOC starts
        last_toc_entry_line = 0  # Track the last line where we found a TOC entry
        # End markers should be unique content that signals end of TOC, not chapter markers
        # that also appear in TOC entries.
        toc_end_markers = ['INTRODUCTION BY', 'ZARATHUSTRA\'S PROLOGUE', 'FIRST PART']

        # Track chapter markers to detect duplicates and decreases
        # When we see a duplicate or a decrease, TOC has ended and actual content started
        seen_markers = set()  # Track all markers we've seen (e.g., 'I', 'II', 'III')
        highest_number = 0    # Track highest chapter number for decrease detection

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Start of TOC
            # Match either "CONTENTS", "TABLE OF CONTENTS", "LIST OF CHAPTERS",
            # or a standalone "CHAPTER" line (which indicates TOC header).
            if re.match(
                r'^\s*(CONTENTS|TABLE\s+OF\s+CONTENTS|LIST\s+OF\s+CHAPTERS|CHAPTER)\.?\s*$',
                line_stripped,
                re.IGNORECASE,
            ):
                in_toc = True
                toc_start_line = i
                continue

            # End of TOC - when we hit the actual content
            # End markers are unique content that signals end of TOC
            if in_toc and any(marker in line_stripped for marker in toc_end_markers):
                break

            # Parse TOC entries
            if in_toc and line_stripped:
                # Pattern 1: Roman numerals with title (e.g., "LVI. Old and New Tables")
                # MUST have a period after the numeral to avoid matching "I have..." sentences
                match = re.match(r'^([IVXLCDM]+)\.\s+(.+?)\.?\s*$', line_stripped)
                if match:
                    roman_num = match.group(1)
                    title = match.group(2).strip('. ')
                    # Clean page numbers from title
                    title = self.clean_page_numbers_from_title(title)

                    # Check for duplicate or decrease (signals TOC ended)
                    if roman_num in seen_markers:
                        break  # Duplicate detected - TOC has ended

                    # Convert to number for decrease detection
                    current_number = self.roman_to_int(roman_num)
                    if current_number > 0 and current_number < highest_number:
                        break  # Number decreased - TOC has ended

                    # Update tracking
                    seen_markers.add(roman_num)
                    highest_number = max(highest_number, current_number)
                    last_toc_entry_line = i  # Update last TOC entry line

                    toc[roman_num] = title
                    continue

                # Pattern 2: "Chapter" + number (e.g., "Chapter 1", "Chapter 12", "CHAPTER ONE", "CHAPTER TWENTY-TWO")
                # Support spelled-out numbers (ONE through SEVENTY with hyphens)
                # IMPORTANT: Longer patterns must come first to avoid partial matches (e.g., SIXTY-SEVEN before SIX)
                # IMPORTANT: Use non-capturing group (?:...) to avoid creating extra capture groups
                spelled_out_pattern = r'(?:SEVENTY|SIXTY-NINE|SIXTY-EIGHT|SIXTY-SEVEN|SIXTY-SIX|SIXTY-FIVE|SIXTY-FOUR|SIXTY-THREE|SIXTY-TWO|SIXTY-ONE|SIXTY|FIFTY-NINE|FIFTY-EIGHT|FIFTY-SEVEN|FIFTY-SIX|FIFTY-FIVE|FIFTY-FOUR|FIFTY-THREE|FIFTY-TWO|FIFTY-ONE|FIFTY|FORTY-NINE|FORTY-EIGHT|FORTY-SEVEN|FORTY-SIX|FORTY-FIVE|FORTY-FOUR|FORTY-THREE|FORTY-TWO|FORTY-ONE|FORTY|THIRTY-NINE|THIRTY-EIGHT|THIRTY-SEVEN|THIRTY-SIX|THIRTY-FIVE|THIRTY-FOUR|THIRTY-THREE|THIRTY-TWO|THIRTY-ONE|THIRTY|TWENTY-NINE|TWENTY-EIGHT|TWENTY-SEVEN|TWENTY-SIX|TWENTY-FIVE|TWENTY-FOUR|TWENTY-THREE|TWENTY-TWO|TWENTY-ONE|TWENTY|NINETEEN|EIGHTEEN|SEVENTEEN|SIXTEEN|FIFTEEN|FOURTEEN|THIRTEEN|TWELVE|ELEVEN|TEN|NINE|EIGHT|SEVEN|SIX|FIVE|FOUR|THREE|TWO|ONE)'
                match = re.match(rf'^Chapter\s+([IVXLCDM]+|[0-9]+|{spelled_out_pattern})(?:[\.\s]+(.+?))?\.?\s*$', line_stripped, re.IGNORECASE)
                if match:
                    chapter_marker = match.group(1)
                    # Title is in group 2 (after the period and space)
                    title = match.group(2).strip('. ') if match.group(2) else ""
                    # Clean page numbers from title
                    title = self.clean_page_numbers_from_title(title)

                    # Check for duplicate or decrease (signals TOC ended)
                    if chapter_marker in seen_markers:
                        break  # Duplicate detected - TOC has ended

                    # Convert to number for decrease detection
                    if chapter_marker.isdigit():
                        current_number = int(chapter_marker)
                    else:
                        # Try spelled-out number first
                        current_number = self.word_to_int(chapter_marker)
                        # If not a spelled-out number, try Roman numeral
                        if current_number == 0:
                            current_number = self.roman_to_int(chapter_marker)

                    if current_number > 0 and current_number < highest_number:
                        break  # Number decreased - TOC has ended

                    # Update tracking
                    seen_markers.add(chapter_marker)
                    highest_number = max(highest_number, current_number)
                    last_toc_entry_line = i  # Update last TOC entry line

                    # Don't overwrite existing TOC entries with empty titles
                    # (prevents standalone chapter markers from overwriting detailed TOC entries)
                    if chapter_marker in toc and toc[chapter_marker] and not title:
                        continue

                    toc[chapter_marker] = title
                    continue

                # Pattern 3: "Stave" + number (e.g., "Stave I", "Stave V") for A Christmas Carol
                match = re.match(r'^Stave\s+([IVXLCDM]+|[0-9]+)(?::\s+(.+?))?\.?\s*$', line_stripped, re.IGNORECASE)
                if match:
                    chapter_marker = match.group(1)
                    title = match.group(2).strip('. ') if match.group(2) else ""

                    # Check for duplicate or decrease (signals TOC ended)
                    if chapter_marker in seen_markers:
                        break  # Duplicate detected - TOC has ended

                    # Convert to number for decrease detection
                    if chapter_marker.isdigit():
                        current_number = int(chapter_marker)
                    else:
                        current_number = self.roman_to_int(chapter_marker)

                    if current_number > 0 and current_number < highest_number:
                        break  # Number decreased - TOC has ended

                    # Update tracking
                    seen_markers.add(chapter_marker)
                    highest_number = max(highest_number, current_number)
                    last_toc_entry_line = i  # Update last TOC entry line

                    toc[chapter_marker] = title
                    continue

                # NOTE: "Letter" patterns intentionally removed
                # Per user requirement: "anything before Chapter 1 or Chapter I or Book 1 etc
                # are grouped together into a single Preface chapter"
                # Letters should not be treated as numbered chapters, but as preface content

        # If we found TOC entries, scan forward to find where TOC section actually ends
        # Look for the first real chapter marker (not TOC entry) after the last TOC entry
        # Real chapter markers have substantial paragraph content following them
        toc_end_line = 0
        if last_toc_entry_line > 0:
            # Scan forward from last TOC entry to find actual end of TOC section
            for scan_idx in range(last_toc_entry_line + 1, len(lines)):
                scan_line_original = lines[scan_idx]  # Keep original with indentation
                scan_line = scan_line_original.strip()

                # Skip blank lines
                if not scan_line:
                    continue

                # Check if this looks like a chapter marker
                is_chapter_marker = (
                    re.match(r'^([IVXLCDM]+)\.\s+', scan_line) or
                    re.match(r'^Chapter\s+', scan_line, re.IGNORECASE) or
                    re.match(r'^CHAPTER\s+', scan_line) or  # Oliver Twist style: " CHAPTER I."
                    re.match(r'^Stave\s+', scan_line, re.IGNORECASE)
                )

                # If it's a chapter marker, look ahead to see if it's followed by substantial content
                # Real chapters have paragraph text following them, TOC entries don't
                if is_chapter_marker:
                    # Look ahead LOOKAHEAD_CONTENT_VALIDATION_LINES for substantial content (> 50 chars, looks like paragraph text)
                    has_content_following = False
                    for lookahead_idx in range(scan_idx + 1, min(scan_idx + ChapterDetectionConstants.LOOKAHEAD_CONTENT_VALIDATION_LINES + 1, len(lines))):
                        lookahead_line = lines[lookahead_idx].strip()
                        # Check if this looks like paragraph content (not another chapter marker, not blank)
                        if (lookahead_line and
                            len(lookahead_line) > 50 and
                            not re.match(r'^(CHAPTER|Chapter|[IVXLCDM]+\.)\s+', lookahead_line)):
                            has_content_following = True
                            break

                    if has_content_following:
                        # This is a real chapter marker with content following
                        # TOC ends just before this line
                        toc_end_line = scan_idx - 1
                        break
                    else:
                        # This is likely a TOC entry (no content following)
                        continue

                # If we found a non-blank, non-chapter-marker line, this is where TOC ends
                # (This handles books with content between TOC and first chapter)
                toc_end_line = scan_idx
                break

            # If we never found content after TOC (edge case), use last TOC entry
            if toc_end_line == 0:
                toc_end_line = last_toc_entry_line

        return toc, toc_end_line

    def extract_story_collection_toc(self, text: str) -> List[Dict]:
        """
        Extract two-level structure for story collections where stories are top-level
        and some stories have internal chapters (Part I, Part II, etc.).

        Example: "The Eternal Moment and Other Stories" by E.M. Forster
        - THE MACHINE STOPS (with Part I, Part II, Part III)
        - THE POINT OF IT (single chapter)
        - MR. ANDREWS (single chapter)
        - etc.

        Returns list of dictionaries with structure like extract_two_level_toc(),
        or None if this is not a story collection.
        """
        lines = text.split('\n')

        # First, extract the simple TOC (story titles without numbers)
        title_toc = self.extract_title_only_toc(text)

        if len(title_toc) < 3:
            # Not enough stories to be a collection
            return None

        # Find where TOC ends using duplicate detection
        # Strategy: When a story title appears twice, the first is in TOC, the second is actual content
        # Find the first duplicate occurrence - that's where the body starts
        toc_end_line = 0

        for story_title in title_toc:
            story_pattern = r'^\s*' + re.escape(story_title) + r'\s*$'
            occurrences = []

            # Find all occurrences of this story title
            for i, line in enumerate(lines):
                if re.match(story_pattern, line.strip(), re.IGNORECASE):
                    occurrences.append(i)

            # If we found 2+ occurrences, the second one is likely the actual story start
            if len(occurrences) >= 2:
                # Verify the second occurrence has content after it (not another TOC)
                second_occurrence = occurrences[1]

                # Check for part markers or substantial paragraph content
                has_content = False
                for lookahead in range(second_occurrence + 1, min(second_occurrence + 20, len(lines))):
                    lookahead_line = lines[lookahead].strip()

                    # Check for part markers
                    if re.match(r'^\s*_Part\s+I_\s*$', lines[lookahead], re.IGNORECASE):
                        has_content = True
                        break
                    if re.match(r'^\s+I\s*$', lines[lookahead]):  # Centered roman "I"
                        has_content = True
                        break

                    # Check for paragraph content
                    if lookahead_line and len(lookahead_line) > 50 and lookahead_line[0].isalpha():
                        has_content = True
                        break

                if has_content:
                    toc_end_line = second_occurrence
                    break

        # If no duplicates found, fall back to finding CONTENTS marker
        if toc_end_line == 0:
            for i, line in enumerate(lines):
                if re.match(r'^\s*CONTENTS\s*$', line.strip(), re.IGNORECASE):
                    # Assume body starts ~20 lines after CONTENTS
                    toc_end_line = i + 20
                    break

        # Now search for each story in the body and check if it has internal parts
        toc_structure = []

        for story_idx, story_title in enumerate(title_toc, start=1):
            # Find where this story starts in the text (after TOC ends)
            # Allow optional period at end (many stories have titles like "The Happy Prince.")
            story_pattern = r'^\s*' + re.escape(story_title) + r'\.?\s*$'
            story_start_line = None

            # Start searching after TOC ends
            search_start = max(0, toc_end_line) if toc_end_line else 0

            for i in range(search_start, len(lines)):
                if re.match(story_pattern, lines[i].strip(), re.IGNORECASE):
                    # To distinguish TOC entries from actual stories, check if this is followed by:
                    # 1. Part markers (_Part I_ or centered roman numerals), OR
                    # 2. Substantial paragraph content (3+ long lines), OR
                    # 3. Illustration markers like [Picture: ...]
                    has_part_marker = False
                    paragraph_lines = 0
                    has_illustration = False

                    # Skip if this line has page numbers (indicates TOC entry)
                    # Page numbers are typically at end of line, separated by dots or spaces
                    if re.search(r'\s+\d+\s*$', lines[i]):
                        continue  # This is a TOC entry, skip it

                    for lookahead in range(i + 1, min(i + 15, len(lines))):
                        lookahead_line = lines[lookahead].strip()

                        # Check for illustration markers
                        if lookahead_line.startswith('[Picture:'):
                            has_illustration = True
                            break

                        # Check for part markers
                        if re.match(r'^\s*_Part\s+I_\s*$', lines[lookahead], re.IGNORECASE):
                            has_part_marker = True
                            break
                        if re.match(r'^\s+I\s*$', lines[lookahead]):  # Centered roman "I"
                            has_part_marker = True
                            break

                        # Count paragraph lines
                        if lookahead_line and len(lookahead_line) > 40 and (lookahead_line[0].isalpha() or lookahead_line[0] == '"'):
                            paragraph_lines += 1

                    # Accept if we found part markers OR illustration OR 3+ paragraph lines
                    if has_part_marker or has_illustration or paragraph_lines >= 3:
                        story_start_line = i
                        break

            if story_start_line is None:
                continue

            # Look for Part I, Part II, Part III within this story
            # Scan until we hit the next story title
            next_story_title = title_toc[story_idx] if story_idx < len(title_toc) else None
            scan_end = len(lines)

            if next_story_title:
                # Allow optional period at end (many stories have titles like "The Happy Prince.")
                next_story_pattern = r'^\s*' + re.escape(next_story_title) + r'\.?\s*$'
                for i in range(story_start_line + 1, len(lines)):
                    if re.match(next_story_pattern, lines[i].strip(), re.IGNORECASE):
                        # Verify this is the actual story start, not TOC
                        has_content = False
                        for lookahead in range(i + 1, min(i + 20, len(lines))):
                            lookahead_line = lines[lookahead].strip()
                            if lookahead_line and len(lookahead_line) > 40:
                                has_content = True
                                break
                        if has_content:
                            scan_end = i
                            break

            # Search for part markers within this story
            # Try two patterns:
            # 1. _Part I_, _Part II_, _Part III_ (italicized format, e.g., "The Machine Stops")
            # 2. Standalone roman numerals I, II, III (e.g., "The Point of It", "The Eternal Moment")
            part_chapters = []
            part_pattern_italic = r'^\s*_Part\s+(I|II|III|IV|V|VI|VII|VIII|IX|X|ONE|TWO|THREE|FOUR|FIVE)_\s*$'
            part_pattern_roman = r'^\s+(I|II|III|IV|V|VI|VII|VIII|IX|X)\s*$'  # Centered roman numerals

            for i in range(story_start_line, scan_end):
                line_stripped = lines[i].strip()
                part_match = re.match(part_pattern_italic, line_stripped, re.IGNORECASE)
                if not part_match:
                    # Try standalone roman numeral pattern (must have whitespace padding)
                    part_match = re.match(part_pattern_roman, lines[i])

                if part_match:
                    part_numeral = part_match.group(1)
                    # Convert to number
                    if part_numeral.isdigit():
                        part_number = int(part_numeral)
                    else:
                        part_number = self.word_to_int(part_numeral)
                        if part_number == 0:
                            part_number = self.roman_to_int(part_numeral)

                    # Look for chapter title on next non-empty line
                    chapter_title = ""
                    for offset in range(1, 5):
                        if i + offset < len(lines):
                            next_line = lines[i + offset].strip()
                            if next_line and len(next_line) > 3:
                                chapter_title = next_line
                                break

                    part_chapters.append({
                        'number': part_number,
                        'numeral': part_numeral,
                        'title': chapter_title
                    })

            # Add this story to the structure
            # If no parts found, it's a single-chapter story
            if not part_chapters:
                part_chapters = [{
                    'number': 1,
                    'numeral': '1',
                    'title': story_title  # Use story title as chapter title
                }]

            toc_structure.append({
                'type': 'STORY',
                'number': story_idx,
                'numeral': str(story_idx),
                'title': story_title,
                'chapters': part_chapters,
                'line_index': story_start_line
            })

        # Only return if we found at least 3 stories
        if len(toc_structure) >= 3:
            print(f"  📖 Detected story collection: {len(toc_structure)} stories")
            for story in toc_structure:
                parts_info = f"({len(story['chapters'])} part{'s' if len(story['chapters']) != 1 else ''})"
                print(f"     • STORY {story['number']}: {story['title']} {parts_info}")
            return toc_structure

        return None

    def extract_two_level_toc(self, text: str) -> List[Dict]:
        """
        Extract two-level table of contents (Book/Part/Act → Chapters).

        Analyzes TOC structure to detect books with hierarchical organization like:
        - PART ONE/TWO (Treasure Island, Anna Karenina)
        - BOOK I/II (War and Peace, Principles of Political Economy)
        - ACT I/II (Romeo and Juliet)

        Each with nested chapters/scenes.

        Returns list of dictionaries with structure:
        [
            {
                'type': 'PART' | 'BOOK' | 'ACT',
                'number': 1,
                'numeral': 'ONE' | 'I' | '1',
                'title': 'The Old Buccaneer',
                'chapters': [
                    {'number': 1, 'numeral': 'I', 'title': 'The Old Sea-dog at the Admiral Benbow'},
                    {'number': 2, 'numeral': 'II', 'title': 'Black Dog Appears and Disappears'},
                    ...
                ]
            },
            ...
        ]

        Returns None if no two-level structure is detected.
        """
        lines = text.split('\n')

        # Look for CONTENTS section
        in_toc = False
        toc_structure = []
        current_section = None

        # Patterns for section markers (PART/BOOK/ACT/EPILOGUE/PROLOGUE) - allow leading whitespace
        # Pattern 1: Numbered sections - "BOOK I", "BOOK I. Title", "BOOK I: Title", "BOOK I - Title"
        # Also matches: "Book the First", "Book the Second", etc. (A Tale of Two Cities)
        section_pattern = r'(PART|BOOK|ACT|Part|Book|Act)\s+(?:the\s+)?(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth|[0-9]+|[IVXLCDM]+)(?:\.?\s*[:—-]?\s*(.+?))?\s*$'

        # Pattern 2: Unnumbered sections - "Epilogue", "Prologue", "Epilogue: Title"
        unnumbered_section_pattern = r'(EPILOGUE|PROLOGUE)(?:\.?\s*[:—-]?\s*(.+?))?\s*$'

        # Also match decorative section markers like "— I —", "— II —", "— III —" (Ulysses)
        decorative_section_pattern = r'^\s*—+\s*([IVXLCDM]+)\s*—+\s*$'

        # Patterns for chapter/scene markers within sections - allow leading whitespace
        # Matches: "Chapter I", "CHAPTER 1", "CHAPTER ONE", "CHAPTER TWENTY-TWO", "Scene I. Title", etc.
        # IMPORTANT: Longer spelled-out patterns first to avoid partial matches
        # IMPORTANT: Use non-capturing group (?:...) to avoid creating extra capture groups
        spelled_out = r'(?:SEVENTY|SIXTY-NINE|SIXTY-EIGHT|SIXTY-SEVEN|SIXTY-SIX|SIXTY-FIVE|SIXTY-FOUR|SIXTY-THREE|SIXTY-TWO|SIXTY-ONE|SIXTY|FIFTY-NINE|FIFTY-EIGHT|FIFTY-SEVEN|FIFTY-SIX|FIFTY-FIVE|FIFTY-FOUR|FIFTY-THREE|FIFTY-TWO|FIFTY-ONE|FIFTY|FORTY-NINE|FORTY-EIGHT|FORTY-SEVEN|FORTY-SIX|FORTY-FIVE|FORTY-FOUR|FORTY-THREE|FORTY-TWO|FORTY-ONE|FORTY|THIRTY-NINE|THIRTY-EIGHT|THIRTY-SEVEN|THIRTY-SIX|THIRTY-FIVE|THIRTY-FOUR|THIRTY-THREE|THIRTY-TWO|THIRTY-ONE|THIRTY|TWENTY-NINE|TWENTY-EIGHT|TWENTY-SEVEN|TWENTY-SIX|TWENTY-FIVE|TWENTY-FOUR|TWENTY-THREE|TWENTY-TWO|TWENTY-ONE|TWENTY|NINETEEN|EIGHTEEN|SEVENTEEN|SIXTEEN|FIFTEEN|FOURTEEN|THIRTEEN|TWELVE|ELEVEN|TEN|NINE|EIGHT|SEVEN|SIX|FIVE|FOUR|THREE|TWO|ONE|the\s+last)'
        chapter_pattern = rf'(?:CHAPTER|Chapter|SCENE|Scene)\s+({spelled_out}|[IVXLCDM]+|[0-9]+)\.?\s*(.+)?\.?\s*$'

        # Also match bracket-style chapter markers like "[ 1 ]", "[ 10 ]" (Ulysses)
        bracket_chapter_pattern = r'^\s*\[\s*([0-9]+)\s*\]\s*$'

        # Also match Roman numerals followed by period and title (common in some books)
        roman_title_pattern = r'^\s*([IVXLCDM]+)\.\s+(.+?)\.?\s*$'

        should_exit_toc = False
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Start of TOC (case-insensitive)
            # Also match "CONTENTS VOLUME I", "CONTENTS VOLUME II" etc.
            if re.match(r'^\s*Contents\.?\s*$', line_stripped, re.IGNORECASE):
                in_toc = True
                continue

            # Check for "VOLUME I/II" or "CONTENTS VOLUME I/II" pattern (e.g., Don Quixote)
            volume_toc_match = re.match(r'^\s*(?:CONTENTS\s+)?VOLUME\s+(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|[IVXLCDM]+|[0-9]+)\.?\s*$', line_stripped, re.IGNORECASE)
            if volume_toc_match:
                in_toc = True
                # Treat this as a VOLUME section marker
                volume_numeral = volume_toc_match.group(1)

                # Convert numeral to number
                if volume_numeral.isdigit():
                    volume_number = int(volume_numeral)
                else:
                    # Try spelled-out word first
                    volume_number = self.word_to_int(volume_numeral)
                    # If that didn't work, try Roman numeral
                    if volume_number == 0:
                        volume_number = self.roman_to_int(volume_numeral)

                # Check if this VOLUME number was already captured (e.g., TOC has
                # 'VOLUME I' and body has 'VOLUME 1' — both parse to number 1).
                # If duplicate, TOC has ended and body section markers are starting.
                existing_volume_numbers = [s['number'] for s in toc_structure if s['type'] == 'VOLUME']
                if current_section and current_section.get('type') == 'VOLUME':
                    existing_volume_numbers.append(current_section['number'])
                if volume_number in existing_volume_numbers:
                    # Duplicate detected - stop TOC parsing
                    break

                # Save previous section if exists
                if current_section and len(current_section['chapters']) > 0:
                    toc_structure.append(current_section)

                current_section = {
                    'type': 'VOLUME',
                    'number': volume_number,
                    'numeral': volume_numeral,
                    'title': '',
                    'chapters': []
                }
                continue

            if not in_toc:
                continue

            # Skip empty lines
            if not line_stripped:
                continue

            # Check for section marker (PART/BOOK/ACT/EPILOGUE/PROLOGUE or decorative "— I —" style)
            section_match = re.match(section_pattern, line_stripped, re.IGNORECASE)
            unnumbered_match = re.match(unnumbered_section_pattern, line_stripped, re.IGNORECASE)
            decorative_match = re.match(decorative_section_pattern, line_stripped)

            if section_match or unnumbered_match or decorative_match:
                if decorative_match:
                    # Decorative section marker like "— I —"
                    section_type = 'PART'  # Treat as PART
                    section_numeral = decorative_match.group(1)
                    section_title = ""
                elif unnumbered_match:
                    # Unnumbered section like "Epilogue" or "Prologue"
                    section_type = unnumbered_match.group(1).upper()
                    # Assign special numerals: Prologue = 0, Epilogue = 999 (sorts after all numbered sections)
                    if section_type == 'PROLOGUE':
                        section_numeral = "0"
                    else:  # EPILOGUE
                        section_numeral = "999"
                    section_title = unnumbered_match.group(2).strip() if unnumbered_match.group(2) else ""
                else:
                    # Standard PART/BOOK/ACT marker
                    section_type = section_match.group(1).upper()
                    section_numeral = section_match.group(2)
                    section_title = section_match.group(3).strip() if section_match.group(3) else ""
                    # If the optional title regex captured a stray separator
                    # (e.g. bare 'PART I.' captures '.' as the title), discard it.
                    if section_title and not re.search(r'[A-Za-z0-9]', section_title):
                        section_title = ""

                # If we've already detected VOLUME sections, and now we hit a BOOK/PART/ACT,
                # it means the TOC has ended and we're in content (these section types don't mix)
                if len(toc_structure) > 0 and toc_structure[0]['type'] == 'VOLUME' and section_type in ['BOOK', 'PART', 'ACT']:
                    # TOC ended - we're now in the introduction/preface content
                    break

                # Convert numeral to number
                if section_numeral.isdigit():
                    section_number = int(section_numeral)
                else:
                    # Try spelled-out word first
                    section_number = self.word_to_int(section_numeral)
                    # If that didn't work, try Roman numeral
                    if section_number == 0:
                        section_number = self.roman_to_int(section_numeral)

                # Check if this is a duplicate section (TOC ended, content started)
                # Skip duplicate check for EPILOGUE/PROLOGUE since they use fixed numeral "1"
                if section_type not in ['EPILOGUE', 'PROLOGUE']:
                    existing_numbers = [s['number'] for s in toc_structure if s['type'] == section_type]
                    if section_number in existing_numbers:
                        # Duplicate detected - TOC has ended
                        break

                # Save previous section if exists
                if current_section and len(current_section['chapters']) > 0:
                    toc_structure.append(current_section)

                # For numbered sections, check next line for title if empty
                if not section_title and section_type not in ['EPILOGUE', 'PROLOGUE'] and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # If next line is not empty and doesn't look like a chapter marker, use it as title
                    if next_line and not re.match(chapter_pattern, next_line) and not re.match(r'^[IVXLCDM]+\.', next_line):
                        section_title = next_line

                current_section = {
                    'type': section_type,
                    'number': section_number,
                    'numeral': section_numeral,
                    'title': section_title,
                    'chapters': []
                }
                continue

            # Check for chapter/scene marker
            if current_section:
                # Try bracket-style chapter markers first (e.g., "[ 1 ]", "[ 10 ]")
                bracket_match = re.match(bracket_chapter_pattern, line_stripped)
                if bracket_match:
                    chapter_numeral = bracket_match.group(1)
                    chapter_number = int(chapter_numeral)
                    chapter_title = ""  # Bracket chapters don't have titles in TOC

                    current_section['chapters'].append({
                        'number': chapter_number,
                        'numeral': chapter_numeral,
                        'title': chapter_title
                    })
                    continue

                # Try chapter/scene pattern
                chapter_match = re.match(chapter_pattern, line_stripped)
                if chapter_match:
                    chapter_numeral = chapter_match.group(1)
                    chapter_title = chapter_match.group(2).strip() if chapter_match.group(2) else ""

                    # Convert numeral to number
                    if chapter_numeral.isdigit():
                        chapter_number = int(chapter_numeral)
                    elif chapter_numeral.lower() == "the last":
                        # Special case for "the last" - assign a placeholder number
                        # The actual chapter number will be determined by its position
                        # We use a large placeholder number that will be replaced during processing
                        chapter_number = 9999  # Placeholder for "the last"
                    else:
                        # Try spelled-out number first
                        chapter_number = self.word_to_int(chapter_numeral)
                        # If not a spelled-out number, try Roman numeral
                        if chapter_number == 0:
                            chapter_number = self.roman_to_int(chapter_numeral)

                    current_section['chapters'].append({
                        'number': chapter_number,
                        'numeral': chapter_numeral,
                        'title': chapter_title
                    })
                    continue

                # Try Roman numeral + title pattern (for books like Treasure Island)
                roman_match = re.match(roman_title_pattern, line_stripped)
                if roman_match:
                    chapter_numeral = roman_match.group(1)
                    chapter_title = roman_match.group(2).strip()
                    chapter_number = self.roman_to_int(chapter_numeral)

                    # Only add if this looks like a chapter (not another section marker)
                    # Check if numeral is small enough to be a chapter (< 50)
                    if chapter_number > 0 and chapter_number < 50:
                        current_section['chapters'].append({
                            'number': chapter_number,
                            'numeral': chapter_numeral,
                            'title': chapter_title
                        })
                    continue

            # Check if we've left TOC (hit content or other markers)
            # Exit if we see the actual start of content (e.g., "Chapter 1" followed by paragraph text)
            # or if we see a duplicate section marker (means TOC ended and content started)
            if in_toc:
                # If we see a duplicate section (e.g., "PART I" appears again), TOC has ended
                if current_section:
                    check_section = re.match(section_pattern, line_stripped, re.IGNORECASE)
                    if check_section:
                        # Check if this section number already exists
                        existing_numbers = [s['number'] for s in toc_structure]
                        if current_section['number'] in existing_numbers:
                            # Duplicate detected - TOC ended, actual content started
                            break

            # Note: Removed exit_markers as they're unreliable
            # Rely on duplicate detection and chapter count thresholds instead

        # Save last section (allow sections with 0 chapters - they might be filled in later by body scan)
        if current_section:
            toc_structure.append(current_section)

        # Return None if no two-level structure detected
        if len(toc_structure) == 0:
            return None

        # Only return if we have at least 2 sections (to qualify as two-level)
        if len(toc_structure) < 2:
            return None

        # Check if at least some sections have chapters (to avoid false positives)
        # Allow some sections to have 0 chapters (like in Gulliver's Travels TOC)
        sections_with_chapters = sum(1 for s in toc_structure if len(s['chapters']) > 0)
        if sections_with_chapters == 0:
            # No chapters found in any section - this is not a valid two-level structure
            return None

        return toc_structure

    def extract_two_level_structure_from_body(self, text: str) -> List[Dict]:
        """
        Extract two-level structure by scanning the entire document body.

        This is a fallback method for books where the TOC doesn't list chapters,
        but the document body has clear PART/BOOK/ACT markers followed by Chapter markers.

        Example: Anna Karenina - TOC only shows "PART ONE" through "PART EIGHT"
        but the document body has "PART ONE" followed by "Chapter 1", "Chapter 2", etc.

        Returns same structure as extract_two_level_toc(), or None if not detected.
        """
        lines = text.split('\n')

        # Patterns for section markers
        # Allow optional title after numeral with various separators:
        # - "PART ONE" (no separator)
        # - "PART ONE." (period, no title)
        # - "PART I. A VOYAGE TO LILLIPUT." (period + space + title)
        # - "PART ONE--The Old Buccaneer" (double-dash + title)
        # - "Book the First--Recalled to Life" (A Tale of Two Cities)
        # Capture group 3 is the title (after period or double-dash)
        section_pattern = r'^\s*(PART|BOOK|ACT|VOLUME|Part|Book|Act|Volume)\s+(?:the\s+)?(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|Eleventh|Twelfth|[0-9]+|[IVXLCDM]+)(?:\.?\s*$|\.?\s+(.+?)\s*$|(?:--|\s+--)\s*(.+?)\s*$)'

        # Reversed format for plays: "FIRST ACT", "SECOND ACT", etc.
        reversed_section_pattern = r'^\s*(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH|SEVENTEENTH|EIGHTEENTH|NINETEENTH|TWENTIETH|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|[0-9]+|[IVXLCDM]+)\s+(PART|BOOK|ACT|VOLUME)(?:\.?\s*$|\.?\s+(.+?)\s*$)'

        # Also match decorative section markers like "— I —", "— II —", "— III —" (Ulysses)
        decorative_section_pattern = r'^\s*—+\s*([IVXLCDM]+)\s*—+\s*$'

        # Patterns for chapter markers - must be on their own line or with short title
        # IMPORTANT: Longer spelled-out patterns first to avoid partial matches
        # IMPORTANT: Use non-capturing group (?:...) to avoid creating extra capture groups
        spelled_out = r'(?:SEVENTY|SIXTY-NINE|SIXTY-EIGHT|SIXTY-SEVEN|SIXTY-SIX|SIXTY-FIVE|SIXTY-FOUR|SIXTY-THREE|SIXTY-TWO|SIXTY-ONE|SIXTY|FIFTY-NINE|FIFTY-EIGHT|FIFTY-SEVEN|FIFTY-SIX|FIFTY-FIVE|FIFTY-FOUR|FIFTY-THREE|FIFTY-TWO|FIFTY-ONE|FIFTY|FORTY-NINE|FORTY-EIGHT|FORTY-SEVEN|FORTY-SIX|FORTY-FIVE|FORTY-FOUR|FORTY-THREE|FORTY-TWO|FORTY-ONE|FORTY|THIRTY-NINE|THIRTY-EIGHT|THIRTY-SEVEN|THIRTY-SIX|THIRTY-FIVE|THIRTY-FOUR|THIRTY-THREE|THIRTY-TWO|THIRTY-ONE|THIRTY|TWENTY-NINE|TWENTY-EIGHT|TWENTY-SEVEN|TWENTY-SIX|TWENTY-FIVE|TWENTY-FOUR|TWENTY-THREE|TWENTY-TWO|TWENTY-ONE|TWENTY|NINETEEN|EIGHTEEN|SEVENTEEN|SIXTEEN|FIFTEEN|FOURTEEN|THIRTEEN|TWELVE|ELEVEN|TEN|NINE|EIGHT|SEVEN|SIX|FIVE|FOUR|THREE|TWO|ONE|the\s+last)'
        chapter_pattern = rf'^\s*(?:CHAPTER|Chapter)\s+({spelled_out}|[IVXLCDMivxlcdm]+|[0-9]+)\.?\s*(.{{0,60}})$'
        # Alternative patterns for standalone Roman numerals (Treasure Island, War of the Worlds styles)
        standalone_roman_pattern = r'^\s*([IVXLCDMivxlcdm]+)\s*$'  # Without period: "I", "II", "III"
        standalone_roman_with_period_pattern = r'^\s*([IVXLCDMivxlcdm]+)\.\s*$'  # With period: "I.", "II.", "III."
        # Bracket-style chapter markers like "[ 1 ]", "[ 10 ]" (Ulysses)
        bracket_chapter_pattern = r'^\s*\[\s*([0-9]+)\s*\]\s*$'

        toc_structure = []
        current_section = None
        section_line_indices = []  # Track where sections appear

        # First pass: Find all section markers and chapters that follow them
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                continue

            # Check for section marker (standard, reversed, or decorative)
            section_match = re.match(section_pattern, line_stripped, re.IGNORECASE)
            reversed_match = re.match(reversed_section_pattern, line_stripped, re.IGNORECASE)
            decorative_match = re.match(decorative_section_pattern, line_stripped)

            if section_match or reversed_match or decorative_match:
                if decorative_match:
                    # Decorative section marker like "— I —"
                    section_type = 'PART'  # Treat decorative markers as PART
                    section_numeral = decorative_match.group(1)
                elif reversed_match:
                    # Reversed format: "FIRST ACT", "SECOND ACT", etc.
                    section_numeral = reversed_match.group(1)
                    section_type = reversed_match.group(2).upper()

                    # Check for false positive: if title exists and starts with lowercase, likely prose
                    title_group_3 = reversed_match.group(3)
                    if title_group_3 and title_group_3[0].islower():
                        # This is likely prose, not a section marker - skip it
                        continue
                else:
                    # Standard PART/BOOK/ACT marker
                    section_type = section_match.group(1).upper()
                    section_numeral = section_match.group(2)

                    # Check for false positive: if title exists and starts with lowercase, likely prose
                    # Example: "part I am in doubt." (from Anna Karenina dialog)
                    title_group_3 = section_match.group(3)
                    title_group_4 = section_match.group(4)
                    if (title_group_3 and title_group_3[0].islower()) or (title_group_4 and title_group_4[0].islower()):
                        # This is likely prose, not a section marker - skip it
                        continue

                # Convert numeral to number
                if section_numeral.isdigit():
                    section_number = int(section_numeral)
                else:
                    section_number = self.word_to_int(section_numeral)
                    if section_number == 0:
                        section_number = self.roman_to_int(section_numeral)

                if section_number == 0:
                    continue

                # Check if duplicate - if so, remove the old one (TOC entry) and keep the new one (actual content)
                # The FIRST occurrence is usually in the TOC, the LAST occurrence is the actual content
                existing_index = next((idx for idx, s in enumerate(toc_structure) if s['number'] == section_number), None)
                if existing_index is not None:
                    # Remove the old entry (TOC)
                    old_section = toc_structure.pop(existing_index)

                # Also check if current_section matches this number
                if current_section and current_section['number'] == section_number:
                    # Replace current_section with this new occurrence
                    pass  # Will be replaced below
                elif current_section:
                    # Save previous section (even if it has 0 chapters - chapters might be detected later)
                    toc_structure.append(current_section)

                # Extract section title
                if decorative_match:
                    # Decorative markers don't have titles
                    section_title = ""
                elif reversed_match:
                    # Reversed format: "FIRST ACT" - check for title in group 3
                    section_title = ""
                    if reversed_match.group(3):
                        section_title = reversed_match.group(3).strip()
                else:
                    # Standard format: try to get it from the match if it exists on the same line
                    # Group 3: "PART I. A VOYAGE TO LILLIPUT." (period + space + title)
                    # Group 4: "PART ONE--The Old Buccaneer" (double-dash + title)
                    section_title = ""
                    if section_match.group(3):
                        section_title = section_match.group(3).strip()
                    elif section_match.group(4):
                        section_title = section_match.group(4).strip()
                    # Discard captures that are pure separator chars (e.g. bare 'PART I.' yields '.').
                    if section_title and not re.search(r'[A-Za-z0-9]', section_title):
                        section_title = ""

                    # If not on same line, check next few lines for section title
                    # Skip empty lines and collect multi-line titles (e.g., Tom Jones)
                    if not section_title and i + 1 < len(lines):
                        title_lines = []
                        # Look ahead up to 5 lines, skipping empty ones
                        for offset in range(1, 6):
                            if i + offset >= len(lines):
                                break
                            candidate_line = lines[i + offset].strip()

                            # Skip empty lines
                            if not candidate_line:
                                continue

                            # Stop if we hit a chapter marker
                            if re.match(chapter_pattern, candidate_line):
                                break

                            # Check if it looks like a title line (all caps or title case, not too long)
                            if (candidate_line[0].isupper() or candidate_line[0].isdigit()) and len(candidate_line) < 100:
                                title_lines.append(candidate_line)
                            else:
                                # Hit prose content, stop collecting title
                                break

                        # Join multi-line title with spaces
                        if title_lines:
                            section_title = ' '.join(title_lines)

                current_section = {
                    'type': section_type,
                    'number': section_number,
                    'numeral': section_numeral,
                    'title': section_title,
                    'chapters': [],
                    'line_index': i
                }
                section_line_indices.append(i)
                continue

            # Check for chapter marker (only if we're inside a section)
            if current_section:
                chapter_match = re.match(chapter_pattern, line_stripped)
                bracket_match = re.match(bracket_chapter_pattern, line_stripped) if not chapter_match else None
                standalone_match = re.match(standalone_roman_pattern, line_stripped) if not chapter_match and not bracket_match else None
                standalone_with_period_match = re.match(standalone_roman_with_period_pattern, line_stripped) if not chapter_match and not bracket_match and not standalone_match else None

                if chapter_match or bracket_match or standalone_match or standalone_with_period_match:
                    if chapter_match:
                        chapter_numeral = chapter_match.group(1)
                        chapter_title = chapter_match.group(2).strip() if chapter_match.group(2) else ""
                    elif bracket_match:
                        # Bracket-style chapter (Ulysses)
                        chapter_numeral = bracket_match.group(1)
                        chapter_title = ""
                    elif standalone_with_period_match:
                        # Standalone Roman numeral with period (War of the Worlds)
                        chapter_numeral = standalone_with_period_match.group(1)
                        chapter_title = ""
                    else:  # standalone_match
                        chapter_numeral = standalone_match.group(1)
                        chapter_title = ""

                    # If title is empty, check next few lines (skip empty lines)
                    # Format: "CHAPTER I" or "Chapter i." on one line, empty line(s), then title
                    # Tom Jones: "Chapter i." → empty line → "The introduction to the work..."
                    if not chapter_title:
                        # Look ahead up to 3 lines, skipping empty ones
                        for offset in range(1, 4):
                            if i + offset >= len(lines):
                                break
                            next_line = lines[i + offset].strip()

                            # Skip empty lines
                            if not next_line:
                                continue

                            # If next line doesn't look like another marker, use it as title
                            # Also verify it looks like a title (starts with capital or quote, isn't too long)
                            # Include both straight quotes (", ') and curly quotes (\u201c, \u201d, \u2018, \u2019)
                            if (not re.match(chapter_pattern, next_line) and
                                not re.match(standalone_roman_pattern, next_line) and
                                not re.match(section_pattern, next_line, re.IGNORECASE) and
                                len(next_line) > 3 and len(next_line) < ContentThresholds.MAX_CHAPTER_TITLE_LENGTH and
                                (next_line[0].isupper() or next_line[0] in '"\'\u201c\u201d\u2018\u2019')):
                                chapter_title = next_line
                                break
                            else:
                                # Hit a marker or prose, stop searching
                                break

                    # Convert numeral to number
                    if chapter_numeral.isdigit():
                        chapter_number = int(chapter_numeral)
                    elif chapter_numeral.lower() == "the last":
                        # Special case for "the last" - assign a placeholder number
                        # The actual chapter number will be determined by its position
                        chapter_number = 9999  # Placeholder for "the last"
                    else:
                        # Try spelled-out number first
                        chapter_number = self.word_to_int(chapter_numeral)
                        # If not a spelled-out number, try Roman numeral
                        if chapter_number == 0:
                            chapter_number = self.roman_to_int(chapter_numeral)

                    if chapter_number == 0:
                        continue

                    # Check if this chapter already exists in current section (avoid duplicates)
                    existing_chapter_nums = [ch['number'] for ch in current_section['chapters']]
                    if chapter_number in existing_chapter_nums:
                        continue

                    current_section['chapters'].append({
                        'number': chapter_number,
                        'numeral': chapter_numeral,
                        'title': chapter_title
                    })

        # Save last section (allow sections with 0 chapters - chapters might not be detected yet)
        if current_section:
            toc_structure.append(current_section)

        # Validation: Only return if we have a valid two-level structure
        if len(toc_structure) < 2:
            return None

        # Validation: Each section should have at least 2 chapters on average (for sections that have chapters)
        sections_with_chapters = [s for s in toc_structure if len(s['chapters']) > 0]
        total_chapters = sum(len(s['chapters']) for s in sections_with_chapters)

        if len(sections_with_chapters) == 0:
            # No chapters found in ANY section - this is not a valid 2-layer structure
            # The BOOKs/PARTs/ACTs are actually the chapters themselves (1-layer structure)
            # Example: Paradise Lost has "BOOK I", "BOOK II", etc. with no chapter markers
            return None

        # Validation: Each section should have at least 2 chapters on average
        avg_chapters_per_section = total_chapters / len(sections_with_chapters)
        if avg_chapters_per_section < 2:
            return None

        # Validation: Total chapters should be substantial (at least 10)
        if total_chapters < 10:
            return None

        print(f"  📖 Document body scan detected {len(toc_structure)} sections with {total_chapters} total chapters")
        for section in toc_structure[:3]:  # Show first 3 sections
            print(f"     • {section['type']} {section['numeral']}: {section['title'] or '(untitled)'} ({len(section['chapters'])} chapters)")
        if len(toc_structure) > 3:
            print(f"     • ... and {len(toc_structure) - 3} more sections")

        return toc_structure

    def extract_title_only_toc(self, text: str) -> List[str]:
        """
        Extract title-only table of contents (no chapter numbers).
        For books like "The King in Yellow" that use story titles without numbers.
        Returns list of story/chapter titles in order.
        """
        titles = []
        lines = text.split('\n')

        # Look for CONTENTS section
        in_toc = False
        consecutive_empty_lines = 0
        found_any_titles = False

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Start of TOC
            if re.match(r'^\s*CONTENTS[\.:]*\s*$', line_stripped, re.IGNORECASE):
                in_toc = True
                consecutive_empty_lines = 0
                continue

            # Track consecutive empty lines to detect section breaks
            if in_toc:
                if not line_stripped:
                    consecutive_empty_lines += 1
                    # If we've found some titles and hit 2+ consecutive empty lines, TOC is done
                    # This separates TOC from epigraphs/poetry that might follow
                    if found_any_titles and consecutive_empty_lines >= 2:
                        break
                    continue
                else:
                    consecutive_empty_lines = 0

                # Check if line looks like a title entry
                # Title-only entries are typically in ALL CAPS or Title Case
                # Must be substantial (>5 chars) and not too long (<60 chars)
                # Must not contain common non-title markers
                is_title = (
                    5 < len(line_stripped) < 60 and
                    not line_stripped.startswith('By ') and
                    not line_stripped.startswith('PART ') and
                    not line_stripped.startswith('BOOK ') and
                    not re.match(r'^[IVXLCDM]+\.', line_stripped) and  # Not numbered with Roman numerals
                    not re.match(r'^\d+\.', line_stripped) and  # Not numbered with Arabic numerals (e.g., "1. HOW THEY...")
                    not re.match(r'^(FIRST|SECOND|THIRD) STORY$', line_stripped, re.IGNORECASE) and  # Not "FIRST STORY", "SECOND STORY", etc.
                    not re.match(r'^Chapter', line_stripped, re.IGNORECASE) and
                    # Exclude lines that look like poetry (start with lowercase after quote, or end with comma)
                    not (line_stripped.startswith('"') and len(line_stripped) > 1 and line_stripped[1].islower()) and
                    not line_stripped.endswith(',')
                )

                if is_title:
                    # Strip trailing page numbers (e.g., "The Happy Prince                           1" -> "The Happy Prince")
                    # Page numbers are typically at the end, separated by whitespace
                    title_without_page = re.sub(r'\s+\d+\s*$', '', line_stripped).strip()
                    titles.append(title_without_page)
                    found_any_titles = True
                elif found_any_titles:
                    # After finding titles, if we hit a non-title line (poetry, etc.), stop
                    # This handles cases where there's no blank separator
                    if line_stripped and (line_stripped[0].islower() or line_stripped.startswith('"')):
                        break

        # Deduplicate titles while preserving order (dict keys maintain insertion order in Python 3.7+)
        return list(dict.fromkeys(titles))

    def _detect_chapters_from_toc_structure(self, text: str, toc_structure: List[Dict], toc_end_line: int, is_poetry: bool = False) -> Tuple[List[Tuple[int, str, str]], set]:
        """
        Detect chapters using a provided two-level structure (PART/BOOK/ACT → Chapters).

        Args:
            text: Full book text
            toc_structure: Two-level structure from extract_two_level_toc() or extract_two_level_structure_from_body()
            toc_end_line: Line number where TOC ends (unused for two-level structures, kept for API compat)
            is_poetry: If True, preserves line breaks in text normalization (for poetry)

        Returns:
            Tuple of (chapters, consumed_line_indices)

        Note: Chapter numbers are sequential (1, 2, 3, ..., 25) across all sections,
        not composite encoding (101, 201, 301). Chapter titles preserve the original
        section context (e.g., "THE TRAIL OF THE MEAT" not "Part I, Chapter I: ...").
        """
        lines = text.split('\n')
        chapters = []
        consumed_line_indices = set()

        # For two-level structures, start searching after TOC (if detected) to avoid finding TOC entries
        # When toc_end_line is available, use it as the starting point to skip the TOC section.
        # Even for VOLUME-based structures: if the body also contains the VOLUME markers
        # (possibly with a different numeral system), we must search past the TOC to find
        # the real body markers (pg3268 Mysteries of Udolpho has TOC 'VOLUME I' but body
        # 'VOLUME 1'). The numeral alternation built below matches both forms.
        is_volume_structure = len(toc_structure) > 0 and toc_structure[0]['type'] == 'VOLUME'
        search_start_line = toc_end_line if toc_end_line > 0 else 0

        # Sequential chapter counter across all sections (1, 2, 3, ...)
        sequential_chapter_num = 1

        # Check for preface/introduction before the first section
        # Capture all content from beginning up to first chapter/section
        # Find the first section start line by searching for it in the body
        first_section = toc_structure[0] if toc_structure else None
        first_section_line = len(lines)  # Default to end of file if not found

        if first_section:
            # Use line_index if available (from extract_story_collection_toc or body scan)
            if 'line_index' in first_section:
                first_section_line = first_section['line_index']
                print(f"  Using first section from line_index at line {first_section_line}")
            else:
                # Search for the first section in the body (starting after TOC)
                section_search_start = toc_end_line if toc_end_line > 0 else 0

                # Special handling for VOLUME structures: search for first CHAPTER instead of VOLUME marker
                # The VOLUME marker is just a heading, actual content starts at first chapter
                if first_section['type'] == 'VOLUME' and len(first_section.get('chapters', [])) > 0:
                    # Search for the first body CHAPTER marker. Accept Roman or Arabic '1/I',
                    # with optional trailing period. pg3268's body uses 'CHAPTER I' (no period).
                    first_chapter_pattern = r'^\s*CHAPTER\s+(?:I|1)\.?\s*$'
                    for i in range(section_search_start, len(lines)):
                        if re.match(first_chapter_pattern, lines[i], re.IGNORECASE):
                            first_section_line = i
                            break
                elif first_section['type'] == 'STORY':
                    # Story collection - use title-based search
                    if first_section['title']:
                        title_escaped = re.escape(first_section['title'])
                        # Allow optional period at end
                        story_pattern = rf'^\s*{title_escaped}\.?\s*$'
                        for i in range(section_search_start, len(lines)):
                            if re.match(story_pattern, lines[i].strip(), re.IGNORECASE):
                                # Verify this is the actual story start
                                has_content = False
                                for lookahead in range(i + 1, min(i + 20, len(lines))):
                                    lookahead_line = lines[lookahead].strip()
                                    if lookahead_line and (len(lookahead_line) > 40 or lookahead_line.startswith('[Picture:')):
                                        has_content = True
                                        break
                                if has_content:
                                    first_section_line = i
                                    print(f"  Found first STORY \"{first_section['title']}\" at line {i}")
                                    break
                else:
                    # Build pattern to match section marker (with or without title)
                    # Matches: "BOOK I", "BOOK I.", "BOOK I. Title", "BOOK I: Title"
                    # Also matches: "Book the First", "Book the Second" (A Tale of Two Cities)
                    # Also matches reversed format: "FIRST ACT", etc.
                    # IMPORTANT: Always try without title first, as title may be on a separate line
                    # Match just "TYPE NUMERAL" (no title), with optional "the" between
                    # IMPORTANT: Match BOTH the numeral form from TOC AND any equivalent
                    # numeral form. The TOC might list "VOLUME I" (Roman) while body has
                    # "VOLUME 1" (Arabic) — pg3268 case. Build an alternation that accepts
                    # any equivalent representation of first_section['number'].
                    numeral_alt = self._build_numeral_alternation(
                        first_section.get("number", 0), first_section.get("numeral", "")
                    )
                    first_section_pattern = rf'^\s*{first_section["type"]}\s+(?:the\s+)?(?:{numeral_alt})\.?\s*$'
                    reversed_section_pattern = rf'^\s*(?:{numeral_alt})\s+{first_section["type"]}\.?\s*$'
                    # Also create pattern WITH title for exact matching (as fallback)
                    if first_section['title']:
                        title_escaped = re.escape(first_section['title'])
                        first_section_pattern_with_title = rf'^\s*{first_section["type"]}\s+(?:the\s+)?(?:{numeral_alt})\.?\s*[:—-]?\s*{title_escaped}\s*$'
                        reversed_section_pattern_with_title = rf'^\s*(?:{numeral_alt})\s+{first_section["type"]}\.?\s*[:—-]?\s*{title_escaped}\s*$'
                    else:
                        first_section_pattern_with_title = None
                        reversed_section_pattern_with_title = None

                    for i in range(section_search_start, len(lines)):
                        # Try pattern without title first (most common case)
                        if re.match(first_section_pattern, lines[i], re.IGNORECASE):
                            first_section_line = i
                            break
                        # Try reversed pattern (NUMERAL TYPE format)
                        elif re.match(reversed_section_pattern, lines[i], re.IGNORECASE):
                            first_section_line = i
                            break
                        # Try pattern with title (fallback for when title is on same line)
                        elif first_section_pattern_with_title and re.match(first_section_pattern_with_title, lines[i], re.IGNORECASE):
                            first_section_line = i
                            break
                        elif reversed_section_pattern_with_title and re.match(reversed_section_pattern_with_title, lines[i], re.IGNORECASE):
                            first_section_line = i
                            break

        # Start after TOC to skip title page and table of contents
        # Uses existing TOC detection to find where actual content begins
        # Safety check: if toc_end_line is after first_section_line, TOC detection failed - start from 0
        if toc_end_line > 0 and toc_end_line < first_section_line:
            preface_start = toc_end_line
        else:
            preface_start = 0
        preface_end = first_section_line

        print(f"  Searching for preface in lines {preface_start}-{preface_end} (TOC ends at {toc_end_line}, first section at line {first_section_line})")

        # Extract content from TOC end to first section
        if preface_end > preface_start:
            preface_text = '\n'.join(lines[preface_start:preface_end])

            # Normalize text formatting (same as regular chapters)
            preface_text = self.normalize_chapter_text(preface_text, is_poetry)

            preface_words = len(preface_text.split())

            # Only include if substantial (>MIN_PREFACE_WORDS)
            if preface_words > ContentThresholds.MIN_PREFACE_WORDS:
                # Try to extract the actual preface marker from the text as title
                # Look for patterns like "PRELUDE", "TRANSLATOR'S PREFACE", "INTRODUCTION", etc.
                preface_marker_patterns = [
                    r'^\s*(TRANSLATOR[\'\']S PREFACE|PRELUDE|PREFACE|INTRODUCTION|PROLOGUE)\.?\s*$',
                ]
                preface_title = "Preface"  # Default fallback
                for line in lines[preface_start:preface_end]:
                    for pattern in preface_marker_patterns:
                        match = re.match(pattern, line.strip(), re.IGNORECASE)
                        if match:
                            # Found a preface marker - use it as the title
                            preface_title = match.group(1).title()  # Capitalize first letter of each word
                            preface_title = fix_roman_numerals_in_text(preface_title)  # Fix any title-cased Roman numerals
                            print(f"  Found preface marker: {preface_title}")
                            break
                    if preface_title != "Preface":
                        break
                chapters.append((0, preface_title, preface_text))
                for idx in range(preface_start, preface_end):
                    consumed_line_indices.add(idx)
                print(f"  ✓ Created Chapter 0 ({preface_title}): {len(preface_text)} chars, ~{preface_words} words")
                sequential_chapter_num = 1  # Chapters start at 1 after preface
            else:
                print(f"  Preface content too short ({preface_words} words), skipping")
        else:
            print(f"  No preface content found (first section starts at beginning)")

        # Build list of expected chapter markers from the structure
        # For each PART/BOOK/ACT, use the line_index from the structure (if available)
        for section in toc_structure:
            section_type = section['type']
            section_number = section['number']
            section_numeral = section['numeral']
            section_title = section['title']

            # Use line_index from structure if available (from body scan)
            # Otherwise search for the section marker (from TOC scan)
            if 'line_index' in section:
                section_start_line = section['line_index']
                print(f"  Using {section_type} {section_numeral} from body scan at line {section_start_line}")
            else:
                # Fallback: search for section marker
                # Build pattern to match section (with or without numeral)
                if section_type == 'STORY':
                    # Story collection - match story title (may end with period)
                    if section_title:
                        title_escaped = re.escape(section_title)
                        # Try both with and without period
                        section_pattern = rf'^\s*{title_escaped}\.?\s*$'
                    else:
                        section_pattern = None
                    decorative_pattern = None
                    reversed_pattern = None
                    section_pattern_with_title = None
                    reversed_pattern_with_title = None
                elif section_type in ['EPILOGUE', 'PROLOGUE']:
                    # Unnumbered sections - match just the type (no numeral)
                    if section_title:
                        title_escaped = re.escape(section_title)
                        section_pattern = rf'^\s*{section_type}\.?\s*[:—-]?\s*{title_escaped}\s*$'
                    else:
                        section_pattern = rf'^\s*{section_type}\.?\s*$'
                    decorative_pattern = None  # No decorative pattern for epilogue/prologue
                    reversed_pattern = None
                    section_pattern_with_title = None
                    reversed_pattern_with_title = None
                else:
                    # Numbered sections - "BOOK I", "BOOK I. Title", etc.
                    # Also matches: "Book the First", "Book the Second" (A Tale of Two Cities)
                    # Also support reversed format for plays: "FIRST ACT", "SECOND ACT", etc.
                    # IMPORTANT: Always try without title first, as title may be on a separate line
                    # IMPORTANT: Match BOTH the TOC numeral and any equivalent representation
                    # (Roman/Arabic) — TOC may use 'VOLUME I' but body uses 'VOLUME 1' (pg3268).
                    numeral_alt = self._build_numeral_alternation(
                        section.get('number', 0), section_numeral
                    )
                    # Match just "TYPE NUMERAL" (no title) with optional trailing period, with optional "the" between
                    section_pattern = rf'^\s*{section_type}\s+(?:the\s+)?(?:{numeral_alt})\.?\s*$'
                    # Alternative: "NUMERAL TYPE" (for plays like "FIRST ACT")
                    reversed_pattern = rf'^\s*(?:{numeral_alt})\s+{section_type}\.?\s*$'
                    # Also create pattern WITH title for exact matching (as fallback)
                    if section_title:
                        title_escaped = re.escape(section_title)
                        section_pattern_with_title = rf'^\s*{section_type}\s+(?:the\s+)?(?:{numeral_alt})\.?\s*[:—-]?\s*{title_escaped}\s*$'
                        reversed_pattern_with_title = rf'^\s*(?:{numeral_alt})\s+{section_type}\.?\s*[:—-]?\s*{title_escaped}\s*$'
                    else:
                        section_pattern_with_title = None
                        reversed_pattern_with_title = None

                    # Also try decorative pattern (e.g., "— I —")
                    decorative_pattern = rf'^\s*—+\s*(?:{numeral_alt})\s*—+\s*$'

                section_start_line = None
                for i in range(search_start_line, len(lines)):
                    # Try pattern without title first (most common case)
                    if section_pattern and re.match(section_pattern, lines[i].strip() if section_type == 'STORY' else lines[i], re.IGNORECASE):
                        # For STORY type, verify this is the actual story start by checking for content
                        if section_type == 'STORY':
                            has_content = False
                            for lookahead in range(i + 1, min(i + 20, len(lines))):
                                lookahead_line = lines[lookahead].strip()
                                if lookahead_line and (len(lookahead_line) > 40 or lookahead_line.startswith('[Picture:')):
                                    has_content = True
                                    break
                            if not has_content:
                                continue  # This is likely a TOC entry, keep searching
                        section_start_line = i
                        print(f"  Found {section_type} {section_numeral} at line {i}")
                        break
                    # Try reversed pattern (NUMERAL TYPE format, like "FIRST ACT")
                    elif reversed_pattern and re.match(reversed_pattern, lines[i], re.IGNORECASE):
                        section_start_line = i
                        print(f"  Found {section_numeral} {section_type} at line {i}")
                        break
                    # Try decorative pattern (e.g., "— I —")
                    elif decorative_pattern and re.match(decorative_pattern, lines[i]):
                        section_start_line = i
                        print(f"  Found decorative {section_type} {section_numeral} at line {i}")
                        break
                    # Try pattern with title (fallback for when title is on same line)
                    elif section_pattern_with_title and re.match(section_pattern_with_title, lines[i], re.IGNORECASE):
                        section_start_line = i
                        print(f"  Found {section_type} {section_numeral} with title at line {i}")
                        break
                    elif reversed_pattern_with_title and re.match(reversed_pattern_with_title, lines[i], re.IGNORECASE):
                        section_start_line = i
                        print(f"  Found {section_numeral} {section_type} with title at line {i}")
                        break

                if section_start_line is None:
                    print(f"  ⚠️  Warning: Could not find {section_type} {section_numeral} in document body")
                    continue

            # For VOLUME structures: Use the actual chapter boundary from previous VOLUME (if any)
            # to avoid searching duplicate chapters
            if section_type == 'VOLUME':
                current_section_idx_for_vol = toc_structure.index(section)
                if current_section_idx_for_vol > 0:
                    prev_section = toc_structure[current_section_idx_for_vol - 1]
                    if prev_section['type'] == 'VOLUME' and 'actual_end_line' in prev_section:
                        # Start searching from where previous VOLUME ended
                        section_start_line = prev_section['actual_end_line']
                        print(f"  Starting {section_type} {section_numeral} search from line {section_start_line} (after previous VOLUME)")
                # Otherwise, keep section_start_line as the VOLUME marker position

            # Determine where this section ends (for chapter boundary detection)
            section_end_line = len(lines)
            current_section_idx = toc_structure.index(section)
            next_section = None  # Initialize to None for last section
            if current_section_idx + 1 < len(toc_structure):
                # Find the next section to determine where this section ends
                next_section = toc_structure[current_section_idx + 1]

                # Build pattern to match next section (with or without numeral)
                if next_section['type'] == 'STORY':
                    # Story collection - match story title (may end with period)
                    # Use line_index if available (from extract_story_collection_toc)
                    if 'line_index' in next_section:
                        section_end_line = next_section['line_index']
                        print(f"  Using next STORY boundary at line {section_end_line} (from line_index)")
                    elif next_section['title']:
                        # Search for the story title in the body
                        # Match "Title" or "Title."
                        next_title_escaped = re.escape(next_section['title'])
                        # Try both with and without period
                        next_section_pattern = rf'^\s*{next_title_escaped}\.?\s*$'

                        # Start searching after current section start to avoid TOC matches
                        search_from = max(section_start_line + 1, toc_end_line)
                        for i in range(search_from, len(lines)):
                            if re.match(next_section_pattern, lines[i].strip(), re.IGNORECASE):
                                # Verify this is the actual story start by checking for content after
                                has_content = False
                                for lookahead in range(i + 1, min(i + 20, len(lines))):
                                    lookahead_line = lines[lookahead].strip()
                                    # Check for paragraph content or illustration markers
                                    if lookahead_line and (len(lookahead_line) > 40 or lookahead_line.startswith('[Picture:')):
                                        has_content = True
                                        break
                                if has_content:
                                    section_end_line = i
                                    print(f"  Found next STORY \"{next_section['title']}\" at line {i}")
                                    break
                    next_decorative_pattern = None
                    next_reversed_pattern = None
                    next_section_pattern_with_title = None
                    next_reversed_pattern_with_title = None
                elif next_section['type'] in ['EPILOGUE', 'PROLOGUE']:
                    # Unnumbered section - match just the type
                    if next_section['title']:
                        next_title_escaped = re.escape(next_section['title'])
                        next_section_pattern = rf'^\s*{next_section["type"]}\.?\s*[:—-]?\s*{next_title_escaped}\s*$'
                    else:
                        next_section_pattern = rf'^\s*{next_section["type"]}\.?\s*$'
                    next_decorative_pattern = None
                    next_reversed_pattern = None
                    next_section_pattern_with_title = None
                    next_reversed_pattern_with_title = None
                else:
                    # Numbered section - "BOOK II", "BOOK II. Title", etc.
                    # Also matches: "Book the Second", "Book the Third" (A Tale of Two Cities)
                    # Also support reversed format for plays: "SECOND ACT", etc.
                    # IMPORTANT: Always try without title first, as title may be on a separate line
                    # IMPORTANT: Match Roman/Arabic equivalent numerals (pg3268: TOC 'VOLUME II' but body 'VOLUME 2').
                    next_numeral_alt = self._build_numeral_alternation(
                        next_section.get('number', 0), next_section.get('numeral', '')
                    )
                    next_section_pattern = rf'^\s*{next_section["type"]}\s+(?:the\s+)?(?:{next_numeral_alt})\.?\s*$'
                    next_reversed_pattern = rf'^\s*(?:{next_numeral_alt})\s+{next_section["type"]}\.?\s*$'
                    # Also create pattern WITH title for exact matching (as fallback)
                    if next_section['title']:
                        next_title_escaped = re.escape(next_section['title'])
                        next_section_pattern_with_title = rf'^\s*{next_section["type"]}\s+(?:the\s+)?(?:{next_numeral_alt})\.?\s*[:—-]?\s*{next_title_escaped}\s*$'
                        next_reversed_pattern_with_title = rf'^\s*(?:{next_numeral_alt})\s+{next_section["type"]}\.?\s*[:—-]?\s*{next_title_escaped}\s*$'
                    else:
                        next_section_pattern_with_title = None
                        next_reversed_pattern_with_title = None
                    next_decorative_pattern = rf'^\s*—+\s*(?:{next_numeral_alt})\s*—+\s*$'

                # Start searching after TOC to avoid finding section markers in the TOC
                # (Skip this search if we already found section_end_line for STORY type)
                if next_section['type'] != 'STORY' or section_end_line == len(lines):
                    search_from = max(section_start_line + 1, toc_end_line)
                    for i in range(search_from, len(lines)):
                        # Try pattern without title first (most common case - title on separate line)
                        if re.match(next_section_pattern, lines[i], re.IGNORECASE):
                            section_end_line = i
                            break
                        # Try reversed pattern (NUMERAL TYPE format, like "FIRST ACT")
                        elif next_reversed_pattern and re.match(next_reversed_pattern, lines[i], re.IGNORECASE):
                            section_end_line = i
                            break
                        # Try decorative pattern (e.g., "— II —")
                        elif next_decorative_pattern and re.match(next_decorative_pattern, lines[i]):
                            section_end_line = i
                            break
                        # Try pattern with title (fallback for when title is on same line)
                        elif next_section_pattern_with_title and re.match(next_section_pattern_with_title, lines[i], re.IGNORECASE):
                            section_end_line = i
                            break
                        elif next_reversed_pattern_with_title and re.match(next_reversed_pattern_with_title, lines[i], re.IGNORECASE):
                            section_end_line = i
                            break

            # Special handling for VOLUME sections: Scan for ALL chapters directly in the body
            # Don't rely on TOC as it may be incomplete for multi-volume works
            if section_type == 'VOLUME':
                print(f"  Scanning for all chapters in {section_type} {section_numeral} body...")
                # Scan for all CHAPTER patterns from section start to section end
                found_chapters = []

                # Pattern to match: "CHAPTER <roman_numeral>."
                chapter_pattern = r'^\s*CHAPTER\s+([IVXLCDM]+)\.'

                # For VOLUME I: scan until we find CHAPTER I. again (start of VOLUME II)
                # For other VOLUMEs: scan until end or next VOLUME's CHAPTER I.
                scan_end = section_end_line
                if section_numeral == 'I':
                    # Find the SECOND occurrence of "CHAPTER I." (first is VOLUME I, second is VOLUME II)
                    chapter_i_pattern = r'^\s*CHAPTER\s+I\.'
                    chapter_i_count = 0
                    for i in range(section_start_line, len(lines)):
                        if re.match(chapter_i_pattern, lines[i], re.IGNORECASE):
                            chapter_i_count += 1
                            if chapter_i_count == 2:
                                # Found start of VOLUME II
                                scan_end = i
                                print(f"  Adjusted VOLUME I end to line {i} (VOLUME II's CHAPTER I.)")
                                break

                print(f"  Scan range: lines {section_start_line} to {scan_end} ({scan_end - section_start_line} lines)")

                for scan_line_idx in range(section_start_line, scan_end):
                    match = re.match(chapter_pattern, lines[scan_line_idx], re.IGNORECASE)
                    if match:
                        roman_numeral = match.group(1)
                        # Convert Roman numeral to number
                        chapter_number = self.roman_to_int(roman_numeral)

                        # Extract title from same line or next few lines
                        title = ""
                        # Check if title is on same line after the numeral
                        remaining_text = lines[scan_line_idx][match.end():].strip()
                        if remaining_text:
                            title = remaining_text
                        # Otherwise check next few lines for title
                        elif scan_line_idx + 1 < len(lines):
                            # Continue collecting title lines until blank line or paragraph start
                            title_lines = []
                            for j in range(1, min(6, len(lines) - scan_line_idx)):
                                next_line = lines[scan_line_idx + j].strip()
                                # Stop at blank line or start of paragraph
                                if not next_line or next_line.startswith('In a'):
                                    break
                                # Stop at next chapter marker
                                if next_line.startswith('CHAPTER'):
                                    break
                                # Collect title line if it looks like a title (all caps or long enough)
                                if next_line.isupper() or (len(next_line) > 10 and not title_lines):
                                    title_lines.append(next_line)
                                # Continue collecting if previous line looked like a title
                                elif title_lines and next_line.isupper():
                                    title_lines.append(next_line)
                                else:
                                    break

                            if title_lines:
                                title = ' '.join(title_lines)

                        found_chapters.append({
                            'number': chapter_number,
                            'numeral': roman_numeral,
                            'title': title,
                            'line': scan_line_idx
                        })

                if found_chapters:
                    print(f"  Found {len(found_chapters)} chapters in {section_type} {section_numeral} body")
                    # Replace section['chapters'] with found chapters (with actual line positions)
                    section['chapters'] = found_chapters

                    # Now determine actual section_end_line from chapter positions:
                    # For VOLUME I, end is where VOLUME II's first chapter starts
                    # For last VOLUME, end is end of document
                    if next_section and next_section['type'] == 'VOLUME' and len(next_section.get('chapters', [])) > 0:
                        # Search for next volume's first chapter (CHAPTER I.)
                        # This will be the boundary
                        next_vol_first_chapter_pattern = r'^\s*CHAPTER\s+I\.'
                        # Start searching from last chapter of current volume
                        search_from = found_chapters[-1]['line'] + 100  # Start 100 lines after last chapter
                        for scan_line_idx in range(search_from, len(lines)):
                            if re.match(next_vol_first_chapter_pattern, lines[scan_line_idx], re.IGNORECASE):
                                section_end_line = scan_line_idx
                                print(f"  Adjusted {section_type} {section_numeral} end to line {scan_line_idx} (next VOLUME's CHAPTER I.)")
                                # Save this boundary for next VOLUME to use
                                section['actual_end_line'] = section_end_line
                                break

                    # For the last VOLUME, check for epilogue content
                    # NOTE: For Don Quixote, the epilogue "And said most sage Cide Hamete to his pen..."
                    # is an essential part of the narrative and should be INCLUDED, not excluded.
                    # The epilogue exclusion logic below is disabled for now as it was removing
                    # important literary content. If we need to exclude appendices/notes in the future,
                    # we should be more selective about what patterns to match.
                    if False:  # Disabled epilogue exclusion
                        if not next_section or next_section['type'] != 'VOLUME':
                            # This is the last VOLUME - check for epilogue markers
                            print(f"  Checking for epilogue after last chapter of {section_type} {section_numeral}...")
                            # Common epilogue patterns that indicate post-story content
                            epilogue_patterns = [
                                # r'^\s*And said most sage',  # Don Quixote epilogue - SHOULD BE INCLUDED
                                r'^\s*APPENDIX\s*$',
                                r'^\s*NOTES?\s*$',
                            ]

                            # Search backwards from end of document to find epilogue
                            # Start from last chapter and search forward
                            search_from = found_chapters[-1]['line'] + 50  # Start 50 lines after last chapter
                            print(f"  Searching for epilogue from line {search_from} to {len(lines)}")
                            for scan_line_idx in range(search_from, len(lines)):
                                for pattern in epilogue_patterns:
                                    if re.match(pattern, lines[scan_line_idx], re.IGNORECASE):
                                        section_end_line = scan_line_idx
                                        print(f"  Adjusted {section_type} {section_numeral} end to line {scan_line_idx} (epilogue detected)")
                                        section['actual_end_line'] = section_end_line
                                        break
                                if section_end_line < len(lines):
                                    break  # Found epilogue, stop searching
                            if section_end_line == len(lines):
                                print(f"  No epilogue detected, section extends to end of document (line {len(lines)})")

                    # Mark this section as VOLUME so we can skip the normal chapter detection
                    section['_volume_chapters_already_found'] = True
                else:
                    print(f"  ⚠️  Warning: Could not find any TOC chapters in {section_type} {section_numeral} body")

            # Handle sections with no chapters: create an implicit chapter
            if len(section['chapters']) == 0:
                # Create implicit chapter covering the entire section
                # Find where content starts (skip section marker line and blank lines)
                implicit_chapter_start = section_start_line
                for i in range(section_start_line + 1, min(section_start_line + 10, section_end_line)):
                    # Skip blank lines and very short lines (likely just "SCENE" or similar markers)
                    # But include lines >= 20 chars (like scene descriptions: "Morning-room at the Manor House.")
                    if lines[i].strip() and len(lines[i].strip()) >= 20:
                        implicit_chapter_start = i
                        break

                # Extract content from chapter start to section end
                chapter_lines = lines[implicit_chapter_start:section_end_line]
                chapter_text = '\n'.join(chapter_lines)
                chapter_text = self.normalize_chapter_text(chapter_text, is_poetry)

                if len(chapter_text) > ContentThresholds.MIN_CHAPTER_CHARS_V1:
                    # Determine the chapter title:
                    # If section_title looks like content (not an explicit title), use format "{Type} {Numeral}"
                    # E.g., Paradise Lost has "Book I" with no title, but TOC parsing picked up the first
                    # line of content "Of Man's first disobedience..." as the title
                    # Heuristic: If title starts with common sentence words or contains sentence punctuation,
                    # it's probably content rather than a real title
                    if section_title and section_title.strip():
                        # Check if title looks like the start of a sentence (content) rather than a real title
                        title_lower = section_title.lower()
                        # Common words that start sentences but rarely start real titles
                        content_indicators = ['of ', 'in ', 'on ', 'at ', 'for ', 'and ', 'but ', 'or ', 'as ', 'if ', 'when ', 'while ', 'which ', 'who ', 'what ', 'how ', 'why ']
                        starts_like_sentence = any(title_lower.startswith(indicator) for indicator in content_indicators)
                        # Check for sentence-like punctuation (commas, semicolons, lowercase after apostrophe)
                        has_sentence_punctuation = ',' in section_title or ';' in section_title or "'s " in section_title.lower()

                        if starts_like_sentence or has_sentence_punctuation:
                            # Use format "{Type} {Numeral}" instead
                            normalized_title = f"{section_type.capitalize()} {section_numeral}"
                        else:
                            # Use the section title as-is
                            normalized_title = self.normalize_chapter_title(section_title)
                    else:
                        # No title - use format "{Type} {Numeral}"
                        normalized_title = f"{section_type.capitalize()} {section_numeral}"

                    chapters.append((sequential_chapter_num, normalized_title, chapter_text))
                    for i in range(implicit_chapter_start, section_end_line):
                        consumed_line_indices.add(i)
                    print(f"    ✓ Chapter {sequential_chapter_num}: {normalized_title or '(untitled)'} ({len(chapter_text)} chars) [implicit from {section_type}]")
                    sequential_chapter_num += 1

                continue  # Skip chapter detection loop for this section

            # For VOLUME sections where we've already found chapters using TOC, use those directly
            if section.get('_volume_chapters_already_found', False):
                # Chapters already have 'line' attribute with actual positions
                # Calculate boundaries using the line positions
                for idx, chapter_info in enumerate(section['chapters']):
                    chapter_start_line = chapter_info['line']
                    # End is the start of next chapter, or section end
                    if idx + 1 < len(section['chapters']):
                        chapter_end_line = section['chapters'][idx + 1]['line']
                    else:
                        chapter_end_line = section_end_line

                    # Extract chapter content
                    chapter_lines = lines[chapter_start_line:chapter_end_line]
                    chapter_text = '\n'.join(chapter_lines)
                    chapter_text = self.normalize_chapter_text(chapter_text, is_poetry)

                    if len(chapter_text) > ContentThresholds.MIN_CHAPTER_CHARS_V1:
                        normalized_title = self.normalize_chapter_title(chapter_info['title']) if chapter_info['title'] else ""
                        chapters.append((sequential_chapter_num, normalized_title, chapter_text))
                        # Mark all lines in this chapter as consumed
                        for i in range(chapter_start_line, chapter_end_line):
                            consumed_line_indices.add(i)
                        print(f"    ✓ Chapter {sequential_chapter_num}: {normalized_title[:50]} ({len(chapter_text)} chars)")
                        sequential_chapter_num += 1
                    else:
                        print(f"    ⚠️  Skipping Chapter {sequential_chapter_num} (too short: {len(chapter_text)} chars)")

                continue  # Skip normal chapter detection loop

            # Track how many chapters we find in this section
            chapters_before_section = len(chapters)

            # Now find each chapter within this section (between section_start_line and section_end_line)
            for chapter_info in section['chapters']:
                chapter_number = chapter_info['number']
                chapter_numeral = chapter_info['numeral']
                chapter_title = chapter_info['title']

                # Pattern to find this chapter
                # Try multiple patterns:
                # 1. "CHAPTER <numeral>" (e.g., White Fang: "CHAPTER I")
                # 2. Standalone "<numeral>" without period (e.g., Treasure Island: "I")
                # 3. Standalone "<numeral>." with period (e.g., War of the Worlds: "I.")
                # 4. Bracket format "[ <numeral> ]" (e.g., Ulysses: "[ 1 ]")
                # 5. "_Part <numeral>_" pattern (e.g., story collections)
                # 6. Centered roman numerals
                # 7. Special case: "Chapter the last" (e.g., Tom Jones)

                # Handle special case for "the last" as a chapter numeral
                if chapter_numeral.lower() == "the last":
                    # Match both "Chapter the last" and "CHAPTER THE LAST"
                    chapter_pattern_with_prefix = r'^\s*(?:CHAPTER|Chapter)\s+the\s+last\.?\s*'
                    chapter_pattern_standalone = None
                    chapter_pattern_standalone_with_period = None
                    chapter_pattern_bracket = None
                    chapter_pattern_part = None
                    chapter_pattern_centered_roman = None
                else:
                    chapter_pattern_with_prefix = rf'^\s*(?:CHAPTER|Chapter)\s+{chapter_numeral}\.?\s*'
                    chapter_pattern_standalone = rf'^\s*{chapter_numeral}\s*$'
                    chapter_pattern_standalone_with_period = rf'^\s*{chapter_numeral}\.\s*$'
                    chapter_pattern_bracket = rf'^\s*\[\s*{chapter_numeral}\s*\]\s*$'
                    # Always try "_Part <numeral>_" pattern and centered roman numerals (all section types)
                    chapter_pattern_part = rf'^\s*_Part\s+{chapter_numeral}_\s*$'
                    chapter_pattern_centered_roman = rf'^\s+{chapter_numeral}\s*$'

                # Find where this chapter starts (between section start and section end)
                chapter_start_line = None
                for i in range(section_start_line + 1, section_end_line):
                    if re.match(chapter_pattern_with_prefix, lines[i], re.IGNORECASE):
                        chapter_start_line = i
                        break
                    if chapter_pattern_standalone and re.match(chapter_pattern_standalone, lines[i]):
                        chapter_start_line = i
                        break
                    if chapter_pattern_standalone_with_period and re.match(chapter_pattern_standalone_with_period, lines[i]):
                        chapter_start_line = i
                        break
                    if chapter_pattern_bracket and re.match(chapter_pattern_bracket, lines[i]):
                        chapter_start_line = i
                        break
                    if chapter_pattern_part and re.match(chapter_pattern_part, lines[i], re.IGNORECASE):
                        chapter_start_line = i
                        break
                    if chapter_pattern_centered_roman and re.match(chapter_pattern_centered_roman, lines[i]):
                        chapter_start_line = i
                        break

                if chapter_start_line is None:
                    print(f"    ⚠️  Warning: Could not find Chapter {chapter_numeral} in {section_type} {section_numeral}")
                    continue

                # Determine where this chapter ends
                # It ends at the start of the next chapter in this section, or the next section, or section end
                chapter_end_line = section_end_line

                # Find the next chapter in this section
                current_chapter_idx = section['chapters'].index(chapter_info)
                if current_chapter_idx + 1 < len(section['chapters']):
                    # There's a next chapter in this section
                    next_chapter_info = section['chapters'][current_chapter_idx + 1]
                    next_chapter_numeral = next_chapter_info['numeral']

                    # Handle special case for "the last" as a chapter numeral
                    if next_chapter_numeral.lower() == "the last":
                        next_chapter_pattern_with_prefix = r'^\s*(?:CHAPTER|Chapter)\s+the\s+last\.?\s*'
                        next_chapter_pattern_standalone = None
                        next_chapter_pattern_standalone_with_period = None
                        next_chapter_pattern_bracket = None
                        next_chapter_pattern_part = None
                        next_chapter_pattern_centered_roman = None
                    else:
                        next_chapter_pattern_with_prefix = rf'^\s*(?:CHAPTER|Chapter)\s+{next_chapter_numeral}\.?\s*'
                        next_chapter_pattern_standalone = rf'^\s*{next_chapter_numeral}\s*$'
                        next_chapter_pattern_standalone_with_period = rf'^\s*{next_chapter_numeral}\.\s*$'
                        next_chapter_pattern_bracket = rf'^\s*\[\s*{next_chapter_numeral}\s*\]\s*$'
                        # Always try "_Part <numeral>_" and centered roman numerals (all section types)
                        next_chapter_pattern_part = rf'^\s*_Part\s+{next_chapter_numeral}_\s*$'
                        next_chapter_pattern_centered_roman = rf'^\s+{next_chapter_numeral}\s*$'

                    for i in range(chapter_start_line + 1, section_end_line):
                        if re.match(next_chapter_pattern_with_prefix, lines[i], re.IGNORECASE):
                            chapter_end_line = i
                            break
                        if next_chapter_pattern_standalone and re.match(next_chapter_pattern_standalone, lines[i]):
                            chapter_end_line = i
                            break
                        if next_chapter_pattern_standalone_with_period and re.match(next_chapter_pattern_standalone_with_period, lines[i]):
                            chapter_end_line = i
                            break
                        if next_chapter_pattern_bracket and re.match(next_chapter_pattern_bracket, lines[i]):
                            chapter_end_line = i
                            break
                        if next_chapter_pattern_part and re.match(next_chapter_pattern_part, lines[i], re.IGNORECASE):
                            chapter_end_line = i
                            break
                        if next_chapter_pattern_centered_roman and re.match(next_chapter_pattern_centered_roman, lines[i]):
                            chapter_end_line = i
                            break

                # Extract chapter text (skip the chapter marker line itself)
                chapter_lines = lines[chapter_start_line + 1:chapter_end_line]
                chapter_text = '\n'.join(chapter_lines)

                # Normalize the chapter text
                chapter_text = self.normalize_chapter_text(chapter_text, is_poetry)

                # Only add if substantial content (> MIN_CHAPTER_CHARS)
                if len(chapter_text) > ContentThresholds.MIN_CHAPTER_CHARS_V1:
                    # Use sequential numbering (1, 2, 3, ...) across all sections

                    # NOTE: Skip "looks like a sentence" validation here because chapter_title
                    # comes from TOC (chapter_info['title']), which is already a reliable source.
                    # We should trust the TOC and not second-guess it.

                    # If no title at all, use "Chapter {number}" as default
                    if not chapter_title or not chapter_title.strip():
                        chapter_title = f"Chapter {chapter_number}"

                    # Normalize chapter title for consistent capitalization
                    normalized_title = self.normalize_chapter_title(chapter_title)
                    # Fix any title-cased Roman numerals (e.g., "Part Ii" -> "Part II")
                    normalized_title = fix_roman_numerals_in_text(normalized_title)
                    chapters.append((sequential_chapter_num, normalized_title, chapter_text))
                    # Mark all lines as consumed
                    for i in range(chapter_start_line, chapter_end_line):
                        consumed_line_indices.add(i)
                    print(f"    ✓ Chapter {sequential_chapter_num}: {chapter_title} ({len(chapter_text)} chars)")
                    sequential_chapter_num += 1

            # Check if any chapters were actually found for this section
            # Compare chapter count before and after processing this section
            chapters_after_section = len(chapters)
            chapters_added = chapters_after_section - chapters_before_section

            if chapters_added == 0 and len(section['chapters']) > 0:
                # No chapters were found but TOC said there should be chapters
                # Create implicit chapter using section title
                implicit_chapter_start = section_start_line
                for i in range(section_start_line + 1, min(section_start_line + 10, section_end_line)):
                    # Skip blank lines and section title, find first paragraph
                    if lines[i].strip() and len(lines[i].strip()) > 40:
                        implicit_chapter_start = i
                        break

                # Extract content from chapter start to section end
                chapter_lines = lines[implicit_chapter_start:section_end_line]
                chapter_text = '\n'.join(chapter_lines)
                chapter_text = self.normalize_chapter_text(chapter_text, is_poetry)

                if len(chapter_text) > ContentThresholds.MIN_CHAPTER_CHARS_V1:
                    # Determine the chapter title:
                    # If section_title looks like content (not an explicit title), use format "{Type} {Numeral}"
                    if section_title and section_title.strip():
                        # Check if title looks like the start of a sentence (content) rather than a real title
                        title_lower = section_title.lower()
                        # Common words that start sentences but rarely start real titles
                        content_indicators = ['of ', 'in ', 'on ', 'at ', 'for ', 'and ', 'but ', 'or ', 'as ', 'if ', 'when ', 'while ', 'which ', 'who ', 'what ', 'how ', 'why ']
                        starts_like_sentence = any(title_lower.startswith(indicator) for indicator in content_indicators)
                        # Check for sentence-like punctuation (commas, semicolons, lowercase after apostrophe)
                        has_sentence_punctuation = ',' in section_title or ';' in section_title or "'s " in section_title.lower()

                        if starts_like_sentence or has_sentence_punctuation:
                            # Use format "{Type} {Numeral}" instead
                            normalized_title = f"{section_type.capitalize()} {section_numeral}"
                        else:
                            # Use the section title as-is
                            normalized_title = self.normalize_chapter_title(section_title)
                    else:
                        # No title - use format "{Type} {Numeral}"
                        normalized_title = f"{section_type.capitalize()} {section_numeral}"

                    chapters.append((sequential_chapter_num, normalized_title, chapter_text))
                    for i in range(implicit_chapter_start, section_end_line):
                        consumed_line_indices.add(i)
                    print(f"    ✓ Chapter {sequential_chapter_num}: {normalized_title or '(untitled)'} ({len(chapter_text)} chars) [implicit - no markers found]")
                    sequential_chapter_num += 1

            # Update search start position for next section
            # Start searching after this section to avoid finding it again
            search_start_line = section_start_line + 1

        return chapters, consumed_line_indices

    def detect_chapters(self, text: str, toc_structure: List[Dict] = None, is_poetry: bool = False) -> Tuple[List[Tuple[int, str, str]], set]:
        """
        Detect chapters in the book text, skipping table of contents
        Supports nested book/chapter structure (e.g., "BOOK I", "BOOK II" with chapters)

        Args:
            text: Full book text
            toc_structure: Optional two-level structure from extract_two_level_toc() or extract_two_level_structure_from_body()
                          If provided, will use this structure to guide chapter detection
            is_poetry: If True, preserves line breaks in text normalization (for poetry)

        Returns (chapters, consumed_line_indices)
        - chapters: list of (chapter_number, chapter_title, chapter_text)
        - consumed_line_indices: set of line indices that were included in chapters
        Chapter numbers are encoded as: book_num * 100 + chapter_num (e.g., 101, 205, 312)
        """
        # Extract TOC for validation and get TOC end line
        toc, toc_end_line = self.extract_toc(text)
        if toc:
            print(f"Found TOC with {len(toc)} chapters")
        if toc_end_line > 0:
            print(f"TOC ends at line {toc_end_line}, will skip TOC section during chapter detection")

        # If we have a two-level structure (PART/BOOK/ACT with chapters), use it directly
        # This is more reliable than trying to re-detect the structure
        if toc_structure:
            print(f"Using provided two-level structure ({len(toc_structure)} sections) to detect chapters")
            return self._detect_chapters_from_toc_structure(text, toc_structure, toc_end_line, is_poetry)

        chapters = []

        # NEW APPROACH: Capture everything before Chapter 1, then filter out TOC and frontmatter
        # This is simpler and more robust than trying to detect specific preface patterns
        #
        # Strategy:
        # 1. Find the first numbered chapter (CHAPTER I, CHAPTER 1, etc.)
        # 2. Everything before that goes into the preface pool
        # 3. Filter out: TOC lines, illustration captions, title pages, copyright notices
        # 4. Keep: All prefaces, dedications, introductions, and substantive content

        all_lines = text.split('\n')

        # Patterns for first numbered chapter (not preface/introduction)
        first_chapter_patterns = [
            r'^\s*BOOK\s+(I|ONE|1)(?:[\.\s]|$)',
            r'^\s*CHAPTER\s+(I|ONE|1)(?:[\.\s]|$)',
            r'^\s*Chapter\s+(I|One|1)(?:[\.\s]|$)',
            r'^\s*PART\s+(I|ONE|1)(?:[\.\s]|$)',
            r'^\s*STAVE\s+(I|ONE|1)(?:[\.\s]|$)',
            r'^\s*SCENE\s+(I|ONE|1)(?:[\.\s]|$)',
            r'^\s*\[\s*1\s*\]\s*$',  # Bracket format: "[1]" - must be standalone on line (not a footnote marker)
            r'^\s*I\.\s+',  # Roman numeral with period: "I. Title"
        ]

        # Find the line where Chapter 1 starts (skipping TOC entries)
        # Use toc_end_line if available (more reliable than manual TOC detection)
        first_chapter_line = None
        search_start = toc_end_line + 1 if toc_end_line > 0 else 0

        for i in range(search_start, len(all_lines)):
            line_stripped = all_lines[i].strip()

            # Now check for first chapter
            if any(re.match(pattern, line_stripped) for pattern in first_chapter_patterns):
                first_chapter_line = i
                print(f"Found first chapter at line {i}: '{line_stripped}'")
                break

        # If we didn't find Chapter 1, there's no preface to extract
        if first_chapter_line is None:
            print("No first chapter found - no preface extraction")
            initial_preface_text = []
            combined_preface_line_indices = set()
        else:
            # Extract all lines before Chapter 1
            preface_pool = all_lines[:first_chapter_line]

            # Filter out non-content lines
            # Strategy: Keep everything before first chapter EXCEPT:
            # 1. TOC entries
            # 2. Illustration captions
            # 3. Title page boilerplate
            filtered_preface_lines = []
            filtered_line_indices = set()

            in_toc = False
            in_illustration = False
            has_content = False  # Track if we've seen any actual content yet

            for i, line in enumerate(preface_pool):
                line_stripped = line.strip()

                # Skip empty lines at the start, but keep them once we have content
                if not line_stripped:
                    if has_content:  # Only keep if we already have content
                        filtered_preface_lines.append(line)
                        filtered_line_indices.add(i)
                    continue

                # Detect start of TOC
                if re.match(r'^\s*(CONTENTS?|TABLE OF CONTENTS|LIST OF CHAPTERS)\s*$', line_stripped, re.IGNORECASE):
                    in_toc = True
                    continue

                # Detect end of TOC (first substantive line after TOC that's not a chapter listing)
                if in_toc:
                    # Check if this looks like a TOC entry (chapter name with page number)
                    # or a TOC-related line (like "PAGE", "CHAPTER", section headers, etc.)
                    is_toc_entry = (
                        re.search(r'\d+\s*$', line_stripped) or  # Ends with page number
                        re.match(r'^(PAGE|CHAPTER|BOOK|PART|VOLUME|ACT|SCENE|STAVE|EPILOGUE|PREFACE|AUTHOR|DEDICATION|INTRODUCTION|PROLOGUE)\s*', line_stripped, re.IGNORECASE) or
                        re.match(r'^[IVXLCDM]+\.?\s+', line_stripped) or  # Roman numeral listing
                        re.match(r'^\d+\.?\s+', line_stripped) or  # Arabic numeral listing
                        len(line_stripped) < 3  # Very short lines in TOC
                    )

                    if not is_toc_entry:
                        in_toc = False
                        # Don't skip this line - it's the start of real content
                    else:
                        continue  # Skip TOC entries

                # Handle illustration captions
                if line_stripped.startswith('[Illustration'):
                    in_illustration = True
                    if ']' in line_stripped:
                        in_illustration = False
                    continue

                if in_illustration:
                    if ']' in line_stripped:
                        in_illustration = False
                    continue

                # Skip title page elements (all caps, centered, short lines)
                # Only do this before we've seen real content (first 100 lines)
                # Be conservative - only skip obvious boilerplate, not actual content
                if not has_content and i < 100:
                    is_title_page_element = (
                        re.match(r'^BY\s*$', line_stripped, re.IGNORECASE) or
                        re.match(r'^Illustrated\.?$', line_stripped) or
                        re.match(r'^(BOSTON|LONDON|NEW YORK|CHICAGO|PHILADELPHIA):', line_stripped) or
                        re.match(r'^COPYRIGHT', line_stripped, re.IGNORECASE) or
                        re.match(r'^All rights reserved', line_stripped, re.IGNORECASE) or
                        re.match(r'^\d{4}\.?$', line_stripped)  # Just a year
                    )
                    if is_title_page_element:
                        continue

                # Keep this line as preface content
                filtered_preface_lines.append(line)
                filtered_line_indices.add(i)
                has_content = True

            initial_preface_text = filtered_preface_lines
            combined_preface_line_indices = filtered_line_indices

            if filtered_preface_lines:
                print(f"Extracted preface material: {len(filtered_preface_lines)} lines, {sum(len(l) for l in filtered_preface_lines)} chars")
            else:
                print("No preface material found before first chapter")

        # Pattern for BOOK/VOLUME/ACT markers (e.g., "BOOK I", "BOOK II", "BOOK ONE", "BOOK TWO", "VOLUME I", "ACT I")
        # IMPORTANT: Spelled-out words must come BEFORE Roman numerals in alternation to avoid partial matches
        # (e.g., "FIFTEEN" would match as "I" if Roman numerals are tried first)
        volume_book_pattern = r'(BOOK|VOLUME|ACT)\s+(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|[0-9]+|[IVXLCDM]+)[:\.\s]*(.*)$'

        # SPECIAL: Pattern for Paradise Lost style title-case "Book I", "Book II" etc.
        # These are CHAPTER markers in Paradise Lost (1-layer), not section markers (2-layer)
        # Only matches title-case "Book" to avoid conflicts with all-caps "BOOK" (which is for 2-layer structures)
        paradise_lost_book_pattern = r'^(Book)\s+([IVXLCDM]+)$'

        # Pattern for EPILOGUE markers (e.g., "FIRST EPILOGUE", "SECOND EPILOGUE")
        # These are treated as book-level markers (like BOOK XVI, BOOK XVII)
        epilogue_pattern = r'(FIRST|SECOND)\s+EPILOGUE[:\.\s]*(.*)$'

        # Common chapter patterns - must start new line
        chapter_patterns = [
            r'^([0-9]+)$',  # Standalone number format: "1", "2", etc. with title on next line (A Little Princess)
            r'^\[\s*([0-9]+)\s*\]$',  # Bracket format: "[ 1 ]", "[ 10 ]" (Ulysses)
            # Spelled-out chapter numbers (must come before generic CHAPTER pattern)
            # IMPORTANT: Longer patterns first to avoid partial matches (SIXTY-SEVEN before SIX)
            r'CHAPTER\s+(SEVENTY|SIXTY-NINE|SIXTY-EIGHT|SIXTY-SEVEN|SIXTY-SIX|SIXTY-FIVE|SIXTY-FOUR|SIXTY-THREE|SIXTY-TWO|SIXTY-ONE|SIXTY|FIFTY-NINE|FIFTY-EIGHT|FIFTY-SEVEN|FIFTY-SIX|FIFTY-FIVE|FIFTY-FOUR|FIFTY-THREE|FIFTY-TWO|FIFTY-ONE|FIFTY|FORTY-NINE|FORTY-EIGHT|FORTY-SEVEN|FORTY-SIX|FORTY-FIVE|FORTY-FOUR|FORTY-THREE|FORTY-TWO|FORTY-ONE|FORTY|THIRTY-NINE|THIRTY-EIGHT|THIRTY-SEVEN|THIRTY-SIX|THIRTY-FIVE|THIRTY-FOUR|THIRTY-THREE|THIRTY-TWO|THIRTY-ONE|THIRTY|TWENTY-NINE|TWENTY-EIGHT|TWENTY-SEVEN|TWENTY-SIX|TWENTY-FIVE|TWENTY-FOUR|TWENTY-THREE|TWENTY-TWO|TWENTY-ONE|TWENTY|NINETEEN|EIGHTEEN|SEVENTEEN|SIXTEEN|FIFTEEN|FOURTEEN|THIRTEEN|TWELVE|ELEVEN|TEN|NINE|EIGHT|SEVEN|SIX|FIVE|FOUR|THREE|TWO|ONE)[:\.\s]*(.*)$',
            r'Chapter\s+(Seventy|Sixty-Nine|Sixty-Eight|Sixty-Seven|Sixty-Six|Sixty-Five|Sixty-Four|Sixty-Three|Sixty-Two|Sixty-One|Sixty|Fifty-Nine|Fifty-Eight|Fifty-Seven|Fifty-Six|Fifty-Five|Fifty-Four|Fifty-Three|Fifty-Two|Fifty-One|Fifty|Forty-Nine|Forty-Eight|Forty-Seven|Forty-Six|Forty-Five|Forty-Four|Forty-Three|Forty-Two|Forty-One|Forty|Thirty-Nine|Thirty-Eight|Thirty-Seven|Thirty-Six|Thirty-Five|Thirty-Four|Thirty-Three|Thirty-Two|Thirty-One|Thirty|Twenty-Nine|Twenty-Eight|Twenty-Seven|Twenty-Six|Twenty-Five|Twenty-Four|Twenty-Three|Twenty-Two|Twenty-One|Twenty|Nineteen|Eighteen|Seventeen|Sixteen|Fifteen|Fourteen|Thirteen|Twelve|Eleven|Ten|Nine|Eight|Seven|Six|Five|Four|Three|Two|One)[:\.\s]*(.*)$',
            r'CHAPTER\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # CHAPTER I: Title or CHAPTER 1
            r'Chapter\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',
            r'STAVE\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # STAVE I: Title (A Christmas Carol)
            r'Stave\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # Stave I: Title
            r'SCENE\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # SCENE I. A public place (for plays)
            r'Scene\s+([IVXLCDM]+|[0-9]+)[:\.\s]*(.*)$',  # Scene I. or Scene 1. (for plays)
            r'^([IVXLCDM]+)$',  # Standalone Roman numeral without period (e.g., "I", "II", "III" in The Great Gatsby)
            r'^([IVXLCDM]+)\.$',  # Roman numeral only format: "I." with title on next line (must be checked first)
            r'^([IVXLCDM]+)\.\s+(.+)$',  # Roman numeral only format: "I. TITLE" (must have title after period)
            r'^(CHAPTER\s+THE\s+LAST)\.?$',  # "CHAPTER THE LAST" or "CHAPTER THE LAST." (special ending chapter)
            r'^(Chapter\s+the\s+last)\.?$',  # "Chapter the last" or "Chapter the last." (special ending chapter, lowercase variant)
            r'^(EPILOGUE)$',  # Standalone "EPILOGUE"
            r'^(Epilogue)$',  # Standalone "Epilogue"
            # Introductory material patterns (only if not numbered in TOC)
            # These are checked last and validated against TOC
            r'^(INTRODUCTION)$',  # Standalone "INTRODUCTION"
            r'^(Introduction)$',  # Standalone "Introduction"
            r'^(PREFACE)(?:\s+.*)?$',  # "PREFACE" or "PREFACE By The Editor" etc.
            r'^(Preface)(?:\s+.*)?$',  # "Preface" or "Preface Of The Author" etc.
            r"^(TRANSLATOR'S PREFACE)$",  # "TRANSLATOR'S PREFACE"
            r"^(Translator's Preface)$",  # "Translator's Preface"
            r"^(AUTHOR'S PREFACE)$",  # "AUTHOR'S PREFACE"
            r"^(Author's Preface)$",  # "Author's Preface"
        ]

        lines = text.split('\n')
        current_chapter = None
        current_text = []
        current_book_num = 1  # Track current book number for nested structure
        has_book_markers = False  # Track if we found any BOOK markers
        expecting_first_chapter_of_book = False  # Track if we just saw a BOOK marker

        # Track chapter headings to detect TOC (table of contents)
        # If we see many chapter headings close together with little content, it's likely a TOC
        potential_chapters = []

        # Track BOOK/VOLUME/ACT markers for books where these ARE the chapters (not nested)
        book_markers = []

        # Track illustration blocks to skip chapter markers inside them
        in_illustration = False

        # Track if we've found the first numbered chapter
        # Everything before the first numbered chapter goes into Chapter 0 (Preface)
        found_first_chapter = False
        preface_text = []

        # Track lines that have been consumed as chapter title continuations
        # These should be skipped in the main loop to avoid double-processing
        consumed_lines = set()

        # Track which line indices were included in chapters (for identifying removed content)
        consumed_line_indices = set()

        for i, line in enumerate(lines):
            # Skip lines that were already consumed as title continuations
            if i in consumed_lines:
                continue

            # Skip lines before TOC end (the entire TOC section)
            if toc_end_line > 0 and i < toc_end_line:
                continue

            line_stripped = line.strip()

            # Track illustration blocks (update state before processing)
            if line_stripped.startswith('[Illustration'):
                in_illustration = True
                # Check if illustration closes on the same line (has a closing ']')
                # Handles both "[Illustration: text]" and "[Illustration: ] text" formats
                if ']' in line_stripped:
                    in_illustration = False
                    # Skip this line entirely
                    continue

            # Check if this closes an illustration block
            closes_illustration = in_illustration and line_stripped.endswith(']')

            # Check if line contains a chapter marker (before we skip it)
            has_chapter_marker = any(re.match(pattern, line_stripped) for pattern in chapter_patterns)

            if closes_illustration:
                in_illustration = False
                # Skip this closing line ONLY if it doesn't have a chapter marker
                if not has_chapter_marker:
                    continue

            # Skip empty lines initially
            if not line_stripped:
                if current_chapter is not None and not in_illustration:
                    current_text.append(line)
                    consumed_line_indices.add(i)
                elif not found_first_chapter and not in_illustration and i not in combined_preface_line_indices:
                    preface_text.append(line)
                    consumed_line_indices.add(i)
                continue

            # SPECIAL: Check for Paradise Lost style "Book I", "Book II" chapter markers
            # These are treated as CHAPTERS, not BOOK-level section markers
            paradise_lost_match = re.match(paradise_lost_book_pattern, line_stripped)
            if paradise_lost_match:
                # Extract chapter number from Roman numeral
                chapter_numeral = paradise_lost_match.group(2)
                chapter_number = self.roman_to_int(chapter_numeral)

                # Create title like "Book I", "Book II"
                chapter_title = f"Book {chapter_numeral}"

                # Save current chapter if exists
                if current_chapter is not None:
                    chapter_text = '\n'.join(current_text)
                    chapter_text = self.normalize_chapter_text(chapter_text, is_poetry)
                    chapters.append((current_chapter[0], current_chapter[1], chapter_text))

                # Start new chapter
                current_chapter = (chapter_number, chapter_title, i)
                current_text = []
                found_first_chapter = True
                print(f"Detected Paradise Lost chapter: {chapter_title}")
                continue

            # Check if this line is a BOOK/VOLUME marker (e.g., "BOOK I", "VOLUME II")
            # Case-sensitive to avoid false positives
            volume_book_match = re.match(volume_book_pattern, line_stripped)
            if volume_book_match:
                # Check if this BOOK marker is embedded in a paragraph
                # by looking at surrounding lines for substantial content
                # IMPORTANT: Only treat as embedded if substantial content is on ADJACENT lines
                # (no blank lines in between), to avoid false positives where BOOK markers
                # appear between sections separated by blank lines
                is_embedded = False

                # Look at 3 lines before and after for context
                context_range = 3
                for offset in range(-context_range, context_range + 1):
                    if offset == 0:
                        continue  # Skip current line

                    context_idx = i + offset
                    if 0 <= context_idx < len(lines):
                        context_line = lines[context_idx].strip()

                        # Check if this is substantial content (not a marker, not empty)
                        # Substantial = has lowercase letters and is longer than 20 chars
                        has_lowercase = any(c.islower() for c in context_line)
                        is_long_enough = len(context_line) > 20
                        is_not_marker = not re.match(r'^(CHAPTER|BOOK|VOLUME|PART|ACT)\s+', context_line)

                        if has_lowercase and is_long_enough and is_not_marker:
                            # Found substantial content - check if there are blank lines in between
                            # If all lines between current and context line are non-empty, it's truly embedded
                            has_blank_between = False
                            start_check = min(i, context_idx)
                            end_check = max(i, context_idx)
                            for check_idx in range(start_check + 1, end_check):
                                if not lines[check_idx].strip():
                                    has_blank_between = True
                                    break

                            # Only treat as embedded if no blank lines between
                            if not has_blank_between:
                                is_embedded = True
                                break

                # If embedded in a paragraph, treat as content not a chapter boundary
                # ALSO: If we're currently inside a numbered chapter (not preface/intro) AND we haven't
                # seen any BOOK markers yet, treat BOOK markers as content. This handles cases like
                # Moby Dick's Cetology chapter where BOOK markers are part of the discussion
                # (BOOK I Folio, BOOK II Octavo, etc.)
                # BUT: If we already have BOOK markers, this is a nested BOOK/CHAPTER structure
                # and we should process BOOK markers as book boundaries
                # ALSO: Preface (Chapter 0) doesn't prevent BOOK markers from being processed
                is_embedded_in_chapter = (current_chapter is not None and
                                         current_chapter[0] != 0 and  # Not preface/intro
                                         len(book_markers) == 0)
                if is_embedded or is_embedded_in_chapter:
                    # This is content within a chapter (e.g., Moby Dick's Cetology chapter)
                    # Add to current chapter text instead of treating as boundary
                    if current_chapter is not None and not in_illustration:
                        current_text.append(line)
                        consumed_line_indices.add(i)
                    elif not found_first_chapter and not in_illustration and i not in combined_preface_line_indices:
                        preface_text.append(line)
                        consumed_line_indices.add(i)
                    continue

                has_book_markers = True  # Mark that we found BOOK/VOLUME markers
                marker_type = volume_book_match.group(1)  # "BOOK" or "VOLUME"
                marker_numeral = volume_book_match.group(2)  # Roman/Arabic numeral
                marker_title = volume_book_match.group(3).strip() if volume_book_match.group(3) else ""  # Optional title

                # Determine book/volume number from marker
                if marker_numeral.isdigit():
                    current_book_num = int(marker_numeral)
                else:
                    # Try spelled-out word first (before Roman numeral)
                    # This prevents "FIFTEEN" from being parsed as "I" (Roman numeral 1)
                    current_book_num = self.word_to_int(marker_numeral)
                    # If that didn't work, try Roman numeral
                    if current_book_num == 0:
                        current_book_num = self.roman_to_int(marker_numeral)

                # Store this BOOK marker for potential conversion to chapter later
                book_markers.append({
                    'line_index': i,
                    'marker_type': marker_type,
                    'number': current_book_num,
                    'numeral': marker_numeral,
                    'title': marker_title,
                    'line': line_stripped
                })

                # Set flag to expect first chapter after BOOK marker
                expecting_first_chapter_of_book = True

                print(f"Detected {marker_type} {current_book_num}")
                # Don't add BOOK/VOLUME markers to text, just update tracking
                continue

            # Check if this line is an EPILOGUE marker (e.g., "FIRST EPILOGUE", "SECOND EPILOGUE")
            # Treat these as book-level markers (Book 16, Book 17)
            epilogue_match = re.match(epilogue_pattern, line_stripped)
            if epilogue_match:
                has_book_markers = True  # Mark that we found BOOK-level markers
                epilogue_ordinal = epilogue_match.group(1)  # "FIRST" or "SECOND"
                epilogue_title = epilogue_match.group(2).strip() if epilogue_match.group(2) else ""  # Optional subtitle

                # Map FIRST -> 16, SECOND -> 17 (assuming 15 regular books)
                epilogue_num_map = {'FIRST': 16, 'SECOND': 17}
                current_book_num = epilogue_num_map.get(epilogue_ordinal, 16)

                # Store this EPILOGUE marker as a BOOK marker
                book_markers.append({
                    'line_index': i,
                    'marker_type': 'EPILOGUE',
                    'number': current_book_num,
                    'numeral': epilogue_ordinal,
                    'title': epilogue_title,
                    'line': line_stripped
                })

                print(f"Detected {epilogue_ordinal} EPILOGUE (Book {current_book_num})")
                # Don't add EPILOGUE markers to text, just update tracking
                continue

            # Explicitly ignore PART markers (e.g., "PART I", "PART II", "PART III")
            # These are section markers within chapters, not chapter boundaries
            # Case-sensitive to avoid false positives
            part_pattern = r'^PART\s+([IVXLCDM]+|[0-9]+)'
            if re.match(part_pattern, line_stripped):
                # This is a section marker within a chapter, include it in current chapter
                if current_chapter is not None and not in_illustration:
                    current_text.append(line)
                    consumed_line_indices.add(i)
                continue

            # Skip chapter detection if inside an illustration block
            if in_illustration:
                continue

            # Check if this line is a chapter heading
            is_chapter = False
            chapter_title = None
            chapter_num = None

            for pattern in chapter_patterns:
                # Don't use IGNORECASE - chapter markers should be uppercase to avoid false positives
                # (e.g., "chapter into three parts" should not match)
                match = re.match(pattern, line_stripped)
                if match:
                    # For Roman numeral-only pattern, verify original line only has whitespace before it
                    # This prevents false positives like "Frederick II. But Fate..." where II. starts the line
                    # but is part of a sentence, not a chapter marker
                    if pattern == r'^([IVXLCDM]+)\.\s+(.+)$':
                        # Check if original line (before strip) only has whitespace before the Roman numeral
                        if not line.lstrip() == line_stripped:
                            # Original line had non-whitespace content before the Roman numeral
                            continue
                        # Additionally, require that the title portion is in ALL CAPS or starts with a capital
                        # Real chapters in this format have ALL CAPS titles like "I. THE THREE METAMORPHOSES"
                        # False positives have sentence case like "II. But Fate lay behind it all"
                        title_part = match.group(2).strip()
                        # Get first word of title
                        title_words = title_part.split() if title_part else []
                        first_word = title_words[0] if title_words else ""
                        # Skip if first word is not all caps (allows for titles like "THE TITLE" but not "But fate")
                        if first_word and not first_word.isupper():
                            continue
                        # Additional check: if first word is a single letter (like "I"), require at least
                        # one more all-caps word to confirm it's a real chapter title
                        # This prevents false positives like "I. I was wrong..." from being detected
                        if first_word and len(first_word) == 1 and len(title_words) > 1:
                            # Check if there's at least one more all-caps word (longer than 1 char)
                            has_caps_word = any(word.isupper() and len(word) > 1 for word in title_words[1:])
                            if not has_caps_word:
                                continue

                    # Skip PREFACE/INTRODUCTION/AUTHOR'S PREFACE/EPILOGUE patterns that appear before first_chapter_line
                    # These are typically in TOC or frontmatter and should go into Chapter 0 (Preface), not be treated as separate chapters
                    frontmatter_patterns = [
                        r'^(INTRODUCTION)$', r'^(Introduction)$',
                        r'^(PREFACE)(?:\s+.*)?$', r'^(Preface)(?:\s+.*)?$',
                        r"^TRANSLATOR'S PREFACE$", r"^Translator's Preface$",
                        r"^AUTHOR'S PREFACE$", r"^Author's Preface$",
                        r'^(EPILOGUE)$', r'^(Epilogue)$',  # EPILOGUE in TOC or frontmatter
                    ]
                    is_frontmatter_pattern = any(re.match(p, line_stripped) for p in frontmatter_patterns)
                    if is_frontmatter_pattern and first_chapter_line is not None and i < first_chapter_line:
                        # This PREFACE/INTRODUCTION/EPILOGUE is before the first numbered chapter
                        # It should be part of Chapter 0 (if preface-like) or skipped (if TOC entry)
                        # Don't treat it as a separate chapter
                        continue

                    is_chapter = True
                    # Convert Roman numerals to numbers or use number directly
                    chapter_marker = match.group(1)
                    # Handle both single-group (PREFACE/INTRODUCTION) and two-group (CHAPTER) patterns
                    try:
                        chapter_title = match.group(2).strip() if match.group(2) else ""
                    except IndexError:
                        # Single-group pattern (PREFACE/INTRODUCTION)
                        chapter_title = ""

                    # Clean up title: remove trailing periods, brackets, and other punctuation
                    chapter_title = re.sub(r'[.\]\[]+$', '', chapter_title).strip()

                    # Track which line was used as title continuation (will be marked consumed if chapter validates)
                    continuation_line_idx = None
                    part_marker_line_idx = None

                    # Check if this is the standalone number pattern (e.g., "1", "2", etc.)
                    # For this pattern, the title is ALWAYS on the next line
                    # BUT: Only apply if we're in an appropriate context (not in TOC, preceded by blank lines)
                    is_standalone_number = False
                    is_standalone_roman = False

                    if pattern == r'^([0-9]+)$':
                        # Check context:
                        # 1. Must be past TOC section (if TOC exists)
                        # 2. Must be preceded by at least 2 blank lines (chapter break context)
                        # 3. Number should be reasonable (MIN_CHAPTER_NUMBER-MAX_CHAPTER_NUMBER range)

                        # Check if past TOC
                        past_toc = (toc_end_line == 0) or (i >= toc_end_line)

                        # Check if preceded by at least 2 consecutive blank lines immediately before
                        # This ensures we're at a chapter break, not mid-paragraph
                        preceded_by_blanks = False
                        if i >= ChapterDetectionConstants.MIN_BLANK_LINES_BEFORE_STANDALONE_NUMBER:  # Need at least 2 lines before to check
                            # Check that the 2 lines immediately before are both blank
                            line_before_1 = lines[i - 1].strip() if i - 1 >= 0 else None
                            line_before_2 = lines[i - 2].strip() if i - 2 >= 0 else None
                            preceded_by_blanks = (line_before_1 == "" and line_before_2 == "")

                        # Check if number is in reasonable range
                        try:
                            num_value = int(chapter_marker)
                            reasonable_number = ChapterDetectionConstants.MIN_CHAPTER_NUMBER <= num_value <= ChapterDetectionConstants.MAX_CHAPTER_NUMBER
                        except ValueError:
                            reasonable_number = False

                        # Only treat as standalone number if all conditions met
                        is_standalone_number = past_toc and preceded_by_blanks and reasonable_number

                        # If context validation failed, skip this match entirely
                        if not is_standalone_number:
                            continue

                    # Check if this is the standalone Roman numeral pattern (e.g., "I", "II", "III")
                    # or Roman numeral with period and title on same line (e.g., "I. Title")
                    # Similar validation as standalone numbers but more lenient
                    elif pattern in [r'^([IVXLCDM]+)$', r'^([IVXLCDM]+)\.$', r'^([IVXLCDM]+)\.\s+(.+)$']:
                        # Check context:
                        # 1. Must be past TOC section (if TOC exists)
                        # 2. Must be preceded by at least 1 blank line (chapter break context)
                        # 3. Roman numeral should be valid and reasonable (convert to number, check range)

                        # Check if past TOC
                        past_toc = (toc_end_line == 0) or (i >= toc_end_line)

                        # Check if preceded by at least 1 blank line
                        # (less strict than numbers since Roman numerals are more explicit chapter markers)
                        preceded_by_blank = False
                        if i >= 1:
                            line_before = lines[i - 1].strip() if i - 1 >= 0 else None
                            preceded_by_blank = (line_before == "")

                        # Check if Roman numeral is valid and reasonable
                        try:
                            # Convert Roman numeral to integer (remove period and any title part)
                            roman_part = chapter_marker.rstrip('.').split()[0] if ' ' in chapter_marker else chapter_marker.rstrip('.')
                            rom_value = self.roman_to_int(roman_part)
                            reasonable_roman = ChapterDetectionConstants.MIN_CHAPTER_NUMBER <= rom_value <= ChapterDetectionConstants.MAX_CHAPTER_NUMBER
                        except (ValueError, AttributeError):
                            reasonable_roman = False

                        # Only treat as standalone Roman if all conditions met
                        is_standalone_roman = past_toc and preceded_by_blank and reasonable_roman

                        # If context validation failed, skip this match entirely
                        if not is_standalone_roman:
                            continue

                    # Check if next line is a continuation of the title (for multi-line titles)
                    # Do this BEFORE removing part markers so we can check if continuation is part of the marker
                    # Skip up to 2 blank lines to find the continuation/title
                    next_line = None
                    next_line_idx_offset = None
                    if i + 1 < len(lines):
                        # Find the next non-blank line (skip up to 2 blank lines)
                        for lookahead in range(1, min(4, len(lines) - i)):
                            candidate_line = lines[i + lookahead].strip()
                            if candidate_line:  # Found non-blank line
                                next_line = candidate_line
                                next_line_idx_offset = lookahead
                                break

                        # Check if next line is just a part marker continuation (e.g., " I.", "II.", etc.)
                        # These should be concatenated to the title for regex removal, but consumed to prevent re-detection
                        is_part_marker_continuation = re.match(r'^[IVXLCDM]+\.$', next_line) if next_line else False

                        # If this is a part marker continuation, mark it for consumption
                        if is_part_marker_continuation:
                            part_marker_line_idx = i + next_line_idx_offset
                            # Also concatenate it to the title so the part marker removal regex can find it
                            chapter_title = chapter_title + ' ' + next_line
                            continuation_line_idx = i + next_line_idx_offset
                            # IMMEDIATELY consume this line to prevent it from being detected as a separate chapter
                            consumed_lines.add(i + next_line_idx_offset)
                        else:
                            # Check if next line looks like a title continuation:
                            # - Not another chapter marker
                            # - Not illustration or footnote markers
                            # - Relatively short (< 100 chars)
                            # - Either starts with lowercase or looks like a title word
                            is_continuation = (
                                next_line and
                                not re.match(r'(CHAPTER|Chapter|SCENE|Scene|PREFACE|Preface|INTRODUCTION|Introduction|BOOK|VOLUME|ACT|PART)\s+', next_line) and
                                not re.match(r'^[IVXLCDM]+\.\s+', next_line) and  # Not Roman numeral-only chapter format
                                not re.match(r'^[0-9]+$', next_line) and  # Not another standalone number
                                not next_line.startswith('[Illustration') and
                                not next_line.startswith('By ') and
                                len(next_line) < 100 and
                                len(next_line) > 1 and
                                (next_line[0].islower() or next_line[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or next_line.startswith('Æ'))
                            )

                            # For standalone number pattern, ALWAYS use next line as title (if it's not another chapter marker)
                            # For standalone Roman numeral patterns, also use next line as title
                            # For other patterns, only use next line if title is empty or it looks like continuation
                            if is_standalone_number:
                                # Standalone number pattern - next line is ALWAYS the title
                                if next_line and not re.match(r'^[0-9]+$', next_line) and len(next_line) > 0:
                                    chapter_title = next_line
                                    continuation_line_idx = i + next_line_idx_offset
                                    # IMMEDIATELY consume this line to prevent it from being detected as a separate chapter
                                    consumed_lines.add(i + next_line_idx_offset)
                            elif is_standalone_roman and not chapter_title:
                                # Standalone Roman numeral pattern WITHOUT title on same line
                                # Check if next line is actually a title or just content
                                # (unless it's another Roman numeral chapter marker)
                                if next_line and not re.match(r'^[IVXLCDM]+\.?\s*$', next_line) and len(next_line) > 0:
                                    # Check if next line is part of a paragraph by looking at the line after it
                                    is_part_of_paragraph = False
                                    if i + next_line_idx_offset + 1 < len(lines):
                                        line_after_next = lines[i + next_line_idx_offset + 1].strip()
                                        # If the line after next has lowercase content or is long, it's part of a paragraph
                                        if line_after_next and (any(c.islower() for c in line_after_next) or len(line_after_next) > 20):
                                            is_part_of_paragraph = True

                                    # Only use next line as title if it looks like a title, not content
                                    looks_like_title = (
                                        len(next_line) > 3 and
                                        len(next_line) <= ContentThresholds.MAX_CHAPTER_TITLE_LENGTH and
                                        not next_line.endswith('—') and
                                        not next_line.endswith('-') and
                                        not is_part_of_paragraph
                                    )

                                    if looks_like_title:
                                        chapter_title = next_line
                                        continuation_line_idx = i + next_line_idx_offset
                                        # IMMEDIATELY consume this line to prevent it from being detected as a separate chapter
                                        consumed_lines.add(i + next_line_idx_offset)
                            elif not chapter_title:
                                # Title is empty - use next line as title ONLY if it looks like a title
                                # Don't use it if it looks like content (long sentence, ends with dash/em-dash, or part of a paragraph)

                                # Check if next line is part of a paragraph by looking at the line after it
                                # If the line after next is also text (not blank), it's likely a paragraph
                                is_part_of_paragraph = False
                                if next_line and i + next_line_idx_offset + 1 < len(lines):
                                    line_after_next = lines[i + next_line_idx_offset + 1].strip()
                                    # If the line after next has lowercase content or is long, it's part of a paragraph
                                    if line_after_next and (any(c.islower() for c in line_after_next) or len(line_after_next) > 20):
                                        is_part_of_paragraph = True

                                # A proper title should be:
                                # 1. Reasonably short (<= 150 chars as specified)
                                # 2. Not ending with dashes
                                # 3. Not part of a paragraph (standalone)
                                looks_like_title = (
                                    is_continuation and
                                    len(next_line) > 3 and
                                    len(next_line) <= ContentThresholds.MAX_CHAPTER_TITLE_LENGTH and  # Titles can be long (max chars)
                                    not next_line.endswith('—') and  # Em-dash indicates continuation
                                    not next_line.endswith('-') and  # Regular dash indicates continuation
                                    not is_part_of_paragraph  # Not part of a multi-line paragraph
                                )
                                if looks_like_title:
                                    chapter_title = next_line
                                    continuation_line_idx = i + next_line_idx_offset
                                    # IMMEDIATELY consume this line to prevent it from being detected as a separate chapter
                                    consumed_lines.add(i + next_line_idx_offset)
                            elif is_continuation:
                                # Title exists and next line is a valid continuation - check if we should append it

                                # Check if this is an ALL-CAPS multi-line title (like Don Quixote)
                                # ALL-CAPS titles continue until we hit a blank line
                                is_all_caps_title = (
                                    chapter_title and
                                    all(c.isupper() or not c.isalpha() for c in chapter_title) and
                                    all(c.isupper() or not c.isalpha() for c in next_line)
                                )

                                if is_all_caps_title:
                                    # ALL-CAPS title - keep appending lines until we hit a blank line
                                    # This handles multi-line ALL-CAPS titles like:
                                    # "WHICH TREATS OF THE CHARACTER AND PURSUITS OF THE FAMOUS GENTLEMAN DON
                                    #  QUIXOTE OF LA MANCHA"
                                    current_offset = next_line_idx_offset
                                    while next_line and is_continuation:
                                        chapter_title = chapter_title + ' ' + next_line
                                        consumed_lines.add(i + current_offset)
                                        continuation_line_idx = i + current_offset

                                        # Look for next line
                                        next_line = None
                                        for lookahead in range(current_offset + 1, min(current_offset + 4, len(lines) - i)):
                                            candidate_line = lines[i + lookahead].strip()
                                            if candidate_line:  # Found non-blank line
                                                next_line = candidate_line
                                                current_offset = lookahead
                                                break
                                            else:
                                                # Hit a blank line - stop
                                                break

                                        if not next_line:
                                            # No more lines or hit blank line
                                            break

                                        # Check if next line is still part of ALL-CAPS title
                                        is_continuation = (
                                            next_line and
                                            all(c.isupper() or not c.isalpha() for c in next_line) and
                                            not re.match(r'(CHAPTER|Chapter|SCENE|Scene|PREFACE|Preface|INTRODUCTION|Introduction|BOOK|VOLUME|ACT|PART)\s+', next_line) and
                                            not re.match(r'^[IVXLCDM]+\.\s+', next_line) and
                                            not re.match(r'^[0-9]+$', next_line) and
                                            not next_line.startswith('[Illustration') and
                                            len(next_line) < 100 and
                                            len(next_line) > 1
                                        )

                                elif next_line[0].islower() or (len(next_line.split()) <= 3 and not next_line.endswith('.')):
                                    # Mixed-case title continuation
                                    # Only append if:
                                    # 1. Starts with lowercase (e.g., "of the") - likely part of title, OR
                                    # 2. Starts with uppercase AND is short (≤3 words) AND doesn't end with period
                                    #    (e.g., "Antonines" is 1 word, but "This is a sentence." is 4 words ending with period)
                                    # This avoids appending chapter content that starts with uppercase
                                    chapter_title = chapter_title + ' ' + next_line
                                    continuation_line_idx = i + next_line_idx_offset
                                    # IMMEDIATELY consume this line to prevent it from being detected as a separate chapter
                                    consumed_lines.add(i + next_line_idx_offset)

                    # Remove part markers from titles (e.g., "—Part I", ".—Part II", ". Part IV", etc.)
                    # Do this AFTER concatenation so we handle multi-line part markers
                    # Handle various formats: "—Part I", "—Part", ".—Part II.", ". Part IV", etc.
                    # The dash is optional (?) to handle cases like ". Part IV" without a dash
                    chapter_title = re.sub(r'[.\s]*[—–-]?\s*Part\s+[IVXLCDM]+[.\s]*$', '', chapter_title, flags=re.IGNORECASE).strip()
                    chapter_title = re.sub(r'[.\s]*[—–-]?\s*Part[.\s]*$', '', chapter_title, flags=re.IGNORECASE).strip()

                    # Determine base chapter number from marker
                    base_chapter_num = None
                    # Special handling for PREFACE, INTRODUCTION, and EPILOGUE
                    # BUT check TOC first - if they appear as numbered chapters in TOC, use that number
                    if chapter_marker.upper() in ['PREFACE', 'INTRODUCTION']:
                        # Check if Introduction/Preface is in TOC as a numbered chapter
                        toc_number = None
                        if toc:
                            # Look for Introduction/Preface in TOC values
                            for roman_num, toc_title in toc.items():
                                if chapter_marker.upper() in toc_title.upper():
                                    # Found in TOC with a number - use that number
                                    toc_number = self.roman_to_int(roman_num)
                                    chapter_title = toc_title  # Use TOC title
                                    print(f"Found '{chapter_marker}' in TOC as Chapter {roman_num} ({toc_number})")
                                    break

                        if toc_number is not None:
                            # Use the TOC number (e.g., "I Introduction" -> Chapter 1)
                            base_chapter_num = toc_number
                        else:
                            # Not in TOC or no TOC - treat as preface (Chapter 0)
                            base_chapter_num = 0
                            if not chapter_title:
                                # Use the marker name itself as title (capitalize first letter only)
                                chapter_title = chapter_marker.capitalize()
                    elif 'CHAPTER' in chapter_marker.upper() and 'THE' in chapter_marker.upper() and 'LAST' in chapter_marker.upper():
                        # "CHAPTER THE LAST" - assign chapter number 43
                        base_chapter_num = 43
                        if not chapter_title:
                            chapter_title = "Chapter the Last"
                    elif chapter_marker.upper() == 'EPILOGUE':
                        # Epilogue will be renumbered at the end to be sequential
                        # For now, use a placeholder that will be replaced
                        base_chapter_num = 999  # Temporary placeholder
                        if not chapter_title:
                            chapter_title = "Epilogue"
                    elif chapter_marker.isdigit():
                        base_chapter_num = int(chapter_marker)
                    else:
                        # Try spelled-out number first (ONE, TWO, TWENTY-ONE, etc.)
                        base_chapter_num = self.word_to_int(chapter_marker)
                        # If not a spelled-out number, try Roman numeral
                        if base_chapter_num == 0:
                            base_chapter_num = self.roman_to_int(chapter_marker)

                    # Encode as book_num * 100 + chapter_num (e.g., Book 1 Chapter 5 = 105)
                    # For regular books without BOOK markers, use simple encoding (1, 2, 3...)
                    if has_book_markers:
                        chapter_num = current_book_num * 100 + base_chapter_num
                        # Keep original chapter title WITHOUT "Book X, Chapter Y:" prefix
                        # Just store the actual chapter title
                        if not chapter_title:
                            chapter_title = f"Chapter {base_chapter_num}"
                    else:
                        # Regular book - use simple chapter numbering
                        chapter_num = base_chapter_num
                        # Keep original chapter title
                        if not chapter_title:
                            chapter_title = f"Chapter {base_chapter_num}"

                    # TOC-based validation (if TOC exists and has content)
                    # Skip TOC validation if TOC entries are empty (e.g., Frankenstein's simple TOC)
                    if toc:
                        # Numeric equivalence helper: TOC may use Roman numerals while body
                        # uses Arabic (or vice-versa) — e.g. pg245 (Life on the Mississippi)
                        # has TOC "CHAPTER I, II, III…" but body "CHAPTER 1, 2, 3…".
                        # Match by integer value, not string equality.
                        def _toc_lookup(marker):
                            if marker in toc:
                                return marker
                            # Convert marker to int via Roman / spelled-out / Arabic
                            n = 0
                            if marker.isdigit():
                                n = int(marker)
                            else:
                                n = self.word_to_int(marker) or self.roman_to_int(marker)
                            if n <= 0:
                                return None
                            for toc_key in toc.keys():
                                tk_n = 0
                                if toc_key.isdigit():
                                    tk_n = int(toc_key)
                                else:
                                    tk_n = self.word_to_int(toc_key) or self.roman_to_int(toc_key)
                                if tk_n == n:
                                    return toc_key
                            return None

                        matched_toc_key = _toc_lookup(chapter_marker)
                        # Check if this chapter marker is in the TOC
                        if matched_toc_key is not None:
                            toc_title = toc[matched_toc_key]
                            # Only use TOC validation if the TOC title is not empty
                            # Empty TOC titles indicate a simple TOC format that shouldn't override detection
                            if toc_title and toc_title.strip():
                                # Always use the TOC title as the authoritative title
                                # TOC has the properly formatted version
                                if chapter_title != toc_title:
                                    # Title differs from TOC - use TOC version
                                    print(f"Chapter {chapter_marker}: Using TOC title '{toc_title}' (detected: '{chapter_title}')")
                                chapter_title = toc_title
                            # If TOC title is empty, just skip TOC validation and use detected chapter
                        elif all(not v or not v.strip() for v in toc.values()):
                            # All TOC entries are empty - skip TOC validation entirely
                            pass
                        else:
                            # Chapter marker not in TOC and TOC has content
                            # EXCEPTION: Allow special chapter markers (EPILOGUE, PREFACE, INTRODUCTION)
                            # These may appear in TOC but not get captured by TOC parser
                            special_markers = ['EPILOGUE', 'PREFACE', 'INTRODUCTION', 'Epilogue', 'Preface', 'Introduction']
                            if chapter_marker.upper() not in [m.upper() for m in special_markers]:
                                # Not a special marker - skip this false positive
                                is_chapter = False
                                continue
                            # Special marker - allow it through even though not in TOC

                    # Record potential chapter
                    potential_chapters.append({
                        'line_index': i,
                        'marker': chapter_marker,
                        'number': chapter_num,
                        'title': chapter_title,
                        'line': line_stripped
                    })
                    break

            if is_chapter and chapter_num is not None:
                # Check if this is a TOC entry based on format
                # TOC entries have format: "CHAPTER I. Title" (title on same line with period/punctuation)
                # Actual chapters have format: "CHAPTER I" (standalone), then "TITLE" (on next line)
                # We detect this by checking if the original matched line has substantial text in group(2)
                # BEFORE the title continuation logic added more content

                # Get the original matched title from the regex (before title continuation)
                # This will be empty for standalone chapter markers, non-empty for TOC entries
                original_matched_title = ""
                for pattern in chapter_patterns:
                    match = re.match(pattern, line_stripped)
                    if match:
                        try:
                            # Get group(2) if it exists (the title portion)
                            original_matched_title = match.group(2).strip() if match.group(2) else ""
                        except IndexError:
                            original_matched_title = ""
                        break

                # A TOC entry has substantial title text on the same line (> 10 chars)
                # An actual chapter marker has empty or minimal text (chapter title comes from next line)
                has_inline_title = len(original_matched_title) > 10

                # Skip TOC entries: If we haven't accumulated substantial content yet (< 1000 chars)
                # and this looks like a chapter marker, it's likely a TOC entry
                accumulated_content_size = sum(len(line) for line in preface_text) if not found_first_chapter else sum(len(line) for line in current_text)

                # Check if this is the first chapter after a BOOK/VOLUME/ACT marker
                # If so, it's a real chapter, not a TOC entry
                recently_saw_book_marker = expecting_first_chapter_of_book

                # Look ahead to see if there's substantial content after this chapter marker
                # If there is, it's a real chapter regardless of inline title format
                lookahead_content_size = 0
                # Check if current line ends with "Part" patterns (for multi-line title detection)
                line_ends_with_part = bool(re.search(r'[—\-.]?\s*Part\s*$', line_stripped, re.IGNORECASE))

                # Scan forward until we hit another chapter marker (unbounded lookahead)
                for lookahead_idx in range(i+1, len(lines)):
                    lookahead_line = lines[lookahead_idx].strip()

                    # Check if this looks like a chapter marker
                    is_chapter_marker = any(re.match(pattern, lookahead_line) for pattern in chapter_patterns)

                    # Special case: if the current line ended with "Part" and the next line is just a
                    # Roman numeral (like " I." or " IV."), it's likely a title continuation, not a chapter marker
                    if is_chapter_marker and lookahead_idx == i + 1 and line_ends_with_part:
                        # Check if this is just a standalone Roman numeral (likely title continuation)
                        is_standalone_roman = bool(re.match(r'^\s*[IVXLCDM]+\.?\s*$', lookahead_line))
                        if is_standalone_roman:
                            # This is a title continuation, not a chapter marker - include it and continue
                            lookahead_content_size += len(lookahead_line)
                            continue

                    # Stop if we hit another chapter marker (that's not a title continuation)
                    if is_chapter_marker:
                        break
                    lookahead_content_size += len(lookahead_line)

                has_substantial_content_ahead = lookahead_content_size > ChapterDetectionConstants.MIN_LOOKAHEAD_CONTENT_FOR_CHAPTER

                # Also check: if the next few lines are also chapter markers, we're in TOC
                # Extended window (15 lines) to catch TOC entries near the end of the TOC
                # EXCEPTION: Never skip PREFACE/INTRODUCTION as TOC - they should always be saved as Chapter 0
                # EXCEPTION: Never skip chapters immediately after BOOK/VOLUME/ACT markers
                # EXCEPTION: Never skip if there's no inline title (actual chapter format)
                # EXCEPTION: Never skip if there's substantial content ahead (> MIN_LOOKAHEAD_CONTENT_FOR_CHAPTER chars)
                is_likely_toc = False
                is_preface_intro = chapter_num == 0  # Chapter 0 is PREFACE/INTRODUCTION
                if accumulated_content_size < ChapterDetectionConstants.MIN_ACCUMULATED_CONTENT_FOR_TOC_END and not is_preface_intro and not recently_saw_book_marker and not has_substantial_content_ahead:
                    # If this line has an inline title AND no substantial content follows, it's a TOC entry
                    # BUT only if we're still within the TOC section (haven't passed toc_end_line)
                    if has_inline_title and toc and (toc_end_line == 0 or i < toc_end_line):
                        is_likely_toc = True
                        print(f"Skipping TOC entry (inline title, no substantial content ahead): {line_stripped}")
                    # Only use lookahead TOC detection if we actually found a TOC (toc is not empty)
                    # AND we haven't passed the TOC end line yet
                    # This prevents false positives when a book starts with Chapter 1 (no TOC)
                    # and prevents skipping actual chapters that appear after the TOC
                    elif toc and (toc_end_line == 0 or i < toc_end_line):
                        # No inline title - check lookahead to see if surrounded by other chapter markers
                        # Look ahead until we hit substantial content or end of file
                        lookahead_chapter_count = 0
                        for lookahead_idx in range(i + 1, len(lines)):
                            # Skip lines that have already been consumed as continuation lines
                            if lookahead_idx in consumed_lines:
                                continue
                            lookahead_line = lines[lookahead_idx].strip()
                            if not lookahead_line:  # Skip empty lines
                                continue
                            # Check if this looks like a chapter marker
                            if any(re.match(pattern, lookahead_line) for pattern in chapter_patterns):
                                lookahead_chapter_count += 1
                            else:
                                # Hit non-chapter content - stop looking
                                break

                        # If we see 1+ more chapter markers ahead, we're in TOC
                        # (Reduced from 2 to handle cases where only 1-2 chapters remain at end of TOC)
                        # ALSO: If we have very small accumulated content (< 50 chars), treat as TOC
                        # even if no markers ahead (handles last TOC entry before actual content)
                        # (Reduced from 200 to 50 to handle books with small prefaces like A Christmas Carol)
                        if lookahead_chapter_count >= 1 or accumulated_content_size < 50:
                            is_likely_toc = True
                            print(f"Skipping TOC entry (lookahead): {line_stripped}")

                if is_likely_toc:
                    # This is a TOC entry - skip it entirely (don't add to preface)
                    continue

                # Note: continuation lines are now consumed immediately when detected (see lines 769, 795, 801)
                # No need to consume them again here

                # If this is the first numbered chapter, save all preface content as Chapter 0
                if not found_first_chapter and (preface_text or initial_preface_text):
                    # Combine pre-TOC preface material with post-TOC preface material
                    combined_preface = initial_preface_text + preface_text

                    # Normalize preface text to check if it's substantial
                    preface_content = '\n'.join(combined_preface)
                    preface_content = self.normalize_chapter_text(preface_content, is_poetry)

                    # Create Chapter 0 if:
                    # 1. First chapter is NOT Chapter 1 (e.g., Introduction, Prologue), OR
                    # 2. First chapter IS Chapter 1 BUT there's substantial preface content:
                    #    - Either > MIN_PREFACE_CONTENT_FOR_CREATION chars (like Frankenstein with Letters), OR
                    #    - Contains MIN_SENTENCE_COUNT_FOR_PREFACE+ sentences (indicates narrative content, not just metadata)
                    #      Count sentences by looking for ". " or ".\n" or ".End"
                    sentence_count = preface_content.count('. ') + preface_content.count('.\n') + preface_content.count('.—') + (1 if preface_content.endswith('.') else 0)
                    has_narrative_content = sentence_count >= ContentThresholds.MIN_SENTENCE_COUNT_FOR_PREFACE
                    should_create_preface = (chapter_num != 1) or (len(preface_content) > ContentThresholds.MIN_PREFACE_CONTENT_FOR_CREATION) or has_narrative_content

                    if should_create_preface:
                        # Only save if substantial content (minimum threshold: MIN_PREFACE_CHARS)
                        if len(preface_content) > ContentThresholds.MIN_PREFACE_CHARS:
                            # V1 parser always uses "Preface" title (v2 uses TOC preface markers)
                            preface_title = "Preface"
                            chapters.append((0, preface_title, preface_content))
                            print(f"Created Chapter 0 ({preface_title}) with {len(preface_content)} characters")
                        else:
                            print(f"Preface content too small ({len(preface_content)} chars), skipping Chapter 0")
                    else:
                        # First detected chapter is Chapter 1 with minimal preface content
                        print(f"First detected chapter is Chapter 1 with minimal preface content ({len(preface_content)} chars), skipping preface creation")

                    found_first_chapter = True
                    preface_text = []  # Clear preface text

                # Save previous chapter (only if it has substantial content)
                if current_chapter is not None and current_text:
                    # Preserve original formatting including paragraph breaks and spacing
                    content = '\n'.join(current_text)
                    # Only remove excessive leading/trailing blank lines
                    while content.startswith('\n'):
                        content = content[1:]
                    while content.endswith('\n'):
                        content = content[:-1]
                    # Normalize newlines: remove single newlines, keep paragraph breaks
                    content = self.normalize_chapter_text(content, is_poetry)
                    # Always add chapter, even if very short (some books have intentionally short chapters)
                    # Summary generation will skip chapters that are too short
                    chapters.append((current_chapter[0], current_chapter[1], content))

                # Normalize chapter title for consistent capitalization
                normalized_title = self.normalize_chapter_title(chapter_title)
                # Fix any title-cased Roman numerals (e.g., "Part Ii" -> "Part II")
                normalized_title = fix_roman_numerals_in_text(normalized_title)

                # Start new chapter
                current_chapter = (chapter_num, normalized_title)
                current_text = []

                # Clear the BOOK marker flag now that we've processed the first chapter
                expecting_first_chapter_of_book = False
            elif current_chapter is not None:
                # Skip table of contents entries
                # Pattern 1: Lines starting with "Heading to"
                # Pattern 2: Common TOC headers
                # Pattern 3: Lines with lots of whitespace followed by page numbers (e.g., "Title    123" or "Title    vii")
                is_toc_entry = (
                    line_stripped.startswith('Heading to') or
                    line_stripped.startswith('Dedication') or
                    line_stripped in ['PAGE', 'CONTENTS', 'TABLE OF CONTENTS', 'LIST OF ILLUSTRATIONS', 'Frontispiece', 'Title-page'] or
                    re.match(r'.+\s{10,}[ivxlcdm\d]+\s*$', line_stripped, re.IGNORECASE)  # Text followed by 10+ spaces and page number
                )
                if is_toc_entry:
                    continue

                # Add to current chapter (skip illustration content)
                if not in_illustration:
                    current_text.append(line)
                    consumed_line_indices.add(i)
            else:
                # No chapter started yet - collect into preface if we haven't found first chapter
                # Skip if already in combined_preface_line_indices to avoid duplication
                if not found_first_chapter and not in_illustration and i not in combined_preface_line_indices:
                    preface_text.append(line)
                    consumed_line_indices.add(i)

        # Add last chapter
        if current_chapter is not None and current_text:
            # Preserve original formatting including paragraph breaks and spacing
            content = '\n'.join(current_text)
            # Only remove excessive leading/trailing blank lines
            while content.startswith('\n'):
                content = content[1:]
            while content.endswith('\n'):
                content = content[:-1]
            # Normalize newlines: remove single newlines, keep paragraph breaks
            content = self.normalize_chapter_text(content, is_poetry)
            # Always add chapter, even if very short (some books have intentionally short chapters)
            # Summary generation will skip chapters that are too short
            chapters.append((current_chapter[0], current_chapter[1], content))

        # Filter out duplicate chapter numbers and merge multi-part chapters
        # For chapters split into parts (e.g., "Chapter X Part I", "Chapter X Part II"),
        # concatenate all parts together into one chapter
        if chapters:
            chapter_dict = {}
            for chapter_num, chapter_title, chapter_text in chapters:
                if chapter_num in chapter_dict:
                    # Already have this chapter number - merge the parts
                    existing_title, existing_text = chapter_dict[chapter_num]
                    existing_length = len(existing_text)
                    new_length = len(chapter_text)

                    # Concatenate the texts with a separator
                    merged_text = existing_text + "\n\n" + chapter_text

                    # Keep the LONGEST title (most complete version)
                    # This handles cases where TOC entries are shorter than actual chapter titles
                    better_title = existing_title

                    # Special handling for Chapter 0 (Introduction/Preface)
                    # Always prefer "Introduction & Prefaces" over specific footnote titles
                    if chapter_num == 0:
                        if "Introduction" in existing_title or "Preface" in existing_title:
                            better_title = existing_title  # Keep the generic intro title
                        elif "Introduction" in chapter_title or "Preface" in chapter_title:
                            better_title = chapter_title  # Use the new intro title
                        # Otherwise keep existing_title (first encountered)
                    else:
                        # Always prefer the longer title (more complete)
                        if len(chapter_title) > len(existing_title):
                            better_title = chapter_title

                    print(f"Merged Chapter {chapter_num} parts: {existing_length} + {new_length} = {len(merged_text)} chars (title: {better_title})")
                    chapter_dict[chapter_num] = (better_title, merged_text)
                else:
                    chapter_dict[chapter_num] = (chapter_title, chapter_text)

            # Rebuild chapters list from dict, sorted by chapter number
            chapters = [(num, title, text) for num, (title, text) in sorted(chapter_dict.items())]

        # Improved TOC detection: filter out short chapter instances that are likely TOC entries
        # If we detect duplicate chapter numbers where some are very short (TOC) and some are longer (actual),
        # keep only the longer versions
        if chapters and len(chapters) > 3:
            # Group chapters by chapter number to find duplicates
            chapter_groups = {}
            for ch_num, ch_title, ch_text in chapters:
                if ch_num not in chapter_groups:
                    chapter_groups[ch_num] = []
                chapter_groups[ch_num].append((ch_num, ch_title, ch_text, len(ch_text)))

            # If we have multiple instances of the same chapter number,
            # keep only instances that are > 500 chars (likely actual chapters, not TOC)
            filtered_chapters = []
            for ch_num in sorted(chapter_groups.keys()):
                instances = chapter_groups[ch_num]
                if len(instances) > 1:
                    # Multiple instances - filter by length
                    # Keep only those > 500 chars (the longer, actual chapters)
                    long_instances = [inst for inst in instances if inst[3] > 500]
                    if long_instances:
                        # Add the longest instance (should be just one after merging was already done)
                        longest = max(long_instances, key=lambda x: x[3])
                        filtered_chapters.append((longest[0], longest[1], longest[2]))
                    else:
                        # All instances are short - keep the longest one
                        longest = max(instances, key=lambda x: x[3])
                        filtered_chapters.append((longest[0], longest[1], longest[2]))
                else:
                    # Only one instance - keep it if it's substantial enough
                    ch_num, ch_title, ch_text, ch_len = instances[0]
                    filtered_chapters.append((ch_num, ch_title, ch_text))

            # If we filtered out any chapters, update the list
            if len(filtered_chapters) != len(chapters):
                print(f"Filtered out {len(chapters) - len(filtered_chapters)} TOC entries, keeping {len(filtered_chapters)} actual chapters")
                chapters = filtered_chapters

            # Final sanity check: if ALL remaining chapters are tiny (< MIN_AVG_CHAPTER_CHARS average),
            # likely the entire detection failed and we should treat as single text
            # UNLESS we successfully detected and skipped a TOC (indicated by toc_end_line > 0)
            # and have multiple chapters (MIN_PARAGRAPH_LINES_FOR_CHAPTER+) - in that case, trust the detection even if chapters are short
            if chapters:
                avg_length = sum(len(ch[2]) for ch in chapters) / len(chapters)
                has_toc_and_multiple_chapters = (toc_end_line > 0 and len(chapters) >= ChapterDetectionConstants.MIN_PARAGRAPH_LINES_FOR_CHAPTER)
                if avg_length < ContentThresholds.MIN_AVG_CHAPTER_CHARS and not has_toc_and_multiple_chapters:
                    print("Warning: Detected potential table of contents. Treating book as single text.")
                    chapters = [(1, "Full Text", text)]

        # Special handling: If we found BOOK/VOLUME/ACT markers but no nested chapters,
        # treat the BOOK markers themselves as chapters
        # This handles cases where BOOK/VOLUME/ACT are the actual chapters (e.g., The Odyssey)
        # Condition: We have BOOK markers AND either:
        #   1. No chapters at all
        #   2. Only a few chapters (like just intro/preface) compared to many BOOK markers
        should_convert_books = False
        if book_markers and len(book_markers) > 3:
            # Count chapters that aren't just intro/preface (chapter 0 or X00 encoded)
            # Also exclude very large chapter numbers like 2400 which suggest merged content
            non_intro_chapters = [ch for ch in chapters if ch[0] != 0 and ch[0] % 100 != 0]

            # If we have way fewer actual chapters than BOOK markers, convert the BOOK markers
            if len(non_intro_chapters) < len(book_markers) * 0.3:  # Less than 30% of expected
                should_convert_books = True
                print(f"Detected {len(book_markers)} {book_markers[0]['marker_type']} markers but only {len(non_intro_chapters)} nested chapters")
                print(f"Converting {book_markers[0]['marker_type']} markers to chapters with simple numbering")

        if should_convert_books:
            # Preserve Chapter 0 (preface) if it exists, clear the rest
            # (they're just merged intro content that won't be used)
            preface_chapter = next((ch for ch in chapters if ch[0] == 0), None)
            chapters = [preface_chapter] if preface_chapter else []

            # Deduplicate book_markers - keep only LAST occurrence of each book number
            # (BOOK markers often appear twice: once in TOC, once in actual content)
            # We want the actual content occurrence, not the TOC occurrence
            seen_numbers = {}
            for marker in book_markers:
                # Always update - this keeps the last occurrence
                seen_numbers[marker['number']] = marker

            # Convert back to list, sorted by book number
            unique_book_markers = [seen_numbers[num] for num in sorted(seen_numbers.keys())]

            print(f"Deduplicated to {len(unique_book_markers)} unique {unique_book_markers[0]['marker_type']} markers")

            # Extract content for each BOOK marker
            book_markers = unique_book_markers
            for idx, marker_info in enumerate(book_markers):
                book_num = marker_info['number']
                marker_type = marker_info['marker_type']
                marker_title = marker_info['title']
                start_line = marker_info['line_index']

                # Determine end line (next BOOK marker or end of text)
                if idx + 1 < len(book_markers):
                    end_line = book_markers[idx + 1]['line_index']
                else:
                    end_line = len(lines)

                # Extract content between this BOOK marker and the next
                book_content_lines = lines[start_line + 1:end_line]
                book_content = '\n'.join(book_content_lines)

                # Normalize the content
                book_content = self.normalize_chapter_text(book_content, is_poetry)

                # Create a descriptive title
                if marker_title:
                    chapter_title = f"{marker_type} {marker_info['numeral']}: {marker_title}"
                else:
                    chapter_title = f"{marker_type} {marker_info['numeral']}"

                # Fix any title-cased Roman numerals to ensure they're uppercase
                chapter_title = fix_roman_numerals_in_text(chapter_title)

                # Use simple sequential numbering (1, 2, 3...) instead of nested encoding
                chapter_num = book_num

                if len(book_content) > 100:  # Only add if substantial content
                    chapters.append((chapter_num, chapter_title, book_content))

            print(f"Created {len(chapters)} chapters from {book_markers[0]['marker_type']} markers")

            # Check if we have post-TOC preface material that should be added as Chapter 0
            # This handles cases like The Iliad where the introduction appears between TOC and BOOK I
            if initial_preface_text:
                # Check if Chapter 0 doesn't already exist
                has_chapter_0 = any(ch[0] == 0 for ch in chapters)
                if not has_chapter_0:
                    # Normalize preface text
                    preface_content = '\n'.join(initial_preface_text)
                    preface_content = self.normalize_chapter_text(preface_content, is_poetry)

                    # Only create Chapter 0 if substantial (> 100 chars)
                    if len(preface_content) > 100:
                        chapters.insert(0, (0, "Introduction", preface_content))
                        print(f"✓ Created Chapter 0 (Introduction) from post-TOC content: {len(preface_content)} chars")
                        # Mark these lines as consumed
                        consumed_line_indices.update(combined_preface_line_indices)

        # If no chapters detected (or very few), try title-only TOC extraction
        # This handles books like "The King in Yellow" with story titles but no numbers
        if len(chapters) <= 2:
            # Try extracting title-only TOC
            title_toc = self.extract_title_only_toc(text)
            if len(title_toc) >= 3:  # Must have at least 3 titles to be worth using
                print(f"No numbered chapters found. Trying title-only TOC extraction...")
                print(f"Found {len(title_toc)} titles in TOC: {title_toc}")

                # Search for each title in the text and use as chapter boundaries
                title_positions = []
                for title in title_toc:
                    # Search for exact title match (case-sensitive, on its own line)
                    # Use a pattern that matches the title at start of line, possibly with leading whitespace
                    # Also allow optional prefix words like "IN" before the title

                    # Special handling for bracket patterns like "[ 1 ]" or "[  1 ]"
                    # Normalize spaces inside brackets to match variations
                    bracket_match = re.match(r'^\[\s*(\d+)\s*\]$', title)
                    if bracket_match:
                        # Create pattern that matches bracket with any amount of whitespace
                        chapter_num = bracket_match.group(1)
                        exact_pattern = r'^\s*\[\s*' + chapter_num + r'\s*\]\s*$'
                        fuzzy_pattern = exact_pattern  # No fuzzy variant for brackets
                    else:
                        # Allow optional period at end (for story collections like "The Happy Prince.")
                        exact_pattern = r'^\s*' + re.escape(title) + r'\.?\s*$'
                        fuzzy_pattern = r'^\s*(?:IN\s+)?' + re.escape(title) + r'\.?\s*$'

                    # Find ALL occurrences, then filter for actual chapters (not TOC entries)
                    matches = []
                    for i, line in enumerate(lines):
                        # Try exact match first, then fuzzy match (case-insensitive)
                        if re.match(exact_pattern, line, re.IGNORECASE) or re.match(fuzzy_pattern, line, re.IGNORECASE):
                            matches.append(i)

                    # Filter matches to find actual chapter starts (not TOC entries)
                    # A real chapter is followed by substantial paragraph content within 5 lines
                    # If we need to look further, we're probably in a TOC
                    chapter_matches = []
                    for match_idx in matches:
                        # Skip if this line has page numbers (indicates TOC entry)
                        if re.search(r'\s+\d+\s*$', lines[match_idx]):
                            continue

                        # Look ahead only 5 lines - real chapters have immediate content
                        has_paragraph = False
                        uppercase_subtitle_count = 0
                        for lookahead in range(match_idx + 1, min(match_idx + 6, len(lines))):
                            lookahead_line = lines[lookahead].strip()
                            # Skip blank lines
                            if not lookahead_line:
                                continue

                            # Check for illustration markers (common in story collections)
                            if lookahead_line.startswith('[Picture:'):
                                has_paragraph = True
                                break

                            # Check if this is paragraph content (> 40 chars with mixed case or punctuation)
                            if len(lookahead_line) > 40:
                                has_mixed_case = not lookahead_line.isupper()
                                ends_with_punctuation = lookahead_line[-1] in '.,"!?;:'
                                if has_mixed_case or ends_with_punctuation:
                                    has_paragraph = True
                                    break

                            # If we hit uppercase short lines (potential titles/subtitles)
                            # Allow 1-2 subtitles like "AN OLD STORY TOLD ANEW"
                            if lookahead_line.isupper() and len(lookahead_line) < 50:
                                uppercase_subtitle_count += 1
                                if uppercase_subtitle_count > 2:
                                    # Too many uppercase lines without paragraph = TOC
                                    break

                        if has_paragraph:
                            chapter_matches.append(match_idx)

                    # Only use matches that have paragraph content nearby
                    # Don't use TOC-only entries (no fallback)
                    if chapter_matches:
                        last_match = chapter_matches[-1]
                        title_positions.append((last_match, title))
                        print(f"  Found '{title}' at line {last_match}")
                    elif matches:
                        # Title exists but has no paragraph content nearby = TOC-only entry
                        print(f"  Skipping '{title}' - found at line {matches[-1]} but no paragraph content (likely TOC-only)")

                # If we found most of the titles, create chapters from them
                if len(title_positions) >= len(title_toc) * 0.6:  # Found at least 60% of titles
                    print(f"Creating {len(title_positions)} chapters from title positions")
                    chapters = []

                    for idx, (line_idx, title) in enumerate(title_positions):
                        chapter_num = idx + 1

                        # Determine end line (next title or end of text)
                        if idx + 1 < len(title_positions):
                            end_line = title_positions[idx + 1][0]
                        else:
                            end_line = len(lines)

                        # Extract content between this title and next
                        # Skip the title line itself
                        chapter_lines = lines[line_idx + 1:end_line]
                        chapter_content = '\n'.join(chapter_lines)

                        # Normalize the content
                        chapter_content = self.normalize_chapter_text(chapter_content, is_poetry)

                        # Always add chapter, even if very short (some books have intentionally short chapters)
                        # Summary generation will skip chapters that are too short
                        chapters.append((chapter_num, title, chapter_content))
                        word_count = len(chapter_content.split())
                        if len(chapter_content) <= 100:
                            print(f"  Chapter {chapter_num}: {title} ({len(chapter_content)} chars, ~{word_count} words - very short)")
                        else:
                            print(f"  Chapter {chapter_num}: {title} ({len(chapter_content)} chars)")

                        # Mark all lines in this chapter as consumed (including the title line)
                        for i in range(line_idx, end_line):
                                consumed_line_indices.add(i)
                else:
                    print(f"Only found {len(title_positions)}/{len(title_toc)} titles in content - not using TOC extraction")

        # If still no chapters detected, treat the whole book as one chapter
        if not chapters:
            chapters = [(1, "Full Text", text)]

        # Renumber Epilogue (chapter 999) to be sequential after the last numbered chapter
        # This ensures Epilogue appears at the end in proper order
        if chapters:
            # Find Epilogue (chapter 999)
            epilogue_idx = next((i for i, (num, title, _) in enumerate(chapters) if num == 999), None)
            if epilogue_idx is not None:
                # Find the highest non-Epilogue chapter number
                max_chapter = max((num for num, title, _ in chapters if num != 999), default=0)
                next_chapter_num = max_chapter + 1

                # Renumber Epilogue
                epilogue_chapter = chapters[epilogue_idx]
                chapters[epilogue_idx] = (next_chapter_num, epilogue_chapter[1], epilogue_chapter[2])
                print(f"Renumbered Epilogue from 999 to {next_chapter_num}")

        # Renumber chapters sequentially (1, 2, 3, ...) while preserving Chapter 0 (preface)
        # This fixes the encoded numbering (101, 102, 228, 229) used for books with VOLUME markers
        if chapters and has_book_markers:
            # Separate Chapter 0 (preface) from regular chapters
            preface = [ch for ch in chapters if ch[0] == 0]
            regular_chapters = [ch for ch in chapters if ch[0] != 0]

            # Renumber regular chapters sequentially
            renumbered_chapters = []
            for idx, (old_num, title, text) in enumerate(regular_chapters, start=1):
                renumbered_chapters.append((idx, title, text))

            # Combine: preface first, then renumbered regular chapters
            chapters = preface + renumbered_chapters

            if renumbered_chapters:
                print(f"Renumbered {len(renumbered_chapters)} chapters sequentially (1-{len(renumbered_chapters)})")

        # Add both pre-TOC and post-TOC preface line indices to consumed set
        consumed_line_indices.update(combined_preface_line_indices)

        return chapters, consumed_line_indices

    def generate_concise_summary(self, text: str, title: str, author: str, dry_run: bool = False) -> str:
        """Generate concise 500-word summary without spoilers for fiction"""
        model_name = config.SUMMARY_CONFIGS['combined']['model']

        # Note: We don't include book content in the prompt for concise summaries
        # The LLM should use its training data knowledge of the book
        # Estimate tokens for prompt only (much smaller now)
        estimated_tokens = 500

        prompt = f"""Generate a concise 500-word summary of "{title}" by {author}.

Focus on the main theme, setting, and central conflict. For fiction, avoid spoilers (no plot twists, endings, or major reveals). For non-fiction, cover main arguments and key takeaways. Write in an engaging, accessible style."""

        if dry_run:
            print(f"\n[DRY RUN] Would generate concise summary using {model_name}")
            print(f"[DRY RUN] Prompt ({len(prompt)} chars):")
            print("-" * DisplayConstants.SEPARATOR_WIDTH)
            print(prompt[:10000] + f"\n... [truncated, {len(prompt) - 10000} chars omitted]" if len(prompt) > 10000 else prompt)
            print("-" * DisplayConstants.SEPARATOR_WIDTH)
            return "[DRY RUN] Summary would be generated here"

        # Wait if needed for large API calls
        self.wait_if_needed_for_large_call(estimated_tokens)

        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input word count
        input_words = len(prompt.split())
        print(f"Generating concise summary using {model_name} (fallback chain enabled)...")
        print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

        response, used_model = self._generate_content_with_fallback(
            'combined', prompt, log_label="concise-summary API call"
        )
        result = self.clean_llm_response(response.text)
        if used_model != config.SUMMARY_CONFIGS['combined']['model']:
            print(f"  ✓ Concise summary generated on fallback model: {used_model}")

        output_words = len(result.split())
        print(f"  ← Output: {output_words:,} words")

        return result

    def generate_medium_summary(self, text: str, title: str, author: str, dry_run: bool = False) -> str:
        """Generate medium-length 2000-3000 word summary"""
        model_name = config.SUMMARY_CONFIGS['combined']['model']

        # Note: We don't include book content in the prompt for medium summaries
        # The LLM should use its training data knowledge of the book
        # Estimate tokens for prompt only (much smaller now)
        estimated_tokens = 3000

        prompt = f"""Generate a comprehensive 2000-3000 word summary of "{title}" by {author}.

Cover all major plot points, themes, and character developments in chronological order. Discuss the author's writing style and analyze major themes. Spoilers are acceptable. For non-fiction, cover all main arguments, evidence, and conclusions."""

        if dry_run:
            print(f"\n[DRY RUN] Would generate medium summary using {model_name}")
            print(f"[DRY RUN] Prompt ({len(prompt)} chars):")
            print("-" * DisplayConstants.SEPARATOR_WIDTH)
            print(prompt[:10000] + f"\n... [truncated, {len(prompt) - 10000} chars omitted]" if len(prompt) > 10000 else prompt)
            print("-" * DisplayConstants.SEPARATOR_WIDTH)
            return "[DRY RUN] Summary would be generated here"

        # Wait if needed for large API calls
        self.wait_if_needed_for_large_call(estimated_tokens)

        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input word count
        input_words = len(prompt.split())
        print(f"Generating medium summary using {model_name} (fallback chain enabled)...")
        print(f"  → Input: {input_words:,} words (~{len(prompt):,} chars)")

        response, used_model = self._generate_content_with_fallback(
            'combined', prompt, log_label="medium-summary API call"
        )
        result = self.clean_llm_response(response.text)
        if used_model != config.SUMMARY_CONFIGS['combined']['model']:
            print(f"  ✓ Medium summary generated on fallback model: {used_model}")

        output_words = len(result.split())
        print(f"  ← Output: {output_words:,} words")

        return result


    def parse_bulk_summary_response(self, response_text: str, index_to_chapter: Dict[int, int]) -> Dict[int, str]:
        """
        Parse bulk summary response to extract individual chapter summaries.
        Returns dict mapping chapter_number -> summary_text

        Args:
            response_text: Raw LLM response text
            index_to_chapter: Dict mapping sequential index (1, 2, 3...) to actual chapter number

        Note: This function expects the LLM to use sequential indices (1, 2, 3...) in the response,
        not the actual chapter numbers. This makes parsing more defensive and independent of
        chapter numbering schemes (Arabic vs Roman numerals, encoded numbers like 101, 201, etc.)
        """
        summaries = {}

        # Split by chapter markers
        # Expected format: ### CHAPTER N: TITLE\n[content]\n### END CHAPTER N
        # N should be sequential indices (1, 2, 3...) as specified in the prompt
        # Also handle LLM errors where it outputs "### END CHAPTER N: TITLE" instead of "### CHAPTER N: TITLE"
        pattern = r'###\s*(?:END\s+)?CHAPTER\s+(\d+):\s*[^\n]*\n(.*?)(?=###\s*(?:(?:END\s+)?CHAPTER\s+|END\s+CHAPTER\s+)|$)'

        matches = re.finditer(pattern, response_text, re.DOTALL | re.IGNORECASE)

        for match in matches:
            index_str = match.group(1).strip()
            summary_text = match.group(2).strip()

            # Convert index to integer
            index = int(index_str)

            # Remove the END CHAPTER marker if present
            summary_text = re.sub(r'###\s*END\s+CHAPTER\s+\d+\s*$', '', summary_text, flags=re.IGNORECASE).strip()

            # Map index back to actual chapter number
            if index in index_to_chapter:
                chapter_num = index_to_chapter[index]
                summaries[chapter_num] = summary_text
            else:
                print(f"  ⚠️  Warning: Parsed index {index} not found in index_to_chapter mapping")

        # Verify we got all expected chapters
        expected_chapters = set(index_to_chapter.values())
        missing = expected_chapters - set(summaries.keys())
        if missing:
            print(f"  ⚠️  Warning: Missing summaries for chapters: {sorted(missing)}")

        return summaries

    def generate_bulk_chapter_summaries(self, chapters_batch: List[Tuple], book_title: str,
                                       medium_summary: str = None, previous_chapter_text: str = None,
                                       dry_run: bool = False, partial_run: bool = False,
                                       return_prompt_only: bool = False) -> Dict[int, str] | Dict:
        """
        Generate summaries for multiple chapters in a single API call.
        Returns dict mapping chapter_number -> summary_text

        Uses sequential indices (1, 2, 3...) in the LLM prompt for defensive parsing,
        independent of actual chapter numbering schemes (Arabic, Roman, encoded, etc.)

        Args:
            chapters_batch: List of (chapter_num, chapter_title, chapter_text) tuples for consecutive chapters
            book_title: Title of the book
            medium_summary: Optional medium summary of the book for context (truncated at 20,000 chars)
            previous_chapter_text: Optional text of the chapter immediately before the first chapter in the batch (truncated at 100,000 chars)
            dry_run: If True, skip API calls and return dummy data
            partial_run: If True, display API output to stdout
        """
        model_name = config.SUMMARY_CONFIGS['comprehensive']['model']
        max_words = config.SUMMARY_CONFIGS['comprehensive']['words_per_chapter']

        # Build the prompt with all chapters
        # Calculate dynamic target words for each chapter (same as regular mode)
        chapters_text = []
        chapter_numbers = []
        index_to_chapter = {}  # Map sequential index (1, 2, 3...) to actual chapter number
        chapter_targets = {}  # Map chapter_num -> target_words
        total_words = 0
        total_target_words = 0

        for idx, (chapter_num, chapter_title, chapter_text) in enumerate(chapters_batch, start=1):
            chapter_numbers.append(chapter_num)
            index_to_chapter[idx] = chapter_num  # Create index mapping
            chapter_word_count = len(chapter_text.split())
            total_words += chapter_word_count

            # Calculate dynamic target: min(chapter_words / 4, max_words)
            # Ensure a minimum of MIN_CHAPTER_SUMMARY_OUTPUT_WORDS for very short chapters
            target_words = min(chapter_word_count // 4, max_words)
            target_words = max(target_words, SummaryConstants.MIN_CHAPTER_SUMMARY_OUTPUT_WORDS)
            chapter_targets[chapter_num] = target_words
            total_target_words += target_words

            # Format using sequential index (not actual chapter number)
            # Include actual chapter info in the section header for context
            chapter_section = f"CHAPTER {idx} (Book Chapter {chapter_num}: {chapter_title})\n\n{chapter_text}"
            chapters_text.append(chapter_section)

        # Build context section
        context_sections = []

        if medium_summary:
            context_sections.append(f"""## CONTEXT: Overall Book Summary (for reference)\n\n{medium_summary[:APIConstants.MAX_MEDIUM_SUMMARY_CONTEXT_CHARS]}""")

        if previous_chapter_text:
            # Get the chapter number immediately before the first chapter in the batch
            first_chapter_num = chapters_batch[0][0] if chapters_batch else 0
            prev_chapter_num = first_chapter_num - 1 if first_chapter_num > 0 else 0

            context_sections.append(f"""## CONTEXT: Previous Chapter {prev_chapter_num} Content (for narrative continuity)

{previous_chapter_text[:APIConstants.MAX_PREVIOUS_CHAPTER_CONTEXT_CHARS]}""")

        context = "\n\n".join(context_sections) + "\n\n" if context_sections else ""

        # Build chapter-specific word count instructions using sequential indices
        chapter_instructions = []
        for idx, (chapter_num, chapter_title, _) in enumerate(chapters_batch, start=1):
            target = chapter_targets[chapter_num]
            # Show both index and actual chapter info for clarity
            chapter_instructions.append(f"  - Chapter {idx} (Book Chapter {chapter_num}: {chapter_title}) (~{target} words)")

        # Build structured prompt
        prompt = f"""Summarize the following {len(chapters_batch)} chapters from "{book_title}".

IMPORTANT: Format your response EXACTLY as shown below. Use sequential chapter numbers (1, 2, 3...) in your response markers, NOT the book chapter numbers. Follow the word count targets for each chapter:

{chr(10).join(chapter_instructions)}

FORMAT (use sequential numbers 1, 2, 3... in the markers):
### CHAPTER 1: TITLE
[Your summary here following the word count target above]
Cover important events, dialogues, and developments. Analyze character development and relationships. Identify key themes and symbols. Note important quotes. Explain how this chapter advances the overall narrative.

### END CHAPTER 1

### CHAPTER 2: TITLE
[Your summary for the second chapter...]

### END CHAPTER 2

... and so on for all {len(chapters_batch)} chapters.

{context}## CHAPTERS TO SUMMARIZE:

{"=" * DisplayConstants.CHAPTER_BATCH_SEPARATOR_WIDTH}
{chr(10).join(chapters_text)}
{"=" * DisplayConstants.CHAPTER_BATCH_SEPARATOR_WIDTH}

Now provide summaries for all {len(chapters_batch)} chapters above, following the exact format and word count targets specified. Remember to use sequential numbers (1, 2, 3...) in the ### CHAPTER markers."""

        # Return prompt and metadata for batch mode
        if return_prompt_only:
            return {
                'prompt': prompt,
                'chapter_numbers': chapter_numbers,
                'model': model_name
            }

        if dry_run:
            print(f"\n[DRY RUN] Would generate bulk summary for {len(chapters_batch)} chapters")
            print(f"[DRY RUN] Chapters: {chapter_numbers}")
            print(f"[DRY RUN] Total input: {total_words:,} words")
            print(f"[DRY RUN] Expected output: ~{total_target_words:,} words")
            return {ch_num: f"[DRY RUN] Summary for chapter {ch_num}" for ch_num in chapter_numbers}

        # Estimate tokens
        estimated_tokens = len(prompt) // 4 + total_target_words
        self.rate_limiter.wait_if_needed(estimated_tokens)

        # Log input
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating bulk summary for {len(chapters_batch)} chapters: {chapter_numbers} (fallback chain enabled)")
        print(f"  → Input: {total_words:,} words (~{len(prompt):,} chars)")

        response, used_model = self._generate_content_with_fallback(
            'comprehensive', prompt,
            log_label=f"bulk-chapter API call (chapters {chapter_numbers})"
        )
        response_text = response.text
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ API call successful for chapters {chapter_numbers} on {used_model}")

        # Log the full API response for debugging
        try:
            import json
            from pathlib import Path
            logs_dir = Path(__file__).parent.parent.parent / "data" / "log" / "gemini_logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_filename = f"gemini_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}_ch{chapter_numbers[0]}-{chapter_numbers[-1]}.json"
            log_path = logs_dir / log_filename

            log_data = {
                "timestamp": datetime.now().isoformat(),
                "chapter_numbers": chapter_numbers,
                "model": used_model,
                "response_text": response_text,
                "prompt_preview": prompt[:500] + "..." if len(prompt) > 500 else prompt
            }

            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            print(f"  → Logged full response to: {log_path}")
        except Exception as log_error:
            print(f"  → Warning: Could not log response: {log_error}")

        # Safety check: ensure we got a response
        if response_text is None:
            raise RuntimeError(f"Failed to generate bulk summary for chapters {chapter_numbers}: API returned None")

        output_words = len(response_text.split())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ← Output: {output_words:,} words for chapters {chapter_numbers}")

        # Display output in partial-run mode
        if partial_run:
            print(f"\n{'='*60}")
            print(f"BULK SUMMARY OUTPUT (Chapters {chapter_numbers[0]}-{chapter_numbers[-1]}):")
            print(f"{'='*60}")
            print(response_text)
            print(f"{'='*60}\n")

        # Parse response using index-to-chapter mapping
        summaries = self.parse_bulk_summary_response(response_text, index_to_chapter)

        # Verify we got all summaries
        if len(summaries) == len(chapter_numbers):
            print(f"  ✓ Successfully parsed all {len(summaries)} chapter summaries")
        else:
            print(f"  ⚠️  Parsed {len(summaries)}/{len(chapter_numbers)} summaries")
            # Debug: Print raw response when parsing fails
            print(f"\n{'='*60}")
            print(f"DEBUG: Raw LLM response that failed to parse:")
            print(f"{'='*60}")
            print(response_text)
            print(f"{'='*60}\n")

        return summaries


    def generate_comprehensive_summary(self, text: str, title: str,
                                      author: str, chapters: List[Tuple],
                                      book_id: int = None,
                                      medium_summary: str = None,
                                      dry_run: bool = False,
                                      partial_run: bool = False,
                                      chapter_to_section_id: Dict[int, int] = None,
                                      regenerate_chapters: List[int] = None) -> Tuple[str, List[Dict]]:
        """
        Generate comprehensive chapter-by-chapter summaries using bulk processing.

        All chapter summaries are generated using bulk processing via generate_bulk_chapter_summaries,
        which processes all consecutive chapters in a single API call for improved efficiency and context.

        Args:
            text: Full book text (used for reference)
            title: Book title
            author: Author name
            chapters: List of (chapter_num, chapter_title, chapter_text) tuples
            book_id: Database book ID (for saving results)
            medium_summary: Optional medium summary for context (passed to bulk processing)
            dry_run: If True, skip API calls and return dummy data
            partial_run: If True, process only first 3 chapters
            chapter_to_section_id: Optional dict mapping chapter numbers to section IDs (for 2-layer structures)
            regenerate_chapters: Optional list of chapter numbers to regenerate (filters chapters)

        Returns:
            Tuple of (overall_summary, chapter_summaries):
            - overall_summary: Empty string (no longer generated)
            - chapter_summaries: List of dicts with keys: chapter_number, chapter_title, summary, word_count
        """
        # Initialize chapter_to_section_id if not provided
        if chapter_to_section_id is None:
            chapter_to_section_id = {}

        chapter_summaries = []

        # Filter chapters based on mode
        if regenerate_chapters:
            # Regenerate mode: filter to only requested chapters
            chapters_to_process = [(num, title, text) for num, title, text in chapters if num in regenerate_chapters]

            if not chapters_to_process:
                print(f"ERROR: None of the requested chapters {regenerate_chapters} were found in the book")
                print(f"Available chapters: {[num for num, _, _ in chapters]}")
                return "", []

            print(f"[REGENERATE MODE] Found {len(chapters_to_process)} chapter(s) to regenerate:")
            for ch_num, ch_title, _ in chapters_to_process:
                print(f"  - Chapter {ch_num}: {ch_title}")
            print()

            # Validate that chapters are consecutive
            if len(chapters_to_process) > 1:
                chapter_nums = sorted([ch[0] for ch in chapters_to_process])
                for i in range(len(chapter_nums) - 1):
                    if chapter_nums[i+1] != chapter_nums[i] + 1:
                        print(f"\n{'='*60}")
                        print("ERROR: Chapters must be consecutive!")
                        print(f"{'='*60}")
                        print(f"Requested chapters: {regenerate_chapters}")
                        print(f"Found chapters: {chapter_nums}")
                        print(f"\nGap detected between Chapter {chapter_nums[i]} and {chapter_nums[i+1]}")
                        print("\nBulk chapter summary generation requires consecutive chapters only.")
                        print("Please provide a consecutive range of chapter numbers.")
                        print(f"{'='*60}\n")
                        sys.exit(1)
        elif partial_run:
            # Partial run mode: first 3 chapters
            chapters_to_process = chapters[:3]
            if len(chapters) > 3:
                print(f"PARTIAL RUN: Processing first 3 of {len(chapters)} chapters\n")
        else:
            # Normal mode: all chapters
            chapters_to_process = chapters

        # Filter chapters by word count - separate long and short chapters
        MIN_WORDS_FOR_SUMMARY = SummaryConstants.MIN_WORDS_FOR_CHAPTER_SUMMARY
        chapters_needing_summary = []
        short_chapters = []

        for chapter_num, chapter_title, chapter_text in chapters_to_process:
            word_count = len(chapter_text.split())
            if word_count >= MIN_WORDS_FOR_SUMMARY:
                chapters_needing_summary.append((chapter_num, chapter_title, chapter_text))
            else:
                short_chapters.append((chapter_num, chapter_title, chapter_text, word_count))
                print(f"  Skipping summary for Chapter {chapter_num}: {chapter_title} ({word_count} words - too short)")

        # Generate bulk summaries for all chapters (split into batches to respect token limits)
        if chapters_needing_summary:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Generating Bulk Chapter Summaries ({len(chapters_needing_summary)} chapters) ---")

            # Split chapters into batches to avoid token limits
            # Max input: 250K tokens/min, but need to leave room for:
            # - Context (medium summary ~MAX_MEDIUM_SUMMARY_CONTEXT_CHARS, previous chapter ~MAX_PREVIOUS_CHAPTER_CONTEXT_CHARS)
            # - Output tokens (~25% of input for summaries)
            # - Safety margin for rate limiting
            # Conservative batch size: MAX_BATCH_CHARS (~100K tokens input + ~25K output + context)
            MAX_BATCH_CHARS = APIConstants.MAX_BATCH_CHARS
            MAX_CHAPTERS_PER_BATCH = APIConstants.MAX_CHAPTERS_PER_BATCH  # Limit chapters per batch to improve quality and reduce parsing errors

            batches = []
            current_batch = []
            current_batch_chars = 0

            for chapter_num, chapter_title, chapter_text in chapters_needing_summary:
                chapter_chars = len(chapter_text)

                # If adding this chapter would exceed char limit or chapter limit, start new batch
                if current_batch and (current_batch_chars + chapter_chars > MAX_BATCH_CHARS or
                                     len(current_batch) >= MAX_CHAPTERS_PER_BATCH):
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_chars = 0

                current_batch.append((chapter_num, chapter_title, chapter_text))
                current_batch_chars += chapter_chars

            # Add last batch
            if current_batch:
                batches.append(current_batch)

            print(f"  Split into {len(batches)} batch(es) to respect token limits")

            # Add 1-minute delay before starting chapter summaries to avoid rate limits
            # This prevents back-to-back large API calls (book summary -> chapter summaries)
            if not dry_run and not regenerate_chapters:
                print(f"\n⏱️  Waiting {APIConstants.RATE_LIMIT_RETRY_WAIT_SECONDS} seconds before starting chapter summaries to avoid rate limits...")
                time.sleep(APIConstants.RATE_LIMIT_RETRY_WAIT_SECONDS)
                print(f"✓ Delay complete, starting chapter summary generation\n")

            # Generate bulk summaries for each batch and save immediately
            previous_batch_last_chapter = None  # Track last chapter from previous batch for context

            for batch_idx, batch in enumerate(batches, 1):
                batch_chars = sum(len(ch[2]) for ch in batch)
                batch_chapter_nums = [ch[0] for ch in batch]
                print(f"\n  Batch {batch_idx}/{len(batches)}: Chapters {batch_chapter_nums[0]}-{batch_chapter_nums[-1]} ({len(batch)} chapters, ~{batch_chars:,} chars)")

                # Get previous chapter text for narrative continuity (from last chapter of previous batch)
                previous_chapter_text = previous_batch_last_chapter[2] if previous_batch_last_chapter else None

                batch_summaries = self.generate_bulk_chapter_summaries(
                    batch,
                    title,
                    medium_summary=medium_summary,
                    previous_chapter_text=previous_chapter_text,
                    dry_run=dry_run,
                    partial_run=partial_run
                )

                # Track last chapter of this batch for next batch's context
                previous_batch_last_chapter = batch[-1]

                # Save batch results to database immediately
                for chapter_num, chapter_title, chapter_text in batch:
                    summary = batch_summaries.get(chapter_num, f"ERROR: Summary not generated for chapter {chapter_num}")

                    chapter_summaries.append({
                        'chapter_number': chapter_num,
                        'chapter_title': chapter_title,
                        'summary': summary,
                        'word_count': len(summary.split())
                    })

                    # Commit chapter to database immediately after batch generation
                    if not dry_run and not partial_run and book_id is not None:
                        section_id = chapter_to_section_id.get(chapter_num)
                        self.db.add_chapter(
                            book_id,
                            chapter_num,
                            chapter_title,
                            summary,
                            chapter_text,  # Full chapter text
                            section_id  # Link to section if two-level structure
                        )
                        print(f"  ✓ Saved chapter {chapter_num} to database")

            print(f"\n✓ Completed bulk summary generation")

        # In regenerate mode, we're done after generating the requested chapters
        if regenerate_chapters:
            print(f"\n{'='*60}")
            print(f"✓ Regenerated {len(chapter_summaries)} chapter summaries!")
            print(f"{'='*60}\n")
            # Return empty overall summary and the chapter summaries
            return "", chapter_summaries

        # Save short chapters to DB with empty summary (for both bulk and single modes)
        for chapter_num, chapter_title, chapter_text, word_count in short_chapters:
            chapter_summaries.append({
                'chapter_number': chapter_num,
                'chapter_title': chapter_title,
                'summary': '',  # Empty summary
                'word_count': 0
            })

            # Save to database with empty summary
            if not dry_run and not partial_run and book_id is not None:
                section_id = chapter_to_section_id.get(chapter_num)
                self.db.add_chapter(
                    book_id,
                    chapter_num,
                    chapter_title,
                    '',  # Empty summary - frontend will show full text instead
                    chapter_text,  # Still save full chapter text
                    section_id  # Link to section if two-level structure
                )
                print(f"  ✓ Saved Chapter {chapter_num} to database (no summary - {word_count} words)")

        # Show skipped chapters in partial run
        if partial_run and len(chapters) > 3:
            print(f"\n[PARTIAL RUN] Skipped remaining {len(chapters) - 3} chapters:")
            for ch_num, ch_title, _ in chapters[3:]:
                print(f"  - Chapter {ch_num}: {ch_title}")

        # Skip overall analysis - no longer generating comprehensive overall summaries
        if partial_run:
            print(f"\n[PARTIAL RUN] Skipping overall comprehensive analysis")
            print(f"[PARTIAL RUN] Total API calls made: 2 (combined summaries + bulk chapters)")
        else:
            print(f"\nSkipping overall comprehensive analysis (disabled)")

        overall_summary = ""  # No overall summary generated

        return overall_summary, chapter_summaries

    def _detect_book_structure(self, text: str) -> List[Dict]:
        """
        Helper method to detect book structure (2-layer or single-level).
        Shared by both normal and regenerate modes.

        Returns:
            toc_structure: List of sections with chapters, or None for single-level
        """
        # Try TOC-based detection FIRST (for books with explicit BOOK/PART/ACT markers)
        # This is most reliable when a TOC is present
        toc_structure = self.extract_two_level_toc(text)

        if toc_structure:
            return toc_structure

        # Try body scanning for traditional 2-level structures (BOOK/PART/ACT)
        toc_structure = self.extract_two_level_structure_from_body(text)

        if toc_structure:
            return toc_structure

        # Fallback to story collection detection (for books like "The Eternal Moment")
        # These have story titles as top-level with some stories having internal parts
        # DISABLED: Story collections should be treated as single-layer (each story = 1 chapter)
        # instead of two-level structure which adds unnecessary complexity
        toc_structure = None  # self.extract_story_collection_toc(text)

        # Validate TOC structure quality
        if toc_structure and False:  # Disabled
            toc_is_valid = True
            for section in toc_structure:
                # Check for invalid section types (should be PART, BOOK, ACT, VOLUME, or STORY)
                if section['type'] not in ['PART', 'BOOK', 'ACT', 'VOLUME', 'STORY']:
                    toc_is_valid = False
                    break
                # Check for garbage in section titles
                if section.get('title') and len(section['title']) > 5:
                    if section['title'][0].islower() or section['title'].startswith('i:'):
                        toc_is_valid = False
                        break

            if not toc_is_valid:
                return None

        return toc_structure

    def process_book(self, file_path: Path, title: str = None, author: str = None,
                    dry_run: bool = False, parse_only: bool = False, partial_run: bool = False, regenerate_chapters: List[int] = None, regenerate_overall: bool = False, use_batch_api: bool = True, is_poetry: bool = False) -> Dict:
        """Process a single book and generate all summaries

        Args:
            use_batch_api: If True (default), use async Batch API for 50% cost savings. If False, use sync API.
            is_poetry: If True, preserves line breaks for poetry (do not join lines within paragraphs)
        """
        print(f"\n{'='*60}")
        print(f"Processing: {file_path.name}")
        print(f"{'='*60}\n")

        # Read book
        text = self.read_book(file_path)
        raw_file_text = text  # Preserve original for --dry-run line-number anchors
        print(f"Book loaded: {len(text)} characters, ~{len(text.split())} words")

        # Extract metadata if not provided
        if not title or not author:
            extracted_title, extracted_author = self.extract_metadata(text, file_path.stem)
            title = title or extracted_title
            author = author or extracted_author
        else:
            # Normalize user-provided title
            title = normalize_book_title(title)

        print(f"Title: {title}")
        print(f"Author: {author}\n")

        # Try to extract Gutenberg ID for cover download (optional - only used for cover images)
        # Note: Title and author are now extracted from the text file itself, not from Gutenberg API
        gutenberg_id = self.extract_gutenberg_id(text)
        cover_image_path = None

        if gutenberg_id:
            print(f"Found Gutenberg ID: {gutenberg_id} (will attempt cover download)")
            # Download and save cover image locally from Project Gutenberg
            cover_image_path = self.download_gutenberg_cover(gutenberg_id, dry_run)
            if cover_image_path:
                print(f"Cover image: {cover_image_path}\n")
            else:
                print(f"No cover image found for Gutenberg ID {gutenberg_id}\n")
        else:
            print("No Gutenberg ID found (cover download skipped)\n")

        # Clean up Gutenberg headers/footers if present (gracefully handles non-Gutenberg books)
        text = self.extract_gutenberg_content(text)
        print(f"Extracted content: {len(text)} characters, ~{len(text.split())} words\n")

        if dry_run:
            print("\n" + "=" * DisplayConstants.SEPARATOR_WIDTH)
            print("DRY RUN MODE - No API calls will be made")
            print("=" * DisplayConstants.SEPARATOR_WIDTH + "\n")
        elif partial_run:
            print("\n" + "=" * DisplayConstants.SEPARATOR_WIDTH)
            print("PARTIAL RUN MODE - Making up to 4 API calls for testing")
            print("Will generate: Combined (Concise + Medium) + First 3 Chapters")
            print("Note: Reusing existing summaries from DB when available")
            print("API outputs will be displayed to stdout")
            print("=" * DisplayConstants.SEPARATOR_WIDTH + "\n")
        elif regenerate_chapters:
            print("\n" + "=" * DisplayConstants.SEPARATOR_WIDTH)
            print(f"REGENERATE CHAPTERS MODE - Regenerating {len(regenerate_chapters)} chapter(s)")
            print(f"Chapters to regenerate: {regenerate_chapters}")
            print("Will skip concise/medium/comprehensive overall summaries")
            print("=" * DisplayConstants.SEPARATOR_WIDTH + "\n")
        elif regenerate_overall:
            print("\n" + "=" * DisplayConstants.SEPARATOR_WIDTH)
            print(f"REGENERATE OVERALL MODE - Regenerating concise and medium summaries only")
            print("Will skip chapter detection and summaries")
            print("=" * DisplayConstants.SEPARATOR_WIDTH + "\n")

        # Check if book already exists (skip database operations in dry-run mode)
        if dry_run:
            # In dry-run mode, use a fake book ID
            existing_book = None
            book_id = 999  # Dummy ID for dry-run
            print(f"[DRY RUN] Would check if book exists in database")
            print(f"Book added to database (ID: {book_id})\n")

            # Simulate cover processing in dry-run mode
            if gutenberg_id and cover_image_path:
                self.process_cover_image(gutenberg_id, book_id, dry_run=True)
        else:
            existing_book = self.db.get_book_by_filename(file_path.name)
            if existing_book:
                print(f"Book already exists in database (ID: {existing_book['id']})")
                book_id = existing_book['id']

                # Update is_poetry flag if it has changed
                if is_poetry != bool(existing_book.get('is_poetry', 0)):
                    self.db.update_book_poetry_flag(book_id, is_poetry)
                    print(f"✓ Updated is_poetry flag: {is_poetry}")

                # Load existing chapters from database for batch mode
                # Get chapters with their full text for async batch processing
                db_chapters = self.db.get_chapters(book_id)
                if db_chapters:
                    print(f"  Loaded {len(db_chapters)} existing chapters from database")
                    # Convert database chapters to the format expected later
                    # Database returns: {'chapter_number', 'chapter_title', 'chapter_text', 'summary', 'section_id', ...}
                    # We need tuples: (chapter_num, chapter_title, chapter_text)
                    chapters = [(ch['chapter_number'], ch.get('chapter_title', f"Chapter {ch['chapter_number']}"), ch.get('chapter_text', ''))
                               for ch in db_chapters]

                    # Build chapter_to_section_id mapping from database
                    chapter_to_section_id = {ch['chapter_number']: ch.get('section_id')
                                            for ch in db_chapters if ch.get('section_id')}
                else:
                    # No chapters in database - will need to detect them
                    chapters = None
                    chapter_to_section_id = {}
            else:
                # Ensure author exists in authors table before adding book
                author_record = self.db.get_author_by_name(author)
                if not author_record:
                    # Author doesn't exist - create it
                    print(f"Creating author entry: {author}")
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO authors (name) VALUES (?)', (author,))
                    conn.commit()
                    author_id = cursor.lastrowid
                    conn.close()
                    print(f"✓ Created author: {author} (ID: {author_id})")
                    author_record = {'id': author_id, 'name': author}

                # Add book to database with local cover image path
                # Note: add_book will automatically lookup and link author_id if author exists in authors table
                book_id = self.db.add_book(title, author, file_path.name, text, gutenberg_id, cover_image_path, is_poetry=is_poetry)
                print(f"Book added to database (ID: {book_id})")
                print(f"✓ Author linked: {author} (author_id: {author_record['id']})")
                print()

                # Process cover image: rename to book_id and create WebP version
                if gutenberg_id and cover_image_path:
                    updated_cover_path = self.process_cover_image(gutenberg_id, book_id, dry_run=False)
                    if updated_cover_path and updated_cover_path != cover_image_path:
                        # Update the database with the new cover path
                        self.db.update_book_cover(book_id, gutenberg_id, updated_cover_path)
                        print(f"✓ Updated cover path in database: {updated_cover_path}\n")

        results = {
            'book_id': book_id,
            'title': title,
            'author': author,
            'filename': file_path.name,
            'summaries': {}
        }

        # In parse-only mode, detect chapters and save to database without LLM summaries
        # This allows --parse-only to extract chapter structure and full text
        if parse_only:
            print(f"\n{'='*60}")
            print(f"PARSE-ONLY MODE - Detecting chapters and saving to database")
            print(f"Skipping all LLM summary generation")
            print(f"{'='*60}\n")

            # Detect book structure (same as normal mode)
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Detecting Book Structure ---")
            toc_structure = self._detect_book_structure(text)

            # Create mapping from chapter number to section_id
            chapter_to_section_id = {}

            if toc_structure:
                print(f"✓ Detected two-level structure: {len(toc_structure)} sections")
                for section in toc_structure[:3]:  # Show first 3 sections
                    print(f"  {section['type']} {section['numeral']}: {section['title']} ({len(section['chapters'])} chapters)")
                if len(toc_structure) > 3:
                    print(f"  ... and {len(toc_structure) - 3} more sections")
            else:
                print("✓ Single-level structure (traditional chapters)")

            # Detect chapters FIRST (before saving sections)
            # This is needed because the actual detected chapters may differ from TOC
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Detecting Chapters ---")
            chapters, consumed_line_indices = self.detect_chapters(text, toc_structure, is_poetry)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Detected {len(chapters)} chapter(s)")

            # Now save sections and build chapter-to-section mapping based on ACTUAL detected chapters
            if toc_structure:
                if not dry_run:
                    print("\nSaving book sections to database...")
                    # Save sections and build mapping using the detected chapter numbers
                    # We need to find which section each chapter belongs to based on TOC detection
                    section_ids = []
                    for section in toc_structure:
                        section_id = self.db.add_book_section(
                            book_id,
                            section['type'],
                            section['number'],
                            section['title']
                        )
                        section_ids.append(section_id)
                        print(f"  ✓ Saved {section['type']} {section['numeral']}: {section['title']}")

                    # Build mapping from actual detected chapters to sections
                    # IMPORTANT: The TOC may use per-section numbering (e.g., VOLUME I: 1-52, VOLUME II: 1-74)
                    # but the body scan uses sequential numbering (e.g., 1-52, 53-126).
                    # We need to use the actual chapter numbers from the body scan, not the TOC.

                    # Group detected chapters by their section based on scan results
                    # The section info is embedded in the chapter detection
                    # We'll use the section_start_line to determine which section each chapter belongs to

                    # Get the chapter numbers that were actually detected in the body scan for each section
                    section_chapter_ranges = []
                    current_ch_start = None

                    for section_idx, section in enumerate(toc_structure):
                        # Count how many chapters were found in this section's body
                        # This info is printed during detection as "Found X chapters in VOLUME Y body"
                        # For now, we'll determine ranges based on detected chapter sequence

                        # Find all chapters that belong to this section
                        # Since chapters are detected sequentially, we can infer section boundaries
                        # from the chapter numbers

                        if section_idx == 0:
                            # First section: starts at chapter 1
                            current_ch_start = 1
                        else:
                            # Subsequent sections: start after the previous section's last chapter
                            current_ch_start = section_chapter_ranges[-1][1] + 1

                        # Find the actual last chapter number for this section
                        # by counting chapters that were detected in the body scan
                        # The log shows "Found 52 chapters in VOLUME I body" and "Found 74 chapters in VOLUME II body"
                        # We can infer this from the chapter count in the detection

                        # For Don Quixote specifically:
                        # VOLUME I: chapters 1-52 (52 chapters)
                        # VOLUME II: chapters 53-126 (74 chapters)

                        # Count chapters that would belong to this section
                        # Since we can't easily parse the log, we'll use the actual chapter numbers
                        section_chapters = []

                        # The section['chapters'] list contains the actual detected chapters
                        # These use per-section numbering (both VOLUME I and II start at 1)
                        # But the returned chapters tuple uses sequential numbering (1-52, 53-126)
                        # So we map based on the COUNT of chapters in each section

                        section_ch_count = len(section['chapters'])
                        current_ch_end = current_ch_start + section_ch_count - 1

                        section_chapter_ranges.append((current_ch_start, current_ch_end))
                        section_id = section_ids[section_idx]

                        # Map all chapters in this sequential range to this section
                        for ch_num in range(current_ch_start, current_ch_end + 1):
                            chapter_to_section_id[ch_num] = section_id

                        print(f"Section {section_idx} ({section['type']} {section['number']}): chapters {current_ch_start}-{current_ch_end} ({section_ch_count} chapters) → section_id {section_id}")

            # Note: Coverage will be calculated later in the common code path
            # after removed content analysis

            # Save chapters to database with empty summaries
            if not dry_run and book_id is not None:
                print(f"\nSaving {len(chapters)} chapters to database (with empty summaries)...")
                for chapter_num, chapter_title, chapter_text in chapters:
                    section_id = chapter_to_section_id.get(chapter_num)
                    self.db.add_chapter(
                        book_id,
                        chapter_num,
                        chapter_title,
                        '',  # Empty summary - will be generated later
                        chapter_text,  # Full chapter text
                        section_id  # Link to section if two-level structure
                    )
                print(f"✓ Saved {len(chapters)} chapters to database")

            print(f"\n{'='*60}")
            print(f"PARSE-ONLY MODE COMPLETE")
            print(f"Book metadata, sections, and chapter full text saved to database")
            print(f"Run without --parse-only to generate summaries")
            print(f"{'='*60}\n")
            return results

        # Route to async batch mode if enabled
        # Only route if chapters are already loaded (from database for existing books)
        # For new books, chapters haven't been detected yet, so skip routing and use normal flow
        if use_batch_api and not dry_run and not parse_only and not regenerate_overall and not partial_run and 'chapters' in locals() and chapters is not None:
            print("\n" + "="*60)
            print("🚀 ASYNC BATCH MODE ENABLED (50% cost savings)")
            print("="*60)

            # Convert chapters to the format expected by process_book_async_batch
            chapters_list = []
            for chapter_num, chapter_title, chapter_text in chapters:
                chapters_list.append({
                    'chapter_number': chapter_num,
                    'title': chapter_title,
                    'text': chapter_text
                })

            return self.process_book_async_batch(
                file_path=file_path,
                title=title,
                author=author,
                book_text=text,
                chapters=chapters_list,
                book_id=book_id,
                medium_summary_for_context=None,  # Will be None on first run
                chapter_to_section_id=chapter_to_section_id,
                skip_overall_summaries=bool(regenerate_chapters)  # Skip overall if regenerating chapters
            )

        # Early return for regenerate mode - skip concise/medium generation
        # Use the normal mode flow for everything else
        if regenerate_chapters:
            print(f"\n{'='*60}")
            print(f"REGENERATE CHAPTERS MODE - Regenerating {len(regenerate_chapters)} chapter(s)")
            print(f"Chapters to regenerate: {regenerate_chapters}")
            print(f"Will skip concise/medium summaries (already exist)")
            print(f"{'='*60}\n")

        # Generate combined concise and medium summaries (skip in regenerate_chapters mode, but DO generate in regenerate_overall mode)
        if not regenerate_chapters or regenerate_overall:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Generating Combined Summaries (Concise + Medium) ---")

            # In partial-run mode, check if we already have both summaries
            if partial_run:
                existing_concise = self.db.get_summary(book_id, 'concise')
                existing_medium = self.db.get_summary(book_id, 'medium')

                if existing_concise and existing_medium:
                    concise = existing_concise['content']
                    medium = existing_medium['content']
                    print(f"[PARTIAL RUN] Reusing existing summaries from database")
                else:
                    summary_data = self.generate_combined_summaries(text, title, author, dry_run)
                    concise = summary_data['concise_summary']
                    medium = summary_data['medium_summary']
                    if not dry_run:
                        # Save summaries
                        self.db.add_summary(book_id, 'concise', concise)
                        self.db.add_summary(book_id, 'medium', medium)

                        # Save book metadata (about_text, relevance_now)
                        self.db.update_book_metadata(
                            book_id,
                            about_text=summary_data.get('about_text'),
                            relevance_now=summary_data.get('relevance_now')
                        )
            else:
                summary_data = self.generate_combined_summaries(text, title, author, dry_run)
                concise = summary_data['concise_summary']
                medium = summary_data['medium_summary']
                if not dry_run:
                    # Save summaries
                    self.db.add_summary(book_id, 'concise', concise)
                    self.db.add_summary(book_id, 'medium', medium)

                    # Save book metadata (about_text, relevance_now)
                    self.db.update_book_metadata(
                        book_id,
                        about_text=summary_data.get('about_text'),
                        relevance_now=summary_data.get('relevance_now')
                    )

            results['summaries']['concise'] = {
                'text': concise,
                'word_count': len(concise.split())
            }
            results['summaries']['medium'] = {
                'text': medium,
                'word_count': len(medium.split())
            }

            print(f"✓ Concise summary: {results['summaries']['concise']['word_count']} words")
            print(f"✓ Medium summary: {results['summaries']['medium']['word_count']} words")

            # Categorize the book automatically after medium summary is generated (skip in regenerate_overall mode)
            if not dry_run and not regenerate_overall:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Categorizing Book ---")
                try:
                    # Get all categories from database
                    categories = self.db.get_all_categories()
                    if categories:
                        # Categorize using medium summary
                        book_info = {
                            'id': book_id,
                            'title': title,
                            'author': author
                        }
                        category_names = categorization.categorize_single_book(
                            self.client,
                            self.db,
                            book_info,
                            categories,
                            medium_summary=medium
                        )

                        if category_names:
                            # Save categories to database
                            categorization.save_book_categories(self.db, book_id, category_names)
                            print(f"✓ Assigned {len(category_names)} categories:")
                            for cat_name in category_names:
                                print(f"  - {cat_name}")
                        else:
                            print("⚠️  No categories assigned")
                    else:
                        print("⚠️  No categories found in database, skipping categorization")
                except Exception as e:
                    print(f"⚠️  Error during categorization: {e}")
                    print("   Continuing with summary generation...")

            if partial_run and not dry_run:
                print(f"\n{'='*60}")
                print("CONCISE SUMMARY OUTPUT:")
                print(f"{'='*60}")
                print(concise)
                print(f"{'='*60}\n")
                print(f"{'='*60}")
                print("MEDIUM SUMMARY OUTPUT:")
                print(f"{'='*60}")
                print(medium)
                print(f"{'='*60}\n")

            # Early return for regenerate_overall mode - we're done after generating summaries
            if regenerate_overall:
                print(f"\n{'='*60}")
                print("✓ REGENERATE OVERALL MODE COMPLETE")
                print(f"{'='*60}\n")
                print(f"✓ Updated concise summary: {results['summaries']['concise']['word_count']} words")
                print(f"✓ Updated medium summary: {results['summaries']['medium']['word_count']} words\n")
                return results
        else:
            # Regenerate mode: get medium summary from database for context
            medium_summary_record = self.db.get_summary(book_id, 'medium')
            medium = medium_summary_record['content'] if medium_summary_record else None
            print(f"[REGENERATE MODE] Skipping concise/medium generation (using existing from database)")
            if medium:
                print(f"  ✓ Found medium summary ({len(medium.split())} words) for context")

        # Check if chapters already exist in database (from --parse-only run)
        # If they exist, skip chapter detection and use existing chapter data
        existing_chapters_from_db = None
        if not dry_run:
            existing_chapters_from_db = self.db.get_chapters(book_id)

        if existing_chapters_from_db and len(existing_chapters_from_db) > 0:
            # Chapters already exist - use them instead of re-parsing
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Using Existing Chapters from Database ---")
            print(f"✓ Found {len(existing_chapters_from_db)} existing chapters in database")
            print(f"  Skipping chapter detection (already parsed with --parse-only)")

            # Convert database chapters to the format expected by the rest of the code
            # Format: List of tuples (chapter_num, chapter_title, chapter_text)
            chapters = [
                (ch['chapter_number'], ch['chapter_title'], ch['chapter_text'])
                for ch in existing_chapters_from_db
            ]

            # Get existing sections if any
            existing_sections = self.db.get_book_sections(book_id)
            toc_structure = None  # We don't need to detect structure since we have chapters

            # Build chapter_to_section_id mapping from existing database chapters
            chapter_to_section_id = {}
            for ch in existing_chapters_from_db:
                if ch.get('section_id'):
                    chapter_to_section_id[ch['chapter_number']] = ch['section_id']

            # Set consumed_line_indices to empty set since we're using pre-parsed chapters
            # This is only used for tracking removed content during initial parsing
            consumed_line_indices = set()

            print(f"  ✓ Loaded {len(chapters)} chapters from database")
            if existing_sections:
                print(f"  ✓ Book has {len(existing_sections)} sections")
            else:
                print(f"  ✓ Single-level structure (no sections)")
        else:
            # No existing chapters - run normal detection flow
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Detecting Book Structure ---")
            toc_structure = self._detect_book_structure(text)

            # Create mapping from chapter number to section_id
            # This will be used when saving chapters to link them to their sections
            chapter_to_section_id = {}

            if toc_structure:
                print(f"✓ Detected two-level structure: {len(toc_structure)} sections")
                for section in toc_structure[:3]:  # Show first 3 sections
                    print(f"  {section['type']} {section['numeral']}: {section['title']} ({len(section['chapters'])} chapters)")
                if len(toc_structure) > 3:
                    print(f"  ... and {len(toc_structure) - 3} more sections")

                # Save book sections to database and build chapter mapping
                # Skip section creation in regenerate mode to avoid deleting existing sections
                if not dry_run and not partial_run and not regenerate_chapters:
                    print("\nSaving book sections to database...")
                    sequential_chapter_num = 1  # Track sequential chapter numbers (1, 2, 3, ...)
                    for section in toc_structure:
                        section_id = self.db.add_book_section(
                            book_id,
                            section['type'],
                            section['number'],
                            section['title']
                        )
                        print(f"  ✓ Saved {section['type']} {section['numeral']}: {section['title']}")

                        # Map each chapter in this section to the section_id
                        # Use sequential numbering (1, 2, 3, ...) across all sections
                        for chapter in section['chapters']:
                            chapter_to_section_id[sequential_chapter_num] = section_id
                            sequential_chapter_num += 1
                elif regenerate_chapters:
                    # In regenerate mode, retrieve existing sections from database instead of recreating
                    print("\n[REGENERATE MODE] Using existing book sections from database...")
                    existing_sections = self.db.get_book_sections(book_id)
                    if existing_sections:
                        # Build section_id mapping from existing database sections
                        # Match by section_number (1, 2, 3, ...) to the detected structure
                        section_lookup = {s['section_number']: s['id'] for s in existing_sections}

                        sequential_chapter_num = 1
                        for section in toc_structure:
                            section_number = section['number']
                            section_id = section_lookup.get(section_number)
                            if section_id:
                                print(f"  ✓ Using existing {section['type']} {section['numeral']}: section_id={section_id}")
                                # Map chapters to existing section_id
                                for chapter in section['chapters']:
                                    chapter_to_section_id[sequential_chapter_num] = section_id
                                    sequential_chapter_num += 1
                            else:
                                print(f"  ⚠️  WARNING: No existing section found for {section['type']} {section['numeral']}")
                    else:
                        print("  ⚠️  WARNING: No existing sections found in database for regenerate mode")
                else:
                    # dry_run or partial_run mode - just build the mapping without saving
                    sequential_chapter_num = 1
                    for section in toc_structure:
                        for chapter in section['chapters']:
                            sequential_chapter_num += 1
            else:
                print("✓ Single-level structure (traditional chapters)")

            # Detect chapters
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Detecting Chapters ---")
            chapters, consumed_line_indices = self.detect_chapters(text, toc_structure, is_poetry)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Detected {len(chapters)} chapter(s)")

        # Calculate total parsed content
        total_parsed_chars = sum(len(ch_text) for _, _, ch_text in chapters)
        original_chars = len(text)

        # Calculate statistics for removed content (needed for all modes)
        word_counts = [len(ch_text.split()) for _, _, ch_text in chapters]
        total_words_parsed = sum(word_counts)
        original_word_count = len(text.split())

        # Extract and save removed/skipped content (for all modes, not just dry-run)
        # Use consumed_line_indices to find lines that weren't included in chapters
        original_lines = text.split('\n')
        removed_lines = []
        for i, line in enumerate(original_lines):
            if i not in consumed_line_indices:
                removed_lines.append(line)

        removed_content = '\n'.join(removed_lines)

        # Calculate removed content metrics from the actual removed content
        # (not from difference, as that doesn't account for line-join character differences)
        removed_word_count = len(removed_content.split())
        removed_char_count = len(removed_content)

        # Calculate coverage based on actual removed content (not normalized chapter sizes)
        # Coverage = (Original - Removed) / Original
        coverage_percent = ((original_chars - removed_char_count) / original_chars * 100) if original_chars > 0 else 0

        print(f"\nContent Coverage:")
        print(f"  Original text: {original_chars:,} chars")
        print(f"  Removed content: {removed_char_count:,} chars")
        print(f"  Coverage: {coverage_percent:.1f}%")

        if coverage_percent < ContentThresholds.MIN_COVERAGE_PERCENT:
            print(f"  ⚠️  WARNING: Only {coverage_percent:.1f}% of content captured - may be losing content!")
        elif coverage_percent > ContentThresholds.MAX_COVERAGE_PERCENT:
            print(f"  ⚠️  WARNING: Parsed content is {coverage_percent:.1f}% - may have duplicates!")
        else:
            print(f"  ✓ Good coverage - parsing looks correct")

        # Save both the removed content and analysis
        removed_file = Path('data/removed_content') / f"{file_path.stem}_removed.txt"
        removed_file.parent.mkdir(parents=True, exist_ok=True)
        with open(removed_file, 'w', encoding='utf-8') as f:
            f.write(f"REMOVED/SKIPPED CONTENT FOR: {title} by {author}\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Total Chapters Detected: {len(chapters)}\n")
            f.write(f"Coverage: {coverage_percent:.1f}%\n\n")

            # Show 2-layer structure if applicable
            if toc_structure:
                f.write(f"Book Structure: 2-layer ({len(toc_structure)} sections)\n")
                for section in toc_structure:
                    section_title_display = f": {section['title']}" if section['title'] else ""
                    f.write(f"  {section['type']} {section['numeral']}{section_title_display} ({len(section['chapters'])} chapters)\n")
                f.write(f"\n")
            else:
                f.write(f"Book Structure: Single-level (traditional chapters)\n\n")

            f.write(f"Original Content:\n")
            f.write(f"  {original_word_count:,} words\n")
            f.write(f"  {len(text):,} characters\n\n")
            f.write(f"Parsed Content:\n")
            f.write(f"  {total_words_parsed:,} words\n")
            f.write(f"  {total_parsed_chars:,} characters\n\n")
            f.write(f"Removed/Skipped Content:\n")
            f.write(f"  {removed_word_count:,} words ({100 - coverage_percent:.1f}%)\n")
            f.write(f"  {removed_char_count:,} characters\n\n")
            f.write(f"{'='*60}\n")
            f.write(f"DETECTED CHAPTERS:\n")
            f.write(f"{'='*60}\n\n")

            # If 2-layer structure, show chapters grouped by section
            if toc_structure:
                # First, show preface if it exists (Chapter 0)
                preface_chapters = [ch for ch in chapters if ch[0] == 0]
                if preface_chapters:
                    f.write(f"PREFACE\n")
                    for ch_num, ch_title, ch_text in preface_chapters:
                        ch_words = len(ch_text.split())
                        f.write(f"  Chapter {ch_num}: {ch_title} ({ch_words:,} words)\n")
                    f.write(f"\n")

                # Create a mapping of section indices to actual chapter numbers
                # We need to figure out which chapters belong to which section
                section_chapter_map = {}
                chapter_idx = 0 if not preface_chapters else 1  # Start after preface

                for section_idx, section in enumerate(toc_structure):
                    section_chapter_map[section_idx] = []
                    # Expected chapters for this section (from TOC)
                    expected_count = len(section['chapters'])

                    # Assign the next N chapters to this section
                    for _ in range(expected_count):
                        if chapter_idx < len(chapters):
                            section_chapter_map[section_idx].append(chapters[chapter_idx])
                            chapter_idx += 1

                # Now display chapters grouped by section
                for section_idx, section in enumerate(toc_structure):
                    section_title_display = f": {section['title']}" if section['title'] else ""
                    f.write(f"{section['type']} {section['numeral']}{section_title_display}\n")
                    for ch_num, ch_title, ch_text in section_chapter_map[section_idx]:
                        ch_words = len(ch_text.split())
                        f.write(f"  Chapter {ch_num}: {ch_title} ({ch_words:,} words)\n")
                    f.write(f"\n")
            else:
                # Single-level structure: just list chapters
                for ch_num, ch_title, ch_text in chapters:
                    ch_words = len(ch_text.split())
                    f.write(f"Chapter {ch_num}: {ch_title} ({ch_words:,} words)\n")
                f.write(f"\n")
            f.write(f"{'='*60}\n")
            f.write(f"WHAT SHOULD BE REMOVED (typically):\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"- Title pages and frontmatter\n")
            f.write(f"- Copyright notices and publication info\n")
            f.write(f"- Table of Contents\n")
            f.write(f"- Illustration captions ([Illustration: ...])\n")
            f.write(f"- Project Gutenberg headers/footers\n")
            f.write(f"- Dedications and preface poems\n")
            f.write(f"- List of illustrations\n\n")
            f.write(f"If coverage is >95%, the parsing is likely correct.\n")
            f.write(f"If coverage is <{ContentThresholds.MIN_COVERAGE_PERCENT}%, review the chapter detection carefully.\n\n")
            f.write(f"{'='*60}\n")
            f.write(f"ACTUAL REMOVED CONTENT:\n")
            f.write(f"{'='*60}\n\n")
            f.write(removed_content)
        print(f"  Removed content saved to: {removed_file}")

        # Display detailed statistics only in dry-run mode
        if dry_run:
            avg_words = total_words_parsed / len(chapters) if chapters else 0
            min_words = min(word_counts) if word_counts else 0
            max_words = max(word_counts) if word_counts else 0

            print(f"\n{'='*60}")
            print("DRY RUN - CHAPTER DETECTION STATISTICS")
            print(f"{'='*60}")
            print(f"\nTotal Chapters Detected: {len(chapters)}")
            print(f"Total Words Parsed: {total_words_parsed:,}")
            print(f"\nWord Count Distribution:")
            print(f"  Average: {avg_words:,.0f} words/chapter")
            print(f"  Smallest: {min_words:,} words")
            print(f"  Largest: {max_words:,} words")

            print(f"\nRemoved/Skipped Content:")
            print(f"  {removed_word_count:,} words ({100 - coverage_percent:.1f}% of original)")
            print(f"  {removed_char_count:,} characters")

            print(f"\n{'='*60}")
            print("CHAPTER BREAKDOWN")
            print(f"{'='*60}\n")
            line_ranges = derive_chapter_line_ranges(raw_file_text, chapters)
            ranges_by_num = {ch_num: (s, e) for ch_num, s, e in line_ranges}
            for ch_num, ch_title, ch_text in chapters:
                ch_words = len(ch_text.split())
                s, e = ranges_by_num.get(ch_num, (-1, -1))
                if s == -1:
                    line_info = "lines: (anchor not found in raw file)"
                else:
                    line_info = f"lines: {s}-{e}  ({e - s + 1} raw lines)"
                print(f"  Chapter {ch_num}: {ch_title}")
                print(f"    Length: {len(ch_text):,} chars (~{ch_words:,} words)  |  {line_info}")
            print()
            print("  (Line numbers refer to the RAW source file; use to spot-check boundaries.)")
            print()

        # Generate comprehensive summary
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] --- Generating Comprehensive Summary ---")
        overall, chapter_summaries = self.generate_comprehensive_summary(
            text, title, author, chapters,
            book_id=book_id,
            medium_summary=medium,
            dry_run=dry_run, partial_run=partial_run,
            chapter_to_section_id=chapter_to_section_id,
            regenerate_chapters=regenerate_chapters
        )

        # Save comprehensive summary (only if not empty)
        if not dry_run and not partial_run and overall:
            self.db.add_summary(book_id, 'comprehensive', overall)
        results['summaries']['comprehensive'] = {
            'overall': overall,
            'overall_word_count': len(overall.split()) if overall else 0,
            'chapters': chapter_summaries
        }

        # Note: Chapters are now saved immediately after generation (see generate_comprehensive_summary)

        if overall:
            print(f"✓ Comprehensive summary: {len(overall.split())} words")
        print(f"✓ Chapter summaries: {len(chapter_summaries)} chapters")

        # Save results to JSON file
        if not dry_run and not partial_run:
            output_file = config.SUMMARIES_DIR / f"{file_path.stem}_summaries.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n✓ Results saved to: {output_file}")
        elif dry_run:
            print(f"\n[DRY RUN] Results would be saved to: {config.SUMMARIES_DIR / f'{file_path.stem}_summaries.json'}")
        elif partial_run:
            print(f"\n[PARTIAL RUN] Results NOT saved (test mode only)")

        print(f"\n{'='*60}")
        if partial_run:
            print(f"✓ Partial run complete! (4 API calls made)")
            print(f"   Run without --partial-run to generate all summaries")
        else:
            print(f"✓ Book processing complete!")
        print(f"{'='*60}\n")

        return results

    def process_book_async_batch(self, file_path: Path, title: str, author: str,
                                 book_text: str, chapters: List, book_id: int,
                                 medium_summary_for_context: str = None,
                                 chapter_to_section_id: Dict = None,
                                 poll_interval: int = BATCH_POLL_INTERVAL_SECONDS,
                                 skip_overall_summaries: bool = False) -> Dict:
        """
        Process book using async Batch API for 50% cost savings.

        Builds all prompts, submits as one batch job, polls for completion,
        and saves results to database.

        Args:
            skip_overall_summaries: If True, skip generating concise/medium summaries (for --regenerate-chapters)
        """
        print(f"\n{'='*60}")
        if skip_overall_summaries:
            print("ASYNC BATCH MODE - Regenerating chapter summaries only...")
        else:
            print("ASYNC BATCH MODE - Building requests...")
        print(f"{'='*60}")

        batch_requests = []
        request_metadata = []

        # Request 1: Overall summaries (concise + medium) - skip if regenerating chapters only
        if not skip_overall_summaries:
            print(f"\n[1/N] Building overall summaries request...")
            overall_prompt = self.generate_combined_summaries(
                text=book_text,
                title=title,
                author=author,
                return_prompt_only=True
            )
            batch_requests.append(self.build_batch_request(overall_prompt))
            request_metadata.append({
                'type': 'overall',
                'model': config.SUMMARY_CONFIGS['combined']['model']
            })
        else:
            print(f"\n[Skipping overall summaries - regenerating chapters only]")

        # Requests 2-N: Chapter summaries (keeping existing bulk batching)
        print(f"\n[2/N] Building chapter summary requests...")

        # Prepare chapters for bulk processing (reuse existing logic from process_book)
        chapters_needing_summary = []
        for chapter in chapters:
            chapter_num = chapter['chapter_number']
            chapter_title = chapter['title']
            chapter_text = chapter['text']
            word_count = len(chapter_text.split())

            if word_count < SummaryConstants.MIN_WORDS_FOR_CHAPTER_SUMMARY:
                continue

            chapters_needing_summary.append((chapter_num, chapter_title, chapter_text))

        # Split into batches (reuse existing batching logic)
        MAX_BATCH_CHARS = APIConstants.MAX_BATCH_CHARS
        MAX_CHAPTERS_PER_BATCH = APIConstants.MAX_CHAPTERS_PER_BATCH

        batches = []
        current_batch = []
        current_batch_chars = 0

        for chapter_num, chapter_title, chapter_text in chapters_needing_summary:
            chapter_chars = len(chapter_text)

            if current_batch and (current_batch_chars + chapter_chars > MAX_BATCH_CHARS or
                                 len(current_batch) >= MAX_CHAPTERS_PER_BATCH):
                batches.append(current_batch)
                current_batch = []
                current_batch_chars = 0

            current_batch.append((chapter_num, chapter_title, chapter_text))
            current_batch_chars += chapter_chars

        if current_batch:
            batches.append(current_batch)

        # Build chapter number to title and text mappings
        chapter_num_to_title = {}
        chapter_num_to_text = {}
        for chapter_num, chapter_title, chapter_text in chapters_needing_summary:
            chapter_num_to_title[chapter_num] = chapter_title
            chapter_num_to_text[chapter_num] = chapter_text

        # Build bulk chapter summary requests
        previous_batch_last_chapter = None

        for batch_idx, batch in enumerate(batches, 1):
            previous_chapter_text = previous_batch_last_chapter[2] if previous_batch_last_chapter else None

            prompt_data = self.generate_bulk_chapter_summaries(
                batch,
                title,
                medium_summary=medium_summary_for_context,
                previous_chapter_text=previous_chapter_text,
                return_prompt_only=True
            )

            batch_requests.append(self.build_batch_request(prompt_data['prompt']))
            request_metadata.append({
                'type': 'chapters',
                'chapter_numbers': prompt_data['chapter_numbers'],
                'chapter_titles': {num: chapter_num_to_title[num] for num in prompt_data['chapter_numbers']},
                'model': prompt_data['model'],
                'batch_index': batch_idx
            })

            previous_batch_last_chapter = batch[-1]

        print(f"\n✓ Built {len(batch_requests)} batch request(s)")
        if not skip_overall_summaries:
            print(f"  - 1 overall summaries request")
        print(f"  - {len(batches)} chapter summary request(s)")

        # Submit batch job
        print(f"\n{'='*60}")
        print("Submitting batch job...")
        print(f"{'='*60}")

        model_name = config.SUMMARY_CONFIGS['combined']['model']
        job_name = self.submit_batch_job(
            requests=batch_requests,
            model_name=model_name,
            display_name=f"book-{book_id}-summaries"
        )

        if not job_name:
            raise ValueError("Failed to submit batch job")

        # Save state for resumption
        state_file = save_batch_job_state(
            book_id=book_id,
            job_name=job_name,
            book_title=title,
            request_metadata=request_metadata
        )
        update_batch_job_state(state_file, "running")

        print(f"\n💡 Job can be resumed later using:")
        print(f"   python {Path(__file__).name} --resume {state_file}")

        # Poll for completion
        print(f"\n{'='*60}")
        print(f"⏳ Waiting for batch completion...")
        print(f"{'='*60}")

        batch_job = self.poll_batch_job(job_name, poll_interval_seconds=poll_interval)

        if not batch_job:
            update_batch_job_state(state_file, "failed")
            raise ValueError("Batch job did not complete successfully")

        # Retrieve results
        print(f"\n{'='*60}")
        print(f"📥 Retrieving results...")
        print(f"{'='*60}")

        results = self.retrieve_batch_results(batch_job)

        if not results or len(results) != len(request_metadata):
            update_batch_job_state(state_file, "failed")
            raise ValueError(f"Expected {len(request_metadata)} results, got {len(results)}")

        # Process results and save to database
        print(f"\n{'='*60}")
        print(f"💾 Processing results and saving to database...")
        print(f"{'='*60}")

        all_success = True

        for idx, (result, metadata) in enumerate(zip(results, request_metadata)):
            if 'error' in result:
                print(f"  ❌ Request {idx+1} failed: {result['error']}")
                all_success = False
                continue

            response_text = result['text']

            if metadata['type'] == 'overall':
                # Parse and save overall summaries (reuse existing parsing logic)
                parsed = self.parse_combined_summaries_response(response_text, title, author)
                if parsed:
                    # Save summaries
                    self.db.add_summary(book_id, 'concise', parsed['concise_summary'])
                    self.db.add_summary(book_id, 'medium', parsed['medium_summary'])

                    # Save book metadata (about_text, relevance_now)
                    self.db.update_book_metadata(
                        book_id,
                        about_text=parsed.get('about_text'),
                        relevance_now=parsed.get('relevance_now')
                    )
                    print(f"  ✓ Saved overall summaries")
                else:
                    all_success = False

            elif metadata['type'] == 'chapters':
                # Parse and save chapter summaries (reuse existing parsing logic)
                chapter_numbers = metadata['chapter_numbers']
                chapter_titles = metadata.get('chapter_titles', {})

                # Build index_to_chapter mapping (sequential index -> actual chapter number)
                index_to_chapter = {i+1: chapter_num for i, chapter_num in enumerate(chapter_numbers)}

                summaries = self.parse_bulk_summary_response(
                    response_text,
                    index_to_chapter
                )

                for chapter_num in chapter_numbers:
                    if chapter_num in summaries:
                        section_id = chapter_to_section_id.get(chapter_num) if chapter_to_section_id else None
                        chapter_title = chapter_titles.get(chapter_num, f"Chapter {chapter_num}")
                        chapter_text = chapter_num_to_text.get(chapter_num)  # Get full chapter text

                        self.db.add_chapter(
                            book_id=book_id,
                            chapter_number=chapter_num,
                            chapter_title=chapter_title,
                            summary=summaries[chapter_num],
                            chapter_text=chapter_text,  # Include full chapter text
                            section_id=section_id
                        )
                        print(f"  ✓ Saved chapter {chapter_num}")
                    else:
                        print(f"  ⚠️  Missing summary for chapter {chapter_num}")
                        all_success = False

        if all_success:
            update_batch_job_state(state_file, "completed")
            print(f"\n✅ All summaries generated and saved successfully!")
        else:
            update_batch_job_state(state_file, "partial_failure")
            print(f"\n⚠️  Some requests failed - check output above")

        return {
            'success': all_success,
            'state_file': state_file
        }


def derive_chapter_line_ranges(raw_text, chapters):
    """Derive 1-indexed (start, end) line ranges in raw_text for each detected chapter.

    Used by --dry-run to print line anchors so an LLM reviewer can spot
    boundary bugs against the source file.

    Strategy:
      1. Build a per-chapter anchor: the first ~6 distinct words of the
         normalized chapter text (skipping the chapter title if it appears
         at the start).
      2. Walk raw lines from the previous match cursor; find the first
         non-blank line whose normalized text contains the anchor.
      3. End line = (start of next chapter) - 1, or EOF for the last chapter.
      4. If an anchor can't be located, emit (-1, -1) for it.

    Args:
        raw_text: The original source file contents (str).
        chapters: List of (chapter_number, chapter_title, chapter_text) tuples
                  from SummaryGenerator.detect_chapters().

    Returns:
        List of (chapter_number, start_line, end_line) — 1-indexed, inclusive.
        Same length and order as chapters.
    """
    if not chapters:
        return []

    def _norm(s):
        s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
        s = re.sub(r"\s+", " ", s).strip()
        return s

    raw_lines = raw_text.split("\n")
    normalized_lines = [_norm(line) for line in raw_lines]
    total_lines = len(raw_lines)

    ANCHOR_WORDS = 6

    def _anchor_for(ch_title, ch_text):
        """First ANCHOR_WORDS distinct words of chapter prose, after skipping
        any leading repetition of the chapter title — but only if doing so
        still leaves enough words to anchor against."""
        norm_text = _norm(ch_text)
        if not norm_text:
            return None
        norm_title = _norm(ch_title) if ch_title else ""
        if norm_title and norm_text.startswith(norm_title):
            stripped = norm_text[len(norm_title):].strip()
            if len(stripped.split()) >= ANCHOR_WORDS:
                norm_text = stripped
            # else: keep title in the anchor — better than no anchor at all
        words = norm_text.split()
        if not words:
            return None
        return " ".join(words[:ANCHOR_WORDS])

    anchors = [_anchor_for(t, txt) for (_n, t, txt) in chapters]

    starts = []
    cursor = 0
    for anchor in anchors:
        if anchor is None:
            starts.append(-1)
            continue
        start = -1
        for i in range(cursor, total_lines):
            line = normalized_lines[i]
            if not line:
                continue
            if anchor in line:
                start = i + 1  # 1-indexed
                cursor = i + 1
                break
            # Anchor may span this line + the next (handles soft-wrapped prose)
            if i + 1 < total_lines:
                joined = (line + " " + normalized_lines[i + 1]).strip()
                if anchor in joined:
                    start = i + 1
                    cursor = i + 1
                    break
        starts.append(start)

    # End line = (next found start) - 1, or EOF for the last chapter.
    ends = []
    for idx, start in enumerate(starts):
        if start == -1:
            ends.append(-1)
            continue
        next_start = -1
        for follow in starts[idx + 1 :]:
            if follow > 0:
                next_start = follow
                break
        ends.append(next_start - 1 if next_start > 0 else total_lines)

    return [(chapters[i][0], starts[i], ends[i]) for i in range(len(chapters))]


def main():
    parser = argparse.ArgumentParser(description='Generate book summaries using Gemini API')
    parser.add_argument('input', nargs='?', help='Book file (.txt) or directory for batch processing')
    parser.add_argument('--title', help='Book title (optional, will try to extract from text)')
    parser.add_argument('--author', help='Author name (optional, will try to extract from text)')
    parser.add_argument('--batch', action='store_true', help='Process all .txt files in directory')
    parser.add_argument('--dry-run', action='store_true', help='Preview chapter detection and prompts without making API calls')
    parser.add_argument('--parse-only', action='store_true', help='Parse book and store to database without making any LLM calls')
    parser.add_argument('--partial-run', action='store_true', help='Test mode: Make only 5 LLM calls (concise + medium + first 3 chapters)')
    parser.add_argument('--regenerate-chapters', help='Regenerate specific chapters only (comma-separated, e.g., "101,111")')
    parser.add_argument('--regenerate-overall', action='store_true', help='Regenerate only concise and medium overall summaries')
    parser.add_argument('--sync', action='store_true', help='Use synchronous API mode (default is async batch mode for 50%% cost savings)')
    parser.add_argument('--resume', type=str, metavar='STATE_FILE', help='Resume a previously interrupted batch job from state file')
    parser.add_argument('--list-jobs', action='store_true', help='List all pending batch jobs')
    parser.add_argument('--batch-poll-interval', type=int, default=BATCH_POLL_INTERVAL_SECONDS, help=f'Seconds between batch status checks (default: {BATCH_POLL_INTERVAL_SECONDS})')
    parser.add_argument('--poetry', action='store_true', help='Preserve line breaks for poetry (do not join lines within paragraphs)')

    args = parser.parse_args()

    # Validate that input is provided when needed
    if not args.list_jobs and not args.resume and not args.input:
        parser.error('input is required unless using --list-jobs or --resume')

    # Handle --list-jobs
    if args.list_jobs:
        print("\n" + "="*60)
        print("Pending Batch Jobs")
        print("="*60 + "\n")

        pending_jobs = list_pending_batch_jobs()
        if not pending_jobs:
            print("No pending batch jobs found.")
        else:
            for i, job in enumerate(pending_jobs, 1):
                print(f"{i}. Book ID: {job['book_id']} - {job['book_title']}")
                print(f"   Status: {job['status']}")
                print(f"   Job Name: {job['job_name']}")
                print(f"   State File: {job['state_file']}")
                created_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job['created_at']))
                print(f"   Created: {created_time}\n")
        return

    # Parse regenerate_chapters argument
    regenerate_chapters = None
    if args.regenerate_chapters:
        try:
            regenerate_chapters = [int(ch.strip()) for ch in args.regenerate_chapters.split(',')]
            print(f"Regenerate mode: Will regenerate chapters {regenerate_chapters}")
        except ValueError:
            print("Error: --regenerate-chapters must be comma-separated integers (e.g., '101,111')")
            sys.exit(1)

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables")
        print("Please set it in a .env file or export it")
        sys.exit(1)

    # Initialize generator
    generator = SummaryGenerator(api_key)

    # Handle --resume
    if args.resume:
        state_file = Path(args.resume)
        if not state_file.exists():
            print(f"❌ State file not found: {state_file}")
            sys.exit(1)

        print(f"\n{'='*60}")
        print(f"📂 Resuming batch job from state file...")
        print(f"{'='*60}")

        state = load_batch_job_state(state_file)
        book_id = state['book_id']
        job_name = state['job_name']
        request_metadata = state['request_metadata']

        print(f"  📖 Book ID: {book_id} - {state['book_title']}")
        print(f"  🆔 Job Name: {job_name}")
        print(f"  📊 Status: {state['status']}")

        update_batch_job_state(state_file, "running")

        # Poll for job completion
        batch_job = generator.poll_batch_job(job_name, poll_interval_seconds=args.batch_poll_interval)

        if not batch_job:
            print(f"❌ Batch job did not complete successfully")
            update_batch_job_state(state_file, "failed")
            sys.exit(1)

        # Retrieve and save results
        print(f"\n{'='*60}")
        print(f"📥 Retrieving results...")
        print(f"{'='*60}")

        results = generator.retrieve_batch_results(batch_job)

        if not results or len(results) != len(request_metadata):
            update_batch_job_state(state_file, "failed")
            print(f"❌ Expected {len(request_metadata)} results, got {len(results)}")
            sys.exit(1)

        # Process results and save to database
        print(f"\n{'='*60}")
        print(f"💾 Processing results and saving to database...")
        print(f"{'='*60}")

        # Get book info and chapter_to_section_id from database
        book = generator.db.get_book(book_id)
        chapters = generator.db.get_chapters(book_id)
        chapter_to_section_id = {}
        for chapter in chapters:
            if chapter.get('section_id'):
                chapter_to_section_id[chapter['chapter_number']] = chapter['section_id']

        all_success = True

        for idx, (result, metadata) in enumerate(zip(results, request_metadata)):
            if 'error' in result:
                print(f"  ❌ Request {idx+1} failed: {result['error']}")
                all_success = False
                continue

            response_text = result['text']

            if metadata['type'] == 'overall':
                # Parse and save overall summaries
                parsed = generator.parse_combined_summaries_response(response_text, book['title'], book['author'])
                if parsed:
                    # Save summaries
                    generator.db.add_summary(book_id, 'concise', parsed['concise_summary'])
                    generator.db.add_summary(book_id, 'medium', parsed['medium_summary'])

                    # Save book metadata (about_text, relevance_now)
                    generator.db.update_book_metadata(
                        book_id,
                        about_text=parsed.get('about_text'),
                        relevance_now=parsed.get('relevance_now')
                    )
                    print(f"  ✓ Saved overall summaries")
                else:
                    all_success = False

            elif metadata['type'] == 'chapters':
                # Parse and save chapter summaries
                chapter_numbers = metadata['chapter_numbers']
                chapter_titles = metadata.get('chapter_titles', {})

                # Build index_to_chapter mapping (sequential index -> actual chapter number)
                index_to_chapter = {i+1: chapter_num for i, chapter_num in enumerate(chapter_numbers)}

                summaries = generator.parse_bulk_summary_response(
                    response_text,
                    index_to_chapter
                )

                for chapter_num in chapter_numbers:
                    if chapter_num in summaries:
                        section_id = chapter_to_section_id.get(chapter_num) if chapter_to_section_id else None
                        chapter_title = chapter_titles.get(chapter_num, f"Chapter {chapter_num}")

                        generator.db.add_chapter(
                            book_id=book_id,
                            chapter_number=chapter_num,
                            chapter_title=chapter_title,
                            summary=summaries[chapter_num],
                            section_id=section_id
                        )
                        print(f"  ✓ Saved chapter {chapter_num}")
                    else:
                        print(f"  ⚠️  Missing summary for chapter {chapter_num}")
                        all_success = False

        if all_success:
            update_batch_job_state(state_file, "completed")
            print(f"\n✅ Job resumed and completed successfully!")
        else:
            update_batch_job_state(state_file, "partial_failure")
            print(f"\n⚠️  Some requests failed - check output above")

        sys.exit(0 if all_success else 1)

    # Process books
    if args.batch:
        # Batch mode: process all .txt files in directory
        input_path = Path(args.input)
        if not input_path.is_dir():
            print(f"Error: {input_path} is not a directory")
            sys.exit(1)

        txt_files = list(input_path.glob('*.txt'))
        if not txt_files:
            print(f"No .txt files found in {input_path}")
            sys.exit(1)

        print(f"Found {len(txt_files)} book(s) to process\n")

        for book_file in txt_files:
            try:
                generator.process_book(book_file, dry_run=args.dry_run, parse_only=args.parse_only, partial_run=args.partial_run, regenerate_chapters=regenerate_chapters, regenerate_overall=args.regenerate_overall, use_batch_api=not args.sync, is_poetry=args.poetry)
            except Exception as e:
                print(f"Error processing {book_file.name}: {e}")
                continue

    else:
        # Single file mode
        book_file = Path(args.input)
        if not book_file.exists():
            print(f"Error: File not found: {book_file}")
            sys.exit(1)

        generator.process_book(book_file, args.title, args.author, args.dry_run, args.parse_only, args.partial_run, regenerate_chapters, args.regenerate_overall, use_batch_api=not args.sync, is_poetry=args.poetry)


if __name__ == '__main__':
    main()
