# 📚 Summra - AI-Powered Classic Book Summaries

Summra is a web application that provides AI-generated summaries of classic books in the public domain. It offers three different summary lengths to suit your reading needs, from quick overviews to comprehensive chapter-by-chapter analyses.

## ✨ Features

- **Three Summary Lengths:**
  - **Concise** (~500 words): Quick overview without spoilers for fiction
  - **Medium** (2000-3000 words): Comprehensive summary with all key details
  - **Comprehensive**: Chapter-by-chapter breakdown with overall analysis (2000-3000 words each)

- **AI-Powered Summaries**: Uses Google Gemini API (Gemini 2.0 Flash and Gemini Exp 1206) for high-quality summaries
- **Text-to-Speech**: Listen to summaries using VITS open-source TTS model
- **Public Domain Focus**: Works with classic books available in the public domain
- **Rate Limit Handling**: Intelligent rate limiting for API calls (10 requests/min, 250k tokens/min)
- **Clean Web Interface**: Modern, responsive design for easy browsing

## 🏗️ Project Structure

```
summra/
├── backend/
│   ├── app.py              # Flask web application
│   ├── models.py           # Database models and operations
│   ├── config.py           # Configuration settings
│   ├── tts_handler.py      # Text-to-speech handler
│   └── requirements.txt    # Python dependencies
├── scripts/
│   ├── content/             # generate_summaries.py and other content scripts
│   ├── audio/               # TTS generation scripts
│   ├── images/              # cover / illustration scripts
│   ├── migrations/, backfills/, audits/, book_fixes/, blog/, archive/
│   └── README.md            # Index of every subfolder
├── docs/                    # PRD.md, ERD.md, USAGE.md, marketing/, archive/
├── deploy/                  # systemd + nginx + gunicorn configs
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css   # Styles
│   │   ├── js/
│   │   │   └── app.js      # Frontend JavaScript
│   │   └── audio/          # Generated TTS audio files
│   └── templates/
│       └── index.html      # Main HTML template
├── data/
│   ├── books/              # Place your .txt book files here
│   ├── summaries/          # Generated summaries (JSON)
│   └── database.db         # SQLite database
├── .env.example            # Example environment variables
├── .gitignore
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Gemini API key (from Google AI Studio)
- pip (Python package manager)

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd summra
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

5. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your Gemini API key:
   ```
   GEMINI_API_KEY=your_actual_api_key_here
   ```

   Get your API key from: https://makersuite.google.com/app/apikey

### First Time Setup

The first time you run the TTS functionality, it will download the VITS model (approximately 100-200MB). This is a one-time download and will be cached for future use.

## 📖 Usage

### Step 1: Generate Summaries

Before using the web interface, you need to generate summaries for your books.

1. **Place your book .txt files in the `data/books/` directory**

   You can find public domain books at:
   - [Project Gutenberg](https://www.gutenberg.org/)
   - [Standard Ebooks](https://standardebooks.org/)
   - [Internet Archive](https://archive.org/details/texts)

2. **Generate summaries for a single book:**
   ```bash
   python scripts/content/generate_summaries.py data/books/your_book.txt
   ```

   With custom title and author:
   ```bash
   python scripts/content/generate_summaries.py data/books/your_book.txt \
       --title "The Great Gatsby" \
       --author "F. Scott Fitzgerald"
   ```

3. **Batch process multiple books:**
   ```bash
   python scripts/content/generate_summaries.py data/books/ --batch
   ```

The script will:
- Extract title and author from the text (if available)
- Detect chapters automatically
- Generate all three types of summaries
- Store results in the database and as JSON files
- Handle API rate limits automatically

**Note:** Generating summaries can take several minutes per book, especially for comprehensive summaries with many chapters.

### Step 2: Run the Web Application

1. **Start the Flask server:**
   ```bash
   python backend/app.py
   ```

2. **Open your browser and navigate to:**
   ```
   http://localhost:5000
   ```

3. **Browse and read summaries:**
   - Select a book from the grid
   - Choose your preferred summary length
   - Click "Listen to Summary" to hear it via TTS

## 🔧 Configuration

Edit `backend/config.py` to customize:

- **API Models**: Change which Gemini models to use
- **Summary Lengths**: Adjust target word counts
- **Rate Limits**: Modify API rate limit thresholds
- **TTS Model**: Change the VITS model variant
- **Server Settings**: Modify host, port, and debug mode

## 🎯 API Endpoints

The backend provides the following REST API endpoints:

- `GET /api/books` - List all books
- `GET /api/books/<id>` - Get book details
- `GET /api/books/<id>/summary/<type>` - Get summary (type: concise, medium, comprehensive)
- `GET /api/books/<id>/chapters` - Get chapter summaries
- `POST /api/tts/generate` - Generate TTS audio
- `GET /api/summary-configs` - Get summary configuration options

## 📝 Summary Generation Script Options

```bash
usage: generate_summaries.py [-h] [--title TITLE] [--author AUTHOR] [--batch] input

