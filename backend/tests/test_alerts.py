import pytest
import time
from datetime import datetime, timezone, timedelta
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert, AlertHistory
from app.models.settings import SystemConfiguration
from app.services.alert_service import AlertService


@pytest.fixture(autouse=True)
def reset_alert_cooldowns():
    """Ensure in-memory cooldown cache is cleared before and after each test."""
    AlertService.reset_cooldowns()
    yield
    AlertService.reset_cooldowns()


def create_sample_camera_and_event(db_session, risk_score=80.0, risk_level="HIGH", event_type="restricted_area_intrusion"):
    """Helper to persist a camera and associated security event."""
    camera = Camera(
        name="ICU Entrance Cam",
        source="0",
        source_type="webcam",
        location="ICU Unit A",
        enabled=True
    )
    db_session.add(camera)
    db_session.commit()

    event = SecurityEvent(
        camera_id=camera.id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        confidence=0.92,
        risk_score=risk_score,
        risk_level=risk_level,
        description="Unauthorized movement detected inside sterile zone.",
        snapshot_path="/api/snapshots/sample_snap.jpg",
        event_metadata={
            "zone_id": "zone_icu_sterile",
            "zone_name": "ICU Sterile Corridor",
            "track_id": 4,
            "rule_risk_score": risk_score,
            "ml_risk_score": 75.0,
            "ml_anomalous": True,
            "ml_indicators": ["Speed anomaly (+2.4 sigma)"]
        }
    )
    db_session.add(event)
    db_session.commit()
    return camera, event


def test_alert_creation_from_security_event(db_session):
    """Test creating an Alert from a SecurityEvent via AlertService."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=88.0, risk_level="CRITICAL")

    alert = AlertService.create_alert_from_event(event)

    assert alert is not None
    assert alert.id is not None
    assert alert.event_id == event.id
    assert alert.camera_id == camera.id
    assert alert.severity == "CRITICAL"
    assert alert.status == "NEW"
    assert alert.snapshot_path == "/api/snapshots/sample_snap.jpg"
    assert "ICU Sterile Corridor" in alert.title
    assert alert.alert_metadata["final_risk_score"] == 88.0
    assert alert.alert_metadata["ml_anomalous"] is True

    # Check that initial AlertHistory was recorded
    history = AlertHistory.query.filter_by(alert_id=alert.id).all()
    assert len(history) == 1
    assert history[0].previous_status is None
    assert history[0].new_status == "NEW"
    assert "System" in history[0].operator


def test_alert_severity_determination():
    """Verify mapping of risk scores and levels to standard severities."""
    assert AlertService.determine_severity(90.0) == "CRITICAL"
    assert AlertService.determine_severity(70.0) == "HIGH"
    assert AlertService.determine_severity(50.0) == "MEDIUM"
    assert AlertService.determine_severity(25.0) == "LOW"
    assert AlertService.determine_severity(10.0, risk_level="CRITICAL") == "CRITICAL"
    assert AlertService.determine_severity(95.0, risk_level="LOW") == "LOW"


def test_alert_cooldown_deduplication(db_session):
    """Verify that identical events within the cooldown period are deduplicated/suppressed."""
    camera, event1 = create_sample_camera_and_event(db_session, risk_score=75.0, risk_level="HIGH")

    # First alert should succeed
    alert1 = AlertService.create_alert_from_event(event1)
    assert alert1 is not None

    # Immediate second event with identical (camera_id, event_type, zone_id, severity)
    event2 = SecurityEvent(
        camera_id=camera.id,
        event_type=event1.event_type,
        timestamp=datetime.now(timezone.utc),
        confidence=0.90,
        risk_score=75.0,
        risk_level="HIGH",
        description="Subsequent violation within 2 seconds",
        event_metadata=event1.event_metadata
    )
    db_session.add(event2)
    db_session.commit()

    alert2 = AlertService.create_alert_from_event(event2)
    assert alert2 is None  # Suppressed by cooldown deduplication


def test_alert_multi_tier_cooldown_duration(db_session):
    """Verify that different severities have independent cooldown configurations."""
    crit_cool = AlertService.get_cooldown_seconds("CRITICAL")
    high_cool = AlertService.get_cooldown_seconds("HIGH")
    med_cool = AlertService.get_cooldown_seconds("MEDIUM")
    low_cool = AlertService.get_cooldown_seconds("LOW")

    assert crit_cool == 15
    assert high_cool == 30
    assert med_cool == 60
    assert low_cool == 120
    assert crit_cool < high_cool < med_cool < low_cool


def test_alert_cooldown_reset(db_session):
    """Verify reset_cooldowns clears deduplication suppression immediately."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=80.0, risk_level="HIGH")

    alert1 = AlertService.create_alert_from_event(event)
    assert alert1 is not None

    # Reset cooldown cache
    AlertService.reset_cooldowns()

    # Create new event
    event2 = SecurityEvent(
        camera_id=camera.id,
        event_type=event.event_type,
        timestamp=datetime.now(timezone.utc),
        confidence=0.88,
        risk_score=80.0,
        risk_level="HIGH",
        description="Event after cooldown reset",
        event_metadata=event.event_metadata
    )
    db_session.add(event2)
    db_session.commit()

    alert2 = AlertService.create_alert_from_event(event2)
    assert alert2 is not None


