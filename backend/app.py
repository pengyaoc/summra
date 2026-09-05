"""
Development Flask application with full TTS generation support.
Imports common routes from app_base and adds development-specific features.
"""
from flask import jsonify, request
from pathlib import Path

# Handle both direct execution (`python backend/app.py`, dev) and package
# import — `backend` is installed as an editable package (see
# pyproject.toml), so the fallback resolves from anywhere without a
# sys.path hack.
try:
    from . import config
    from .app_base import app, logger, ensure_directories
except ImportError:
    from backend import config
    from backend.app_base import app, logger, ensure_directories

# Set development mode flag
app.config['IS_DEVELOPMENT'] = True

# Track active TTS generations and their chunk files for cleanup
# Format: {audio_id: [chunk_file_paths]}
active_tts_generations = {}


@app.route('/api/tts/generate', methods=['POST'])
def generate_tts():
    """Generate TTS audio for a summary or chapter with streaming support and caching"""
    try:
        data = request.json
        text = data.get('text')
        audio_id = data.get('id')  # Unique identifier for caching
        use_streaming = data.get('streaming', True)  # Default to streaming

        if not text:
            return jsonify({
                'success': False,
                'error': 'No text provided'
            }), 400

        # Import Gemini TTS handler (local Coqui/VITS handler removed).
        try:
            from .gemini_tts_handler import GeminiTTSHandler
        except ImportError:
            from backend.gemini_tts_handler import GeminiTTSHandler
        import threading
        import hashlib
        import wave

        tts = GeminiTTSHandler()

        # Check for cached audio using shared utility function
        try:
            from . import tts_utils
        except ImportError:
            from backend import tts_utils
        cached_audio = tts_utils.check_cached_audio(audio_id, config.TTS_OUTPUT_DIR, config.BASE_DIR)
        if cached_audio:
            logger.info(f"Using cached audio: {cached_audio['provider']}")
            return jsonify({
                'success': True,
                'audio_url': request.script_root + cached_audio['audio_url'],
                'streaming': False,
                'cached': cached_audio['cached'],
                'provider': cached_audio['provider']
            })

        # Use streaming for better UX (immediate playback)
        if use_streaming and len(text) > 100:  # Lower threshold for streaming
            # Split text into sentence-based chunks
            # This ensures we never break in the middle of a sentence
            import re

            # Split into sentences - simpler, more reliable pattern
            # Matches sentence-ending punctuation followed by whitespace
            sentence_pattern = re.compile(r'(?<=[.!?])\s+')
            sentences = sentence_pattern.split(text)

            # Clean up sentences - remove extra whitespace and ensure proper ending
            cleaned_sentences = []
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence:
                    # Ensure sentence ends with punctuation
                    if sentence and sentence[-1] not in '.!?':
                        sentence = sentence + '.'
                    cleaned_sentences.append(sentence)

            sentences = cleaned_sentences

            # Group sentences into chunks (max ~300 chars per chunk for faster playback)
            chunks = []
            current_chunk = []
            current_length = 0
            max_chunk_chars = 300

            for sentence in sentences:
                sentence_length = len(sentence)

                # If adding this sentence would exceed limit, start new chunk
                if current_length + sentence_length > max_chunk_chars and current_chunk:
                    # Join with space and ensure proper ending
                    chunk_text = ' '.join(current_chunk)
                    # Ensure chunk ends with punctuation
                    if chunk_text and chunk_text[-1] not in '.!?':
                        chunk_text = chunk_text + '.'
                    chunks.append(chunk_text)
                    current_chunk = [sentence]
                    current_length = sentence_length
                else:
                    current_chunk.append(sentence)
                    current_length += sentence_length + 1  # +1 for space

            # Add final chunk
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                # Ensure chunk ends with punctuation
                if chunk_text and chunk_text[-1] not in '.!?':
                    chunk_text = chunk_text + '.'
                chunks.append(chunk_text)

            # Generate first chunk immediately for instant playback
            chunk_hash = hashlib.md5(f"{text[:50]}_0".encode()).hexdigest()
            first_audio_path = tts.generate_audio(chunks[0], f"chunk_{chunk_hash}")

            if not first_audio_path:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate first audio chunk'
                }), 500

            # Start background thread to generate remaining chunks AND concatenate
            remaining_chunks = chunks[1:]
            chunk_files = []

            def generate_and_concatenate():
                """Background task to generate remaining chunks and concatenate all"""
                all_chunk_files = [first_audio_path]

                # Generate remaining chunks
                for i, chunk in enumerate(remaining_chunks, start=1):
                    chunk_hash = hashlib.md5(f"{text[:50]}_{i}".encode()).hexdigest()
                    chunk_path = tts.generate_audio(chunk, f"chunk_{chunk_hash}")
                    if chunk_path:
                        all_chunk_files.append(chunk_path)

                # Concatenate all chunks into a single file
                if audio_id and len(all_chunk_files) > 0:
                    try:
                        concatenate_audio_files(all_chunk_files, config.TTS_OUTPUT_DIR / f"{audio_id}_complete.wav")
                        logger.info(f"Concatenated {len(all_chunk_files)} chunks into {audio_id}_complete.wav")

                        # Keep chunks available for streaming playback
                        # They will be cleaned up when user stops playback or on next request
                        logger.debug(f"Keeping {len(all_chunk_files)} chunks available for streaming")
                    except Exception as e:
                        logger.error(f"Error concatenating audio files: {e}")

            if remaining_chunks or audio_id:
                thread = threading.Thread(target=generate_and_concatenate, daemon=True)
                thread.start()

            # Return all chunk URLs (some will be generated in background)
            audio_urls = []
            chunk_file_paths = []
            for i in range(len(chunks)):
                chunk_hash = hashlib.md5(f"{text[:50]}_{i}".encode()).hexdigest()
                audio_path = config.TTS_OUTPUT_DIR / f"chunk_{chunk_hash}.wav"
                chunk_file_paths.append(str(audio_path))
                relative_path = str(audio_path.relative_to(config.BASE_DIR / 'frontend' / 'static'))
                audio_urls.append(request.script_root + f'/static/{relative_path}')

            # Track chunk files for cleanup if user stops playback
            if audio_id:
                active_tts_generations[audio_id] = chunk_file_paths
                logger.debug(f"Tracking {len(chunk_file_paths)} chunks for audio_id: {audio_id}")

            return jsonify({
                'success': True,
                'audio_urls': audio_urls,
                'streaming': True,
                'total_chunks': len(chunks),
                'audio_id': audio_id  # Return audio_id so frontend can send it when stopping
            })
        else:
            # Generate single audio file for short text
            audio_path = tts.generate_audio(text, audio_id)

            if audio_path:
                # Return relative path for frontend
                relative_path = str(Path(audio_path).relative_to(config.BASE_DIR / 'frontend' / 'static'))
                return jsonify({
                    'success': True,
                    'audio_url': request.script_root + f'/static/{relative_path}',
                    'streaming': False
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate audio'
                }), 500

    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def concatenate_audio_files(file_paths, output_path):
    """Concatenate multiple WAV files into a single file"""
    import wave

    # Read parameters from first file
    with wave.open(file_paths[0], 'rb') as first_wav:
        params = first_wav.getparams()

    # Open output file
    with wave.open(str(output_path), 'wb') as output_wav:
        output_wav.setparams(params)

        # Write each file's audio data
        for file_path in file_paths:
            with wave.open(file_path, 'rb') as input_wav:
                output_wav.writeframes(input_wav.readframes(input_wav.getnframes()))


