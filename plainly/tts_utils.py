"""
Text cleanup for speech, and finding a pre-recorded summary's file.
"""

import re
from typing import Optional, Dict, Any
from pathlib import Path


def clean_text_for_speech(text: str) -> str:
    """
    Clean text for TTS by removing markdown/HTML formatting structures.
    Keeps natural punctuation for proper speech phrasing.

    This is provider-agnostic and works for any TTS engine.

    Args:
        text: Raw text with potential markdown/HTML formatting

    Returns:
        Cleaned text suitable for TTS
    """
    cleaned = text

    # Remove markdown and HTML formatting
    cleaned = re.sub(r'^#{1,6}\s+', '', cleaned, flags=re.MULTILINE)  # Headers
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)  # **bold**
    cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)      # __bold__
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)      # *italic*
    cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)        # _italic_
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)  # Links
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)  # Inline code
    cleaned = re.sub(r'^>\s+', '', cleaned, flags=re.MULTILINE)  # Blockquotes
    cleaned = re.sub(r'^[\-*_]{3,}\s*$', '', cleaned, flags=re.MULTILINE)  # Horizontal rules
    cleaned = re.sub(r'^[\s]*[-*+]\s+', '', cleaned, flags=re.MULTILINE)  # List markers
    cleaned = re.sub(r'^[\s]*\d+\.\s+', '', cleaned, flags=re.MULTILINE)  # Numbered lists
    cleaned = re.sub(r'<[^>]+>', '', cleaned)  # HTML tags

    # Replace special typography with standard characters
    cleaned = cleaned.replace('"', '"').replace('"', '"')
    cleaned = cleaned.replace(''', "'").replace(''', "'")
    cleaned = cleaned.replace('«', '"').replace('»', '"')
    cleaned = cleaned.replace('…', '...')
    cleaned = cleaned.replace('—', ' - ').replace('–', ' - ')

    # Remove only formatting characters, keep natural punctuation
    # KEEP: . , ! ? ; : ' " - (for natural speech phrasing)
    # REMOVE: ` _ ( ) { } [ ] / \ | @ # $ % ^ & * + = ~ < >
    cleaned = re.sub(r'[`_(){}\[\]/\\|@#$%^&*+=~<>]', ' ', cleaned)

    # Remove zero-width and invisible Unicode characters
    cleaned = re.sub(r'[\u200B-\u200D\uFEFF]', '', cleaned)

    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()

    return cleaned


def check_cached_audio(audio_id: str, tts_output_dir: Path, static_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Check for pre-generated cached audio files with prioritization.

    Priority order: Recorded > Opus > Gemini WAV > VITS > Legacy complete

    Args:
        audio_id: Unique identifier for the audio (e.g., "book_1_concise")
        tts_output_dir: Directory where audio files are stored
        static_dir: Static files root that audio URLs are relative to

    Returns:
        Dict with audio info if found, None otherwise:
        {
            'audio_url': str,  # URL path to serve
            'provider': str,   # Provider name
            'cached': bool     # Always True for cached files
        }
    """
    if not audio_id:
        return None

    # Recorded by plainly/scripts/audio/record_summaries.py
    recorded_path = tts_output_dir / f"{audio_id}.m4a"
    if recorded_path.exists():
        relative_path = str(recorded_path.relative_to(static_dir))
        return {
            'audio_url': f'/static/{relative_path}',
            'provider': 'recorded',
            'cached': True
        }

    # Priority 1: Check for Opus (compressed, optimized for speech)
    opus_path = tts_output_dir / f"{audio_id}_gemini.opus"
    if opus_path.exists():
        relative_path = str(opus_path.relative_to(static_dir))
        return {
            'audio_url': f'/static/{relative_path}',
            'provider': 'gemini-opus',
            'cached': True
        }

    # Priority 2: Check for Gemini TTS WAV (pre-generated offline, fallback)
    gemini_path = tts_output_dir / f"{audio_id}_gemini.wav"
    if gemini_path.exists():
        relative_path = str(gemini_path.relative_to(static_dir))
        return {
            'audio_url': f'/static/{relative_path}',
            'provider': 'gemini',
            'cached': True
        }

    # Priority 3: Check for VITS TTS (previously generated)
    vits_path = tts_output_dir / f"{audio_id}_vits.wav"
    if vits_path.exists():
        relative_path = str(vits_path.relative_to(static_dir))
        return {
            'audio_url': f'/static/{relative_path}',
            'provider': 'vits',
            'cached': True
        }

    # Priority 4: Check for legacy concatenated audio (backward compatibility)
    legacy_path = tts_output_dir / f"{audio_id}_complete.wav"
    if legacy_path.exists():
        relative_path = str(legacy_path.relative_to(static_dir))
        return {
            'audio_url': f'/static/{relative_path}',
            'provider': 'vits_legacy',
            'cached': True
        }

    return None
