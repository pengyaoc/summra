"""Reader API shared by both apps: manifest, segments, marker map/recover.
The content DB is looked up per request so apps can swap it (and tests can
patch it) after the blueprint is registered."""
import logging
from typing import Any, Callable

from flask import Blueprint, jsonify, make_response, request

logger = logging.getLogger(__name__)


def make_reader_blueprint(get_content_db: Callable[[], Any], cache_visibility: str) -> Blueprint:
    bp = Blueprint('reader', __name__)

    @bp.route('/api/reader/books/<int:book_id>/manifest', methods=['GET'])
    def get_reader_manifest(book_id):
        """Metadata-only entry point for the continuous reader."""
        db = get_content_db()
        try:
            manifest = db.get_reader_manifest(book_id)
            response = make_response(jsonify({'success': True, 'manifest': manifest}))
            response.set_etag(manifest['etag'])
            response.headers['Cache-Control'] = f'{cache_visibility}, max-age=300, must-revalidate'
            return response.make_conditional(request)
        except ValueError as error:
            return jsonify({'success': False, 'error': str(error)}), 404
        except Exception:
            logger.exception('Error building reader manifest for book %s', book_id)
            return jsonify({'success': False, 'error': 'Unable to load reader metadata'}), 500

    @bp.route('/api/reader/books/<int:book_id>/segments/<segment_id>', methods=['GET'])
    def get_reader_segment(book_id, segment_id):
        """Return one bounded, immutable reader segment for a mode."""
        mode = request.args.get('mode', '')
        db = get_content_db()
        try:
            segment = db.get_reader_segment(book_id, segment_id, mode)
            if not segment:
                return jsonify({'success': False, 'error': 'Segment not found'}), 404
            response = make_response(jsonify({'success': True, 'segment': segment}))
            response.set_etag(segment['etag'])
            response.headers['Cache-Control'] = f'{cache_visibility}, max-age=31536000, immutable'
            return response.make_conditional(request)
        except ValueError as error:
            return jsonify({'success': False, 'error': str(error)}), 404
        except Exception:
            logger.exception('Error loading reader segment %s for book %s', segment_id, book_id)
            return jsonify({'success': False, 'error': 'Unable to load reader segment'}), 500

    @bp.route('/api/reader/books/<int:book_id>/map', methods=['POST'])
    def map_reader_marker(book_id):
        """Map a marker across modes without treating it as progress."""
        payload = request.get_json(silent=True) or {}
        marker = payload.get('marker')
        target_mode = payload.get('target_mode')
        if not isinstance(marker, dict):
            return jsonify({'success': False, 'error': 'A marker is required'}), 400
        try:
            mapped = get_content_db().map_reader_marker(book_id, marker, target_mode)
            if not mapped:
                return jsonify({'success': False, 'error': 'No aligned destination is available'}), 404
            return jsonify({'success': True, 'marker': mapped})
        except ValueError as error:
            return jsonify({'success': False, 'error': str(error)}), 404
        except Exception:
            logger.exception('Error mapping reader marker for book %s', book_id)
            return jsonify({'success': False, 'error': 'Unable to map reader marker'}), 500

    @bp.route('/api/reader/books/<int:book_id>/recover', methods=['POST'])
    def recover_reader_marker(book_id):
        """Resolve a marker from an older content version without writing state."""
        payload = request.get_json(silent=True) or {}
        marker = payload.get('marker')
        if not isinstance(marker, dict):
            return jsonify({'success': False, 'error': 'A marker is required'}), 400
        try:
            recovered = get_content_db().recover_reader_marker(book_id, marker)
            if not recovered:
                return jsonify({'success': False, 'error': 'Marker could not be recovered'}), 404
            return jsonify({'success': True, 'marker': recovered})
        except ValueError as error:
            return jsonify({'success': False, 'error': str(error)}), 404
        except Exception:
            logger.exception('Error recovering reader marker for book %s', book_id)
            return jsonify({'success': False, 'error': 'Unable to recover reader marker'}), 500

    return bp
