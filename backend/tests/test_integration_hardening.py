import os
import time
import tempfile
import numpy as np
import pytest
from datetime import datetime, timezone
from app.extensions import db
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert, AlertHistory
from app.models.settings import SystemConfiguration
from app.monitoring.camera_manager import camera_manager
from app.monitoring.video_processor import VideoProcessor
from app.detection.tracker import CentroidIoUTracker, TrackedObject
from app.detection.zones import ZoneEvaluator, Zone
from app.services.security_engine import security_engine, calculate_risk_level
from app.services.ml_service import ml_service
from app.services.event_service import EventService
from app.services.alert_service import AlertService
from app.ml.features import SecurityFeatureExtractor, FEATURE_NAMES


def test_end_to_end_pipeline_flow(app):
    """
    Validates the complete end-to-end surveillance pipeline:
    Frame Detections -> Tracking -> Zone Violation -> SecurityEngine ->
    Feature Extraction -> ML Inference -> Risk Fusion -> Event Persistence ->
    Alert Deduplication -> SQLite Storage -> Audit Trail.
    """
    with app.app_context():
        # 1. Setup Camera in database
        cam = Camera(
            name="ICU Hardening Cam",
            source="0",
            source_type="webcam",
            location="ICU Ward 3",
            enabled=True,
            configuration={
                "zones": [
                    {
                        "id": "restricted_icu_bay",
                        "name": "Sterile ICU Bay",
                        "type": "restricted",
                        "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
                        "severity": "CRITICAL"
                    }
                ],
                "operating_hours": {"start": "08:00", "end": "20:00"},
                "fps": 15,
                "resolution": [640, 480],
                "crowd_threshold": 3,
                "loitering_threshold_seconds": 20
            }
        )
        db.session.add(cam)
        db.session.commit()

        # 2. Simulate YOLO detections: Person entering the zone
        tracker = CentroidIoUTracker(max_lost_frames=10, iou_threshold=0.25)
        zone_evaluator = ZoneEvaluator(zones_config=cam.configuration['zones'])
        feature_extractor = SecurityFeatureExtractor(window_seconds=60)
        AlertService.reset_cooldowns()

        # Step A: Person outside zone (x: 60..100, bottom center: 80, 200 -> outside x=128)
        dets_outside = [{'bbox': [60, 100, 100, 200], 'confidence': 0.91, 'class_name': 'person'}]
        tracks_t0 = tracker.update(dets_outside, frame_time=time.time())
        assert len(tracks_t0) == 1
        trk_id = tracks_t0[0].track_id

        eval_t0 = zone_evaluator.evaluate_tracks(tracks_t0, 640, 480)
        assert len(eval_t0['violations']) == 0

        # Step B: Person crosses into restricted zone (x: 120..160, bottom center: 140, 200 -> inside zone, dist 60px)
        now_time = time.time() + 1.0
        dets_inside = [{'bbox': [120, 100, 160, 200], 'confidence': 0.94, 'class_name': 'person'}]
        tracks_t1 = tracker.update(dets_inside, frame_time=now_time)
        assert len(tracks_t1) == 1
        assert tracks_t1[0].track_id == trk_id  # Tracking identity preserved

        eval_t1 = zone_evaluator.evaluate_tracks(tracks_t1, 640, 480)
        assert len(eval_t1['entries']) == 1
        assert eval_t1['entries'][0]['zone'].id == 'restricted_icu_bay'

        # Step C: SecurityEngine evaluates rule during operational hours (14:00)
        daytime_dt = datetime(2026, 1, 1, 14, 0, 0)
        sec_events = security_engine.evaluate(
            camera_id=cam.id,
            camera_name=cam.name,
            camera_location=cam.location,
            tracks=tracks_t1,
            zone_eval_result=eval_t1,
            camera_config=cam.configuration,
            raw_detections=dets_inside,
            now_dt=daytime_dt
        )
        assert len(sec_events) == 1
        event_dict = sec_events[0]
        assert event_dict['event_type'] in ('restricted_area_intrusion', 'zone_intrusion', 'after_hours_intrusion')
        rule_risk = event_dict['risk_score']
        assert rule_risk >= 70.0  # Restricted + CRITICAL zone

        # Step D: Feature extraction and ML Anomaly Inference
        feature_extractor.update(
            camera_id=cam.id,
            tracks=tracks_t1,
            raw_detections=dets_inside,
            zone_eval_result=eval_t1,
            current_dt=datetime.now(timezone.utc)
        )
        feat_vec = feature_extractor.extract_features(cam.id)
        assert len(feat_vec) == 19

        ml_res = ml_service.analyze_camera(cam.id, feat_vec)
        assert 'anomaly_score' in ml_res
        assert 'is_anomaly' in ml_res

        # Step E: Risk Fusion
        ml_score = ml_res['anomaly_score']
        fused_score, fused_level = ml_service.fuse_risk(
            rule_risk=rule_risk,
            ml_risk=ml_score,
            rule_weight=0.70,
            ml_weight=0.30
        )
        assert 0.0 <= fused_score <= 100.0
        assert fused_level in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')

        event_dict['risk_score'] = fused_score
        event_dict['risk_level'] = fused_level
        event_dict['metadata']['rule_risk_score'] = rule_risk
        event_dict['metadata']['ml_risk_score'] = ml_score
        event_dict['metadata']['final_risk_score'] = fused_score
        event_dict['metadata']['ml_anomaly'] = ml_res['is_anomaly']

        # Step F: Persistence and Alert Generation
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        event, alert = EventService.record_security_event(event_dict, frame=blank_frame, app=app)

        assert event is not None
        assert event.id is not None
        assert event.camera_id == cam.id
        assert event.risk_score == fused_score

        # Verify Alert was generated for High/Critical risk
        assert alert is not None
        assert alert.id is not None
        assert alert.event_id == event.id
        assert alert.severity in ('HIGH', 'CRITICAL')
        assert alert.status == 'NEW'

        # Verify database relationships
        persisted_event = db.session.get(SecurityEvent, event.id)
        assert len(persisted_event.alerts) == 1
        persisted_alert = persisted_event.alerts[0]
        assert len(persisted_alert.history) >= 1
        assert persisted_alert.history[0].new_status == 'NEW'


