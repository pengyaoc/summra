# Async Batch Mode Implementation Plan

## Overview
This document outlines the remaining work to complete Gemini Batch API integration in `generate_summaries.py`. All infrastructure is in place - only integration into the main processing flow remains.

## ✅ Completed Infrastructure

1. **Batch API Core Methods** (lines 1583-1774)
   - `submit_batch_job()` - Submits requests to Gemini Batch API
   - `poll_batch_job()` - Polls for completion with progress tracking
   - `retrieve_batch_results()` - Parses and returns results
   - `build_batch_request()` - Formats prompts for batch API

2. **State Management** (lines 1574-1656)
   - `save_batch_job_state()` - Saves to `data/batch_jobs/*.json`
   - `load_batch_job_state()` - Loads from JSON
   - `update_batch_job_state()` - Updates state
   - `list_pending_batch_jobs()` - Lists pending jobs

3. **CLI Flags** (lines 7024-7048)
   - `--sync` → Use synchronous mode (async is default)
   - `--resume STATE_FILE` → Resume interrupted jobs
   - `--list-jobs` → List pending jobs
   - `--batch-poll-interval N` → Customize polling

4. **Configuration** (lines 286-289)
   - `BATCH_POLL_INTERVAL_SECONDS = 30`
   - `BATCH_MAX_WAIT_HOURS = 24`
   - `BATCH_JOBS_DIR = data/batch_jobs`

## 🔄 Implementation Steps

### Step 1: Modify `generate_combined_summaries()` (line ~1855)

**Current signature:**
```python
def generate_combined_summaries(self, text: str, title: str, author: str, dry_run: bool = False) -> Dict:
```

**Change to:**
```python
def generate_combined_summaries(self, text: str, title: str, author: str, dry_run: bool = False, return_prompt_only: bool = False) -> Dict | str:
```

**Add after prompt is built (around line 1905):**
```python
if return_prompt_only:
    return prompt  # Return prompt string for batch mode
```

**Keep all existing logic** - just add early return for batch mode.

### Step 2: Modify `generate_bulk_chapter_summaries()` (line ~5822)

**Current signature:**
```python
def generate_bulk_chapter_summaries(self, chapters_batch: List[Tuple], book_title: str,
                                   medium_summary: str = None, previous_chapter_text: str = None,
                                   dry_run: bool = False, partial_run: bool = False) -> Dict[int, str]:
```

**Change to:**
```python
def generate_bulk_chapter_summaries(self, chapters_batch: List[Tuple], book_title: str,
                                   medium_summary: str = None, previous_chapter_text: str = None,
                                   dry_run: bool = False, partial_run: bool = False,
                                   return_prompt_only: bool = False) -> Dict[int, str] | str:
```

**Add after prompt is built (around line 5937):**
```python
if return_prompt_only:
    # Return prompt and metadata for batch mode
    return {
        'prompt': prompt,
        'chapter_numbers': chapter_numbers,
        'model': model_name
    }
```

### Step 3: Create `process_book_async_batch()` Method

Add this new method to `SummaryGenerator` class (after `process_book` method):

