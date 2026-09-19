from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from sqlalchemy import func
from app.extensions import db
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert
from app.monitoring.camera_manager import camera_manager
from app.services.ml_service import ml_service

statistics_bp = Blueprint('statistics', __name__)


@statistics_bp.route('/', methods=['GET'])
def get_statistics():
    """Retrieve system-wide aggregated metrics for the Security Dashboard."""
    # Camera metrics
    total_cameras = Camera.query.count()
    active_cameras = Camera.query.filter_by(enabled=True).count()

    # Event metrics
    total_events = SecurityEvent.query.count()
    high_risk_events = SecurityEvent.query.filter(
        SecurityEvent.risk_level.in_(['HIGH', 'CRITICAL'])
    ).count()

    # Alert metrics
    total_alerts = Alert.query.count()
    critical_alerts = Alert.query.filter_by(severity='CRITICAL').count()
    new_alerts = Alert.query.filter_by(status='NEW').count()

    # Breakdown by risk level
    risk_breakdown_raw = db.session.query(
        SecurityEvent.risk_level, func.count(SecurityEvent.id)
    ).group_by(SecurityEvent.risk_level).all()
    events_by_risk = {r[0]: r[1] for r in risk_breakdown_raw}

    # Breakdown by event type
    type_breakdown_raw = db.session.query(
        SecurityEvent.event_type, func.count(SecurityEvent.id)
    ).group_by(SecurityEvent.event_type).all()
    events_by_type = {t[0]: t[1] for t in type_breakdown_raw}

    # Breakdown by alert severity
    severity_breakdown_raw = db.session.query(
        Alert.severity, func.count(Alert.id)
    ).group_by(Alert.severity).all()
    alerts_by_severity = {s[0]: s[1] for s in severity_breakdown_raw}

    # Recent 5 events
    recent_events = [
        e.to_dict() for e in SecurityEvent.query.order_by(
            SecurityEvent.timestamp.desc()
        ).limit(5).all()
    ]

    # Recent 5 alerts
    recent_alerts = [
        a.to_dict() for a in Alert.query.order_by(
            Alert.created_at.desc()
        ).limit(5).all()
    ]

    # Phase 5 ML Anomaly Statistics - query only required columns to avoid ORM overhead
    events_tuples = db.session.query(
        SecurityEvent.event_metadata, SecurityEvent.risk_score, SecurityEvent.camera_id
    ).all()
    camera_names = {c.id: c.name for c in Camera.query.all()}
    total_ml_anomalies = 0
    rule_risks = []
    ml_risks = []
    camera_anomalies = {}

    for meta, risk_score, camera_id in events_tuples:
        meta = meta or {}
        if meta.get('ml_anomaly') is True or meta.get('ml_anomalous') is True:
            total_ml_anomalies += 1
            cam_name = camera_names.get(camera_id, f"Camera #{camera_id}")
            camera_anomalies[cam_name] = camera_anomalies.get(cam_name, 0) + 1

        if 'rule_risk_score' in meta:
            rule_risks.append(float(meta['rule_risk_score']))
        elif risk_score:
            rule_risks.append(float(risk_score))

        if 'ml_risk_score' in meta:
            ml_risks.append(float(meta['ml_risk_score']))

    avg_rule_risk = round(sum(rule_risks) / len(rule_risks), 1) if rule_risks else 0.0
    avg_ml_risk = round(sum(ml_risks) / len(ml_risks), 1) if ml_risks else 0.0

    return jsonify({
        'success': True,
        'summary': {
            'total_cameras': total_cameras,
            'active_cameras': active_cameras,
            'total_events': total_events,
            'high_risk_events': high_risk_events,
            'total_alerts': total_alerts,
            'critical_alerts': critical_alerts,
            'new_alerts': new_alerts,
            'total_ml_anomalies': total_ml_anomalies,
            'avg_rule_risk': avg_rule_risk,
            'avg_ml_risk': avg_ml_risk,
            'ml_status': ml_service.status
        },
        'breakdowns': {
            'events_by_risk': events_by_risk,
            'events_by_type': events_by_type,
            'alerts_by_severity': alerts_by_severity,
            'anomalies_by_camera': camera_anomalies
        },
        'recent_events': recent_events,
        'recent_alerts': recent_alerts,
        'ml': ml_service.get_status()
    }), 200