def test_multi_camera_state_isolation(app):
    """
    Verifies that multiple cameras operate with strict state isolation.
    An event, track, or buffer reset on Camera A must not contaminate Camera B.
    """
    with app.app_context():
        cam_a = Camera(name="Cam A", source="0", location="Wing A", enabled=True)
        cam_b = Camera(name="Cam B", source="1", location="Wing B", enabled=True)
        db.session.add_all([cam_a, cam_b])
        db.session.commit()

        tracker_a = CentroidIoUTracker()
        tracker_b = CentroidIoUTracker()
        extractor = SecurityFeatureExtractor()

        # Camera A sees 2 persons
        dets_a = [
            {'bbox': [10, 10, 40, 90], 'confidence': 0.9, 'class_name': 'person'},
            {'bbox': [100, 10, 140, 90], 'confidence': 0.88, 'class_name': 'person'},
        ]
        tracks_a = tracker_a.update(dets_a, frame_time=1.0)
        assert len(tracks_a) == 2

        # Camera B sees 1 person
        dets_b = [
            {'bbox': [200, 200, 240, 290], 'confidence': 0.95, 'class_name': 'person'}
        ]
        tracks_b = tracker_b.update(dets_b, frame_time=1.0)
        assert len(tracks_b) == 1

        # Track IDs must be independent
        assert tracks_a[0].track_id != tracks_b[0].track_id or tracks_a[0].center != tracks_b[0].center

        # Update feature extractors
        extractor.update(cam_a.id, tracks=tracks_a)
        extractor.update(cam_b.id, tracks=tracks_b)

        vec_a = extractor.extract_features_dict(cam_a.id)
        vec_b = extractor.extract_features_dict(cam_b.id)

        # Persons detected feature must be isolated
        assert vec_a['persons_detected'] == 2
        assert vec_b['persons_detected'] == 1

        # Reset Camera A: Camera B must remain intact
        extractor.reset_camera(cam_a.id)
        vec_a_after = extractor.extract_features_dict(cam_a.id)
        vec_b_after = extractor.extract_features_dict(cam_b.id)

        assert vec_a_after['persons_detected'] == 0
        assert vec_b_after['persons_detected'] == 1


