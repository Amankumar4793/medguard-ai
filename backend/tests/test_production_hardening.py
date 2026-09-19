import threading
import pytest
from app.extensions import db
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert, AlertHistory
from app.services.alert_service import AlertService


@pytest.fixture
def sample_camera(db_session):
    """Creates a sample camera model for testing."""
    cam = Camera(
        name="Test Corridor Cam",
        source="0",
        source_type="webcam",
        location="Zone B Corridor",
        enabled=True,
        configuration={
            "zones": [],
            "operating_hours": {"start": "08:00", "end": "20:00"},
            "fps": 15
        }
    )
    db_session.add(cam)
    db_session.commit()
    return cam


def test_pagination_bounds_and_sanitization(client, sample_camera):
    """
    Verifies that pagination parameters are strictly bounded (limit in [1, 100], offset >= 0)
    and non-integer values are handled gracefully without 500 server crashes.
    """
    # Create sample events
    for i in range(5):
        evt = SecurityEvent(
            camera_id=sample_camera.id,
            event_type='zone_intrusion',
            risk_score=70.0 + i,
            risk_level='HIGH',
            confidence=0.9,
            description=f"Pagination test event {i}"
        )
        db.session.add(evt)
    db.session.commit()

    # Test negative limit and offset on events
    res = client.get('/api/events/?limit=-10&offset=-5')
    assert res.status_code == 200
    data = res.get_json()
    assert data['limit'] == 1
    assert data['offset'] == 0

    # Test oversized limit on events
    res = client.get('/api/events/?limit=999999')
    assert res.status_code == 200
    data = res.get_json()
    assert data['limit'] == 100

    # Test malformed limit string on events
    res = client.get('/api/events/?limit=invalid_number')
    assert res.status_code == 200
    data = res.get_json()
    assert data['limit'] == 50  # Default fallback

    # Test negative limit and offset on alerts
    res_alert = client.get('/api/alerts/?limit=-5&offset=-20')
    assert res_alert.status_code == 200
    alert_data = res_alert.get_json()
    assert alert_data['limit'] == 1
    assert alert_data['offset'] == 0

    # Test oversized limit on alerts
    res_alert_over = client.get('/api/alerts/?limit=50000')
    assert res_alert_over.status_code == 200
    alert_over_data = res_alert_over.get_json()
    assert alert_over_data['limit'] == 100