@statistics_bp.route('/dashboard', methods=['GET'])
def get_dashboard_statistics():
    """
    Retrieve real-time consolidated SOC dashboard KPIs, system health matrix,
    and camera operational telemetry.
    """
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    # 1. Incident Alerts KPIs
    active_alerts = Alert.query.filter(Alert.status.in_(['NEW', 'ACKNOWLEDGED', 'INVESTIGATING'])).count()
    critical_active = Alert.query.filter(Alert.severity == 'CRITICAL', Alert.status != 'RESOLVED').count()
    high_active = Alert.query.filter(Alert.severity == 'HIGH', Alert.status != 'RESOLVED').count()
    investigating = Alert.query.filter_by(status='INVESTIGATING').count()

    # 2. Camera Telemetry & Status
    cameras = Camera.query.all()
    total_cameras = len(cameras)
    telemetry_map = camera_manager.get_all_statuses()
    online_cam_ids = {
        cam_id for cam_id, tel in telemetry_map.items()
        if tel.get('status') == 'RUNNING' or tel.get('is_running')
    }
    cameras_online = len(online_cam_ids)
    cameras_offline = max(0, total_cameras - cameras_online)

    # 3. Security Events Today
    events_today = SecurityEvent.query.filter(SecurityEvent.timestamp >= today_start).count()

    # 4. Total ML Anomalies detected (lightweight column query)
    events_meta = db.session.query(SecurityEvent.event_metadata).all()
    ml_anomalies_count = sum(
        1 for (m,) in events_meta
        if (m or {}).get('ml_anomaly') is True or (m or {}).get('ml_anomalous') is True
    )

    # 5. Pre-aggregate active alert counts and latest risk per camera to eliminate N+1 queries
    active_alerts_by_cam = dict(
        db.session.query(Alert.camera_id, func.count(Alert.id))
        .filter(Alert.status != 'RESOLVED')
        .group_by(Alert.camera_id)
        .all()
    )

    subq = db.session.query(
        SecurityEvent.camera_id,
        func.max(SecurityEvent.id).label('max_id')
    ).group_by(SecurityEvent.camera_id).subquery()

    latest_events_raw = db.session.query(
        SecurityEvent.camera_id, SecurityEvent.risk_score
    ).join(subq, SecurityEvent.id == subq.c.max_id).all()
    latest_risk_by_cam = {cam_id: score for cam_id, score in latest_events_raw}

    # Camera Status Overview List
    camera_items = []
    for c in cameras:
        tel = telemetry_map.get(c.id, {})
        is_on = c.id in online_cam_ids
        cam_active_alerts = active_alerts_by_cam.get(c.id, 0)
        latest_risk = round(float(latest_risk_by_cam.get(c.id, 0.0)), 1)

        camera_items.append({
            'id': c.id,
            'name': c.name,
            'location': c.location,
            'source_type': c.source_type,
            'status': 'ONLINE' if is_on else ('OFFLINE' if c.enabled else 'DISABLED'),
            'fps': round(float(tel.get('actual_fps', 0.0)), 1) if is_on else 0,
            'resolution': f"{tel.get('frame_width', 640)}x{tel.get('frame_height', 480)}" if is_on else "N/A",
            'detections_count': tel.get('detections_count', 0) if is_on else 0,
            'tracks_count': tel.get('tracks_count', 0) if is_on else 0,
            'active_alerts': cam_active_alerts,
            'latest_risk': latest_risk,
            'zones_count': len((c.configuration or {}).get('zones', []))
        })

    # 6. System Status Matrix
    cam_sys_status = 'ONLINE' if cameras_online > 0 else ('DEGRADED' if total_cameras > 0 else 'OFFLINE')
    system_status = {
        'backend': 'ONLINE',
        'socketio': 'CONNECTED',
        'camera_system': cam_sys_status,
        'ml_model': ml_service.status,
        'alert_engine': 'ONLINE'
    }

    # 7. Recent active alerts for dashboard table
    active_alerts_list = [
        a.to_dict() for a in Alert.query.filter(Alert.status != 'RESOLVED').order_by(
            Alert.created_at.desc()
        ).limit(6).all()
    ]

    # 8. Recent security events
    recent_events_list = [
        e.to_dict() for e in SecurityEvent.query.order_by(
            SecurityEvent.timestamp.desc()
        ).limit(8).all()
    ]

    return jsonify({
        'success': True,
        'kpis': {
            'active_alerts': active_alerts,
            'critical_alerts': critical_active,
            'high_alerts': high_active,
            'investigating': investigating,
            'cameras_online': cameras_online,
            'cameras_offline': cameras_offline,
            'ml_anomalies': ml_anomalies_count,
            'events_today': events_today
        },
        'system_status': system_status,
        'cameras': camera_items,
        'active_alerts_list': active_alerts_list,
        'recent_events': recent_events_list
    }), 200


