from datetime import datetime, timezone
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert
from app.models.settings import SystemConfiguration


def test_camera_model_creation_and_dict(db_session):
    """Test Camera model creation, defaults, and dictionary export."""
    camera = Camera(
        name="Test ICU Camera",
        source="0",
        source_type="webcam",
        location="ICU Ward",
        enabled=True,
        configuration={"zones": [{"id": "z1", "name": "Sterile Zone"}]}
    )
    db_session.add(camera)
    db_session.commit()

    assert camera.id is not None
    data = camera.to_dict()
    assert data['name'] == "Test ICU Camera"
    assert data['location'] == "ICU Ward"
    assert data['configuration']['zones'][0]['name'] == "Sterile Zone"
    assert data['enabled'] is True


def test_security_event_and_alert_relationship(db_session):
    """Test SecurityEvent creation, Alert foreign key, and cascade."""
    camera = Camera(
        name="Pharmacy Cam",
        source="data/videos/test.mp4",
        source_type="video_file",
        location="Pharmacy"
    )
    db_session.add(camera)
    db_session.commit()

    event = SecurityEvent(
        camera_id=camera.id,
        event_type="restricted_area_intrusion",
        timestamp=datetime.now(timezone.utc),
        confidence=0.91,
        risk_score=85.0,
        risk_level="HIGH",
        description="Unauthorized entry into pharmacy vault",
        event_metadata={"bbox": [10, 20, 100, 200]}
    )
    db_session.add(event)
    db_session.commit()

    assert event.id is not None
    assert event.camera.name == "Pharmacy Cam"

    # Create associated Alert
    alert = Alert(
        event_id=event.id,
        severity="HIGH",
        status="NEW",
        notes="High alert triggered"
    )
    db_session.add(alert)
    db_session.commit()

    assert alert.id is not None
    assert alert.event.id == event.id
    assert alert.to_dict()['severity'] == "HIGH"
    assert event.to_dict()['has_alert'] is True


def test_system_configuration_model(db_session):
    """Test SystemConfiguration model key-value persistence."""
    setting = SystemConfiguration(
        key="test_operating_hours",
        value={"start": "09:00", "end": "18:00"},
        category="hours",
        description="Operational test hours"
    )
    db_session.add(setting)
    db_session.commit()

    found = SystemConfiguration.query.filter_by(key="test_operating_hours").first()
    assert found is not None
    assert found.value['start'] == "09:00"
    assert found.to_dict()['category'] == "hours"
