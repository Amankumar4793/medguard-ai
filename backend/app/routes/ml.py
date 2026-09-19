from flask import Blueprint, jsonify, request
from app.services.ml_service import ml_service
from app.ml.features import get_feature_names, get_feature_descriptions, SecurityFeatureExtractor
from app.monitoring.camera_manager import camera_manager
from app.models.camera import Camera

from app.extensions import db

ml_bp = Blueprint('ml', __name__)


@ml_bp.route('/status', methods=['GET'])
def get_ml_status():
    """Returns runtime health, model metadata, feature count, and evaluation metrics."""
    status_data = ml_service.get_status()
    return jsonify({
        'success': True,
        'ml': status_data
    }), 200


@ml_bp.route('/analysis/<int:camera_id>', methods=['GET'])
def get_camera_analysis(camera_id):
    """
    Returns latest ML anomaly analysis, 19-feature vector,
    and explainable indicators for a specific camera.
    """
    camera = db.session.get(Camera, camera_id)
    if not camera:
        return jsonify({
            'success': False,
            'error': f"Camera #{camera_id} not found."
        }), 404

    analysis = camera_manager.get_ml_analysis(camera_id)
    if not analysis:
        # Camera is offline or quiescent - generate baseline analysis
        extractor = SecurityFeatureExtractor()
        feat_dict = extractor.extract_features_dict(camera_id)
        analysis = ml_service.analyze_camera(camera_id, feat_dict)

    return jsonify({
        'success': True,
        'camera_id': camera_id,
        'camera_name': camera.name,
        'camera_location': camera.location,
        'analysis': analysis
    }), 200


@ml_bp.route('/features', methods=['GET'])
def get_features_info():
    """Returns metadata and human-readable definitions for all 19 surveillance features."""
    return jsonify({
        'success': True,
        'feature_count': len(get_feature_names()),
        'features': get_feature_names(),
        'descriptions': get_feature_descriptions()
    }), 200


@ml_bp.route('/reload', methods=['POST'])
def reload_model():
    """Reloads the serialized Isolation Forest model and scaler from disk."""
    success = ml_service.load_model()
    return jsonify({
        'success': success,
        'status': ml_service.status,
        'message': 'Model reloaded successfully' if success else 'Failed to reload model'
    }), 200 if success else 500