def test_alert_lifecycle_new_to_acknowledged(db_session):
    """Test transition from NEW to ACKNOWLEDGED with operator and note."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)

    updated, err = AlertService.acknowledge_alert(alert.id, operator="Officer Smith", note="Notified guard team.")
    assert err is None
    assert updated.status == "ACKNOWLEDGED"
    assert updated.acknowledged_by == "Officer Smith"
    assert updated.acknowledged_at is not None
    assert "Officer Smith" in updated.notes

    # Check history log
    history = AlertHistory.query.filter_by(alert_id=alert.id).order_by(AlertHistory.id.asc()).all()
    assert len(history) == 2
    assert history[1].previous_status == "NEW"
    assert history[1].new_status == "ACKNOWLEDGED"
    assert history[1].operator == "Officer Smith"


def test_alert_lifecycle_acknowledged_to_investigating(db_session):
    """Test transition from ACKNOWLEDGED to INVESTIGATING."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)
    AlertService.acknowledge_alert(alert.id, operator="Operator A")

    updated, err = AlertService.investigate_alert(alert.id, operator="Sergeant Dave", note="Dispatching unit to Zone B.")
    assert err is None
    assert updated.status == "INVESTIGATING"
    assert updated.investigating_by == "Sergeant Dave"
    assert updated.investigating_at is not None

    history = AlertHistory.query.filter_by(alert_id=alert.id).all()
    assert len(history) == 3
    assert history[-1].new_status == "INVESTIGATING"


def test_alert_lifecycle_investigating_to_resolved(db_session):
    """Test transition from INVESTIGATING to RESOLVED."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)
    AlertService.acknowledge_alert(alert.id, operator="Op 1")
    AlertService.investigate_alert(alert.id, operator="Op 2")

    updated, err = AlertService.resolve_alert(alert.id, operator="Supervisor Jane", note="False alarm, authorized doctor badge verified.")
    assert err is None
    assert updated.status == "RESOLVED"
    assert updated.resolved_by == "Supervisor Jane"
    assert updated.resolved_at is not None

    history = AlertHistory.query.filter_by(alert_id=alert.id).all()
    assert len(history) == 4
    assert history[-1].new_status == "RESOLVED"
    assert "False alarm" in history[-1].note


def test_alert_lifecycle_direct_resolve(db_session):
    """Test direct transition from NEW to RESOLVED for minor incidents."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)

    updated, err = AlertService.resolve_alert(alert.id, operator="Officer Fast", note="Immediate resolution on scene.")
    assert err is None
    assert updated.status == "RESOLVED"
    assert updated.resolved_by == "Officer Fast"


