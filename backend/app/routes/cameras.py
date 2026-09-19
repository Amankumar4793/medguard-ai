from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models.camera import Camera
from app.monitoring import camera_manager

cameras_bp = Blueprint('cameras', __name__)


@cameras_bp.route('/', methods=['GET'])
def get_cameras():
    """Retrieve all configured cameras."""
    cameras = Camera.query.order_by(Camera.created_at.desc()).all()
    return jsonify({
        'success': True,
        'count': len(cameras),
        'cameras': [c.to_dict() for c in cameras]
    }), 200


@cameras_bp.route('/<int:camera_id>', methods=['GET'])
def get_camera(camera_id):
    """Retrieve a single camera by ID."""
    camera = Camera.query.get_or_404(camera_id)
    return jsonify({
        'success': True,
        'camera': camera.to_dict()
    }), 200


@cameras_bp.route('/', methods=['POST'])
def create_camera():
    """Create a new camera configuration."""
    data = request.get_json() or {}
    
    # Basic validation
    name = data.get('name', '').strip()
    source = data.get('source', '').strip()
    if not name or not source:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: "name" and "source" are required.'
        }), 400

    camera = Camera(
        name=name,
        source=source,
        source_type=data.get('source_type', 'webcam'),
        location=data.get('location', 'General Area').strip(),
        enabled=data.get('enabled', True),
        configuration=data.get('configuration', {
            "zones": [],
            "operating_hours": {"start": "08:00", "end": "20:00"},
            "fps": 15,
            "resolution": [640, 480],
            "crowd_threshold": 4,
            "loitering_threshold_seconds": 30
        })
    )
    db.session.add(camera)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Camera created successfully.',
        'camera': camera.to_dict()
    }), 201


@cameras_bp.route('/<int:camera_id>', methods=['PUT'])
def update_camera(camera_id):
    """Update camera configuration."""
    camera = Camera.query.get_or_404(camera_id)
    data = request.get_json() or {}

    if 'name' in data:
        camera.name = data['name'].strip()
    if 'source' in data:
        camera.source = data['source'].strip()
    if 'source_type' in data:
        camera.source_type = data['source_type']
    if 'location' in data:
        camera.location = data['location'].strip()
    if 'enabled' in data:
        camera.enabled = bool(data['enabled'])
    if 'configuration' in data:
        camera.configuration = data['configuration']

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Camera updated successfully.',
        'camera': camera.to_dict()
    }), 200


@cameras_bp.route('/<int:camera_id>', methods=['DELETE'])
def delete_camera(camera_id):
    """Delete a camera configuration."""
    camera = Camera.query.get_or_404(camera_id)
    # Stop processor if active to prevent orphaned threads
    try:
        camera_manager.stop_camera(camera_id)
    except Exception:
        pass

    db.session.delete(camera)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Camera {camera_id} deleted successfully.'
    }), 200
