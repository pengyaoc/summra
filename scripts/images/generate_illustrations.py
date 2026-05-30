#!/usr/bin/env python3
"""
Batch generate book covers and chapter illustrations using Gemini image models

This script supports two Gemini image generation models:
1. gemini-3-pro-image-preview (default): High quality, 4K for covers, 2K for chapters
2. gemini-2.5-flash-image: Faster, lower cost, auto resolution (aspect ratio 2:3)

Features:
- Book cover images at 4K resolution (4096x6144 @ 2:3) for highest quality
- Chapter illustrations at 2K resolution (2048x3072 @ 2:3) for balanced quality/cost
- Character consistency via reference images from Chapter 1
- Art style continuity across generations
- Previous chapter context for narrative flow
- Batch API support for 50% cost savings on both covers and chapter illustrations

Processing Modes:
1. Async (default): Submits requests as async batch job via Batch API
   - 50% cost reduction
   - Typical completion: 1-4 hours for 100 chapters
   - For chapters: Chapter 1 generated sync as reference for other chapters
   - For covers: All covers generated asynchronously
2. Synchronous (--sync-mode): Generates one at a time with live progress
   - Costs 2x more than async mode
   - Immediate results with live progress feedback

Usage:
    # Generate cover only (default: async mode with 50% cost savings)
    python scripts/images/generate_gemini_illustrations.py --book-id 53

    # Generate cover with sync mode for immediate results (costs 2x more)
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --sync-mode

    # Use faster flash model (async mode is default)
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --model gemini-2.5-flash-image

    # Generate covers for multiple books (async mode is default)
    python scripts/images/generate_gemini_illustrations.py --book-ids 53,54,55

    # Generate cover AND chapter illustrations (async mode)
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --with-chapters

    # Generate cover AND chapter illustrations (sync mode)
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --with-chapters --sync-mode

    # Generate chapter illustrations only, skip cover (async mode)
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --chapters-only

    # Generate specific chapters (uses existing Chapter 1 if available)
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --chapters-only --chapter-range 2-50

    # Batch process all books missing illustrations (async mode)
    python scripts/images/generate_gemini_illustrations.py --batch-all

    # Dry run to see what would be generated
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --dry-run

    # Customize batch polling interval (for async mode)
    python scripts/images/generate_gemini_illustrations.py --book-id 53 --batch-poll-interval 60

    # List pending batch jobs
    python scripts/images/generate_gemini_illustrations.py --list-jobs

    # Resume an interrupted batch job
    python scripts/images/generate_gemini_illustrations.py --resume data/batch_jobs/book_47_1234567890.json
"""

import sys
import os
import time
import argparse
import base64
import io
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from models import Database
import config

# Import Google GenAI
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai package not found.")
    print("Install it with: pip install google-genai")
    sys.exit(1)


# Configuration for Gemini Image models
# Supported models:
# - "gemini-3-pro-image-preview": High quality, supports explicit image sizing (1K/2K/4K)
# - "gemini-2.5-flash-image": Faster, lower cost, no explicit sizing (aspect ratio only)
DEFAULT_IMAGE_MODEL = "gemini-3-pro-image-preview"
COVER_IMAGE_SIZE = "2K"  # Book covers use 2K (same as chapters, only for gemini-3-pro-image-preview)
IMAGE_SIZE = "2K"  # Chapter illustrations use 2K (only for gemini-3-pro-image-preview)
ASPECT_RATIO = "2:3"  # Book cover aspect ratio (portrait)

# Rate limiting (adjust based on your quota)
# Note: Gemini 3 Pro Image has different rate limits than text models
MAX_REQUESTS_PER_MINUTE = 2  # Conservative limit for image generation
SECONDS_BETWEEN_REQUESTS = 60 / MAX_REQUESTS_PER_MINUTE

# Batch API configuration
BATCH_POLL_INTERVAL_SECONDS = 30  # How often to check batch job status
BATCH_MAX_WAIT_HOURS = 24  # Maximum time to wait for batch completion
BATCH_JOBS_DIR = Path(__file__).parent.parent.parent / "data" / "batch_jobs"  # Directory to store batch job state


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


