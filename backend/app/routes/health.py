import time
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from app.extensions import db
from app.monitoring.camera_manager import camera_manager
from app.services.ml_service import ml_service

health_bp = Blueprint('health', __name__)
START_TIME = time.time()


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint providing comprehensive system status,
    database connectivity, and subsystem operational matrices.
    """
    db_status = "connected"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    uptime_seconds = int(time.time() - START_TIME)

    # Telemetry snapshot for subsystems
    try:
        cam_statuses = camera_manager.get_all_statuses()
        online_cams = sum(1 for s in cam_statuses.values() if s.get('status') == 'RUNNING')
        camera_subsystem = {
            'status': 'operational' if online_cams > 0 else ('idle' if cam_statuses else 'no_cameras'),
            'registered_count': len(cam_statuses),
            'online_count': online_cams
        }
    except Exception:
        camera_subsystem = {'status': 'unknown', 'registered_count': 0, 'online_count': 0}

    ml_status = ml_service.status
    ml_subsystem = {
        'status': ml_status,
        'is_ready': (ml_status == 'READY')
    }

    subsystems = {
        'backend': 'healthy',
        'database': db_status,
        'camera_system': camera_subsystem,
        'ml_subsystem': ml_subsystem,
        'alert_engine': {'status': 'operational'}
    }

    is_healthy = (db_status == "connected")

    return jsonify({
        "status": "healthy" if is_healthy else "degraded",
        "service": "AI-Based Security System in Healthcare",
        "version": "1.0.0",
        "database": db_status,
        "uptime_seconds": uptime_seconds,
        "environment": current_app.config.get('ENV', 'development'),
        "demo_mode": current_app.config.get('DEMO_MODE', True),
        "subsystems": subsystems
    }), 200 if is_healthy else 503