@app.route('/api/tts/stop', methods=['POST'])
def stop_tts():
    """Stop any ongoing TTS generation and clean up temporary chunk files"""
    try:
        data = request.json
        audio_id = data.get('audio_id') if data else None

        # Clean up temporary chunk files if we have an audio_id
        if audio_id and audio_id in active_tts_generations:
            chunk_files = active_tts_generations[audio_id]
            cleanup_count = 0

            import os
            for chunk_file in chunk_files:
                try:
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)
                        cleanup_count += 1
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up chunk {chunk_file}: {cleanup_error}")

            # Remove from tracking
            del active_tts_generations[audio_id]
            logger.info(f"Cleaned up {cleanup_count} temporary chunk files for audio_id: {audio_id}")

            return jsonify({
                'success': True,
                'message': f'Stopped TTS and cleaned up {cleanup_count} temporary files',
                'cleaned_files': cleanup_count
            })
        else:
            return jsonify({
                'success': True,
                'message': 'TTS generation stop requested (no cleanup needed)'
            })

    except Exception as e:
        logger.error(f"Error stopping TTS: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===== ADMIN ENDPOINTS (Development Only) =====

@app.route('/api/admin/chapters/<int:book_id>/<int:chapter_number>', methods=['PUT'])
def update_chapter_admin(book_id, chapter_number):
    """Admin endpoint to update chapter text and modern English text (development only)"""
    # Verify we're in development mode
    if not app.config.get('IS_DEVELOPMENT', False):
        return jsonify({
            'success': False,
            'error': 'Admin endpoints are only available in development mode'
        }), 403

    try:
        from .models import Database
    except ImportError:
        from backend.models import Database

    try:
        data = request.json
        chapter_text = data.get('chapter_text')
        modern_english_text = data.get('modern_english_text')

        if chapter_text is None and modern_english_text is None:
            return jsonify({
                'success': False,
                'error': 'At least one field (chapter_text or modern_english_text) must be provided'
            }), 400

        db = Database()

        # Verify chapter exists
        chapter = db.get_chapter(book_id, chapter_number)
        if not chapter:
            return jsonify({
                'success': False,
                'error': f'Chapter {chapter_number} not found for book {book_id}'
            }), 404

        # Update the chapter
        db.update_chapter_both_texts(
            book_id=book_id,
            chapter_number=chapter_number,
            chapter_text=chapter_text,
            modern_english_text=modern_english_text
        )

        logger.info(f"Updated chapter {chapter_number} for book {book_id}")

        return jsonify({
            'success': True,
            'message': f'Chapter {chapter_number} updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating chapter: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Ensure data directories exist
    ensure_directories()

    # Run the app
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )
