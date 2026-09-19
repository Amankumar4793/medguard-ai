import time
import pytest
import numpy as np
from datetime import datetime, timezone
from app import create_app
from app.extensions import db
from app.models.camera import Camera
from app.ml.features import (
    SecurityFeatureExtractor, FEATURE_NAMES,
    get_feature_names, get_feature_descriptions
)
from app.ml.anomaly_detector import AnomalyDetector
from app.services.ml_service import MLService, ml_service
from app.detection.tracker import TrackedObject
from app.detection.zones import Zone


@pytest.fixture
def app():
    """Create Flask test application."""
    test_app = create_app('testing')
    with test_app.app_context():
        db.create_all()
        # Seed test camera
        cam = Camera(
            name="ICU Corridor Cam",
            source="0",
            source_type="webcam",
            location="ICU Ward",
            enabled=True,
            configuration={
                "zones": [
                    {
                        "id": "zone_icu_rest",
                        "name": "Sterile ICU Storage",
                        "type": "restricted",
                        "severity": "CRITICAL",
                        "polygon": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
                    }
                ]
            }
        )
        db.session.add(cam)
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_feature_names_and_descriptions():
    """Validates that all 19 features have canonical names and descriptive metadata."""
    names = get_feature_names()
    assert len(names) == 19
    assert names == FEATURE_NAMES
    descriptions = get_feature_descriptions()
    assert len(descriptions) == 19
    for name in names:
        assert name in descriptions
        assert len(descriptions[name]) > 10


def test_security_feature_extractor_lifecycle():
    """Validates sliding window buffering and 19-dimensional feature calculation."""
    extractor = SecurityFeatureExtractor(window_seconds=60)
    now_dt = datetime(2026, 9, 18, 14, 30, 0, tzinfo=timezone.utc)

    # Empty extractor returns safe neutral baseline vector
    baseline = extractor.extract_features(camera_id=1, current_dt=now_dt)
    assert len(baseline) == 19
    assert baseline[0] == 0.0  # persons_detected
    assert baseline[16] == 14.0  # activity_hour (14:30)
    assert baseline[17] == 4.0   # day_of_week (Friday=4)

    # Simulate active frame observations
    zone = Zone({'id': "z1", 'name': "Pharmacy", 'type': "restricted", 'severity': "HIGH", 'polygon': [[0, 0], [1, 1]]})
    track1 = TrackedObject(track_id=1, class_name="person", confidence=0.88, bbox=[10, 10, 50, 90])
    track1.current_zone_id = "z1"
    track1.zone_entry_time = time.time() - 32.5

    zone_eval = {
        'entries': [{'track': track1, 'zone': zone, 'timestamp': 100.0}],
        'exits': [],
        'occupancy': {'z1': 1},
        'violations': []
    }

    raw_dets = [{'class_name': 'person', 'confidence': 0.88, 'bbox': [10, 10, 50, 90]}]

    extractor.update(
        camera_id=1,
        tracks=[track1],
        raw_detections=raw_dets,
        zone_eval_result=zone_eval,
        sec_events=[{'type': 'loitering'}],
        current_dt=now_dt,
        is_after_hours=False
    )

    feat_vec = extractor.extract_features(camera_id=1, current_dt=now_dt)
    assert len(feat_vec) == 19
    assert feat_vec[1] >= 1.0   # unique_tracks
    assert feat_vec[2] >= 1.0   # zone_occupancy
    assert feat_vec[3] >= 1.0   # restricted_zone_entries
    assert feat_vec[5] >= 30.0  # time_in_restricted_zone
    assert feat_vec[10] >= 0.80 # detection_confidence_mean

    feat_dict = extractor.extract_features_dict(camera_id=1, current_dt=now_dt)
    assert isinstance(feat_dict, dict)
    assert len(feat_dict) == 19
    assert 'time_in_restricted_zone' in feat_dict


