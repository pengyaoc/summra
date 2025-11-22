import os
import hashlib
import re
from pathlib import Path
import config

# Try to import Coqui TTS
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("Warning: Coqui TTS not available. TTS functionality will be disabled.")


class TTSHandler:
    """Handler for Text-to-Speech using Coqui TTS"""

    def __init__(self):
        self.output_dir = config.TTS_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize TTS model if available
        if TTS_AVAILABLE:
            try:
                # Use a fast, high-quality multilingual model
                # tts_models/multilingual/multi-dataset/xtts_v2 is good but large
                # tts_models/en/ljspeech/tacotron2-DDC is faster for English
                self.tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
                print("Coqui TTS model loaded successfully")
            except Exception as e:
                print(f"Error loading TTS model: {e}")
                self.tts = None
        else:
            self.tts = None

    def truncate_at_sentence_boundary(self, text: str, max_chars: int = 5000) -> str:
        """
        Truncate text at the last complete sentence before max_chars
        Looks for sentence endings: . ! ? followed by space or end of text
        """
        import re

        if len(text) <= max_chars:
            return text

        # Get substring up to max_chars
        truncated = text[:max_chars]

        # Find the last sentence-ending punctuation followed by a space
        # Look for . ! ? followed by space
        sentence_end_pattern = re.compile(r'[.!?][\s]')
        matches = list(sentence_end_pattern.finditer(truncated))

        if matches:
            # Cut at the position after the last punctuation and space
            last_match = matches[-1]
            truncated = truncated[:last_match.end()]
        else:
            # No sentence ending found, try to at least break at a word boundary
            last_space = truncated.rfind(' ')
            if last_space > max_chars * 0.8:  # Only use word boundary if it's reasonably close
                truncated = truncated[:last_space]

        return truncated.strip()

    def clean_text_for_speech(self, text: str) -> str:
        """
        Clean text for TTS by removing formatting and non-speech characters
        """
        import re

        cleaned = text

        # Replace curly quotes and apostrophes with straight ones
        cleaned = cleaned.replace('"', '"').replace('"', '"')  # Curly double quotes
        cleaned = cleaned.replace(''', "'").replace(''', "'")  # Curly single quotes/apostrophes
        cleaned = cleaned.replace('«', '"').replace('»', '"')  # Guillemets
        cleaned = cleaned.replace('…', '...')  # Ellipsis

        # Remove markdown headers
        cleaned = re.sub(r'^#{1,6}\s+', '', cleaned, flags=re.MULTILINE)

        # Remove bold/italic markers
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)  # **bold**
        cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)      # __bold__
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)      # *italic*
        cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)        # _italic_

        # Remove links [text](url) -> text
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)

        # Remove inline code
        cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)

        # Remove blockquotes
        cleaned = re.sub(r'^>\s+', '', cleaned, flags=re.MULTILINE)

        # Remove horizontal rules
        cleaned = re.sub(r'^[\-*_]{3,}\s*$', '', cleaned, flags=re.MULTILINE)

        # Remove list markers
        cleaned = re.sub(r'^[\s]*[-*+]\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^[\s]*\d+\.\s+', '', cleaned, flags=re.MULTILINE)

        # Remove HTML tags
        cleaned = re.sub(r'<[^>]+>', '', cleaned)

        # Remove special characters that don't make sense in speech
        cleaned = re.sub(r'[\[\]{}]', '', cleaned)

        # Replace multiple punctuation with single
        cleaned = re.sub(r'!+', '!', cleaned)      # Multiple exclamation
        cleaned = re.sub(r'\?+', '?', cleaned)     # Multiple question marks
        cleaned = re.sub(r'\.{4,}', '...', cleaned) # More than 3 dots

        # Remove zero-width characters and other invisible Unicode
        cleaned = re.sub(r'[\u200B-\u200D\uFEFF]', '', cleaned)

        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'\n+', ' ', cleaned)

        # Trim
        cleaned = cleaned.strip()

        return cleaned

    def generate_audio(self, text: str, audio_id: str = None, language: str = 'en') -> str:
        """
        Generate audio from text using Coqui TTS

        Args:
            text: Text to convert to speech
            audio_id: Unique identifier for caching (optional)
            language: Language code (default: 'en' for English)

        Returns:
            Path to generated audio file, or None if TTS not available
        """
        if not TTS_AVAILABLE or self.tts is None:
            print("TTS not available")
            return None

        # Generate unique filename based on content hash or provided ID
        if audio_id:
            filename = f"{audio_id}.wav"
        else:
            # Create hash of text for unique filename
            text_hash = hashlib.md5(text.encode()).hexdigest()
            filename = f"{text_hash}.wav"

        output_path = self.output_dir / filename

        # Check if audio already exists (caching)
        if output_path.exists():
            print(f"Audio file already exists: {output_path}")
            return str(output_path)

        try:
            # Debug: Log original text
            print(f"\n{'='*60}")
            print(f"TTS DEBUG - Audio ID: {audio_id}")
            print(f"{'='*60}")
            print(f"Original text length: {len(text)} chars")
            print(f"\nFull original text:")
            print(text)
            print(f"\n{'-' * 60}")

            # Clean text for TTS (remove markdown and formatting)
            text = self.clean_text_for_speech(text)

            # Debug: Log cleaned text
            print(f"\nCleaned text length: {len(text)} chars")
            print(f"\nFull cleaned text:")
            print(text)
            print(f"\n{'-' * 60}")

            # Sanitize text to prevent TTS quality issues
            # Remove problematic punctuation combinations that cause weird sounds
            text = re.sub(r'[?!]{2,}', '!', text)  # Replace ?!?! or similar with single !
            text = re.sub(r'[.]{4,}', '...', text)  # Replace many dots with ellipsis

            # Remove multiple spaces (can cause TTS pauses/issues)
            text = re.sub(r'\s{2,}', ' ', text)

            # Remove any leading/trailing whitespace aggressively
            text = text.strip()

            # Remove any stray newlines or tabs that might have survived
            text = text.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
            text = re.sub(r'\s{2,}', ' ', text)  # Clean up again after replacements

            # Validate text is not empty or whitespace-only
            if not text or text.isspace():
                print("Warning: Text is empty or whitespace-only after cleaning")
                return None

            # Ensure text ends with proper punctuation
            if text and text[-1] not in '.!?':
                text = text + '.'

            # Limit text length to avoid issues - truncate at sentence boundary
            max_chars = 20000  # Increased from 5000 to handle full chapters
            if len(text) > max_chars:
                text = self.truncate_at_sentence_boundary(text, max_chars)
                print(f"\nText truncated to {len(text)} characters at sentence boundary for TTS")

            # Final check: ensure it ends with punctuation after truncation
            if text and text[-1] not in '.!?':
                text = text + '.'

            # Debug: Log final text sent to TTS engine
            print(f"\nFinal text sent to TTS engine ({len(text)} chars):")
            print(text)
            print(f"\n{'='*60}\n")

            # Generate speech using Coqui TTS
            self.tts.tts_to_file(text=text, file_path=str(output_path))

            print(f"Generated audio: {output_path}")
            return str(output_path)

        except Exception as e:
            print(f"Error generating audio: {e}")
            return None

    def generate_audio_chunks(self, text: str, chunk_size: int = 500) -> list:
        """
        Generate audio for long text by splitting into chunks

        Args:
            text: Long text to convert to speech
            chunk_size: Maximum number of words per chunk

        Returns:
            List of paths to generated audio files
        """
        words = text.split()
        chunks = []
        audio_files = []

        # Split text into chunks
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)

        # Generate audio for each chunk
        for i, chunk in enumerate(chunks):
            chunk_hash = hashlib.md5(f"{text[:50]}_{i}".encode()).hexdigest()
            audio_path = self.generate_audio(chunk, f"chunk_{chunk_hash}")
            if audio_path:
                audio_files.append(audio_path)

        return audio_files

    def get_supported_languages(self) -> dict:
        """Get list of supported languages for gTTS"""
        from gtts.lang import tts_langs
        return tts_langs()