class GeminiImageGenerator(ImageGeneratorBase):
    """Handler for generating images using Gemini image models"""

    name = "gemini"
    supports_batch = True
    supports_reference_image = True

    def __init__(self, api_key: str, model: str = DEFAULT_IMAGE_MODEL):
        """Initialize the Gemini image generator

        Args:
            api_key: Google API key for Gemini
            model: Model to use for image generation
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.last_request_time = 0

    def _wait_for_rate_limit(self):
        """Wait to respect rate limits"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < SECONDS_BETWEEN_REQUESTS:
            wait_time = SECONDS_BETWEEN_REQUESTS - time_since_last_request
            print(f"  ⏳ Rate limit: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def generate_cover_image(self, book_title: str, book_author: str,
                            medium_summary: str, dry_run: bool = False) -> Tuple[Optional[bytes], str]:
        """Generate a book cover image

        Args:
            book_title: Title of the book
            book_author: Author of the book
            medium_summary: Medium-length summary of the book
            dry_run: If True, don't actually generate the image

        Returns:
            Tuple of (image bytes in PNG format or None if failed, prompt text)
        """
        # Clean title for better LLM understanding (remove hyphens)
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

        # Print full prompt
        print(f"\n{'='*80}")
        print(f"COVER IMAGE PROMPT:")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}\n")

        if dry_run:
            print(f"  [DRY RUN] Skipping actual image generation")
            return (None, prompt)

        self._wait_for_rate_limit()

        try:
            print(f"  📸 Generating cover image with {self.model}...")

            # Build image config based on model capabilities
            image_config_params = {"aspect_ratio": ASPECT_RATIO}
            # Only gemini-3-pro-image-preview supports explicit image_size
            # Use 2K for book covers (same as chapters)
            if "gemini-3-pro-image" in self.model:
                image_config_params["image_size"] = COVER_IMAGE_SIZE
                print(f"  📐 Using {COVER_IMAGE_SIZE} resolution for cover")

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=1.0,  # Higher creativity for artistic images
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(**image_config_params)
                )
            )

            # Extract image from response
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Return the image bytes and prompt
                            return (part.inline_data.data, prompt)

            print("  ❌ No image found in response")
            return (None, prompt)

        except Exception as e:
            print(f"  ❌ Error generating cover: {e}")
            return (None, prompt)

    def generate_chapter_illustration(self, book_title: str, book_author: str,
                                     medium_summary: str, chapter: Dict,
                                     previous_chapter_summary: Optional[str] = None,
                                     reference_image: Optional[bytes] = None,
                                     character_brief: Optional[str] = None,
                                     dry_run: bool = False) -> Tuple[Optional[bytes], str]:
        """Generate illustration for a single chapter

        Args:
            book_title: Title of the book
            book_author: Author of the book
            medium_summary: Medium-length summary of the entire book
            chapter: Chapter dict with 'chapter_number', 'chapter_title', 'summary'
            previous_chapter_summary: Summary of the previous chapter (for context)
            reference_image: Previous illustration to maintain character consistency
            dry_run: If True, don't actually generate image

        Returns:
            Tuple of (image bytes or None if failed, prompt text)
        """
        # character_brief is unused on the Gemini path — reference images carry
        # cross-chapter consistency. Accepted for ImageGeneratorBase interface parity.
        _ = character_brief
        chapter_num = chapter['chapter_number']

        # Build prompt using shared function
        prompt = build_chapter_illustration_prompt(
            book_title=book_title,
            book_author=book_author,
            medium_summary=medium_summary,
            chapter=chapter,
            previous_chapter_summary=previous_chapter_summary
        )

        # Print full prompt
        print(f"\n{'='*80}")
        print(f"CHAPTER ILLUSTRATION PROMPT (Chapter {chapter_num}):")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}\n")

        if dry_run:
            print(f"  [DRY RUN] Skipping actual image generation")
            return (None, prompt)

        self._wait_for_rate_limit()

        try:
            print(f"  📸 Generating illustration for chapter {chapter_num} with {self.model}...")

            # Prepare content - include reference image if provided
            content_parts = []
            if reference_image:
                # Add reference image for character consistency
                content_parts.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64.b64encode(reference_image).decode('utf-8')
                    }
                })
                print(f"  🎨 Using reference image for character consistency")

            content_parts.append(prompt)

            # Build image config based on model capabilities
            image_config_params = {"aspect_ratio": ASPECT_RATIO}
            # Only gemini-3-pro-image-preview supports explicit image_size
            if "gemini-3-pro-image" in self.model:
                image_config_params["image_size"] = IMAGE_SIZE

            response = self.client.models.generate_content(
                model=self.model,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    temperature=1.0,
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(**image_config_params)
                )
            )

            # Extract image from response
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Return the image bytes and prompt
                            return (part.inline_data.data, prompt)

            print("  ❌ No image found in response")
            return (None, prompt)

        except Exception as e:
            print(f"  ❌ Error generating chapter illustration: {e}")
            return (None, prompt)

    def create_batch_job(self, batch_requests: List[Dict],
                        job_display_name: str = "chapter-illustrations-batch") -> Optional[str]:
        """Create and submit a batch job for multiple chapter illustrations

        Args:
            batch_requests: List of batch request dictionaries with 'key' and 'request' fields
            job_display_name: Display name for the batch job

        Returns:
            Batch job name if successful, None otherwise
        """
        try:
            # Create temporary JSONL file
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
            temp_file_path = temp_file.name

            # Write requests to JSONL
            with open(temp_file_path, 'w') as f:
                for req in batch_requests:
                    f.write(json.dumps(req) + '\n')

            print(f"  📝 Created batch request file with {len(batch_requests)} requests")

            # Upload file
            print(f"  ⬆️  Uploading batch request file...")
            uploaded_file = self.client.files.upload(
                file=temp_file_path,
                config=types.UploadFileConfig(
                    display_name=job_display_name,
                    mime_type='application/jsonl'
                )
            )

            # Clean up temp file
            os.unlink(temp_file_path)

            print(f"  ✅ Uploaded file: {uploaded_file.name}")

            # Create batch job
            print(f"  🚀 Submitting batch job...")
            batch_job = self.client.batches.create(
                model=self.model,
                src=uploaded_file.name,
                config=types.CreateBatchJobConfig(
                    display_name=job_display_name
                )
            )

            print(f"  ✅ Batch job created: {batch_job.name}")
            print(f"  📊 Status: {batch_job.state.name}")

            return batch_job.name

        except Exception as e:
            print(f"  ❌ Error creating batch job: {e}")
            return None

    def poll_batch_job(self, job_name: str, poll_interval: int = BATCH_POLL_INTERVAL_SECONDS,
                      max_wait_hours: int = BATCH_MAX_WAIT_HOURS) -> Optional[Dict]:
        """Poll batch job until completion

        Args:
            job_name: Name of the batch job to poll
            poll_interval: Seconds between status checks
            max_wait_hours: Maximum hours to wait before timing out

        Returns:
            Final batch job object if successful, None if failed/timeout
        """
        completed_states = {
            'JOB_STATE_SUCCEEDED',
            'JOB_STATE_FAILED',
            'JOB_STATE_CANCELLED',
            'JOB_STATE_EXPIRED',
        }

        start_time = time.time()
        max_wait_seconds = max_wait_hours * 3600

        try:
            print(f"\n  ⏳ Polling batch job status (checking every {poll_interval}s)...")
            print(f"  ℹ️  Maximum wait time: {max_wait_hours} hours")

            batch_job = self.client.batches.get(name=job_name)

            while batch_job.state.name not in completed_states:
                elapsed = time.time() - start_time
                elapsed_mins = elapsed / 60

                # Check timeout
                if elapsed > max_wait_seconds:
                    print(f"\n  ⚠️  Timeout: Job did not complete within {max_wait_hours} hours")
                    return None

                # Show progress
                status_msg = f"  [{elapsed_mins:.1f}m] Status: {batch_job.state.name}"
                if hasattr(batch_job, 'request_counts'):
                    counts = batch_job.request_counts
                    total = counts.total if hasattr(counts, 'total') else 0
                    succeeded = counts.succeeded if hasattr(counts, 'succeeded') else 0
                    if total > 0:
                        status_msg += f" | Progress: {succeeded}/{total} ({succeeded*100//total}%)"

                print(status_msg)

                # Wait before next check
                time.sleep(poll_interval)
                batch_job = self.client.batches.get(name=job_name)

            # Job completed
            elapsed_total = (time.time() - start_time) / 60
            print(f"\n  ✅ Job finished in {elapsed_total:.1f} minutes")
            print(f"  📊 Final status: {batch_job.state.name}")

            if hasattr(batch_job, 'request_counts'):
                counts = batch_job.request_counts
                print(f"  📈 Results: {counts.succeeded} succeeded, {counts.failed} failed")

            return batch_job

        except Exception as e:
            print(f"  ❌ Error polling batch job: {e}")
            return None

    def retrieve_batch_results(self, batch_job) -> Dict[str, Tuple[Optional[bytes], Optional[str]]]:
        """Retrieve and parse batch job results

        Args:
            batch_job: Completed batch job object

        Returns:
            Dictionary mapping request keys to (image_data, error_message) tuples
        """
        results = {}

        try:
            if batch_job.state.name != 'JOB_STATE_SUCCEEDED':
                print(f"  ⚠️  Batch job did not succeed: {batch_job.state.name}")
                return results

            # Download results file
            result_file_name = batch_job.dest.file_name
            print(f"  ⬇️  Downloading results from: {result_file_name}")

            file_content_bytes = self.client.files.download(file=result_file_name)
            file_content = file_content_bytes.decode('utf-8')

            # Parse JSONL results
            for line in file_content.splitlines():
                if not line.strip():
                    continue

                parsed_response = json.loads(line)
                request_key = parsed_response.get('key', 'unknown')

                # Check for errors
                if 'error' in parsed_response:
                    error_msg = parsed_response['error'].get('message', 'Unknown error')
                    results[request_key] = (None, error_msg)
                    print(f"  ⚠️  Error for {request_key}: {error_msg}")
                    continue

                # Extract image from response
                if 'response' in parsed_response:
                    response = parsed_response['response']
                    image_data = None

                    if 'candidates' in response and len(response['candidates']) > 0:
                        candidate = response['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            for part in candidate['content']['parts']:
                                if 'inlineData' in part:
                                    # Decode base64 image data
                                    image_data = base64.b64decode(part['inlineData']['data'])
                                    break

                    if image_data:
                        results[request_key] = (image_data, None)
                    else:
                        results[request_key] = (None, "No image data in response")
                        print(f"  ⚠️  No image found for {request_key}")

            print(f"  ✅ Retrieved {len(results)} results")
            return results

        except Exception as e:
            print(f"  ❌ Error retrieving batch results: {e}")
            return results


def save_image(image_data: bytes, output_path: Path, optimize: bool = True) -> bool:
    """Save image data to a file and optionally optimize size

    Args:
        image_data: Raw image bytes
        output_path: Path to save the image
        optimize: Whether to optimize the image size

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if optimize:
            # Load image and optimize
            img = Image.open(io.BytesIO(image_data))

            # Save with optimization
            if output_path.suffix.lower() in ['.jpg', '.jpeg']:
                img.save(output_path, 'JPEG', quality=85, optimize=True)
            else:
                img.save(output_path, 'PNG', optimize=True)
        else:
            # Save raw bytes
            with open(output_path, 'wb') as f:
                f.write(image_data)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  ✅ Saved: {output_path} ({file_size_mb:.2f} MB)")

        return True

    except Exception as e:
        print(f"  ❌ Error saving image to {output_path}: {e}")
        return False


def clean_title_for_prompt(title: str) -> str:
    """Clean book title for use in LLM prompts

    Args:
        title: Original book title

    Returns:
        Cleaned title with hyphens removed
    """
    return title.replace('-', ' ')


def build_chapter_illustration_prompt(book_title: str, book_author: str,
                                     medium_summary: str, chapter: Dict,
                                     previous_chapter_summary: Optional[str] = None) -> str:
    """Build the prompt for chapter illustration generation

    Args:
        book_title: Title of the book
        book_author: Author of the book
        medium_summary: Medium-length summary of the entire book
        chapter: Chapter dict with 'chapter_number', 'chapter_title', 'summary'
        previous_chapter_summary: Summary of the previous chapter (for context)

    Returns:
        Complete prompt string for chapter illustration
    """
    chapter_num = chapter['chapter_number']
    chapter_title = chapter.get('chapter_title', '')
    chapter_summary = chapter['summary']

    title_part = f" - {chapter_title}" if chapter_title else ""

    # Build previous context section
    prev_context = ""
    if previous_chapter_summary:
        prev_context = f"""
Summary of previous chapter for reference:
{previous_chapter_summary}

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

Summary of the overall book (for reference):
{medium_summary}

{prev_context}Chapter to be illustrated:
=== Chapter {chapter_num}{title_part} ===
{chapter_summary}"""

    return prompt


def save_batch_job_state(book_id: int, job_name: str, chapter_numbers: List[int],
                        model: str, chapter_range: Optional[Tuple[int, int]] = None) -> Path:
    """Save batch job state to disk for later resumption

    Args:
        book_id: Book ID being processed
        job_name: Gemini batch job name/ID
        chapter_numbers: List of chapter numbers in this batch
        model: Model used for generation
        chapter_range: Optional chapter range filter

    Returns:
        Path to the saved state file
    """
    BATCH_JOBS_DIR.mkdir(parents=True, exist_ok=True)

    state = {
        "book_id": book_id,
        "job_name": job_name,
        "chapter_numbers": chapter_numbers,
        "model": model,
        "chapter_range": chapter_range,
        "created_at": time.time(),
        "status": "pending"
    }

    state_file = BATCH_JOBS_DIR / f"book_{book_id}_{int(time.time())}.json"
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)

    print(f"  💾 Saved batch job state: {state_file}")
    return state_file


def load_batch_job_state(state_file: Path) -> Dict:
    """Load batch job state from disk

    Args:
        state_file: Path to the state file

    Returns:
        Dictionary with job state
    """
    with open(state_file, 'r') as f:
        return json.load(f)


def update_batch_job_state(state_file: Path, status: str, **kwargs):
    """Update batch job state file

    Args:
        state_file: Path to the state file
        status: New status value
        **kwargs: Additional fields to update
    """
    state = load_batch_job_state(state_file)
    state['status'] = status
    state['updated_at'] = time.time()
    state.update(kwargs)

    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def list_pending_batch_jobs() -> List[Dict]:
    """List all pending batch jobs

    Returns:
        List of job state dictionaries
    """
    if not BATCH_JOBS_DIR.exists():
        return []

    pending_jobs = []
    for state_file in BATCH_JOBS_DIR.glob("book_*.json"):
        try:
            state = load_batch_job_state(state_file)
            if state.get('status') in ['pending', 'running']:
                state['state_file'] = str(state_file)
                pending_jobs.append(state)
        except Exception as e:
            print(f"  ⚠️  Error loading {state_file}: {e}")

    return sorted(pending_jobs, key=lambda x: x.get('created_at', 0))


def filter_eligible_chapters(chapters: List[Dict], chapter_range: Optional[Tuple[int, int]] = None) -> List[Dict]:
    """Filter chapters to only those eligible for illustrations

    Args:
        chapters: List of chapter dictionaries
        chapter_range: Optional tuple of (start_chapter, end_chapter) inclusive

    Returns:
        Filtered list of chapters eligible for illustrations
    """
    # Filter out chapters that shouldn't have illustrations
    filtered_chapters = []
    for chapter in chapters:
        # Skip chapters with less than 200 words
        if chapter.get('word_count', 0) < 200:
            print(f"  ⏭️  Skipping Chapter {chapter['chapter_number']}: too short ({chapter.get('word_count', 0)} words)")
            continue

        # Skip preface chapters (identify by title containing "preface" or chapter_number == 0)
        chapter_title = (chapter.get('chapter_title') or '').lower()
        if 'preface' in chapter_title or chapter['chapter_number'] == 0:
            print(f"  ⏭️  Skipping Chapter {chapter['chapter_number']}: preface chapter")
            continue

        filtered_chapters.append(chapter)

    # Filter by chapter range if specified
    if chapter_range:
        start, end = chapter_range
        filtered_chapters = [ch for ch in filtered_chapters if start <= ch['chapter_number'] <= end]

    return filtered_chapters


def generate_book_cover(db: Database, generator: GeminiImageGenerator,
                       book_id: int, dry_run: bool = False) -> bool:
    """Generate and save cover for a book

    Args:
        db: Database instance
        generator: GeminiImageGenerator instance
        book_id: Book ID
        dry_run: If True, don't actually generate or save

    Returns:
        True if successful, False otherwise
    """
    # Get book info
    book = db.get_book(book_id)
    if not book:
        print(f"❌ Book {book_id} not found")
        return False

    # Check if book already has a custom-generated cover
    if book.get('cover_source') == 'gemini-generated':
        print(f"ℹ️  Book {book_id} already has a gemini-generated cover (cover_source='gemini-generated')")
        print(f"   Skipping cover generation to avoid overwriting existing custom artwork")
        return True

    # Get medium summary
    summary = db.get_summary(book_id, 'medium')
    if not summary:
        print(f"❌ No medium summary found for book {book_id}")
        return False

    print(f"\n{'='*80}")
    print(f"📚 Generating cover for: {book['title']} by {book['author']}")
    print(f"{'='*80}")

    # Generate cover
    cover_data, cover_prompt = generator.generate_cover_image(
        book_title=book['title'],
        book_author=book['author'],
        medium_summary=summary['content'],
        dry_run=dry_run
    )

    if not cover_data and not dry_run:
        return False

    if dry_run:
        return True

    # Save cover image to data/cover_originals first
    cover_originals_dir = project_root / "data" / "cover_originals"
    cover_originals_dir.mkdir(parents=True, exist_ok=True)
    cover_path = cover_originals_dir / f"{book_id}.png"

    if save_image(cover_data, cover_path):
        print(f"  ℹ️  Original cover saved to {cover_path}")

        # Auto-optimize cover to create web-optimized versions
        auto_optimize_covers([book_id], dry_run=dry_run)

        return True

    return False


def auto_optimize_illustrations(book_id: int, chapter_numbers: list = None, dry_run: bool = False) -> bool:
    """Automatically run the optimization script after generating illustrations

    Args:
        book_id: Book ID to optimize
        chapter_numbers: Optional list of chapter numbers to optimize (if None, optimizes all)
        dry_run: If True, don't actually run optimization

    Returns:
        True if optimization succeeded, False otherwise
    """
    if dry_run:
        chapters_str = f" chapters {chapter_numbers}" if chapter_numbers else " all chapters"
        print(f"\n[DRY RUN] Would run optimization for book {book_id}{chapters_str}")
        return True

    chapters_str = f" for {len(chapter_numbers)} chapters" if chapter_numbers else ""
    print(f"\n{'='*80}")
    print(f"🔄 Auto-optimizing illustrations for book {book_id}{chapters_str}...")
    print(f"{'='*80}\n")

    try:
        # Run the optimization script
        optimize_script = project_root / "scripts" / "reduce_illustration_resolution.py"

        # Build command with optional chapter numbers and update-db flag
        cmd = [sys.executable, str(optimize_script), "--book-id", str(book_id)]
        if chapter_numbers:
            chapters_arg = ",".join(str(num) for num in sorted(chapter_numbers))
            cmd.extend(["--chapters", chapters_arg])
        cmd.append("--update-db")  # Always update database when called from generation script

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        # Print the output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode == 0:
            print(f"\n✅ Optimization completed successfully!")
            return True
        else:
            print(f"\n⚠️  Optimization script returned exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n❌ Error running optimization script: {e}")
        return False


def auto_optimize_covers(book_ids: list, dry_run: bool = False) -> bool:
    """Automatically run the optimization script after generating covers

    Args:
        book_ids: List of book IDs to optimize covers for
        dry_run: If True, don't actually run optimization

    Returns:
        True if optimization succeeded, False otherwise
    """
    if dry_run:
        print(f"\n[DRY RUN] Would run cover optimization for books {book_ids}")
        return True

    books_str = f" for {len(book_ids)} books" if len(book_ids) > 1 else f" for book {book_ids[0]}"
    print(f"\n{'='*80}")
    print(f"🔄 Auto-optimizing covers{books_str}...")
    print(f"{'='*80}\n")

    try:
        # First, copy PNGs from data/cover_originals to frontend/static/covers
        # The optimization script expects source files to be in frontend/static/covers
        import shutil
        cover_originals_dir = project_root / "data" / "cover_originals"
        frontend_covers_dir = config.COVERS_DIR

        print(f"📋 Preparing covers for optimization...")
        for book_id in book_ids:
            source_png = cover_originals_dir / f"{book_id}.png"
            dest_png = frontend_covers_dir / f"{book_id}.png"

            if source_png.exists():
                # Remove ALL existing versions (PNG, JPG, WebP) to avoid conflicts with old optimized files
                for ext in ['.png', '.jpg', '.webp']:
                    old_file = frontend_covers_dir / f"{book_id}{ext}"
                    if old_file.exists():
                        old_file.unlink()
                        print(f"  🗑️  Removed old version: {old_file.name}")

                shutil.copy2(source_png, dest_png)
                print(f"  ✓ Prepared cover for book {book_id}")
            else:
                print(f"  ⚠️  No cover found at {source_png}")

        # Run the optimization script
        optimize_script = project_root / "scripts" / "reduce_illustration_resolution.py"

        # Build command for covers optimization
        cmd = [sys.executable, str(optimize_script), "--covers", "--update-db"]

        # If single book, use --book-id; if multiple, process each separately
        if len(book_ids) == 1:
            cmd.extend(["--book-id", str(book_ids[0])])
        else:
            # For multiple books, we'll run the command for each book
            # (Note: could be optimized to process all at once if script supports it)
            all_success = True
            for book_id in book_ids:
                single_cmd = [sys.executable, str(optimize_script), "--covers", "--book-id", str(book_id), "--update-db"]
                result = subprocess.run(single_cmd, capture_output=True, text=True, check=False)

                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)

                if result.returncode != 0:
                    all_success = False
                    print(f"\n⚠️  Optimization failed for book {book_id}")

            if all_success:
                print(f"\n✅ All cover optimizations completed successfully!")
            return all_success

        # Single book case
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        # Print the output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode == 0:
            print(f"\n✅ Cover optimization completed successfully!")
            return True
        else:
            print(f"\n⚠️  Optimization script returned exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"\n❌ Error running optimization script: {e}")
        return False


def generate_chapter_illustrations_for_book(db: Database, generator: GeminiImageGenerator,
                                           book_id: int, chapter_range: Optional[Tuple[int, int]] = None,
                                           dry_run: bool = False) -> bool:
    """Generate illustrations for all chapters of a book

    Args:
        db: Database instance
        generator: GeminiImageGenerator instance
        book_id: Book ID
        chapter_range: Optional tuple of (start_chapter, end_chapter) inclusive
        dry_run: If True, don't actually generate or save

    Returns:
        True if all successful, False if any failed
    """
    # Get book info
    book = db.get_book(book_id)
    if not book:
        print(f"❌ Book {book_id} not found")
        return False

    # Get medium summary
    summary = db.get_summary(book_id, 'medium')
    if not summary:
        print(f"❌ No medium summary found for book {book_id}")
        return False

    # Get chapters
    chapters = db.get_chapters(book_id)
    if not chapters:
        print(f"❌ No chapters found for book {book_id}")
        return False

    # Filter chapters eligible for illustrations
    chapters = filter_eligible_chapters(chapters, chapter_range)

    if not chapters:
        if chapter_range:
            print(f"❌ No chapters found in range {chapter_range[0]}-{chapter_range[1]}")
            return False
        else:
            print(f"ℹ️  No chapters eligible for illustrations after filtering")
            return True

    print(f"\n{'='*80}")
    print(f"🎨 Generating chapter illustrations for: {book['title']} by {book['author']}")
    print(f"   Total chapters: {len(chapters)}")
    print(f"{'='*80}")

    # Create illustrations directory in data/illustration_originals
    illustrations_originals_dir = project_root / "data" / "illustration_originals" / str(book_id)
    illustrations_originals_dir.mkdir(parents=True, exist_ok=True)

    # Also check frontend/static/illustrations for existing files (for reference)
    illustrations_frontend_dir = config.ILLUSTRATIONS_DIR / str(book_id)

    all_success = True
    reference_image = None  # Will store the previous illustration for consistency
    generated_chapters = []  # Track successfully generated chapters for optimization

    # Process chapters one at a time
    for i, chapter in enumerate(chapters):
        chapter_num = chapter['chapter_number']

        print(f"\n--- Chapter {i+1}/{len(chapters)} (Chapter {chapter_num}) ---")

        # Get previous chapter context and illustration from the actual book sequence
        # (not just from the filtered chapters list, for chapter-range support)
        previous_chapter_summary = None

        # Try to load previous illustration from filesystem if this isn't the first chapter
        if chapter_num > 1 and reference_image is None:
            # Load the immediately preceding chapter's illustration from originals first
            prev_img_path = illustrations_originals_dir / f"{chapter_num - 1}.png"
            if not prev_img_path.exists():
                # Fallback to frontend/static/illustrations
                prev_img_path = illustrations_frontend_dir / f"{chapter_num - 1}.png"
            if prev_img_path.exists():
                try:
                    with open(prev_img_path, 'rb') as f:
                        reference_image = f.read()
                    print(f"  📂 Loaded reference image from chapter {chapter_num - 1}")
                except Exception as e:
                    print(f"  ⚠️  Could not load reference image: {e}")

            # Get the previous chapter's summary from database
            prev_chapter_data = db.get_chapter(book_id, chapter_num - 1)
            if prev_chapter_data:
                previous_chapter_summary = prev_chapter_data.get('summary', '')

        # Fallback: if we're processing sequentially and have the previous chapter in our list
        if previous_chapter_summary is None and i > 0:
            prev_chapter = chapters[i - 1]
            previous_chapter_summary = prev_chapter.get('summary', '')

        # Generate illustration for this chapter
        image_data, chapter_prompt = generator.generate_chapter_illustration(
            book_title=book['title'],
            book_author=book['author'],
            medium_summary=summary['content'],
            chapter=chapter,
            previous_chapter_summary=previous_chapter_summary,
            reference_image=reference_image,
            dry_run=dry_run
        )

        if not image_data and not dry_run:
            print(f"  ❌ Failed to generate illustration for chapter {chapter_num}")
            all_success = False
            continue

        if dry_run:
            continue

        # Save image to data/illustration_originals
        img_path = illustrations_originals_dir / f"{chapter_num}.png"
        if save_image(image_data, img_path):
            print(f"  ℹ️  Original illustration saved to {img_path}")
            print(f"  ℹ️  Run reduce_illustration_resolution.py to create optimized versions")

            # Save the generated image as reference for next chapter
            reference_image = image_data
            # Track successfully generated chapter
            generated_chapters.append(chapter_num)
        else:
            all_success = False

    # Auto-optimize only newly generated illustrations
    if generated_chapters and not dry_run:
        auto_optimize_illustrations(book_id, chapter_numbers=generated_chapters, dry_run=dry_run)

    return all_success


def generate_chapter_illustrations_batch(db: Database, generator: GeminiImageGenerator,
                                         book_id: int, chapter_range: Optional[Tuple[int, int]] = None,
                                         poll_interval: int = BATCH_POLL_INTERVAL_SECONDS,
                                         dry_run: bool = False) -> bool:
    """Generate chapter illustrations using batch API

    This function:
    1. Generates Chapter 1 synchronously (if needed) to use as reference
    2. Submits all other chapters as a batch job with Chapter 1 reference
    3. Polls for completion and saves results

    Args:
        db: Database instance
        generator: GeminiImageGenerator instance
        book_id: Book ID
        chapter_range: Optional tuple of (start_chapter, end_chapter) inclusive
        poll_interval: Seconds between batch status checks
        dry_run: If True, don't actually generate or save

    Returns:
        True if all successful, False if any failed
    """
    # Get book info
    book = db.get_book(book_id)
    if not book:
        print(f"❌ Book {book_id} not found")
        return False

    # Get medium summary
    summary = db.get_summary(book_id, 'medium')
    if not summary:
        print(f"❌ No medium summary found for book {book_id}")
        return False

    # Get chapters
    chapters = db.get_chapters(book_id)
    if not chapters:
        print(f"❌ No chapters found for book {book_id}")
        return False

    # Filter chapters eligible for illustrations
    chapters = filter_eligible_chapters(chapters, chapter_range)

    if not chapters:
        if chapter_range:
            print(f"❌ No chapters found in range {chapter_range[0]}-{chapter_range[1]}")
            return False
        else:
            print(f"ℹ️  No chapters eligible for illustrations after filtering")
            return True

    print(f"\n{'='*80}")
    print(f"🎨 Generating chapter illustrations (BATCH MODE) for: {book['title']} by {book['author']}")
    print(f"   Total chapters: {len(chapters)}")
    print(f"{'='*80}")

    # Create illustrations directory in data/illustration_originals
    illustrations_originals_dir = project_root / "data" / "illustration_originals" / str(book_id)
    illustrations_originals_dir.mkdir(parents=True, exist_ok=True)

    # Also check frontend/static/illustrations for existing files (for reference)
    illustrations_frontend_dir = config.ILLUSTRATIONS_DIR / str(book_id)

    # Step 1: Get or generate Chapter 1 as reference image
    reference_image = None
    # Check both originals and frontend directories for Chapter 1
    chapter_1_path = illustrations_originals_dir / "1.png"
    if not chapter_1_path.exists():
        chapter_1_path_frontend = illustrations_frontend_dir / "1.png" if illustrations_frontend_dir.exists() else None
        if chapter_1_path_frontend and chapter_1_path_frontend.exists():
            chapter_1_path = chapter_1_path_frontend

    if chapter_1_path.exists():
        # Load existing Chapter 1 illustration
        try:
            with open(chapter_1_path, 'rb') as f:
                reference_image = f.read()
            print(f"\n✅ Using existing Chapter 1 illustration as reference")
        except Exception as e:
            print(f"⚠️  Could not load Chapter 1 illustration: {e}")
    else:
        # Need to generate Chapter 1 synchronously
        chapter_1 = None
        for ch in chapters:
            if ch['chapter_number'] == 1:
                chapter_1 = ch
                break

        if chapter_1:
            print(f"\n{'='*80}")
            print(f"📸 Generating Chapter 1 synchronously (for reference)...")
            print(f"{'='*80}")

            # Generate Chapter 1 using sync API
            image_data, _ = generator.generate_chapter_illustration(
                book_title=book['title'],
                book_author=book['author'],
                medium_summary=summary['content'],
                chapter=chapter_1,
                previous_chapter_summary=None,
                reference_image=None,
                dry_run=dry_run
            )

            if image_data and not dry_run:
                # Save Chapter 1 to data/illustration_originals
                chapter_1_save_path = illustrations_originals_dir / "1.png"
                if save_image(image_data, chapter_1_save_path):
                    reference_image = image_data
                    print(f"✅ Chapter 1 generated and saved to {chapter_1_save_path}")
                    # Auto-optimize Chapter 1 immediately
                    auto_optimize_illustrations(book_id, chapter_numbers=[1], dry_run=False)
                else:
                    print(f"❌ Failed to save Chapter 1")
                    return False
            elif dry_run:
                print(f"[DRY RUN] Would generate Chapter 1 here")
                reference_image = b"dummy_reference_data"  # For dry run flow
            else:
                print(f"❌ Failed to generate Chapter 1")
                return False

    # Step 2: Prepare batch requests for remaining chapters
    batch_chapters = [ch for ch in chapters if ch['chapter_number'] != 1]

    if not batch_chapters:
        print(f"\nℹ️  Only Chapter 1 needed - batch processing not required")
        return True

    print(f"\n{'='*80}")
    print(f"📦 Preparing batch requests for {len(batch_chapters)} chapters...")
    print(f"{'='*80}")

    batch_requests = []
    for chapter in batch_chapters:
        chapter_num = chapter['chapter_number']

        # Get previous chapter context
        previous_chapter_summary = None
        prev_chapter_data = db.get_chapter(book_id, chapter_num - 1)
        if prev_chapter_data:
            previous_chapter_summary = prev_chapter_data.get('summary', '')

        # Build prompt using shared function
        prompt = build_chapter_illustration_prompt(
            book_title=book['title'],
            book_author=book['author'],
            medium_summary=summary['content'],
            chapter=chapter,
            previous_chapter_summary=previous_chapter_summary
        )

        # Print full prompt for verification
        print(f"\n{'='*80}")
        print(f"BATCH REQUEST PROMPT (Chapter {chapter_num}):")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}\n")

        # Build content parts (including reference image)
        content_parts = []
        if reference_image:
            content_parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(reference_image).decode('utf-8')
                }
            })
        content_parts.append({"text": prompt})

        # Build generation_config with image settings
        generation_config = {
            "temperature": 1.0,
            "response_modalities": ["IMAGE"],
        }

        # Add image config for aspect ratio and size
        image_config = {"aspect_ratio": ASPECT_RATIO}
        if "gemini-3-pro-image" in generator.model:
            image_config["image_size"] = IMAGE_SIZE
        generation_config["image_config"] = image_config

        # Create batch request
        # Batch API JSONL format for file upload:
        # {"key": "...", "request": {"contents": [...], "generation_config": {...}}}
        batch_request = {
            "key": f"chapter-{chapter_num}",
            "request": {
                "contents": [{
                    "parts": content_parts,
                    "role": "user"
                }],
                "generation_config": generation_config
            }
        }

        batch_requests.append(batch_request)

    if dry_run:
        print(f"\n[DRY RUN] Would submit batch of {len(batch_requests)} chapters")
        print(f"[DRY RUN] Batch requests prepared with Chapter 1 reference image")
        return True

    # Step 3: Submit batch job
    print(f"\n{'='*80}")
    print(f"🚀 Submitting batch job...")
    print(f"{'='*80}")

    job_name = generator.create_batch_job(
        batch_requests=batch_requests,
        job_display_name=f"book-{book_id}-chapters"
    )

    if not job_name:
        print(f"❌ Failed to create batch job")
        return False

    # Save job state for resumption
    chapter_numbers = [ch['chapter_number'] for ch in batch_chapters]
    state_file = save_batch_job_state(
        book_id=book_id,
        job_name=job_name,
        chapter_numbers=chapter_numbers,
        model=generator.model,
        chapter_range=chapter_range
    )
    update_batch_job_state(state_file, "running")

    print(f"\n💡 Job can be resumed later using:")
    print(f"   python {Path(__file__).name} --resume {state_file}")

    # Step 4: Poll for completion
    print(f"\n{'='*80}")
    print(f"⏳ Waiting for batch completion...")
    print(f"{'='*80}")

    batch_job = generator.poll_batch_job(job_name, poll_interval=poll_interval)

    if not batch_job:
        print(f"❌ Batch job did not complete successfully")
        return False

    # Step 5: Retrieve and save results
    print(f"\n{'='*80}")
    print(f"📥 Retrieving results...")
    print(f"{'='*80}")

    results = generator.retrieve_batch_results(batch_job)

    if not results:
        print(f"❌ No results retrieved")
        return False

    # Step 6: Save images and update database
    print(f"\n{'='*80}")
    print(f"💾 Saving chapter illustrations...")
    print(f"{'='*80}")

    all_success = True
    generated_chapters = []  # Track successfully saved chapters
    for chapter in batch_chapters:
        chapter_num = chapter['chapter_number']
        result_key = f"chapter-{chapter_num}"

        if result_key not in results:
            print(f"❌ No result for Chapter {chapter_num}")
            all_success = False
            continue

        image_data, error = results[result_key]

        if error:
            print(f"❌ Chapter {chapter_num} failed: {error}")
            all_success = False
            continue

        if not image_data:
            print(f"❌ No image data for Chapter {chapter_num}")
            all_success = False
            continue

        # Save image to data/illustration_originals
        img_path = illustrations_originals_dir / f"{chapter_num}.png"
        if save_image(image_data, img_path):
            print(f"  ℹ️  Original illustration saved for chapter {chapter_num}")
            generated_chapters.append(chapter_num)
        else:
            all_success = False

    print(f"\n{'='*80}")
    if all_success:
        print(f"✅ All chapter illustrations generated successfully!")
        print(f"  ℹ️  Run reduce_illustration_resolution.py to create optimized versions")
        update_batch_job_state(state_file, "completed")
    else:
        print(f"⚠️  Some chapters failed - check output above")
        update_batch_job_state(state_file, "partial_failure")
    print(f"{'='*80}")

    # Auto-optimize only newly generated illustrations
    if generated_chapters:
        auto_optimize_illustrations(book_id, chapter_numbers=generated_chapters, dry_run=False)

    return all_success


def resume_batch_job(state_file: Path, generator: GeminiImageGenerator,
                    poll_interval: int = BATCH_POLL_INTERVAL_SECONDS) -> bool:
    """Resume a previously started batch job

    Args:
        state_file: Path to the saved state file
        generator: GeminiImageGenerator instance
        poll_interval: Seconds between status checks

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*80}")
    print(f"📂 Resuming batch job from state file...")
    print(f"{'='*80}")

    # Load saved state
    state = load_batch_job_state(state_file)
    book_id = state['book_id']
    job_name = state['job_name']
    chapter_numbers = state['chapter_numbers']

    print(f"  📖 Book ID: {book_id}")
    print(f"  🆔 Job Name: {job_name}")
    print(f"  📄 Chapters: {len(chapter_numbers)}")
    print(f"  📊 Status: {state['status']}")

    # Initialize database
    db = Database()

    # Get book info
    book = db.get_book(book_id)
    if not book:
        print(f"❌ Book {book_id} not found")
        return False

    # Create illustrations directory in data/illustration_originals
    illustrations_originals_dir = project_root / "data" / "illustration_originals" / str(book_id)
    illustrations_originals_dir.mkdir(parents=True, exist_ok=True)

    # Poll for job completion
    print(f"\n{'='*80}")
    print(f"⏳ Checking batch job status...")
    print(f"{'='*80}")

    update_batch_job_state(state_file, "running")

    batch_job = generator.poll_batch_job(job_name, poll_interval=poll_interval)

    if not batch_job:
        print(f"❌ Batch job did not complete successfully")
        update_batch_job_state(state_file, "failed")
        return False

    # Retrieve and save results
    print(f"\n{'='*80}")
    print(f"📥 Retrieving results...")
    print(f"{'='*80}")

    results = generator.retrieve_batch_results(batch_job)

    if not results:
        print(f"❌ No results retrieved")
        update_batch_job_state(state_file, "failed")
        return False

    # Save images and update database
    print(f"\n{'='*80}")
    print(f"💾 Saving chapter illustrations...")
    print(f"{'='*80}")

    all_success = True
    generated_chapters = []  # Track successfully saved chapters
    for chapter_num in chapter_numbers:
        result_key = f"chapter-{chapter_num}"

        if result_key not in results:
            print(f"❌ No result for Chapter {chapter_num}")
            all_success = False
            continue

        image_data, error = results[result_key]

        if error:
            print(f"❌ Chapter {chapter_num} failed: {error}")
            all_success = False
            continue

        if not image_data:
            print(f"❌ No image data for Chapter {chapter_num}")
            all_success = False
            continue

        # Get chapter info for database update
        chapter = db.get_chapter(book_id, chapter_num)
        if not chapter:
            print(f"⚠️  Chapter {chapter_num} not found in database")
            all_success = False
            continue

        # Save image to data/illustration_originals
        img_path = illustrations_originals_dir / f"{chapter_num}.png"
        if save_image(image_data, img_path):
            print(f"  ℹ️  Original illustration saved for chapter {chapter_num}")
            generated_chapters.append(chapter_num)
        else:
            all_success = False

    print(f"\n{'='*80}")
    if all_success:
        print(f"✅ All chapter illustrations retrieved successfully!")
        print(f"  ℹ️  Run reduce_illustration_resolution.py to create optimized versions")
        update_batch_job_state(state_file, "completed")
    else:
        print(f"⚠️  Some chapters failed - check output above")
        update_batch_job_state(state_file, "partial_failure")
    print(f"{'='*80}")

    # Auto-optimize only newly retrieved illustrations
    if generated_chapters:
        auto_optimize_illustrations(book_id, chapter_numbers=generated_chapters, dry_run=False)

    return all_success


