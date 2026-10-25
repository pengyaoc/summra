# Modern English (No-Fear) Translation Script

## Overview

The `generate_modern_english.py` script creates modern English translations of classic literature chapters while preserving the exact structure and meaning of the original text. It reads chapter text from the database and uses Google's Gemini API to generate accessible translations for contemporary readers.

## Purpose

Classic literature often uses archaic language, complex sentence structures, and outdated vocabulary that can be challenging for modern readers. This script aims to:

- Make classic literature more accessible to contemporary readers
- Preserve the author's original meaning and intent
- Maintain literary quality while using modern language
- Keep the exact structure (sentences and paragraphs) intact

## Installation

The script requires the following dependencies (already in your environment):

```bash
pip install google-genai
```

Ensure your Google API key is configured in `config.py`:

```python
GOOGLE_API_KEY = "your-api-key-here"
```

## Usage

### Basic Commands

```bash
# Generate modern English for a single chapter
python scripts/content/generate_modern_english.py --book-id 1 --chapter 5

# Generate for multiple chapters (comma-separated)
python scripts/content/generate_modern_english.py --book-id 1 --chapters "1,2,3,4,5"

# Generate for all chapters in a book
python scripts/content/generate_modern_english.py --book-id 1 --all-chapters

# Dry run (preview prompt without making API calls)
python scripts/content/generate_modern_english.py --book-id 1 --chapter 5 --dry-run

# Use a specific Gemini model
python scripts/content/generate_modern_english.py --book-id 1 --chapter 5 --model gemini-2.0-flash-exp
```

### Options

- `--book-id` (required): Database ID of the book
- `--chapter`: Single chapter number to process
- `--chapters`: Comma-separated list of chapter numbers
- `--all-chapters`: Process all chapters in the book
- `--dry-run`: Preview prompts without making API calls
- `--model`: Gemini model to use (default: `gemini-2.0-flash-exp`)
- `--batch-size`: Number of chapters to process sequentially (default: 1)

## Output

Generated translations are saved to:

```
output/modern_english/book_{book_id}_chapter_{chapter_number}_modern.txt
```

Example:
```
output/modern_english/book_1_chapter_5_modern.txt
```

## Prompt Design

The script uses a carefully crafted prompt to ensure high-quality translations. Here's a breakdown of the key components:

### Critical Translation Rules

1. **Preserve Exact Structure**
   - No adding or removing sentences
   - No adding or removing paragraphs
   - No merging or splitting paragraphs
   - Keep dialogue markers and formatting

2. **Modernize Language**
   - Replace archaic words (thou → you, doth → does)
   - Simplify complex Victorian/classical sentence structures
   - Use contemporary vocabulary
   - Make implicit meanings explicit when helpful

3. **Preserve Meaning & Tone**
   - Keep author's intended meaning intact
   - Maintain emotional tone and atmosphere
   - Preserve literary devices (metaphors, imagery, symbolism)
   - Keep character voices distinctive
   - Don't modernize proper nouns or place names

4. **Simplify Syntax**
   - Break complex nested clauses into clearer structures
   - Reorder inverted sentences to standard modern order
   - Clarify ambiguous pronoun references
   - Convert passive voice to active where appropriate

5. **Quality Standards**
   - Should read naturally to modern audience
   - Maintain high school reading level
   - Preserve literary merit and artistry
   - Keep sophistication, just in modern English

### Example Transformations

The prompt includes specific examples to guide the AI:

**Original:** "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife."

**Modern:** "Everyone knows that a wealthy single man must be looking for a wife."

---

**Original:** "I had scarcely laid the first tier of my masonry when I discovered that the intoxication of Fortunato had in a great measure worn off."

**Modern:** "I had barely finished the first layer of bricks when I realized that Fortunato was becoming much less drunk."

---

**Original:** "Methinks I see these things with parted eye, when every thing seems double."

**Modern:** "I think I'm seeing double right now—everything appears twice."

## Technical Details

### Database Schema

The script reads chapter text from the `chapters` table:

```sql
SELECT * FROM chapters WHERE book_id = ? AND chapter_number = ?
```

Required fields:
- `chapter_text`: Full original text of the chapter
- `chapter_title`: Title of the chapter
- `chapter_number`: Sequential chapter number

### API Configuration

```python
config = types.GenerateContentConfig(
    temperature=0.3,      # Lower temperature for consistent translations
    top_p=0.95,
    max_output_tokens=8192,
)
```

**Why temperature=0.3?**
- Lower temperature produces more consistent, predictable translations
- Reduces creative variation while maintaining quality
- Ensures structural preservation is respected

### Quality Validation

The script performs automatic validation:

1. **Paragraph Count Check**
   - Compares original vs. modern paragraph counts
   - Warns if difference exceeds 2 paragraphs
   - Helps identify structural issues

2. **Metrics Logging**
   - Input word count and character count
   - Output word count and character count
   - Processing timestamps

## Workflow Example

```bash
# Step 1: Preview the prompt for chapter 1 (dry run)
python scripts/content/generate_modern_english.py --book-id 1 --chapter 1 --dry-run

# Step 2: Generate the translation
python scripts/content/generate_modern_english.py --book-id 1 --chapter 1

# Step 3: Review the output
cat output/modern_english/book_1_chapter_1_modern.txt

# Step 4: Process remaining chapters in batch
python scripts/content/generate_modern_english.py --book-id 1 --chapters "2,3,4,5"
```

## Future Enhancements

### Database Storage
Add a `modern_english_text` column to the `chapters` table:

```sql
ALTER TABLE chapters ADD COLUMN modern_english_text TEXT;
```

Then save translations directly to the database.

### Frontend Integration
Create a side-by-side comparison view:
- Original text on left
- Modern English on right
- Toggle between views

### Quality Metrics
- Readability scoring (Flesch-Kincaid)
- Vocabulary complexity analysis
- User feedback mechanism
- A/B testing different temperature values

### Bulk Processing
- Rate limiting with exponential backoff
- Progress tracking
- Resume capability for interrupted batches
- Cost estimation before processing

## Troubleshooting

### "Chapter has no text stored in database"
Ensure the chapter was processed with the full text extraction enabled. Run:

```bash
python scripts/content/generate_summaries.py data/books/your_book.txt
```

This will populate the `chapter_text` field.

### API Rate Limits
If you encounter rate limit errors:

1. Add delays between chapters (already included: 2 seconds)
2. Use smaller batch sizes: `--batch-size 1`
3. Implement exponential backoff in the script

### Structural Preservation Issues
If translations don't preserve structure:

1. Check the paragraph count warning in output
2. Review the saved file manually
3. Consider adjusting the prompt to be more explicit
4. Try lower temperature: `--model gemini-2.0-flash-exp` (already uses 0.3)

## Best Practices

1. **Always dry-run first** to preview the prompt
2. **Start with a single chapter** to verify quality
3. **Review output files** before batch processing
4. **Monitor paragraph counts** for structural integrity
5. **Save originals** before any database updates

## Cost Considerations

Gemini API pricing (as of 2025):
- Input: ~$0.001 per 1K tokens
- Output: ~$0.002 per 1K tokens

Average chapter (10,000 words):
- Input tokens: ~13,000 (prompt + chapter)
- Output tokens: ~10,000 (modern text)
- Estimated cost: ~$0.03 per chapter

For a 50-chapter book: ~$1.50 total

## Credits

Inspired by SparkNotes' "No-Fear Shakespeare" series, which provides modern English translations alongside original text.