def test_alert_lifecycle_invalid_transition(db_session):
    """Test that illegal transitions (e.g. RESOLVED to NEW) are rejected."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)
    AlertService.resolve_alert(alert.id, operator="Op")

    # Attempt illegal transition: RESOLVED -> NEW
    failed, err = AlertService.transition_alert(alert.id, "NEW", operator="Hacker")
    assert failed is None
    assert "Invalid transition" in err

    # Attempt illegal transition to unknown status
    failed2, err2 = AlertService.transition_alert(alert.id, "ARCHIVED")
    assert failed2 is None
    assert "Invalid transition" in err2


def test_alert_add_note_without_status_change(db_session):
    """Test appending an investigation note to an active alert without altering status."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)

    updated, err = AlertService.add_note(alert.id, operator="Guard Evans", note="Camera lens cleaned and re-aimed.")
    assert err is None
    assert updated.status == "NEW"
    assert "Guard Evans: Camera lens cleaned" in updated.notes

    history = AlertHistory.query.filter_by(alert_id=alert.id).all()
    assert len(history) == 2
    assert history[1].previous_status == "NEW"
    assert history[1].new_status == "NEW"
    assert history[1].note == "Camera lens cleaned and re-aimed."


def test_get_alerts_filtering(db_session):
    """Test filtering alerts by camera_id, severity, and status."""
    camera1, event1 = create_sample_camera_and_event(db_session, risk_score=90.0, risk_level="CRITICAL")
    alert1 = AlertService.create_alert_from_event(event1)

    AlertService.reset_cooldowns()

    camera2 = Camera(name="Pharmacy Cam", source="1", source_type="webcam", location="Pharmacy")
    db_session.add(camera2)
    db_session.commit()

    event2 = SecurityEvent(
        camera_id=camera2.id,
        event_type="after_hours_loitering",
        timestamp=datetime.now(timezone.utc),
        confidence=0.85,
        risk_score=70.0,
        risk_level="HIGH",
        description="After hours loitering near pharmacy safe.",
        event_metadata={"zone_id": "z_pharm"}
    )
    db_session.add(event2)
    db_session.commit()
    alert2 = AlertService.create_alert_from_event(event2)

    # Acknowledge alert 1
    AlertService.acknowledge_alert(alert1.id, operator="Op")

    # Filter by status: NEW
    new_alerts, total = AlertService.get_alerts(status="NEW")
    assert total == 1
    assert new_alerts[0].id == alert2.id

    # Filter by severity: CRITICAL
    crit_alerts, total_crit = AlertService.get_alerts(severity="CRITICAL")
    assert total_crit == 1
    assert crit_alerts[0].id == alert1.id

    # Filter by camera: camera2
    cam2_alerts, total_cam2 = AlertService.get_alerts(camera_id=camera2.id)
    assert total_cam2 == 1
    assert cam2_alerts[0].id == alert2.id