def find_books_without_covers(db: Database) -> List[Dict]:
    """Find books that don't have generated covers"""
    all_books = db.get_all_books()
    books_needing_covers = []

    for book in all_books:
        # Check if book has medium summary (required for generation)
        summary = db.get_summary(book['id'], 'medium')
        if not summary:
            continue

        # Check if cover exists
        cover_path = config.COVERS_DIR / f"{book['id']}.png"
        if not cover_path.exists():
            books_needing_covers.append(book)

    return books_needing_covers


def find_books_without_chapter_illustrations(db: Database) -> List[Dict]:
    """Find books that have chapters but missing illustrations"""
    all_books = db.get_all_books()
    books_needing_illustrations = []

    for book in all_books:
        # Check if book has chapters with summaries
        chapters = db.get_chapters(book['id'])
        if not chapters:
            continue

        # Check if book has medium summary (required for generation)
        summary = db.get_summary(book['id'], 'medium')
        if not summary:
            continue

        # Check if any chapters are missing illustrations
        illustrations_dir = config.ILLUSTRATIONS_DIR / str(book['id'])
        missing = False
        for chapter in chapters:
            img_path = illustrations_dir / f"{chapter['chapter_number']}.png"
            if not img_path.exists():
                missing = True
                break

        if missing:
            books_needing_illustrations.append(book)

    return books_needing_illustrations


