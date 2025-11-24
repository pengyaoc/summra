"""
Shared TTS utilities for text chunking and WAV file stitching.
Provider-agnostic functions that can be used by any TTS engine.
"""

import re
import wave
import os
from typing import List, Tuple, Optional


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


def chunk_text_at_sentences(text: str, max_words: int = 800) -> List[Tuple[str, int, int]]:
    """
    Chunk text into segments of approximately max_words, cutting at sentence boundaries.

    Provider-agnostic chunking that works for any TTS engine.
    Different providers can use different max_words values:
    - Local TTS (VITS): smaller chunks (200-300 words)
    - API TTS (Gemini): larger chunks (800+ words)

    Args:
        text: Text to chunk (should be cleaned with clean_text_for_speech first)
        max_words: Maximum words per chunk

    Returns:
        List of tuples: (chunk_text, word_count, start_char_index)
    """
    # Split into sentences using regex for . ! ? followed by space or end
    # This pattern captures the punctuation with the sentence
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    current_word_count = 0
    char_position = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())

        # If adding this sentence would exceed max_words and we have content, save chunk
        if current_word_count + sentence_words > max_words and current_chunk:
            # Save current chunk
            chunk_text = ' '.join(current_chunk)
            chunks.append((chunk_text, current_word_count, char_position))

            # Start new chunk
            char_position += len(chunk_text) + 1  # +1 for space
            current_chunk = [sentence]
            current_word_count = sentence_words
        else:
            current_chunk.append(sentence)
            current_word_count += sentence_words

    # Add final chunk
    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunks.append((chunk_text, current_word_count, char_position))

    return chunks


def stitch_wav_files(wav_files: List[str], output_path: str) -> None:
    """
    Stitch multiple WAV files together into a single file.

    Provider-agnostic stitching that works for any WAV files.
    All input files must have same parameters (sample rate, channels, bit depth).

    Args:
        wav_files: List of WAV file paths to stitch together
        output_path: Path for the output stitched file

    Raises:
        ValueError: If wav_files is empty or files have different parameters
    """
    if not wav_files:
        raise ValueError("No WAV files to stitch")

    # Read parameters from first file
    with wave.open(wav_files[0], 'rb') as first_wav:
        params = first_wav.getparams()
        nchannels = params.nchannels
        sampwidth = params.sampwidth
        framerate = params.framerate

    # Verify all files have same parameters and collect PCM data
    pcm_data_list = []
    for wav_file in wav_files:
        with wave.open(wav_file, 'rb') as wf:
            if (wf.getnchannels() != nchannels or
                wf.getsampwidth() != sampwidth or
                wf.getframerate() != framerate):
                raise ValueError(f"WAV file {wav_file} has different parameters")

            pcm_data_list.append(wf.readframes(wf.getnframes()))

    # Write stitched file
    with wave.open(output_path, 'wb') as output_wav:
        output_wav.setnchannels(nchannels)
        output_wav.setsampwidth(sampwidth)
        output_wav.setframerate(framerate)

        for pcm_data in pcm_data_list:
            output_wav.writeframes(pcm_data)

    print(f"Stitched {len(wav_files)} WAV files into: {output_path}")


def print_chunking_debug(chunk_num: int, total_chunks: int, chunk_text: str,
                        word_count: int, start_pos: int, next_chunk_text: Optional[str] = None):
    """
    Print debug information for a text chunk.

    Helps visualize where chunks are split and verify sentence boundaries.

    Args:
        chunk_num: Current chunk number (1-indexed)
        total_chunks: Total number of chunks
        chunk_text: Text content of this chunk
        word_count: Word count of this chunk
        start_pos: Character position where this chunk starts
        next_chunk_text: Optional text of next chunk (to show boundary)
    """
    print(f"\n{'-'*80}")
    print(f"CHUNK {chunk_num}/{total_chunks}")
    print(f"{'-'*80}")
    print(f"Word count: {word_count}")
    print(f"Character count: {len(chunk_text)}")
    print(f"Character position: {start_pos}")
    print(f"\nFirst 100 characters:")
    print(f"  {chunk_text[:100]}...")
    print(f"\nLast 100 characters:")
    print(f"  ...{chunk_text[-100:]}")

    if next_chunk_text:
        # Show boundary - last sentence of current chunk and first of next
        print(f"\nBoundary marker (current chunk ends | next chunk starts):")
        print(f"  ...{chunk_text[-50:]} | {next_chunk_text[:50]}...")
