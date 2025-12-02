import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
DATABASE_PATH = BASE_DIR / 'data' / 'database.db'

# Data directories
BOOKS_DIR = BASE_DIR / 'data' / 'books'
SUMMARIES_DIR = BASE_DIR / 'data' / 'summaries'
COVERS_DIR = BASE_DIR / 'frontend' / 'static' / 'covers'
ILLUSTRATIONS_DIR = BASE_DIR / 'frontend' / 'static' / 'illustrations'

# Gemini API configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Rate limiting for Gemini API
MAX_REQUESTS_PER_MINUTE = 10
MAX_TOKENS_PER_MINUTE = 250000

# Summary configurations
# Note: Use model names compatible with google-genai v1beta API
SUMMARY_CONFIGS = {
    'concise': {
        'max_words': 500,
        'model': 'gemini-2.5-flash',  # Flash model for higher quota and cost efficiency
        'description': 'Most concise summary - get the gist with no spoilers for fiction'
    },
    'medium': {
        'max_words': 2500,  # Target middle of 2000-3000 range
        'model': 'gemini-2.5-flash',  # Flash model for higher quota and cost efficiency
        'description': 'Medium length summary - comprehensive overview'
    },
    'comprehensive': {
        'words_per_chapter': 1000,
        'overall_summary_words': 2500,
        'model': 'gemini-2.5-flash',  # Flash model for higher quota and cost efficiency
        'description': 'Most comprehensive - chapter-by-chapter breakdown with connections'
    }
}

# TTS configuration (using VITS for real-time, Gemini for offline)
TTS_OUTPUT_DIR = BASE_DIR / 'frontend' / 'static' / 'audio'
TTS_LANGUAGE = 'en'  # Default language for TTS

# Gemini TTS API configuration (for offline generation only)
GEMINI_TTS_MODEL = 'gemini-2.5-flash-preview-tts'
GEMINI_TTS_VOICE = 'Kore'  # Default voice (options: Puck, Charon, Kore, Fenrir, Aoede, Sulafat)
GEMINI_TTS_MAX_REQUESTS_PER_MINUTE = 3
GEMINI_TTS_MAX_TOKENS_PER_MINUTE = 10000
GEMINI_TTS_CHUNK_SIZE_WORDS = 900  # Larger chunks for API-based TTS

# VITS TTS configuration (for real-time generation)
VITS_TTS_CHUNK_SIZE_WORDS = 20  # Much smaller chunks for local TTS processing

# Flask configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5001
FLASK_DEBUG = True
