# Summra - Quick Usage Guide

## Quick Start (5 minutes)

### 1. Setup (One-time)

**On macOS/Linux:**
```bash
./setup.sh
```

**On Windows:**
```bash
setup.bat
```

### 2. Add Your API Key

Edit the `.env` file and add your Gemini API key:
```
GEMINI_API_KEY=your_actual_key_here
```

Get your key from: https://makersuite.google.com/app/apikey

### 3. Get Some Books

Download public domain books from Project Gutenberg:

**Example books to try:**
- Pride and Prejudice: https://www.gutenberg.org/ebooks/1342
- The Great Gatsby: https://www.gutenberg.org/ebooks/64317
- Alice in Wonderland: https://www.gutenberg.org/ebooks/11
- Frankenstein: https://www.gutenberg.org/ebooks/84

Click "Plain Text UTF-8" to download the .txt file, then move it to `data/books/`

### 4. Generate Summaries

**For a single book:**
```bash
python scripts/content/generate_summaries.py data/books/pride_and_prejudice.txt
```

**For all books in the directory:**
```bash
python scripts/content/generate_summaries.py data/books/ --batch
```

**Expected time:**
- Concise summary: ~30 seconds
- Medium summary: ~1 minute
- Comprehensive summary: 5-30 minutes (depending on number of chapters)

### 5. Start the Web Server

```bash
python backend/app.py
```

### 6. Open in Browser

Navigate to: http://localhost:5000

## Common Tasks

### Download a Book from Project Gutenberg

1. Visit https://www.gutenberg.org/
2. Search for a book
3. Click "Plain Text UTF-8" format
4. Save to `data/books/` directory
5. Remove the Project Gutenberg header/footer (optional but recommended)

### Generate Summaries with Custom Metadata

```bash
python scripts/content/generate_summaries.py data/books/book.txt \
    --title "The Great Gatsby" \
    --author "F. Scott Fitzgerald"
```

### Re-generate Summaries for Existing Book

The script will update summaries if the book already exists in the database. Just run the same command again.

### View Generated Summaries (JSON)

Check `data/summaries/` for JSON files with all generated summaries.

### Listen to a Summary with TTS

1. Select a book
2. Choose a summary type
3. Click "🔊 Listen to Summary"
4. Wait for audio generation (first time only, then cached)
5. Play audio

## Example Workflow

Here's a complete example:

```bash
# 1. Setup (first time only)
./setup.sh

# 2. Activate virtual environment
source venv/bin/activate

# 3. Download a book
cd data/books
curl -o alice.txt https://www.gutenberg.org/files/11/11-0.txt
cd ../..

# 4. Generate summaries
python scripts/content/generate_summaries.py data/books/alice.txt \
    --title "Alice's Adventures in Wonderland" \
    --author "Lewis Carroll"

# 5. Start server
python backend/app.py

# 6. Open http://localhost:5000 in your browser
```

## Tips

### For Best Results

- **Clean the text**: Remove Project Gutenberg headers and footers
- **Clear chapter markers**: Ensure chapters are clearly marked (CHAPTER I, Chapter 1, etc.)
- **Reasonable length**: Books with 500k+ words may take a long time
- **Rate limits**: The script handles rate limiting automatically, but be patient

### Managing Rate Limits

If you're processing many books:

```bash
# Process books one at a time with pauses
python scripts/content/generate_summaries.py data/books/book1.txt
# Wait a few minutes
python scripts/content/generate_summaries.py data/books/book2.txt
```

Or just use batch mode and let it handle the rate limiting:
```bash
python scripts/content/generate_summaries.py data/books/ --batch
```

### Customizing Summary Length

Edit `backend/config.py` and modify the `SUMMARY_CONFIGS` dictionary:

```python
SUMMARY_CONFIGS = {
    'concise': {
        'max_words': 500,  # Change this
        ...
    },
    ...
}
```

### Using Different Gemini Models

Edit `backend/config.py`:

```python
SUMMARY_CONFIGS = {
    'concise': {
        'model': 'gemini-2.0-flash-exp',  # Fast and cheap
    },
    'comprehensive': {
        'model': 'gemini-exp-1206',  # More capable
    }
}
```

Available models:
- `gemini-2.0-flash-exp` - Fast, cost-effective
- `gemini-exp-1206` - More advanced reasoning
- `gemini-1.5-pro` - Previous generation, still capable

## Troubleshooting

### Script hangs during summary generation
- This is normal! LLM calls can take 30-60 seconds each
- Check console for progress messages
- For comprehensive summaries, wait 10-30 minutes

### "Rate limit exceeded" error
- The script should handle this automatically
- If it doesn't, wait a few minutes and try again
- Consider reducing the number of books processed at once

### Database locked error
- Make sure no other instance is running
- Stop the web server before running the script
- Delete `data/database.db-journal` if it exists

### TTS model download fails
- Check your internet connection
- Try again - sometimes downloads timeout
- The model is ~100-200MB

### No audio generated
- Check browser console for errors
- First generation takes longer (downloads model)
- Subsequent generations use cache

## Advanced Usage

### Running on a Different Port

Edit `backend/config.py`:
```python
FLASK_PORT = 8080  # Change port
```

### Running in Production

```bash
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app
```

### Backing Up Your Data

```bash
# Backup database and summaries
tar -czf summra_backup.tar.gz data/
```

### Exporting Book Data

The database is SQLite, so you can query it directly:

```bash
sqlite3 data/database.db
.tables
SELECT title, author FROM books;
.quit
```

## Performance Notes

- **Concise summaries**: ~30 seconds per book
- **Medium summaries**: ~1-2 minutes per book
- **Comprehensive summaries**: 5-30 minutes depending on chapters
- **TTS generation**: ~10-30 seconds (cached after first generation)
- **Database**: Handles thousands of books efficiently
- **Web interface**: Fast, responsive, works offline after loading

## Getting Help

1. Check the main [README.md](README.md)
2. Review console output for error messages
3. Check `backend/config.py` for configuration options
4. Try with a smaller book first to test your setup

Happy reading! 📚
