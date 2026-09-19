import os
import time
from datetime import datetime, timezone
import numpy as np
import pytest
from app import create_app
from app.extensions import db
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert
from app.detection.tracker import TrackedObject
from app.detection.zones import Zone, ZoneEvaluator
from app.services.security_engine import SecurityEngine, is_time_after_hours, calculate_risk_level
from app.services.event_service import EventService
from app.monitoring import camera_manager


@pytest.fixture
def test_app():
    app = create_app('testing')
    app.config['SNAPSHOT_DIR'] = 'data/test_snapshots'
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_after_hours_schedule_logic():
    # Day operational hours: 08:00 to 20:00
    day_cfg = {'start': '08:00', 'end': '20:00'}
    dt_day = datetime(2026, 9, 18, 14, 30)  # 2:30 PM (inside)
    dt_night = datetime(2026, 9, 18, 22, 15)  # 10:15 PM (outside)
    dt_morning = datetime(2026, 9, 18, 6, 45)  # 6:45 AM (outside)

    assert is_time_after_hours(dt_day, day_cfg) is False
    assert is_time_after_hours(dt_night, day_cfg) is True
    assert is_time_after_hours(dt_morning, day_cfg) is True

    # Overnight operational hours: 21:00 to 06:00
    night_cfg = {'start': '21:00', 'end': '06:00'}
    assert is_time_after_hours(datetime(2026, 9, 18, 23, 0), night_cfg) is False
    assert is_time_after_hours(datetime(2026, 9, 18, 3, 0), night_cfg) is False
    assert is_time_after_hours(datetime(2026, 9, 18, 12, 0), night_cfg) is True


def test_calculate_risk_level():
    assert calculate_risk_level(85.0) == 'CRITICAL'
    assert calculate_risk_level(65.0) == 'HIGH'
    assert calculate_risk_level(35.0) == 'MEDIUM'
    assert calculate_risk_level(15.0) == 'LOW'


def test_zone_intrusion_rule_evaluation():
    engine = SecurityEngine(default_cooldown=10)
    zone = Zone({
        'id': 'zone_icu',
        'name': 'ICU Sterile Zone',
        'type': 'restricted',
        'severity': 'HIGH'
    })
    track = TrackedObject(track_id=1, class_name="person", confidence=0.92, bbox=[100, 100, 200, 300])

    zone_eval = {
        'entries': [{'track': track, 'zone': zone}],
        'exits': [],
        'occupancy': {'zone_icu': [track]},
        'violations': [{'track': track, 'zone': zone}]
    }
    cfg = {'operating_hours': {'start': '08:00', 'end': '20:00'}}
    now_dt = datetime(2026, 9, 18, 11, 0)  # Daytime

    events = engine.evaluate(
        camera_id=1,
        camera_name="CAM-01",
        camera_location="ICU Wing",
        tracks=[track],
        zone_eval_result=zone_eval,
        camera_config=cfg,
        now_dt=now_dt
    )

    assert len(events) == 1
    ev = events[0]
    assert ev['event_type'] == 'restricted_area_intrusion'
    assert ev['risk_level'] in ('HIGH', 'CRITICAL')
    assert ev['risk_score'] >= 60.0
    assert 'ICU Sterile Zone' in ev['description']

    # Immediate second evaluation on same track must be suppressed by cooldown
    events2 = engine.evaluate(
        camera_id=1,
        camera_name="CAM-01",
        camera_location="ICU Wing",
        tracks=[track],
        zone_eval_result=zone_eval,
        camera_config=cfg,
        now_dt=now_dt
    )
    assert len(events2) == 0


def test_after_hours_intrusion_rule():
    engine = SecurityEngine(default_cooldown=10)
    zone = Zone({
        'id': 'zone_pharma',
        'name': 'Pharmacy Storage',
        'type': 'restricted',
        'severity': 'CRITICAL'
    })
    track = TrackedObject(track_id=2, class_name="person", confidence=0.95, bbox=[100, 100, 200, 300])

    zone_eval = {
        'entries': [{'track': track, 'zone': zone}],
        'exits': [],
        'occupancy': {'zone_pharma': [track]},
        'violations': [{'track': track, 'zone': zone}]
    }
    cfg = {'operating_hours': {'start': '08:00', 'end': '18:00'}}
    now_night = datetime(2026, 9, 18, 23, 30)  # 11:30 PM (After-Hours)

    events = engine.evaluate(
        camera_id=2,
        camera_name="CAM-02",
        camera_location="Pharmacy",
        tracks=[track],
        zone_eval_result=zone_eval,
        camera_config=cfg,
        now_dt=now_night
    )

    assert len(events) == 1
    ev = events[0]
    assert ev['event_type'] == 'after_hours_intrusion'
    assert ev['risk_level'] == 'CRITICAL'
    assert 'AFTER-HOURS' in ev['description']


