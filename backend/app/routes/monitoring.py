from flask import Blueprint, jsonify, request, Response
from app.extensions import db
from app.models.camera import Camera
from app.monitoring import camera_manager
from app.utils import setup_logger

logger = setup_logger('monitoring_routes')
monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/status', methods=['GET'])
def get_monitoring_status():
    """
    Get aggregated status of all cameras, merging persistent DB records
    with live VideoProcessor runtime telemetry.
    """
    cameras = Camera.query.all()
    camera_statuses = []

    for cam in cameras:
        telemetry = camera_manager.get_telemetry(cam.id)
        is_active = telemetry is not None and telemetry.get('status') == 'RUNNING'
        camera_statuses.append({
            'camera_id': cam.id,
            'name': cam.name,
            'location': cam.location,
            'enabled': cam.enabled,
            'source': cam.source,
            'source_type': cam.source_type,
            'status': telemetry.get('status', 'OFFLINE') if telemetry else 'OFFLINE',
            'monitoring_active': is_active,
            'fps': telemetry.get('fps', 0.0) if telemetry else 0.0,
            'frame_count': telemetry.get('frame_count', 0) if telemetry else 0,
            'uptime_seconds': telemetry.get('uptime_seconds', 0) if telemetry else 0,
            'error_message': telemetry.get('error_message') if telemetry else None,
            'resolution': telemetry.get('resolution', [640, 480]) if telemetry else [640, 480],
            'configured_fps': cam.configuration.get('fps', 15) if cam.configuration else 15
        })

    active_count = sum(1 for c in camera_statuses if c['monitoring_active'])

    return jsonify({
        'success': True,
        'active_monitors_count': active_count,
        'total_monitors': len(cameras),
        'cameras': camera_statuses
    }), 200


@monitoring_bp.route('/start', methods=['POST'])
def start_monitoring():
    """Start video processing worker for a camera or all enabled cameras."""
    data = request.get_json() or {}
    camera_id = data.get('camera_id')

    if camera_id is not None:
        try:
            camera_id = int(camera_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid camera_id parameter: must be an integer.'}), 400

        camera = db.session.get(Camera, camera_id)
        if not camera:
            return jsonify({'success': False, 'error': f'Camera #{camera_id} not found.'}), 404

        try:
            camera_manager.start_camera(camera.id, camera_model=camera)
            telemetry = camera_manager.get_telemetry(camera.id)
            return jsonify({
                'success': True,
                'message': f'Monitoring started for camera: {camera.name}',
                'camera_id': camera.id,
                'telemetry': telemetry
            }), 200
        except Exception as e:
            logger.error(f"Failed to start camera #{camera.id}: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to start camera feed: {str(e)}'
            }), 500
    else:
        # Start all enabled
        cameras = Camera.query.filter_by(enabled=True).all()
        started_count = 0
        for cam in cameras:
            try:
                camera_manager.start_camera(cam.id, camera_model=cam)
                started_count += 1
            except Exception as e:
                logger.error(f"Could not start enabled camera #{cam.id}: {e}")

        return jsonify({
            'success': True,
            'message': f'Monitoring started for {started_count} enabled cameras.',
            'active_count': started_count
        }), 200