def test_alert_statistics_calculation(db_session):
    """Test aggregate metrics calculation in AlertService.get_statistics."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=95.0, risk_level="CRITICAL")
    alert = AlertService.create_alert_from_event(event)

    AlertService.reset_cooldowns()

    event2 = SecurityEvent(
        camera_id=camera.id,
        event_type="crowd_gathering",
        timestamp=datetime.now(timezone.utc),
        confidence=0.9,
        risk_score=70.0,
        risk_level="HIGH",
        description="Crowd gathering",
        event_metadata={"zone_id": "z2"}
    )
    db_session.add(event2)
    db_session.commit()
    alert2 = AlertService.create_alert_from_event(event2)

    # Resolve alert1 with a slight resolution time
    AlertService.resolve_alert(alert.id, operator="Tester", note="Incident resolved")
    alert_obj = db_session.get(Alert, alert.id)
    alert_obj.resolved_at = alert_obj.created_at + timedelta(minutes=5)
    db_session.commit()



    stats = AlertService.get_statistics()
    assert stats['total_alerts'] == 2
    assert stats['active_alerts'] == 1  # alert2 is NEW
    assert stats['status_counts']['RESOLVED'] == 1
    assert stats['status_counts']['NEW'] == 1
    assert stats['severity_counts']['CRITICAL'] == 1
    assert stats['severity_counts']['HIGH'] == 1
    assert stats['avg_resolution_seconds'] == 300.0


def test_api_alerts_triage_flow(client, db_session):
    """Test complete HTTP REST triage workflow: GET, Acknowledge, Investigate, Resolve, Notes."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=85.0, risk_level="HIGH")
    alert = AlertService.create_alert_from_event(event)

    # 1. GET /api/alerts/
    res = client.get('/api/alerts/')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['count'] >= 1

    # 2. GET /api/alerts/<id>
    res_det = client.get(f'/api/alerts/{alert.id}')
    assert res_det.status_code == 200
    detail = res_det.get_json()['alert']
    assert detail['id'] == alert.id
    assert 'history' in detail
    assert len(detail['history']) >= 1

    # 3. POST /api/alerts/<id>/acknowledge
    res_ack = client.post(f'/api/alerts/{alert.id}/acknowledge', json={
        'operator': 'Officer Daniels',
        'note': 'Acknowledged on dispatch monitor.'
    })
    assert res_ack.status_code == 200
    assert res_ack.get_json()['alert']['status'] == 'ACKNOWLEDGED'

    # 4. POST /api/alerts/<id>/investigate
    res_inv = client.post(f'/api/alerts/{alert.id}/investigate', json={
        'operator': 'Officer Daniels',
        'note': 'Arrived at ICU corridor.'
    })
    assert res_inv.status_code == 200
    assert res_inv.get_json()['alert']['status'] == 'INVESTIGATING'

    # 5. POST /api/alerts/<id>/notes
    res_note = client.post(f'/api/alerts/{alert.id}/notes', json={
        'operator': 'Officer Daniels',
        'note': 'Interviewed person, escorting to visitor desk.'
    })
    assert res_note.status_code == 200
    assert 'Interviewed person' in res_note.get_json()['alert']['notes']

    # 6. POST /api/alerts/<id>/resolve
    res_res = client.post(f'/api/alerts/{alert.id}/resolve', json={
        'operator': 'Officer Daniels',
        'note': 'Perimeter secured. Escort complete.'
    })
    assert res_res.status_code == 200
    assert res_res.get_json()['alert']['status'] == 'RESOLVED'

    # 7. GET /api/alerts/statistics
    res_stats = client.get('/api/alerts/statistics')
    assert res_stats.status_code == 200
    sdata = res_stats.get_json()
    assert sdata['success'] is True
    assert sdata['statistics']['total_alerts'] >= 1


def test_api_alerts_404_and_validation(client):
    """Test 404 response on non-existent alert and validation errors."""
    res = client.get('/api/alerts/99999')
    assert res.status_code == 404

    res_ack = client.post('/api/alerts/99999/acknowledge', json={'operator': 'Op'})
    assert res_ack.status_code == 404

    res_empty_note = client.post('/api/alerts/99999/notes', json={'note': ''})
    assert res_empty_note.status_code == 400


def test_api_create_manual_alert(client, db_session):
    """Test manual alert creation via POST /api/alerts/."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=60.0, risk_level="MEDIUM")

    res = client.post('/api/alerts/', json={
        'event_id': event.id,
        'severity': 'HIGH',
        'notes': 'Manual security supervisor alert escalation.',
        'operator': 'Chief Davis'
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert data['alert']['severity'] == 'HIGH'
    assert data['alert']['event_id'] == event.id


def test_alert_cascade_deletion(db_session):
    """Verify that deleting a SecurityEvent cascades and deletes the Alert and AlertHistory."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=85.0, risk_level="CRITICAL")
    alert = AlertService.create_alert_from_event(event)
    alert_id = alert.id

    assert db_session.get(Alert, alert_id) is not None
    assert AlertHistory.query.filter_by(alert_id=alert_id).count() >= 1

    # Delete the SecurityEvent
    db_session.delete(event)
    db_session.commit()

    # Verify Alert and AlertHistory were cleaned up
    assert db_session.get(Alert, alert_id) is None
    assert AlertHistory.query.filter_by(alert_id=alert_id).count() == 0