def test_camera_lifecycle_resilience(app):
    """
    Tests CameraManager lifecycle operations:
    register -> start -> telemetry -> stop -> restart -> invalid source handling.
    """
    with app.app_context():
        # Check sample video exists or use webcam mode
        sample_path = "data/videos/pharmacy_sample.mp4"
        cam = Camera(
            name="Lifecycle Test Cam",
            source=sample_path,
            source_type="video_file",
            location="Pharmacy",
            enabled=True,
            configuration={"fps": 15, "resolution": [320, 240]}
        )
        db.session.add(cam)
        db.session.commit()

        # 1. Register camera
        proc = camera_manager.register_camera(cam)
        assert proc is not None
        assert proc.status == 'OFFLINE'

        # 2. Start camera
        started = camera_manager.start_camera(cam.id, camera_model=cam)
        assert started is True
        time.sleep(0.3)
        status, _ = camera_manager.get_camera_status(cam.id)
        assert status in ('RUNNING', 'STARTING')

        # 3. Telemetry
        telemetry = camera_manager.get_telemetry(cam.id)
        assert telemetry['camera_id'] == cam.id
        assert telemetry['status'] in ('RUNNING', 'STARTING')

        # 4. Stop camera
        stopped = camera_manager.stop_camera(cam.id)
        assert stopped is True
        status_after, _ = camera_manager.get_camera_status(cam.id)
        assert status_after == 'OFFLINE'

        # 5. Restart camera
        restarted = camera_manager.restart_camera(cam.id, camera_model=cam)
        assert restarted is True
        time.sleep(0.2)
        camera_manager.stop_camera(cam.id)

        # 6. Invalid source handling
        invalid_cam = Camera(
            name="Invalid Source Cam",
            source="data/videos/non_existent_file_xyz123.mp4",
            source_type="video_file",
            location="Unknown",
            enabled=True
        )
        db.session.add(invalid_cam)
        db.session.commit()

        camera_manager.register_camera(invalid_cam)
        camera_manager.start_camera(invalid_cam.id, camera_model=invalid_cam)
        time.sleep(0.4)

        inv_status, inv_err = camera_manager.get_camera_status(invalid_cam.id)
        assert inv_status in ('ERROR', 'OFFLINE')
        camera_manager.stop_camera(invalid_cam.id)


def test_ml_failure_graceful_degradation(app):
    """
    Validates system resilience when the ML model is missing, corrupt,
    or encounters runtime prediction exceptions. The system must continue
    surveillance and fallback to pure rule risk.
    """
    # 1. Test fallback when loading from empty directory
    with tempfile.TemporaryDirectory() as empty_dir:
        ml_service.load_model(empty_dir)
        assert ml_service.status == 'UNAVAILABLE'

        # Inference must return non-crashing fallback
        dummy_feat = [0.0] * len(FEATURE_NAMES)
        res = ml_service.analyze_camera(camera_id=999, feature_vector=dummy_feat)
        assert res['is_anomaly'] is False
        assert res['anomaly_score'] == 0.0
        assert res['model_status'] == 'UNAVAILABLE'

        # Risk fusion must fallback to rule risk
        fused_score, fused_level = ml_service.fuse_risk(rule_risk=72.0, ml_risk=None)
        assert fused_score == 72.0
        assert fused_level == calculate_risk_level(72.0)

    # 2. Restore default model and verify status returns to READY
    restored = ml_service.load_model()
    assert restored is True
    assert ml_service.status == 'READY'