```python
def process_book_async_batch(self, file_path: Path, title: str, author: str,
                             book_text: str, chapters: List, book_id: int,
                             medium_summary_for_context: str = None,
                             chapter_to_section_id: Dict = None,
                             poll_interval: int = BATCH_POLL_INTERVAL_SECONDS) -> Dict:
    """
    Process book using async Batch API for 50% cost savings.

    Builds all prompts, submits as one batch job, polls for completion,
    and saves results to database.
    """
    print(f"\n{'='*60}")
    print("ASYNC BATCH MODE - Building requests...")
    print(f"{'='*60}")

    batch_requests = []
    request_metadata = []

    # Request 1: Overall summaries (concise + medium)
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
        'model': config.SUMMARY_CONFIGS['concise']['model']
    })

    # Requests 2-N: Chapter summaries (keeping existing bulk batching)
    print(f"\n[2/N] Building chapter summary requests...")

    # Prepare chapters for bulk processing (reuse existing logic from process_book)
    chapters_needing_summary = []
    for chapter in chapters:
        chapter_num = chapter['chapter_number']
        chapter_title = chapter['title']
        chapter_text = chapter['text']
        word_count = len(chapter_text.split())

        if word_count < SummaryConstants.MIN_CHAPTER_WORDS:
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
            'model': prompt_data['model'],
            'batch_index': batch_idx
        })

        previous_batch_last_chapter = batch[-1]

    print(f"\n✓ Built {len(batch_requests)} batch request(s)")
    print(f"  - 1 overall summaries request")
    print(f"  - {len(batches)} chapter summary request(s)")

    # Submit batch job
    print(f"\n{'='*60}")
    print("Submitting batch job...")
    print(f"{'='*60}")

    model_name = config.SUMMARY_CONFIGS['concise']['model']
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

    batch_job = self.poll_batch_job(job_name, poll_interval=poll_interval)

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
                self.db.update_book_summaries(book_id, parsed)
                print(f"  ✓ Saved overall summaries")
            else:
                all_success = False

        elif metadata['type'] == 'chapters':
            # Parse and save chapter summaries (reuse existing parsing logic)
            chapter_numbers = metadata['chapter_numbers']
            summaries = self.parse_bulk_chapter_summaries_response(
                response_text,
                chapter_numbers,
                list(range(1, len(chapter_numbers) + 1))
            )

            for chapter_num in chapter_numbers:
                if chapter_num in summaries:
                    section_id = chapter_to_section_id.get(chapter_num)
                    if section_id:
                        self.db.add_chapter(
                            section_id=section_id,
                            chapter_number=chapter_num,
                            summary=summaries[chapter_num]
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
```

### Step 4: Update `process_book()` to Route to Batch Mode

Find the `process_book()` method (around line 7310) and add routing logic at the start of summary generation:

**Add after book parsing/database creation but before summary generation:**
```python
# Route to async batch mode if enabled
if use_batch_api and not dry_run and not parse_only:
    print("\n" + "="*60)
    print("🚀 ASYNC BATCH MODE ENABLED (50% cost savings)")
    print("="*60)

    return self.process_book_async_batch(
        file_path=file_path,
        title=title,
        author=author,
        book_text=book_text,
        chapters=chapters,
        book_id=book_id,
        medium_summary_for_context=None,  # Will be None on first run
        chapter_to_section_id=chapter_to_section_id
    )

# Otherwise, continue with existing sync flow...
```

### Step 5: Implement Resume Functionality

Replace the TODO in `main()` (around line 7073):

```python
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
    batch_job = generator.poll_batch_job(job_name, poll_interval=args.batch_poll_interval)

    if not batch_job:
        print(f"❌ Batch job did not complete successfully")
        update_batch_job_state(state_file, "failed")
        sys.exit(1)

    # Retrieve and save results (reuse logic from process_book_async_batch)
    results = generator.retrieve_batch_results(batch_job)

    # TODO: Parse and save results to database
    # (Copy the result processing logic from process_book_async_batch)

    print(f"\n✅ Job resumed and completed successfully!")
    sys.exit(0)
```

## Testing Plan

1. **Test --list-jobs**: `python scripts/generate_summaries.py --list-jobs`
2. **Test with --sync flag**: `python scripts/generate_summaries.py /tmp/pg75011.txt --sync` (should work as before)
3. **Test async mode**: `python scripts/generate_summaries.py /tmp/pg75011.txt` (new async flow)
4. **Test resume**: Interrupt async job and resume with `--resume`

## Notes

- All prompt-building logic remains unchanged
- Sync mode (`--sync`) continues to work exactly as before
- Async mode simply collects prompts, submits them, and waits
- State management allows safe interruption and resumption
- 50% cost savings automatically applies to batch mode