def test_loitering_rule_evaluation():
    engine = SecurityEngine(default_cooldown=10)
    track = TrackedObject(track_id=3, class_name="person", confidence=0.88, bbox=[150, 150, 250, 350])
    track.set_zone('zone_lab', 'Biosafety Lab', timestamp=time.time() - 35.0)  # In zone for 35 seconds

    zone_eval = {
        'entries': [],
        'exits': [],
        'occupancy': {'zone_lab': [track]},
        'violations': []
    }
    cfg = {'loitering_threshold_seconds': 20}  # Limit 20s

    events = engine.evaluate(
        camera_id=4,
        camera_name="CAM-04",
        camera_location="Lab",
        tracks=[track],
        zone_eval_result=zone_eval,
        camera_config=cfg
    )

    assert len(events) == 1
    ev = events[0]
    assert ev['event_type'] == 'loitering'
    assert track.is_loitering is True
    assert ev['metadata']['duration_seconds'] >= 35.0


def test_crowd_density_rule():
    engine = SecurityEngine(default_cooldown=5)
    tracks = [
        TrackedObject(track_id=i, class_name="person", confidence=0.85, bbox=[100, 100, 150, 200])
        for i in range(1, 6)
    ]
    for t in tracks:
        t.set_zone('zone_triage', 'Triage Bay')

    zone_eval = {
        'entries': [],
        'exits': [],
        'occupancy': {'zone_triage': tracks},
        'violations': []
    }
    cfg = {'crowd_threshold': 4, 'crowd_duration_seconds': 0}  # Immediate threshold

    events = engine.evaluate(
        camera_id=3,
        camera_name="CAM-03",
        camera_location="Emergency",
        tracks=tracks,
        zone_eval_result=zone_eval,
        camera_config=cfg
    )

    assert len(events) == 1
    assert events[0]['event_type'] == 'crowd_density'
    assert events[0]['metadata']['occupant_count'] == 5


def test_event_service_and_snapshot_persistence(test_app):
    frame = np.full((480, 640, 3), 120, dtype=np.uint8)
    event_payload = {
        'camera_id': 1,
        'camera_name': 'ICU Corridor',
        'camera_location': 'Building A - Floor 2',
        'event_type': 'restricted_area_intrusion',
        'risk_score': 82.5,
        'risk_level': 'CRITICAL',
        'confidence': 0.94,
        'description': 'Breach detected in restricted zone.',
        'metadata': {'track_id': 9, 'zone_name': 'ICU Airlock'}
    }

    event, alert = EventService.record_security_event(event_payload, frame=frame, app=test_app)

    assert event is not None
    assert event.id is not None
    assert event.risk_level == 'CRITICAL'
    assert event.snapshot_path is not None
    assert event.snapshot_path.startswith('/api/snapshots/')

    # High/Critical events automatically generate Alert
    assert alert is not None
    assert alert.event_id == event.id
    assert alert.severity == 'CRITICAL'


def test_monitoring_tracks_and_zones_api_endpoints(test_app):
    client = test_app.test_client()

    # Create camera in test DB
    cam = Camera(
        name="Test Camera",
        source="0",
        source_type="webcam",
        location="Corridor",
        enabled=True,
        configuration={
            "zones": [
                {
                    "id": "z1",
                    "name": "Sterile Area",
                    "type": "restricted",
                    "severity": "HIGH",
                    "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
                }
            ]
        }
    )
    with test_app.app_context():
        db.session.add(cam)
        db.session.commit()
        cam_id = cam.id

    # Query tracks endpoint
    res_tracks = client.get(f'/api/monitoring/tracks/{cam_id}')
    assert res_tracks.status_code == 200
    json_tracks = res_tracks.get_json()
    assert json_tracks['success'] is True
    assert 'tracks' in json_tracks

    # Query zones endpoint
    res_zones = client.get(f'/api/monitoring/zones/{cam_id}')
    assert res_zones.status_code == 200
    json_zones = res_zones.get_json()
    assert json_zones['success'] is True
    assert 'zones' in json_zones