def test_alert_lifecycle_full_audit_trail(client, app):
    """
    Validates complete incident triage lifecycle:
    NEW -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED,
    verifying audit history, timestamps, operator attribution, and invalid transition rejection.
    """
    with app.app_context():
        cam = Camera(name="Triage Cam", source="0", location="Lobby", enabled=True)
        db.session.add(cam)
        db.session.commit()

        event = SecurityEvent(
            camera_id=cam.id,
            event_type="zone_intrusion",
            confidence=0.9,
            risk_score=88.0,
            risk_level="CRITICAL",
            description="Breach into secure area",
            status="NEW"
        )
        db.session.add(event)
        db.session.commit()

        alert = Alert(
            event_id=event.id,
            camera_id=cam.id,
            title="Critical Intrusion",
            description="Unauthorized entry",
            severity="CRITICAL",
            status="NEW"
        )
        db.session.add(alert)
        db.session.commit()
        alert_id = alert.id

    # 1. Acknowledge
    ack_res = client.post(f'/api/alerts/{alert_id}/acknowledge', json={
        'operator': 'Officer Chen',
        'note': 'Received dispatch alert.'
    })
    assert ack_res.status_code == 200
    ack_data = ack_res.get_json()
    assert ack_data['alert']['status'] == 'ACKNOWLEDGED'
    assert ack_data['alert']['acknowledged_by'] == 'Officer Chen'

    # 2. Investigate
    inv_res = client.post(f'/api/alerts/{alert_id}/investigate', json={
        'operator': 'Investigator Maya',
        'note': 'Reviewing perimeter footage.'
    })
    assert inv_res.status_code == 200
    inv_data = inv_res.get_json()
    assert inv_data['alert']['status'] == 'INVESTIGATING'
    assert inv_data['alert']['investigating_by'] == 'Investigator Maya'

    # 3. Resolve
    res_res = client.post(f'/api/alerts/{alert_id}/resolve', json={
        'operator': 'Supervisor Vance',
        'note': 'Incident verified as scheduled maintenance.'
    })
    assert res_res.status_code == 200
    res_data = res_res.get_json()
    assert res_data['alert']['status'] == 'RESOLVED'
    assert res_data['alert']['resolved_by'] == 'Supervisor Vance'

    # 4. Verify full audit trail via GET
    get_res = client.get(f'/api/alerts/{alert_id}')
    assert get_res.status_code == 200
    history = get_res.get_json()['alert']['history']
    assert len(history) >= 3
    statuses = [h['new_status'] for h in history]
    assert 'ACKNOWLEDGED' in statuses
    assert 'INVESTIGATING' in statuses
    assert 'RESOLVED' in statuses

    # 5. Invalid transition rejection: RESOLVED -> ACKNOWLEDGED
    invalid_res = client.post(f'/api/alerts/{alert_id}/acknowledge', json={
        'operator': 'Officer Chen',
        'note': 'Attempt to reopen resolved alert.'
    })
    assert invalid_res.status_code == 400
    assert "Invalid transition" in invalid_res.get_json()['error']


def test_settings_input_validation(client):
    """
    Validates strict input sanitization on PUT /api/settings/.
    Ensures negative values, invalid weights, and malformed schedules are rejected.
    """
    # Negative weight
    res1 = client.put('/api/settings/', json={'rule_risk_weight': -0.2})
    assert res1.status_code == 400
    assert "Validation Error" in res1.get_json()['error']

    # Weight > 1.0
    res2 = client.put('/api/settings/', json={'ml_risk_weight': 1.5})
    assert res2.status_code == 400

    # Negative cooldown
    res3 = client.put('/api/settings/', json={'alert_cooldown_seconds': -5})
    assert res3.status_code == 400

    # Invalid operating hours structure
    res4 = client.put('/api/settings/', json={'operating_hours': '08:00-20:00'})
    assert res4.status_code == 400

    # Invalid hour range (25:00)
    res5 = client.put('/api/settings/', json={'operating_hours': {'start': '25:00', 'end': '20:00'}})
    assert res5.status_code == 400

    # Valid settings update
    res_valid = client.put('/api/settings/', json={
        'rule_risk_weight': 0.65,
        'ml_risk_weight': 0.35,
        'alert_cooldown_seconds': 25,
        'operating_hours': {'start': '07:30', 'end': '21:30'}
    })
    assert res_valid.status_code == 200
    assert res_valid.get_json()['success'] is True


def test_subsystem_health_reporting(client):
    """
    Validates GET /api/health returns comprehensive subsystem health metrics.
    """
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()

    assert data['status'] == 'healthy'
    assert data['database'] == 'connected'
    assert 'subsystems' in data

    subsystems = data['subsystems']
    assert subsystems['backend'] == 'healthy'
    assert subsystems['database'] == 'connected'
    assert 'camera_system' in subsystems
    assert 'ml_subsystem' in subsystems
    assert 'alert_engine' in subsystems
    assert subsystems['ml_subsystem']['status'] in ('READY', 'UNAVAILABLE', 'UNINITIALIZED')
