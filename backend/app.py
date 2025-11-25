from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS
from pathlib import Path
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import models

app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# Initialize database
db = models.Database()

# Track active TTS generations and their chunk files for cleanup
# Format: {audio_id: [chunk_file_paths]}
active_tts_generations = {}


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/api/books', methods=['GET'])
def get_books():
    """Get all books"""
    try:
        books = db.get_all_books()

        # Convert cover image paths to URLs for frontend
        for book in books:
            if book.get('cover_image_url') and not book['cover_image_url'].startswith('http'):
                # It's a local path, prepend /static/
                book['cover_image_url'] = f"/static/{book['cover_image_url']}"

        return jsonify({
            'success': True,
            'books': books
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    """Get book details"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # Don't return full text in API response (too large)
        book_data = {k: v for k, v in book.items() if k != 'full_text'}

        # Convert cover image path to URL for frontend
        if book_data.get('cover_image_url') and not book_data['cover_image_url'].startswith('http'):
            # It's a local path, prepend /static/
            book_data['cover_image_url'] = f"/static/{book_data['cover_image_url']}"

        return jsonify({
            'success': True,
            'book': book_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/summary/<summary_type>', methods=['GET'])
def get_summary(book_id, summary_type):
    """Get summary for a book"""
    try:
        # Validate summary type
        if summary_type not in ['concise', 'medium', 'comprehensive', 'full']:
            return jsonify({
                'success': False,
                'error': 'Invalid summary type. Must be: concise, medium, comprehensive, or full'
            }), 400

        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        # For full-length view, use comprehensive summary with chapter text
        if summary_type == 'full':
            summary = db.get_summary(book_id, 'comprehensive')
            chapters = db.get_chapters(book_id)

            # Show partial content if chapters exist, even if overall summary doesn't
            if not chapters:
                return jsonify({
                    'success': False,
                    'error': 'Full-length view requires comprehensive summary. Please generate summaries first.'
                }), 404

            # Check if chapters have text (for backwards compatibility)
            if chapters and not chapters[0].get('chapter_text'):
                return jsonify({
                    'success': False,
                    'error': 'Chapter text not available. Please regenerate summaries to include full text.'
                }), 404

            # Prepare book data with cover image path conversion
            book_data = {
                'id': book['id'],
                'title': book['title'],
                'author': book['author']
            }

            # Add cover image if available
            if book.get('cover_image_url'):
                cover_url = book['cover_image_url']
                if not cover_url.startswith('http'):
                    # It's a local path, prepend /static/
                    cover_url = f"/static/{cover_url}"
                book_data['cover_image_url'] = cover_url

            response_data = {
                'success': True,
                'book': book_data,
                'summary': summary,
                'summary_type': 'full',
                'chapters': chapters
            }

            return jsonify(response_data)

        # For other summary types
        summary = db.get_summary(book_id, summary_type)

        # For comprehensive summary, also get chapters
        chapters = None
        if summary_type == 'comprehensive':
            chapters = db.get_chapters(book_id)

            # Show partial content if chapters exist, even if overall summary doesn't
            # This handles the case where chapters are still being generated
            if not summary and not chapters:
                return jsonify({
                    'success': False,
                    'error': 'Summary not found. Please generate summaries first.'
                }), 404

        # For other summary types (concise, medium), require the summary
        if not summary and summary_type != 'comprehensive':
            return jsonify({
                'success': False,
                'error': 'Summary not found. Please generate summaries first.'
            }), 404

        # Prepare book data with cover image path conversion
        book_data = {
            'id': book['id'],
            'title': book['title'],
            'author': book['author']
        }

        # Add cover image if available
        if book.get('cover_image_url'):
            cover_url = book['cover_image_url']
            if not cover_url.startswith('http'):
                # It's a local path, prepend /static/
                cover_url = f"/static/{cover_url}"
            book_data['cover_image_url'] = cover_url

        response_data = {
            'success': True,
            'book': book_data,
            'summary': summary,
            'summary_type': summary_type
        }

        if chapters:
            response_data['chapters'] = chapters

        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/books/<int:book_id>/chapters', methods=['GET'])
def get_chapters(book_id):
    """Get all chapter summaries for a book"""
    try:
        book = db.get_book(book_id)
        if not book:
            return jsonify({
                'success': False,
                'error': 'Book not found'
            }), 404

        chapters = db.get_chapters(book_id)

        # Prepare book data with cover image path conversion
        book_data = {
            'id': book['id'],
            'title': book['title'],
            'author': book['author']
        }

        # Add cover image if available
        if book.get('cover_image_url'):
            cover_url = book['cover_image_url']
            if not cover_url.startswith('http'):
                # It's a local path, prepend /static/
                cover_url = f"/static/{cover_url}"
            book_data['cover_image_url'] = cover_url

        return jsonify({
            'success': True,
            'book': book_data,
            'chapters': chapters
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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

        # Import TTS handler
        from tts_handler import TTSHandler
        import threading
        import hashlib
        import wave

        tts = TTSHandler()

        # Check for cached audio with prioritization: Gemini > VITS > Legacy complete
        if audio_id:
            # Priority 1: Check for Gemini TTS (pre-generated offline)
            gemini_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_gemini.wav"
            if gemini_audio_path.exists():
                print(f"Using Gemini TTS audio: {gemini_audio_path}")
                relative_path = str(gemini_audio_path.relative_to(config.BASE_DIR / 'frontend' / 'static'))
                return jsonify({
                    'success': True,
                    'audio_url': f'/static/{relative_path}',
                    'streaming': False,
                    'cached': True,
                    'provider': 'gemini'
                })

            # Priority 2: Check for VITS TTS (previously generated)
            vits_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_vits.wav"
            if vits_audio_path.exists():
                print(f"Using VITS TTS audio: {vits_audio_path}")
                relative_path = str(vits_audio_path.relative_to(config.BASE_DIR / 'frontend' / 'static'))
                return jsonify({
                    'success': True,
                    'audio_url': f'/static/{relative_path}',
                    'streaming': False,
                    'cached': True,
                    'provider': 'vits'
                })

            # Priority 3: Check for legacy concatenated audio (backward compatibility)
            cached_audio_path = config.TTS_OUTPUT_DIR / f"{audio_id}_complete.wav"
            if cached_audio_path.exists():
                print(f"Using legacy cached audio: {cached_audio_path}")
                relative_path = str(cached_audio_path.relative_to(config.BASE_DIR / 'frontend' / 'static'))
                return jsonify({
                    'success': True,
                    'audio_url': f'/static/{relative_path}',
                    'streaming': False,
                    'cached': True,
                    'provider': 'vits_legacy'
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
                        print(f"Concatenated {len(all_chunk_files)} chunks into {audio_id}_complete.wav")

                        # Keep chunks available for streaming playback
                        # They will be cleaned up when user stops playback or on next request
                        print(f"Keeping {len(all_chunk_files)} chunks available for streaming")
                    except Exception as e:
                        print(f"Error concatenating audio files: {e}")

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
                audio_urls.append(f'/static/{relative_path}')

            # Track chunk files for cleanup if user stops playback
            if audio_id:
                active_tts_generations[audio_id] = chunk_file_paths
                print(f"Tracking {len(chunk_file_paths)} chunks for audio_id: {audio_id}")

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
                    'audio_url': f'/static/{relative_path}',
                    'streaming': False
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate audio'
                }), 500

    except Exception as e:
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
                    print(f"Error cleaning up chunk {chunk_file}: {cleanup_error}")

            # Remove from tracking
            del active_tts_generations[audio_id]
            print(f"Cleaned up {cleanup_count} temporary chunk files for audio_id: {audio_id}")

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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/summary-configs', methods=['GET'])
def get_summary_configs():
    """Get available summary configurations"""
    return jsonify({
        'success': True,
        'configs': config.SUMMARY_CONFIGS
    })


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    # Ensure data directories exist
    config.BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    config.SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    config.TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.COVERS_DIR.mkdir(parents=True, exist_ok=True)

    # Run the app
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    )