@statistics_bp.route('/analytics', methods=['GET'])
def get_analytics_statistics():
    """
    Retrieve aggregated historical analytics, temporal trends, and categorical distributions
    across selectable time horizons (today, 24h, 7d, 30d).
    """
    range_param = request.args.get('range', '24h').lower()
    now = datetime.now(timezone.utc)

    if range_param == 'today':
        start_time = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        bucket_count = 24
        bucket_type = 'hour'
    elif range_param == '7d':
        start_time = now - timedelta(days=7)
        bucket_count = 7
        bucket_type = 'day'
    elif range_param == '30d':
        start_time = now - timedelta(days=30)
        bucket_count = 30
        bucket_type = 'day'
    else:  # '24h'
        start_time = now - timedelta(hours=24)
        bucket_count = 24
        bucket_type = 'hour'

    events = SecurityEvent.query.filter(SecurityEvent.timestamp >= start_time).order_by(SecurityEvent.timestamp.asc()).all()
    alerts = Alert.query.filter(Alert.created_at >= start_time).order_by(Alert.created_at.asc()).all()

    # Build timeline buckets
    buckets = []
    if bucket_type == 'hour':
        for i in range(bucket_count):
            b_start = start_time + timedelta(hours=i)
            b_end = b_start + timedelta(hours=1)
            b_events = [
                e for e in events
                if b_start <= (e.timestamp if e.timestamp.tzinfo else e.timestamp.replace(tzinfo=timezone.utc)) < b_end
            ]
            rule_scores = [
                float(e.event_metadata.get('rule_risk_score', e.risk_score))
                for e in b_events if e.event_metadata
            ]
            ml_scores = [
                float(e.event_metadata.get('ml_risk_score', 0.0))
                for e in b_events if e.event_metadata
            ]
            final_scores = [float(e.risk_score) for e in b_events]

            buckets.append({
                'label': b_start.strftime('%H:00'),
                'timestamp': b_start.isoformat(),
                'events': len(b_events),
                'avg_rule_risk': round(sum(rule_scores) / len(rule_scores), 1) if rule_scores else 0.0,
                'avg_ml_risk': round(sum(ml_scores) / len(ml_scores), 1) if ml_scores else 0.0,
                'avg_final_risk': round(sum(final_scores) / len(final_scores), 1) if final_scores else 0.0
            })
    else:
        for i in range(bucket_count):
            b_start = start_time + timedelta(days=i)
            b_end = b_start + timedelta(days=1)
            b_events = [
                e for e in events
                if b_start <= (e.timestamp if e.timestamp.tzinfo else e.timestamp.replace(tzinfo=timezone.utc)) < b_end
            ]
            rule_scores = [
                float(e.event_metadata.get('rule_risk_score', e.risk_score))
                for e in b_events if e.event_metadata
            ]
            ml_scores = [
                float(e.event_metadata.get('ml_risk_score', 0.0))
                for e in b_events if e.event_metadata
            ]
            final_scores = [float(e.risk_score) for e in b_events]

            buckets.append({
                'label': b_start.strftime('%b %d'),
                'timestamp': b_start.isoformat(),
                'events': len(b_events),
                'avg_rule_risk': round(sum(rule_scores) / len(rule_scores), 1) if rule_scores else 0.0,
                'avg_ml_risk': round(sum(ml_scores) / len(ml_scores), 1) if ml_scores else 0.0,
                'avg_final_risk': round(sum(final_scores) / len(final_scores), 1) if final_scores else 0.0
            })

    # Severity distribution
    severity_dist = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for a in alerts:
        s = (a.severity or 'MEDIUM').upper()
        if s in severity_dist:
            severity_dist[s] += 1

    # Status distribution
    status_dist = {'NEW': 0, 'ACKNOWLEDGED': 0, 'INVESTIGATING': 0, 'RESOLVED': 0}
    for a in alerts:
        st = (a.status or 'NEW').upper()
        if st in status_dist:
            status_dist[st] += 1

    # Event type distribution
    type_counts = {}
    type_risks = {}
    for e in events:
        t = e.event_type or 'security_event'
        type_counts[t] = type_counts.get(t, 0) + 1
        type_risks.setdefault(t, []).append(float(e.risk_score or 0))

    event_types = [
        {
            'type': t,
            'label': t.replace('_', ' ').title(),
            'count': count,
            'avg_risk': round(sum(type_risks[t]) / len(type_risks[t]), 1) if type_risks.get(t) else 0.0
        }
        for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Camera activity breakdown
    cameras = Camera.query.all()
    camera_activity = []
    for c in cameras:
        cam_evts = [e for e in events if e.camera_id == c.id]
        cam_alts = [a for a in alerts if a.camera_id == c.id or (a.event and a.event.camera_id == c.id)]
        cam_anomalies = [
            e for e in cam_evts
            if (e.event_metadata or {}).get('ml_anomaly') is True or (e.event_metadata or {}).get('ml_anomalous') is True
        ]
        cam_risks = [float(e.risk_score or 0) for e in cam_evts]
        last_evt = cam_evts[-1] if cam_evts else None

        camera_activity.append({
            'camera_id': c.id,
            'name': c.name,
            'location': c.location,
            'status': 'ACTIVE' if c.enabled else 'DISABLED',
            'events_count': len(cam_evts),
            'alerts_count': len(cam_alts),
            'anomalies_count': len(cam_anomalies),
            'avg_risk': round(sum(cam_risks) / len(cam_risks), 1) if cam_risks else 0.0,
            'last_activity': last_evt.timestamp.isoformat() if last_evt and last_evt.timestamp else None
        })

    # ML metrics
    ml_anomalies_events = [
        e for e in events
        if (e.event_metadata or {}).get('ml_anomaly') is True or (e.event_metadata or {}).get('ml_anomalous') is True
    ]
    all_ml_scores = [
        float(e.event_metadata.get('ml_risk_score', 0))
        for e in events if e.event_metadata and 'ml_risk_score' in e.event_metadata
    ]
    all_final_scores = [float(e.risk_score or 0) for e in events]

    ml_metrics = {
        'total_events_in_range': len(events),
        'total_anomalies': len(ml_anomalies_events),
        'anomalous_percentage': round((len(ml_anomalies_events) / len(events)) * 100, 1) if events else 0.0,
        'avg_ml_risk': round(sum(all_ml_scores) / len(all_ml_scores), 1) if all_ml_scores else 0.0,
        'avg_final_risk': round(sum(all_final_scores) / len(all_final_scores), 1) if all_final_scores else 0.0,
        'model_status': ml_service.status
    }

    return jsonify({
        'success': True,
        'range': range_param,
        'total_events': len(events),
        'total_alerts': len(alerts),
        'insufficient_data': len(events) == 0 and len(alerts) == 0,
        'timeline': buckets,
        'severity_distribution': severity_dist,
        'status_distribution': status_dist,
        'event_types': event_types,
        'camera_activity': camera_activity,
        'ml_metrics': ml_metrics
    }), 200
