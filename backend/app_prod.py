"""
Production Flask application with pre-generated TTS only.
Imports common routes from app_base and adds production-specific features.
"""
from flask import jsonify, request
import os

# Handle both direct execution and module execution
try:
    from . import config
    from .app_base import app, logger, ensure_directories
except ImportError:
    import config
    from app_base import app, logger, ensure_directories


@app.route('/api/tts/generate', methods=['POST'])
def generate_tts():
    """Check for pre-generated TTS audio (generation disabled in production)"""
    try:
        data = request.json
        audio_id = data.get('id')  # Unique identifier for caching

        if not audio_id:
            return jsonify({
                'success': False,
                'error': 'No audio ID provided'
            }), 400

        # Check for cached audio using shared utility function
        try:
            from . import tts_utils
        except ImportError:
            import tts_utils

        cached_audio = tts_utils.check_cached_audio(audio_id, config.TTS_OUTPUT_DIR, config.BASE_DIR)
        if cached_audio:
            logger.info(f"Using cached audio: {cached_audio['provider']}")
            return jsonify({
                'success': True,
                'audio_url': cached_audio['audio_url'],
                'streaming': False,
                'cached': cached_audio['cached'],
                'provider': cached_audio['provider']
            })

        # No pre-generated audio found
        return jsonify({
            'success': False,
            'error': 'TTS generation is disabled in production. Audio files are pre-generated.',
            'message': 'Please contact administrator if audio is missing.'
        }), 404

    except Exception as e:
        logger.error(f"Error checking for pre-generated audio: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tts/stop', methods=['POST'])
def stop_tts():
    """Stop TTS endpoint (no-op in production since no generation happens)"""
    return jsonify({
        'success': True,
        'message': 'TTS stop requested (no action needed in production)'
    })


@app.route('/health')
def health_check():
    """Health check endpoint for production monitoring"""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    # Ensure data directories exist
    ensure_directories()

    # This is only for development/testing
    # In production, use: gunicorn -c gunicorn_config.py backend.app_prod:app
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