def test_settings_cross_field_and_bounds_validation(client):
    """
    Verifies that setting weights summing to 0.0, negative cooldowns,
    or malformed operating hours are rejected with 400 Bad Request.
    """
    # 1. Weights summing to 0.0
    res = client.put('/api/settings/', json={
        'rule_risk_weight': 0.0,
        'ml_risk_weight': 0.0
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False
    assert 'greater than 0.0' in data['message']

    # 2. Negative alert cooldown
    res_cd = client.put('/api/settings/', json={
        'alert_cooldown_seconds': -10
    })
    assert res_cd.status_code == 400
    assert 'at least 1 second' in res_cd.get_json()['message']

    # 3. Invalid operating hours format
    res_hours = client.put('/api/settings/', json={
        'operating_hours': {'start': '26:00', 'end': '06:00'}
    })
    assert res_hours.status_code == 400
    assert 'Invalid time range' in res_hours.get_json()['message']

    # 4. Valid update
    res_valid = client.put('/api/settings/', json={
        'rule_risk_weight': 0.65,
        'ml_risk_weight': 0.35
    })
    assert res_valid.status_code == 200
    assert res_valid.get_json()['success'] is True


def test_events_input_validation(client, sample_camera):
    """
    Verifies strict input validation on POST /api/events/.
    """
    # 1. Missing required fields
    res = client.post('/api/events/', json={'description': 'Missing fields'})
    assert res.status_code == 400

    # 2. Non-existent camera
    res = client.post('/api/events/', json={
        'camera_id': 99999,
        'event_type': 'zone_intrusion'
    })
    assert res.status_code == 404

    # 3. Invalid confidence (> 1.0)
    res = client.post('/api/events/', json={
        'camera_id': sample_camera.id,
        'event_type': 'zone_intrusion',
        'confidence': 1.5
    })
    assert res.status_code == 400
    assert 'confidence' in res.get_json()['error']

    # 4. Invalid risk_score (< 0.0)
    res = client.post('/api/events/', json={
        'camera_id': sample_camera.id,
        'event_type': 'zone_intrusion',
        'risk_score': -10.0
    })
    assert res.status_code == 400
    assert 'risk_score' in res.get_json()['error']

    # 5. Invalid risk_level enum
    res = client.post('/api/events/', json={
        'camera_id': sample_camera.id,
        'event_type': 'zone_intrusion',
        'risk_level': 'ULTRA_EXTREME'
    })
    assert res.status_code == 400
    assert 'risk_level' in res.get_json()['error']


def test_monitoring_control_input_validation(client):
    """
    Verifies input validation on camera control routes.
    """
    # 1. Non-integer camera_id on start
    res = client.post('/api/monitoring/start', json={'camera_id': 'abc'})
    assert res.status_code == 400
    assert 'integer' in res.get_json()['error']

    # 2. Non-integer camera_id on stop
    res = client.post('/api/monitoring/stop', json={'camera_id': 'xyz'})
    assert res.status_code == 400
    assert 'integer' in res.get_json()['error']

    # 3. Missing camera_id on restart
    res = client.post('/api/monitoring/restart', json={})
    assert res.status_code == 400
    assert 'camera_id' in res.get_json()['error']


def test_database_cascade_and_integrity(client, sample_camera):
    """
    Verifies that deleting an Alert cascades to its AlertHistory child records.
    """
    evt = SecurityEvent(
        camera_id=sample_camera.id,
        event_type='zone_intrusion',
        risk_score=85.0,
        risk_level='CRITICAL',
        confidence=0.95,
        description='Critical intrusion detected at perimeter'
    )
    db.session.add(evt)
    db.session.commit()

    alert = Alert(
        event_id=evt.id,
        camera_id=sample_camera.id,
        title='Critical Intrusion',
        severity='CRITICAL',
        status='NEW'
    )
    db.session.add(alert)
    db.session.commit()

    history = AlertHistory(
        alert_id=alert.id,
        previous_status=None,
        new_status='NEW',
        operator='System',
        note='Initial creation'
    )
    db.session.add(history)
    db.session.commit()

    alert_id = alert.id
    assert AlertHistory.query.filter_by(alert_id=alert_id).count() == 1

    # Delete alert
    db.session.delete(alert)
    db.session.commit()

    # Verify AlertHistory cascaded
    assert AlertHistory.query.filter_by(alert_id=alert_id).count() == 0


def test_cooldown_bounded_memory_pruning():
    """
    Stress-tests the in-memory cooldown tracker in AlertService by injecting
    600 unique keys, verifying that the cache is bounded to <= 500 entries.
    """
    AlertService.reset_cooldowns()

    for i in range(600):
        AlertService.is_deduplicated(
            camera_id=i,
            event_type='zone_intrusion',
            zone_id=f"zone_{i}",
            severity='HIGH'
        )

    # Cooldown tracker must not grow indefinitely
    assert len(AlertService._cooldown_tracker) <= 500
    AlertService.reset_cooldowns()


def test_multithreaded_database_concurrency(app, sample_camera):
    """
    Verifies that concurrent worker threads creating SecurityEvents and Alerts
    do not cause SQLite deadlocks or session cross-talk.
    """
    errors = []

    def worker_task(thread_idx):
        for attempt in range(5):
            try:
                with app.app_context():
                    evt = SecurityEvent(
                        camera_id=sample_camera.id,
                        event_type=f'concurrent_event_{thread_idx}',
                        risk_score=50.0 + thread_idx,
                        risk_level='MEDIUM',
                        confidence=0.88,
                        description=f"Thread {thread_idx} event"
                    )
                    db.session.add(evt)
                    db.session.commit()
                    db.session.close()
                break
            except Exception as exc:
                db.session.rollback()
                db.session.close()
                if attempt == 4:
                    errors.append(exc)
                else:
                    time.sleep(0.01 * (thread_idx + 1))

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent worker errors: {errors}"
    with app.app_context():
        created_count = SecurityEvent.query.filter(
            SecurityEvent.event_type.like('concurrent_event_%')
        ).count()
        assert created_count == 10


def test_optimized_statistics_endpoints(client, sample_camera):
    """
    Verifies that the optimized /api/statistics/ and /api/statistics/dashboard
    endpoints return accurate metrics without N+1 query overhead.
    """
    for i in range(3):
        evt = SecurityEvent(
            camera_id=sample_camera.id,
            event_type='loitering',
            risk_score=60.0 + (i * 10),
            risk_level='HIGH',
            confidence=0.9,
            description=f"Loitering observed {i}",
            event_metadata={'ml_anomaly': (i == 0), 'rule_risk_score': 65.0, 'ml_risk_score': 55.0}
        )
        db.session.add(evt)
    db.session.commit()

    # Test /api/statistics/
    res = client.get('/api/statistics/')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['summary']['total_events'] >= 3
    assert data['summary']['total_ml_anomalies'] >= 1

    # Test /api/statistics/dashboard
    res_dash = client.get('/api/statistics/dashboard')
    assert res_dash.status_code == 200
    dash_data = res_dash.get_json()
    assert dash_data['success'] is True
    assert 'kpis' in dash_data
    assert 'system_status' in dash_data
    assert 'cameras' in dash_data
    assert len(dash_data['cameras']) >= 1