def test_alert_cooldown_expiration_allows_new_alert(db_session):
    """Verify that once the cooldown window elapses, a new alert is generated."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=80.0, risk_level="HIGH")
    alert1 = AlertService.create_alert_from_event(event)
    assert alert1 is not None

    key = (camera.id, str(event.event_type), "zone_icu_sterile", "HIGH")
    # Simulate time elapsed past 30s cooldown
    AlertService._cooldown_tracker[key] = time.time() - 40.0

    event2 = SecurityEvent(
        camera_id=camera.id,
        event_type=event.event_type,
        timestamp=datetime.now(timezone.utc),
        confidence=0.90,
        risk_score=80.0,
        risk_level="HIGH",
        description="Subsequent event after cooldown expiration",
        event_metadata=event.event_metadata
    )
    db_session.add(event2)
    db_session.commit()

    alert2 = AlertService.create_alert_from_event(event2)
    assert alert2 is not None
    assert alert2.id != alert1.id


def test_alert_custom_cooldown_configuration(db_session):
    """Verify custom cooldown values loaded from SystemConfiguration."""
    custom_cfg = SystemConfiguration(
        key="alert_cooldowns",
        value={"CRITICAL": 5, "HIGH": 8, "MEDIUM": 12, "LOW": 20},
        category="cooldown",
        description="Custom security cooldowns"
    )
    db_session.add(custom_cfg)
    db_session.commit()

    assert AlertService.get_cooldown_seconds("CRITICAL") == 5.0
    assert AlertService.get_cooldown_seconds("HIGH") == 8.0
    assert AlertService.get_cooldown_seconds("MEDIUM") == 12.0
    assert AlertService.get_cooldown_seconds("LOW") == 20.0


def test_alert_investigating_to_acknowledged_reassignment(db_session):
    """Test reassigning an alert under investigation back to acknowledged."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)

    AlertService.acknowledge_alert(alert.id, operator="Op 1")
    AlertService.investigate_alert(alert.id, operator="Op 2")

    # Reassignment: INVESTIGATING -> ACKNOWLEDGED
    reassigned, err = AlertService.transition_alert(alert.id, "ACKNOWLEDGED", operator="Supervisor", note="Reassigned to night shift.")
    assert err is None
    assert reassigned.status == "ACKNOWLEDGED"


def test_alert_patch_backward_compatibility(client, db_session):
    """Test backward compatibility of PATCH /api/alerts/<id> endpoint."""
    camera, event = create_sample_camera_and_event(db_session, risk_score=75.0, risk_level="HIGH")
    alert = AlertService.create_alert_from_event(event)

    res = client.patch(f'/api/alerts/{alert.id}', json={
        'status': 'ACKNOWLEDGED',
        'notes': 'Patched via legacy endpoint',
        'operator': 'Legacy Operator'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['alert']['status'] == 'ACKNOWLEDGED'
    assert 'Legacy Operator' in data['alert']['notes']


def test_alert_to_dict_include_history_flag(db_session):
    """Test Alert.to_dict serialization with and without full history audit logs."""
    camera, event = create_sample_camera_and_event(db_session)
    alert = AlertService.create_alert_from_event(event)
    AlertService.acknowledge_alert(alert.id, operator="Op")

    updated_alert = db_session.get(Alert, alert.id)
    db_session.refresh(updated_alert)
    dict_no_hist = updated_alert.to_dict(include_history=False)
    assert 'history' not in dict_no_hist

    dict_with_hist = updated_alert.to_dict(include_history=True)
    assert 'history' in dict_with_hist
    assert len(dict_with_hist['history']) == 2
    assert dict_with_hist['history'][0]['new_status'] == 'NEW'
    assert dict_with_hist['history'][1]['new_status'] == 'ACKNOWLEDGED'