def generate_book_covers_batch(db: Database, generator: GeminiImageGenerator,
                               book_ids: List[int], poll_interval: int = BATCH_POLL_INTERVAL_SECONDS,
                               dry_run: bool = False) -> bool:
    """Generate book covers for multiple books using async batch API

    Args:
        db: Database instance
        generator: GeminiImageGenerator instance
        book_ids: List of book IDs to generate covers for
        poll_interval: Seconds between batch status checks
        dry_run: If True, don't actually generate or save

    Returns:
        True if all successful, False if any failed
    """
    print(f"\n{'='*80}")
    print(f"📚 Generating covers for {len(book_ids)} books using async batch API")
    print(f"{'='*80}")

    # Prepare batch requests
    batch_requests = []
    book_data = {}  # Store book info for later saving

    for book_id in book_ids:
        # Get book info
        book = db.get_book(book_id)
        if not book:
            print(f"⚠️  Book {book_id} not found, skipping")
            continue

        # Check if book already has a custom-generated cover
        if book.get('cover_source') == 'gemini-generated':
            print(f"ℹ️  Book {book_id} ({book['title']}) already has a gemini-generated cover, skipping")
            continue

        # Get medium summary
        summary = db.get_summary(book_id, 'medium')
        if not summary:
            print(f"⚠️  No medium summary found for book {book_id} ({book['title']}), skipping")
            continue

        # Clean title for better LLM understanding (remove hyphens)
        clean_title = clean_title_for_prompt(book['title'])

        # Build the prompt (same as single cover generation)
        prompt = f"""Generate book cover art for "{clean_title}" by {book['author']}. Your main focus is accurate visual storytelling — the cover should vividly capture the essence, tone, and meaning of the book's content.

Your process:
1. Interpret the book summary below to understand its mood, symbolism, and key imagery.
2. Ensure the cover adheres to the following layout rules:
   - The title "{clean_title}" must appear at the top, complete and correctly spelled.
   - The author name "{book['author']}" must appear at the bottom.
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
{summary['content']}

Generate ONE high-quality, professional book cover."""

        # Print full prompt for verification
        print(f"\n{'='*80}")
        print(f"BATCH COVER REQUEST (Book {book_id}: {book['title']}):")
        print(f"{'='*80}")
        print(prompt)
        print(f"{'='*80}\n")

        # Build generation_config with image settings
        generation_config = {
            "temperature": 1.0,
            "response_modalities": ["IMAGE"],
        }

        # Add image config for aspect ratio and size
        # Use 2K for book covers (same as chapters)
        image_config = {"aspect_ratio": ASPECT_RATIO}
        if "gemini-3-pro-image" in generator.model:
            image_config["image_size"] = COVER_IMAGE_SIZE
        generation_config["image_config"] = image_config

        # Create batch request
        batch_request = {
            "key": f"cover-{book_id}",
            "request": {
                "contents": [{
                    "parts": [{"text": prompt}],
                    "role": "user"
                }],
                "generation_config": generation_config
            }
        }

        batch_requests.append(batch_request)
        book_data[book_id] = book

    if not batch_requests:
        print(f"\nℹ️  No covers need to be generated")
        return True

    if dry_run:
        print(f"\n[DRY RUN] Would submit batch of {len(batch_requests)} cover requests")
        return True

    # Submit batch job
    print(f"\n{'='*80}")
    print(f"🚀 Submitting batch job for {len(batch_requests)} covers...")
    print(f"{'='*80}")

    job_name = generator.create_batch_job(
        batch_requests=batch_requests,
        job_display_name=f"book-covers-{len(batch_requests)}"
    )

    if not job_name:
        print(f"❌ Failed to create batch job")
        return False

    # Poll for completion
    print(f"\n{'='*80}")
    print(f"⏳ Waiting for batch completion...")
    print(f"{'='*80}")

    batch_job = generator.poll_batch_job(job_name, poll_interval=poll_interval)

    if not batch_job:
        print(f"❌ Batch job did not complete successfully")
        return False

    # Retrieve and save results
    print(f"\n{'='*80}")
    print(f"📥 Retrieving results...")
    print(f"{'='*80}")

    results = generator.retrieve_batch_results(batch_job)

    if not results:
        print(f"❌ No results retrieved")
        return False

    # Save covers
    print(f"\n{'='*80}")
    print(f"💾 Saving book covers...")
    print(f"{'='*80}")

    cover_originals_dir = project_root / "data" / "cover_originals"
    cover_originals_dir.mkdir(parents=True, exist_ok=True)

    all_success = True
    generated_covers = []

    for book_id in book_data.keys():
        result_key = f"cover-{book_id}"

        if result_key not in results:
            print(f"❌ No result for book {book_id}")
            all_success = False
            continue

        image_data, error = results[result_key]

        if error:
            print(f"❌ Book {book_id} failed: {error}")
            all_success = False
            continue

        if not image_data:
            print(f"❌ No image data for book {book_id}")
            all_success = False
            continue

        # Save cover image to data/cover_originals
        cover_path = cover_originals_dir / f"{book_id}.png"
        if save_image(image_data, cover_path):
            book = book_data[book_id]
            print(f"  ℹ️  Cover saved for book {book_id}: {book['title']}")
            generated_covers.append(book_id)
        else:
            all_success = False

    print(f"\n{'='*80}")
    if all_success:
        print(f"✅ All {len(generated_covers)} covers generated successfully!")
    else:
        print(f"⚠️  Some covers failed - check output above")
        print(f"  Generated {len(generated_covers)}/{len(batch_requests)} covers")
    print(f"{'='*80}")

    # Auto-optimize all generated covers
    if generated_covers:
        auto_optimize_covers(generated_covers, dry_run=dry_run)

    return all_success


