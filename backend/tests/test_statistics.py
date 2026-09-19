import json
from datetime import datetime, timezone, timedelta
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert
from app.extensions import db


def test_dashboard_statistics_empty(client, db_session):
    """Test /api/statistics/dashboard returns valid KPIs when database is empty."""
    res = client.get('/api/statistics/dashboard')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['success'] is True
    assert 'kpis' in data
    assert 'system_status' in data
    assert 'cameras' in data
    assert 'active_alerts_list' in data
    assert 'recent_events' in data

    kpis = data['kpis']
    assert kpis['active_alerts'] == 0
    assert kpis['critical_alerts'] == 0
    assert kpis['high_alerts'] == 0
    assert kpis['investigating'] == 0
    assert kpis['cameras_online'] == 0
    assert kpis['cameras_offline'] == 0
    assert kpis['ml_anomalies'] == 0
    assert kpis['events_today'] == 0

    status = data['system_status']
    assert status['backend'] == 'ONLINE'
    assert status['socketio'] == 'CONNECTED'
    assert status['alert_engine'] == 'ONLINE'


def test_dashboard_statistics_with_data(client, db_session):
    """Test /api/statistics/dashboard calculates accurate KPIs with populated entities."""
    # 1. Create camera
    cam = Camera(
        name='ICU Corridor Unit 1',
        source='0',
        source_type='webcam',
        location='ICU Ward B',
        enabled=True,
        configuration={'zones': [{'id': 'z1', 'name': 'Entry Zone'}]}
    )
    db_session.add(cam)
    db_session.commit()

    # 2. Create security events
    now = datetime.now(timezone.utc)
    evt1 = SecurityEvent(
        camera_id=cam.id,
        event_type='zone_intrusion',
        risk_score=75.0,
        risk_level='HIGH',
        confidence=0.88,
        description='Person entered restricted ICU zone',
        timestamp=now,
        event_metadata={'ml_anomaly': True, 'ml_risk_score': 82.0}
    )
    evt2 = SecurityEvent(
        camera_id=cam.id,
        event_type='loitering',
        risk_score=92.0,
        risk_level='CRITICAL',
        confidence=0.95,
        description='Loitering detected in pharmacy vault area',
        timestamp=now,
        event_metadata={'ml_anomaly': False, 'ml_risk_score': 30.0}
    )
    db_session.add_all([evt1, evt2])
    db_session.commit()

    # 3. Create alerts
    alt1 = Alert(
        event_id=evt1.id,
        camera_id=cam.id,
        severity='HIGH',
        status='NEW',
        title='High Priority Intrusion Alert',
        created_at=now
    )
    alt2 = Alert(
        event_id=evt2.id,
        camera_id=cam.id,
        severity='CRITICAL',
        status='INVESTIGATING',
        title='Critical Pharmacy Loitering Alert',
        created_at=now
    )
    db_session.add_all([alt1, alt2])
    db_session.commit()

    res = client.get('/api/statistics/dashboard')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['success'] is True

    kpis = data['kpis']
    assert kpis['active_alerts'] == 2
    assert kpis['critical_alerts'] == 1
    assert kpis['high_alerts'] == 1
    assert kpis['investigating'] == 1
    assert kpis['events_today'] == 2
    assert kpis['ml_anomalies'] == 1

    assert len(data['cameras']) == 1
    cam_data = data['cameras'][0]
    assert cam_data['name'] == 'ICU Corridor Unit 1'
    assert cam_data['active_alerts'] == 2
    assert cam_data['zones_count'] == 1


def test_analytics_statistics_empty(client, db_session):
    """Test /api/statistics/analytics handles empty data gracefully without division by zero."""
    res = client.get('/api/statistics/analytics?range=24h')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['success'] is True
    assert data['range'] == '24h'
    assert data['total_events'] == 0
    assert data['total_alerts'] == 0
    assert data['insufficient_data'] is True
    assert isinstance(data['timeline'], list)
    assert isinstance(data['severity_distribution'], dict)
    assert isinstance(data['status_distribution'], dict)
    assert isinstance(data['event_types'], list)
    assert isinstance(data['camera_activity'], list)
    assert data['ml_metrics']['total_anomalies'] == 0


def test_analytics_statistics_ranges(client, db_session):
    """Test /api/statistics/analytics supports all time range filters."""
    for rng in ['today', '24h', '7d', '30d']:
        res = client.get(f'/api/statistics/analytics?range={rng}')
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data['success'] is True
        assert data['range'] == rng
        assert len(data['timeline']) > 0


def test_analytics_statistics_with_data(client, db_session):
    """Test /api/statistics/analytics aggregates events, severity, and ML metrics correctly."""
    cam = Camera(
        name='Emergency Room Aisle',
        source='0',
        source_type='webcam',
        location='ER Sector 3',
        enabled=True
    )
    db_session.add(cam)
    db_session.commit()

    now = datetime.now(timezone.utc)
    evt = SecurityEvent(
        camera_id=cam.id,
        event_type='crowd_detected',
        risk_score=78.0,
        risk_level='HIGH',
        confidence=0.85,
        description='High crowd density detected outside triage room',
        timestamp=now,
        event_metadata={'ml_anomaly': True, 'ml_risk_score': 80.0}
    )
    db_session.add(evt)
    db_session.commit()

    alt = Alert(
        event_id=evt.id,
        camera_id=cam.id,
        severity='HIGH',
        status='ACKNOWLEDGED',
        title='Crowd Alert',
        created_at=now
    )
    db_session.add(alt)
    db_session.commit()

    res = client.get('/api/statistics/analytics?range=today')
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data['success'] is True
    assert data['total_events'] == 1
    assert data['total_alerts'] == 1
    assert data['insufficient_data'] is False

    # Check severity distribution
    assert data['severity_distribution']['HIGH'] == 1

    # Check status distribution
    assert data['status_distribution']['ACKNOWLEDGED'] == 1

    # Check ML metrics
    assert data['ml_metrics']['total_anomalies'] == 1
    assert data['ml_metrics']['anomalous_percentage'] == 100.0

    # Check camera activity
    assert len(data['camera_activity']) == 1
    assert data['camera_activity'][0]['events_count'] == 1
