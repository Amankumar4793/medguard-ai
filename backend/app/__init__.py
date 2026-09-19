import os
import atexit
from flask import Flask, jsonify, send_from_directory, abort
from app.config import config_by_name
from app.extensions import db, cors, socketio
from app.monitoring import camera_manager
from app.routes import register_routes
from app.utils import setup_logger, ensure_directories

logger = setup_logger(__name__)


def create_app(config_name=None):
    """Application factory for Flask backend."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV') or ('production' if os.getenv('RENDER') or os.getenv('PORT') else 'development')

    app = Flask(__name__)
    config_class = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(config_class)

    # Ensure required data directories exist
    ensure_directories(
        app.config.get('SNAPSHOT_DIR'),
        app.config.get('VIDEO_DIR'),
        app.config.get('MODEL_DIR')
    )

    # Initialize extensions
    db.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config.get('CORS_ORIGINS', '*')}})
    socketio.init_app(app, cors_allowed_origins=app.config.get('CORS_ORIGINS', '*'))

    # Ensure database schema is initialized safely on startup
    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            logger.warning(f"Database table initialization notice: {exc}")

    # Initialize CameraManager
    camera_manager.init_app(app)
    atexit.register(camera_manager.shutdown_all)

    # Register blueprints
    register_routes(app)

    # Safe snapshot serving with path traversal protection
    @app.route('/api/snapshots/<path:filename>', methods=['GET'])
    def get_snapshot(filename):
        snapshot_dir = app.config.get('SNAPSHOT_DIR')
        # Prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            abort(400, description="Invalid snapshot filename.")
        return send_from_directory(snapshot_dir, filename)

    # Error handlers
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': getattr(error, 'description', str(error))
        }), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': getattr(error, 'description', 'Resource not found')
        }), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred. Please contact security system administrator.'
        }), 500

    logger.info(f"AI-Based Healthcare Security Backend initialized in [{config_name}] mode.")
    return app