def main():
    parser = argparse.ArgumentParser(
        description='Generate book covers and chapter illustrations using Gemini image models'
    )
    parser.add_argument('--book-id', type=int, help='Process specific book by ID')
    parser.add_argument('--book-ids', type=str, help='Process multiple books by comma-separated IDs (e.g., "53,54,55")')
    parser.add_argument('--with-chapters', action='store_true', help='Generate chapter illustrations in addition to covers (default: covers only)')
    parser.add_argument('--chapters-only', action='store_true', help='Generate chapter illustrations only (skip covers)')
    parser.add_argument('--chapter-range', type=str, help='Chapter range to generate (e.g., "1-10")')
    parser.add_argument('--batch-all', action='store_true', help='Process all books missing illustrations')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be generated without actually generating')
    parser.add_argument(
        '--model',
        type=str,
        default=DEFAULT_IMAGE_MODEL,
        choices=['gemini-3-pro-image-preview', 'gemini-2.5-flash-image'],
        help='Image generation model to use (default: gemini-3-pro-image-preview)'
    )
    parser.add_argument(
        '--sync-mode',
        action='store_true',
        help='Use synchronous API for generation (provides live progress but costs 2x more). '
             'Default is async mode using Batch API for 50%% cost reduction. '
             'For chapters: Chapter 1 generated first as reference, others batched. '
             'For covers: All covers generated asynchronously.'
    )
    parser.add_argument(
        '--batch-poll-interval',
        type=int,
        default=BATCH_POLL_INTERVAL_SECONDS,
        help=f'Seconds between batch status checks (default: {BATCH_POLL_INTERVAL_SECONDS})'
    )
    parser.add_argument(
        '--resume',
        type=str,
        metavar='STATE_FILE',
        help='Resume a previously interrupted batch job from state file'
    )
    parser.add_argument(
        '--list-jobs',
        action='store_true',
        help='List all pending batch jobs and exit'
    )

    args = parser.parse_args()

    # Handle list-jobs command
    if args.list_jobs:
        pending_jobs = list_pending_batch_jobs()
        if not pending_jobs:
            print("No pending batch jobs found.")
            return 0

        print(f"\n{'='*80}")
        print(f"📋 Pending Batch Jobs ({len(pending_jobs)})")
        print(f"{'='*80}\n")

        for i, job in enumerate(pending_jobs, 1):
            created = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job['created_at']))
            elapsed_mins = (time.time() - job['created_at']) / 60

            print(f"{i}. Book ID: {job['book_id']}")
            print(f"   Job: {job['job_name']}")
            print(f"   Chapters: {len(job['chapter_numbers'])} chapters")
            print(f"   Status: {job['status']}")
            print(f"   Created: {created} ({elapsed_mins:.0f} minutes ago)")
            print(f"   Resume: python {Path(__file__).name} --resume {job['state_file']}")
            print()

        return 0

    # Handle resume command
    if args.resume:
        if not config.GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY not found in environment")
            return 1

        state_file = Path(args.resume)
        if not state_file.exists():
            print(f"❌ State file not found: {state_file}")
            return 1

        state = load_batch_job_state(state_file)
        generator = GeminiImageGenerator(config.GEMINI_API_KEY, model=state.get('model', DEFAULT_IMAGE_MODEL))

        success = resume_batch_job(state_file, generator, poll_interval=args.batch_poll_interval)
        return 0 if success else 1

    # Validate arguments for normal operation
    if not args.book_id and not args.book_ids and not args.batch_all:
        parser.error("Either --book-id, --book-ids, --batch-all, --resume, or --list-jobs must be specified")

    if args.book_id and args.book_ids:
        parser.error("Cannot specify both --book-id and --book-ids")

    if args.chapter_range and not args.book_id:
        parser.error("--chapter-range requires --book-id")

    if args.book_ids and args.with_chapters:
        parser.error("--book-ids can only be used for covers (remove --with-chapters flag)")

    # Parse chapter range
    chapter_range = None
    if args.chapter_range:
        try:
            parts = args.chapter_range.split('-')
            chapter_range = (int(parts[0]), int(parts[1]))
        except:
            parser.error(f"Invalid chapter range format: {args.chapter_range}. Use format: '1-10'")

    # Check API key
    if not config.GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not found in environment")
        print("   Set it in your .env file or environment variables")
        return 1

    # Initialize
    db = Database()
    generator = GeminiImageGenerator(config.GEMINI_API_KEY, model=args.model)

    print(f"Using model: {args.model}")
    if "gemini-3-pro-image" in args.model:
        print(f"Resolution: {COVER_IMAGE_SIZE} for covers, {IMAGE_SIZE} for chapters at {ASPECT_RATIO} aspect ratio")
    else:
        print(f"Aspect ratio: {ASPECT_RATIO} (resolution auto-determined by model)")

    # Process single book
    if args.book_id:
        success = True

        if not args.chapters_only:
            # Generate cover using async mode by default
            if args.sync_mode:
                success = generate_book_cover(db, generator, args.book_id, args.dry_run) and success
            else:
                # Use async batch API for cover (default)
                success = generate_book_covers_batch(
                    db, generator, [args.book_id],
                    poll_interval=args.batch_poll_interval,
                    dry_run=args.dry_run
                ) and success

        if args.with_chapters or args.chapters_only:
            if args.sync_mode:
                # Use synchronous API
                success = generate_chapter_illustrations_for_book(
                    db, generator, args.book_id, chapter_range, args.dry_run
                ) and success
            else:
                # Use async batch API for chapter illustrations (default)
                success = generate_chapter_illustrations_batch(
                    db, generator, args.book_id, chapter_range,
                    poll_interval=args.batch_poll_interval,
                    dry_run=args.dry_run
                ) and success

        return 0 if success else 1

    # Process multiple books (covers only with --book-ids)
    if args.book_ids:
        # Parse book IDs
        try:
            book_ids = [int(bid.strip()) for bid in args.book_ids.split(',')]
        except ValueError:
            parser.error(f"Invalid book IDs format: {args.book_ids}. Use comma-separated integers.")

        print(f"Processing covers for {len(book_ids)} books: {book_ids}")

        if args.sync_mode:
            # Generate covers one at a time synchronously
            success = True
            for i, book_id in enumerate(book_ids, 1):
                print(f"\n{'='*80}")
                print(f"Cover {i}/{len(book_ids)}")
                print(f"{'='*80}")
                success = generate_book_cover(db, generator, book_id, args.dry_run) and success
        else:
            # Use async batch API for bulk cover generation (default)
            success = generate_book_covers_batch(
                db, generator, book_ids,
                poll_interval=args.batch_poll_interval,
                dry_run=args.dry_run
            )

        return 0 if success else 1

    # Batch process all books
    if args.batch_all:
        print("🔍 Finding books that need illustrations...")

        books_for_covers = [] if args.chapters_only else find_books_without_covers(db)
        books_for_chapters = [] if not args.with_chapters else find_books_without_chapter_illustrations(db)

        print(f"\n📊 Summary:")
        print(f"   Books needing covers: {len(books_for_covers)}")
        print(f"   Books needing chapter illustrations: {len(books_for_chapters)}")

        if args.dry_run:
            print("\n[DRY RUN MODE - No images will be generated]\n")

        # Generate covers
        for i, book in enumerate(books_for_covers, 1):
            print(f"\n{'='*80}")
            print(f"Cover {i}/{len(books_for_covers)}")
            print(f"{'='*80}")
            generate_book_cover(db, generator, book['id'], args.dry_run)

        # Generate chapter illustrations
        for i, book in enumerate(books_for_chapters, 1):
            print(f"\n{'='*80}")
            print(f"Book {i}/{len(books_for_chapters)}")
            print(f"{'='*80}")
            if args.sync_mode:
                generate_chapter_illustrations_for_book(db, generator, book['id'], None, args.dry_run)
            else:
                generate_chapter_illustrations_batch(
                    db, generator, book['id'], None,
                    poll_interval=args.batch_poll_interval,
                    dry_run=args.dry_run
                )

        print(f"\n{'='*80}")
        print("✅ Batch processing complete!")
        print(f"{'='*80}")

        return 0


if __name__ == '__main__':
    sys.exit(main())
