import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
DATABASE_PATH = BASE_DIR / 'data' / 'database.db'
USER_DATABASE_PATH = BASE_DIR / 'data' / 'summra.db'

# Data directories
BOOKS_DIR = BASE_DIR / 'data' / 'books'
SUMMARIES_DIR = BASE_DIR / 'data' / 'summaries'
BLOG_DIR = BASE_DIR / 'data' / 'blog'
COVERS_DIR = BASE_DIR / 'frontend' / 'static' / 'covers'
ILLUSTRATIONS_DIR = BASE_DIR / 'frontend' / 'static' / 'illustrations'

# Gemini API configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Unsplash API configuration
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY', '')

# Rate limiting for Gemini API
MAX_REQUESTS_PER_MINUTE = 10
MAX_TOKENS_PER_MINUTE = 250000

# Summary configurations
# Note: Use model names compatible with google-genai v1beta API
# 'model' is the primary model. 'model_fallbacks' is an ordered list tried by
# SummaryGenerator._generate_content_with_fallback when the primary returns a
# retriable error (503 / UNAVAILABLE / 429 / RESOURCE_EXHAUSTED). Simpler
# callers (batch jobs, categorization) just read 'model' and ignore the chain.
SUMMARY_CONFIGS = {
    'combined': {
        'concise_max_words': 500,
        'medium_max_words': 2500,  # Target middle of 2000-3000 range
        'model': 'gemini-3.5-flash',  # primary: latest stable flash, free tier
        'model_fallbacks': [
            'gemini-3-flash-preview',  # frontier-preview, free tier
            'gemini-2.5-flash',        # stable predecessor, free tier
        ],
        'description': 'Combined generation of concise (500 words, no spoilers) and medium (2500 words) summaries in single API call'
    },
    'comprehensive': {
        'words_per_chapter': 1000,
        'overall_summary_words': 2500,
        'model': 'gemini-3.5-flash',  # primary: latest stable flash, free tier
        'model_fallbacks': [
            'gemini-3-flash-preview',
            'gemini-2.5-flash',
        ],
        'description': 'Most comprehensive - chapter-by-chapter breakdown with connections'
    }
}

# Plain-text / bulk rewrite model (modern-english translations etc.).
# Flash-Lite: stable, free tier, lower latency, cheaper at paid tier.
PLAIN_TEXT_MODEL = 'gemini-3.1-flash-lite'

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
FLASK_PORT = int(os.environ.get('PORT', 5001))
FLASK_DEBUG = True

# Feature flags — default False so the gated subsystems are dark until ready.
# FEATURE_AUTH gates auth + reading progress + active Save-for-Offline.
# FEATURE_BLOG gates the editorial blog (routes + sitemap entries).
FEATURE_AUTH = True
FEATURE_BLOG = False