Generate book summaries using Gemini API

positional arguments:
  input            Book file (.txt) or directory for batch processing

optional arguments:
  -h, --help       show this help message and exit
  --title TITLE    Book title (optional, will try to extract from text)
  --author AUTHOR  Author name (optional, will try to extract from text)
  --batch          Process all .txt files in directory
```

## 🎤 Text-to-Speech (TTS)

Summra uses the VITS open-source TTS model to generate natural-sounding audio:

- **Model**: `tts_models/en/vctk/vits` (multi-speaker English)
- **Default Voice**: Female (speaker p226)
- **Audio Format**: WAV
- **Caching**: Generated audio is cached to avoid regeneration
- **Text Limit**: First 5000 characters of summary (for performance)

To customize the TTS settings, edit `backend/config.py` and `backend/tts_handler.py`.

## 🔒 Rate Limiting

The summary generation script includes intelligent rate limiting:

- **Maximum Requests**: 10 per minute
- **Maximum Tokens**: 250,000 per minute
- **Automatic Waiting**: The script will pause when approaching limits
- **Token Estimation**: Estimates token usage before making requests

The script tracks both request count and token usage within rolling 1-minute windows.

## 🗄️ Database Schema

Summra uses SQLite with the following tables:

- **books**: Book metadata and full text
- **summaries**: Generated summaries (concise, medium, comprehensive)
- **chapters**: Individual chapter summaries
- **audio_files**: TTS audio file references

## 🎨 Frontend Features

- **Responsive Design**: Works on desktop, tablet, and mobile
- **Clean Interface**: Modern, card-based layout
- **Collapsible Chapters**: Chapter summaries can be expanded/collapsed
- **Audio Player**: Built-in HTML5 audio player for TTS
- **Loading States**: Clear feedback during data loading

## 🐛 Troubleshooting

### "No books found" error
- Make sure you've run the summary generation script first
- Check that the database file exists in `data/database.db`

### TTS not working
- The first run will download the VITS model (be patient)
- Check that you have enough disk space (~200MB for the model)
- Try a different TTS model in `config.py` if issues persist

### API rate limit errors
- The script should handle this automatically
- If you hit limits frequently, consider using a paid API tier
- You can adjust `MAX_REQUESTS_PER_MINUTE` in `config.py`

### Summary generation is slow
- This is normal - comprehensive summaries can take 10-30 minutes
- Rate limiting adds wait times between requests
- Consider running batch processing overnight

### Chapter detection not working
- Some books may not have standard chapter markers
- You can manually edit the text to add clear chapter headings
- The script will treat the whole book as one chapter if none are detected

## 📚 Recommended Book Sources

For public domain books in text format:

1. **Project Gutenberg** (https://www.gutenberg.org/)
   - Largest collection of public domain books
   - Plain text format available
   - Metadata included in files

2. **Standard Ebooks** (https://standardebooks.org/)
   - High-quality formatting
   - Modern, carefully edited texts

3. **Internet Archive** (https://archive.org/details/texts)
   - Vast collection
   - Multiple formats available

## 🔮 Future Enhancements

Potential features to add:
- User accounts and favorites
- Search functionality
- Book recommendations
- Export summaries as PDF
- Multiple TTS voices
- Offline mode support
- Mobile app version

## 📄 License

This project is for educational and personal use. Books should be in the public domain or you should have appropriate rights to process them.

## 🙏 Acknowledgments

- **Google Gemini AI** for summary generation
- **Coqui TTS** for the VITS text-to-speech models
- **Project Gutenberg** for making classic literature freely available
- **Flask** for the web framework

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📧 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the configuration in `backend/config.py`
3. Check the console logs for detailed error messages

---

**Happy Reading! 📚✨**