@monitoring_bp.route('/stop', methods=['POST'])
def stop_monitoring():
    """Stop video processing worker for a camera or all cameras."""
    data = request.get_json() or {}
    camera_id = data.get('camera_id')

    if camera_id is not None:
        try:
            camera_id = int(camera_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid camera_id parameter: must be an integer.'}), 400

        camera_manager.stop_camera(camera_id)
        return jsonify({
            'success': True,
            'message': f'Monitoring stopped for camera #{camera_id}.',
            'camera_id': camera_id
        }), 200
    else:
        camera_manager.shutdown_all()
        return jsonify({
            'success': True,
            'message': 'Monitoring stopped for all cameras.'
        }), 200


@monitoring_bp.route('/restart', methods=['POST'])
def restart_monitoring():
    """Restart video processing worker for a specific camera."""
    data = request.get_json() or {}
    camera_id = data.get('camera_id')

    if camera_id is None:
        return jsonify({'success': False, 'error': 'Missing required parameter: camera_id.'}), 400

    try:
        camera_id = int(camera_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid camera_id parameter: must be an integer.'}), 400

    camera = db.session.get(Camera, camera_id)
    if not camera:
        return jsonify({'success': False, 'error': f'Camera #{camera_id} not found.'}), 404

    try:
        camera_manager.restart_camera(camera.id, camera_model=camera)
        telemetry = camera_manager.get_telemetry(camera.id)
        return jsonify({
            'success': True,
            'message': f'Camera #{camera_id} restarted successfully.',
            'camera_id': camera.id,
            'telemetry': telemetry
        }), 200
    except Exception as e:
        logger.error(f"Failed to restart camera #{camera_id}: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to restart camera: {str(e)}'
        }), 500


@monitoring_bp.route('/telemetry/<int:camera_id>', methods=['GET'])
def get_camera_telemetry(camera_id):
    """Retrieve real-time telemetry metrics for a camera."""
    telemetry = camera_manager.get_telemetry(camera_id)
    if not telemetry:
        # Fall back to DB record if processor hasn't run yet
        camera = db.session.get(Camera, camera_id)
        if not camera:
            return jsonify({'success': False, 'error': f'Camera #{camera_id} not found.'}), 404
        return jsonify({
            'success': True,
            'telemetry': {
                'camera_id': camera.id,
                'name': camera.name,
                'location': camera.location,
                'source': camera.source,
                'source_type': camera.source_type,
                'status': 'OFFLINE',
                'fps': 0.0,
                'frame_count': 0,
                'uptime_seconds': 0,
                'resolution': [640, 480],
                'error_message': None
            }
        }), 200

    return jsonify({
        'success': True,
        'telemetry': telemetry
    }), 200


@monitoring_bp.route('/detections/<int:camera_id>', methods=['GET'])
def get_camera_detections(camera_id):
    """Retrieve latest real-time AI object detections for a camera."""
    camera = db.session.get(Camera, camera_id)
    if not camera:
        return jsonify({'success': False, 'error': f'Camera #{camera_id} not found.'}), 404

    detections_data = camera_manager.get_detections(camera_id)
    return jsonify({
        'success': True,
        'camera_id': camera_id,
        'camera_name': camera.name,
        'location': camera.location,
        **detections_data
    }), 200


@monitoring_bp.route('/tracks/<int:camera_id>', methods=['GET'])
def get_camera_tracks(camera_id):
    """Retrieve active tracked physical entities for a camera."""
    camera = db.session.get(Camera, camera_id)
    if not camera:
        return jsonify({'success': False, 'error': f'Camera #{camera_id} not found.'}), 404

    tracks = camera_manager.get_tracks(camera_id)
    return jsonify({
        'success': True,
        'camera_id': camera_id,
        'camera_name': camera.name,
        'tracked_count': len(tracks),
        'tracks': tracks
    }), 200


@monitoring_bp.route('/zones/<int:camera_id>', methods=['GET'])
def get_camera_zones(camera_id):
    """Retrieve configured zones and live occupancy telemetry for a camera."""
    camera = db.session.get(Camera, camera_id)
    if not camera:
        return jsonify({'success': False, 'error': f'Camera #{camera_id} not found.'}), 404

    zones = camera_manager.get_zones(camera_id)
    return jsonify({
        'success': True,
        'camera_id': camera_id,
        'camera_name': camera.name,
        'zones_count': len(zones),
        'zones': zones
    }), 200


@monitoring_bp.route('/stream/<int:camera_id>', methods=['GET'])
def stream_camera(camera_id):
    """
    Browser-compatible MJPEG stream endpoint.
    Streams multipart/x-mixed-replace JPEG frames.
    """
    processor = camera_manager.get_processor(camera_id)

    # If not registered or offline, auto-start if valid in database
    if processor is None or processor.status in ('OFFLINE', 'ERROR'):
        camera = db.session.get(Camera, camera_id)
        if not camera:
            return jsonify({'success': False, 'error': f'Camera #{camera_id} not found.'}), 404
        try:
            camera_manager.start_camera(camera.id, camera_model=camera)
            processor = camera_manager.get_processor(camera.id)
        except Exception as e:
            logger.error(f"Auto-start stream failed for camera #{camera_id}: {e}")
            return jsonify({'success': False, 'error': f'Could not start camera stream: {str(e)}'}), 500

    if processor is None:
        return jsonify({'success': False, 'error': 'Video processor unavailable.'}), 503

    logger.info(f"Client connected to MJPEG stream for camera #{camera_id}.")
    return Response(
        processor.generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