def test_anomaly_detector_training_and_calibration():
    """Validates Isolation Forest model training, metrics, and 0-100 score calibration."""
    detector = AnomalyDetector(contamination=0.10, n_estimators=50, random_state=42)

    # Generate synthetic training batch: 100 normal + 10 anomalous
    np.random.seed(42)
    X_normal = np.random.normal(loc=0.0, scale=1.0, size=(100, 19))
    X_anomalies = np.random.uniform(low=8.0, high=15.0, size=(10, 19))
    X_train = np.vstack([X_normal, X_anomalies])
    y_true = np.array([0] * 100 + [1] * 10)

    meta = detector.train(X_train, y_true=y_true)
    assert detector.is_ready is True
    assert meta['feature_count'] == 19
    assert 'evaluation_metrics' in meta

    # Test prediction on normal sample
    res_norm = detector.predict_one(X_normal[0])
    assert 'is_anomaly' in res_norm
    assert 'anomaly_score' in res_norm
    assert 0.0 <= res_norm['anomaly_score'] <= 100.0
    assert isinstance(res_norm['indicators'], list)
    assert len(res_norm['indicators']) > 0

    # Test prediction on extreme anomaly sample
    extreme_anomaly = [50.0, 10.0, 8.0, 6.0, 2.0, 180.0, 4.0, 1.0, 8.0, 5.0, 0.75, 0.50, 0.85, 5.0, 8.0, 8.0, 3.0, 2.0, 0.95]
    res_anom = detector.predict_one(extreme_anomaly)
    assert res_anom['anomaly_score'] >= 50.0
    assert any("dwell time" in ind.lower() or "off-hours" in ind.lower() or "loitering" in ind.lower()
               for ind in res_anom['indicators'])


def test_anomaly_detector_serialization(tmp_path):
    """Validates model saving and deserialization from disk."""
    detector = AnomalyDetector(contamination=0.10, n_estimators=30, random_state=42)
    X = np.random.normal(0, 1, size=(50, 19))
    detector.train(X)

    saved_paths = detector.save(tmp_path)
    assert (tmp_path / 'isolation_forest.joblib').exists()
    assert (tmp_path / 'scaler.joblib').exists()
    assert (tmp_path / 'model_metadata.json').exists()
    assert (tmp_path / 'baseline_statistics.json').exists()

    # Load into fresh detector
    new_detector = AnomalyDetector()
    success = new_detector.load(tmp_path)
    assert success is True
    assert new_detector.is_ready is True

    # Test prediction with loaded detector
    pred = new_detector.predict_one(X[0])
    assert 0.0 <= pred['anomaly_score'] <= 100.0


def test_ml_service_risk_fusion_and_degradation():
    """Validates weighted risk fusion formula and graceful degradation fallback."""
    service = MLService()

    # Case 1: Normal operational weights (0.70 rule, 0.30 ML)
    # 0.70 * 60 + 0.30 * 80 = 42 + 24 = 66.0 -> HIGH
    fused_score, risk_lvl = service.fuse_risk(
        rule_risk=60.0,
        ml_risk=80.0,
        rule_weight=0.70,
        ml_weight=0.30
    )
    assert fused_score == 66.0
    assert risk_lvl == 'HIGH'

    # Case 2: Critical event fusion
    # 0.70 * 85 + 0.30 * 90 = 59.5 + 27.0 = 86.5 -> CRITICAL
    fused_score, risk_lvl = service.fuse_risk(
        rule_risk=85.0,
        ml_risk=90.0,
        rule_weight=0.70,
        ml_weight=0.30
    )
    assert fused_score == 86.5
    assert risk_lvl == 'CRITICAL'

    # Case 3: Low threat event
    # 0.70 * 15 + 0.30 * 20 = 10.5 + 6.0 = 16.5 -> LOW
    fused_score, risk_lvl = service.fuse_risk(
        rule_risk=15.0,
        ml_risk=20.0,
        rule_weight=0.70,
        ml_weight=0.30
    )
    assert fused_score == 16.5
    assert risk_lvl == 'LOW'

    # Case 4: Graceful degradation when ML is offline or ml_risk is None
    prev_status = service.status
    service.status = 'UNAVAILABLE'
    fallback_score, fallback_lvl = service.fuse_risk(rule_risk=72.0, ml_risk=90.0)
    assert fallback_score == 72.0
    assert fallback_lvl == 'HIGH'
    service.status = prev_status


def test_ml_api_endpoints(client):
    """Validates REST API endpoints for ML subsystem."""
    # 1. GET /api/ml/status
    res = client.get('/api/ml/status')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'ml' in data
    assert 'status' in data['ml']
    assert data['ml']['feature_count'] == 19

    # 2. GET /api/ml/features
    res = client.get('/api/ml/features')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['feature_count'] == 19
    assert 'loitering_events' in data['features']
    assert 'time_in_restricted_zone' in data['descriptions']

    # 3. GET /api/ml/analysis/1
    res = client.get('/api/ml/analysis/1')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['camera_id'] == 1
    assert 'analysis' in data
    assert 'anomaly_score' in data['analysis']
    assert 'indicators' in data['analysis']

    # 4. GET /api/ml/analysis/999 (Non-existent camera)
    res = client.get('/api/ml/analysis/999')
    assert res.status_code == 404
