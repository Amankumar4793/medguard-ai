from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models.event import SecurityEvent
from app.models.camera import Camera

events_bp = Blueprint('events', __name__)


@events_bp.route('/', methods=['GET'])
def get_events():
    """Retrieve security events with optional filtering and pagination."""
    camera_id = request.args.get('camera_id', type=int)
    risk_level = request.args.get('risk_level')
    event_type = request.args.get('event_type')
    try:
        raw_limit = request.args.get('limit', default=50, type=int)
        limit = max(1, min(raw_limit if raw_limit is not None else 50, 100))
    except (ValueError, TypeError):
        limit = 50

    try:
        raw_offset = request.args.get('offset', default=0, type=int)
        offset = max(0, raw_offset if raw_offset is not None else 0)
    except (ValueError, TypeError):
        offset = 0

    query = SecurityEvent.query

    if camera_id:
        query = query.filter_by(camera_id=camera_id)
    if risk_level:
        query = query.filter_by(risk_level=risk_level.upper())
    if event_type:
        query = query.filter_by(event_type=event_type)

    total_count = query.count()
    events = query.order_by(SecurityEvent.timestamp.desc()).offset(offset).limit(limit).all()

    return jsonify({
        'success': True,
        'total': total_count,
        'limit': limit,
        'offset': offset,
        'events': [e.to_dict() for e in events]
    }), 200


@events_bp.route('/<int:event_id>', methods=['GET'])
def get_event(event_id):
    """Retrieve single security event by ID."""
    event = db.session.get(SecurityEvent, event_id)
    if not event:
        return jsonify({
            'success': False,
            'error': f'Security event #{event_id} not found.'
        }), 404

    return jsonify({
        'success': True,
        'event': event.to_dict()
    }), 200


@events_bp.route('/', methods=['POST'])
def create_event():
    """Create a security event (used by detection engine or testing)."""
    data = request.get_json() or {}
    camera_id = data.get('camera_id')
    event_type = data.get('event_type')
    description = data.get('description', 'Detected security event')

    if not camera_id or not event_type:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: camera_id and event_type.'
        }), 400

    # Ensure camera exists
    camera = db.session.get(Camera, camera_id)
    if not camera:
        return jsonify({
            'success': False,
            'error': f'Camera with ID {camera_id} does not exist.'
        }), 404

    # Validate risk_score, confidence, and risk_level
    try:
        risk_score = float(data.get('risk_score', 50.0))
        if not (0.0 <= risk_score <= 100.0):
            return jsonify({'success': False, 'error': 'risk_score must be between 0.0 and 100.0.'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'risk_score must be a numeric value.'}), 400

    try:
        confidence = float(data.get('confidence', 0.85))
        if not (0.0 <= confidence <= 1.0):
            return jsonify({'success': False, 'error': 'confidence must be between 0.0 and 1.0.'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'confidence must be a numeric value.'}), 400

    raw_level = str(data.get('risk_level', 'MEDIUM')).upper()
    if raw_level not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
        return jsonify({'success': False, 'error': f"Invalid risk_level: '{raw_level}'. Must be LOW, MEDIUM, HIGH, or CRITICAL."}), 400

    event = SecurityEvent(
        camera_id=camera_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        confidence=confidence,
        risk_score=risk_score,
        risk_level=raw_level,
        description=description,
        snapshot_path=data.get('snapshot_path'),
        status=data.get('status', 'NEW'),
        event_metadata=data.get('metadata', {})
    )

    db.session.add(event)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Security event created successfully.',
        'event': event.to_dict()
    }), 201
