from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models.alert import Alert, AlertHistory
from app.models.event import SecurityEvent
from app.services.alert_service import AlertService

alerts_bp = Blueprint('alerts', __name__)


@alerts_bp.route('/', methods=['GET'])
def get_alerts():
    """
    Retrieve alerts with optional camera_id, status, and severity filtering,
    along with offset/limit pagination.
    """
    camera_id = request.args.get('camera_id', type=int)
    status = request.args.get('status')
    severity = request.args.get('severity')

    try:
        raw_limit = request.args.get('limit', default=50, type=int)
        limit = max(1, min(raw_limit if raw_limit is not None else 50, 100))
    except (ValueError, TypeError):
        limit = 50

    try:
        raw_offset = request.args.get('offset', default=0, type=int)
        offset = max(0, raw_offset if raw_offset is not None else 0)
    except (ValueError, TypeError):
        offset = 0

    alerts, total = AlertService.get_alerts(
        camera_id=camera_id,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset
    )

    return jsonify({
        'success': True,
        'count': len(alerts),
        'total': total,
        'limit': limit,
        'offset': offset,
        'alerts': [a.to_dict() for a in alerts]
    }), 200


@alerts_bp.route('/statistics', methods=['GET'])
def get_alert_statistics():
    """Retrieve high-level incident triage statistics and KPI metrics."""
    stats = AlertService.get_statistics()
    return jsonify({
        'success': True,
        'statistics': stats
    }), 200


@alerts_bp.route('/<int:alert_id>', methods=['GET'])
def get_alert(alert_id):
    """Retrieve a single alert with full audit history and event details."""
    alert = AlertService.get_alert(alert_id)
    if not alert:
        return jsonify({
            'success': False,
            'error': f'Alert #{alert_id} not found.'
        }), 404

    return jsonify({
        'success': True,
        'alert': alert.to_dict(include_history=True)
    }), 200


@alerts_bp.route('/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Transition alert to ACKNOWLEDGED state."""
    data = request.get_json() or {}
    operator = data.get('operator', 'Security Operator')
    note = data.get('note', '')

    alert, err = AlertService.acknowledge_alert(alert_id, operator=operator, note=note)
    if err:
        status_code = 404 if "not found" in err.lower() else 400
        return jsonify({'success': False, 'error': err}), status_code

    return jsonify({
        'success': True,
        'message': f'Alert #{alert_id} acknowledged.',
        'alert': alert.to_dict(include_history=True)
    }), 200


@alerts_bp.route('/<int:alert_id>/investigate', methods=['POST'])
def investigate_alert(alert_id):
    """Transition alert to INVESTIGATING state."""
    data = request.get_json() or {}
    operator = data.get('operator', 'Security Operator')
    note = data.get('note', '')

    alert, err = AlertService.investigate_alert(alert_id, operator=operator, note=note)
    if err:
        status_code = 404 if "not found" in err.lower() else 400
        return jsonify({'success': False, 'error': err}), status_code

    return jsonify({
        'success': True,
        'message': f'Alert #{alert_id} is now under active investigation.',
        'alert': alert.to_dict(include_history=True)
    }), 200


@alerts_bp.route('/<int:alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """Transition alert to RESOLVED state with closing resolution notes."""
    data = request.get_json() or {}
    operator = data.get('operator', 'Security Operator')
    note = data.get('note', '')

    alert, err = AlertService.resolve_alert(alert_id, operator=operator, note=note)
    if err:
        status_code = 404 if "not found" in err.lower() else 400
        return jsonify({'success': False, 'error': err}), status_code

    return jsonify({
        'success': True,
        'message': f'Alert #{alert_id} successfully resolved.',
        'alert': alert.to_dict(include_history=True)
    }), 200


@alerts_bp.route('/<int:alert_id>/notes', methods=['POST'])
def add_alert_note(alert_id):
    """Appends an operator note to an alert and records an audit log entry."""
    data = request.get_json() or {}
    operator = data.get('operator', 'Security Operator')
    note = data.get('note', '')

    alert, err = AlertService.add_note(alert_id, operator=operator, note=note)
    if err:
        status_code = 404 if "not found" in err.lower() else 400
        return jsonify({'success': False, 'error': err}), status_code

    return jsonify({
        'success': True,
        'message': f'Note added to Alert #{alert_id}.',
        'alert': alert.to_dict(include_history=True)
    }), 200


@alerts_bp.route('/<int:alert_id>', methods=['PATCH'])
def update_alert(alert_id):
    """
    Backward-compatible triage status update and notes updater.
    Routes to transition_alert or add_note.
    """
    alert = db.session.get(Alert, alert_id)
    if not alert:
        return jsonify({'success': False, 'error': f'Alert #{alert_id} not found.'}), 404

    data = request.get_json() or {}
    new_status = data.get('status')
    notes = data.get('notes')
    operator = data.get('operator', 'Security Operator')

    if new_status:
        alert, err = AlertService.transition_alert(alert_id, new_status, operator=operator, note=notes or '')
        if err:
            return jsonify({'success': False, 'error': err}), 400
    elif notes:
        alert, err = AlertService.add_note(alert_id, operator=operator, note=notes)
        if err:
            return jsonify({'success': False, 'error': err}), 400

    return jsonify({
        'success': True,
        'message': f'Alert #{alert_id} updated.',
        'alert': alert.to_dict(include_history=True)
    }), 200


@alerts_bp.route('/', methods=['POST'])
def create_alert():
    """Manually trigger an alert from an event or custom payload."""
    data = request.get_json() or {}
    event_id = data.get('event_id')

    if not event_id:
        return jsonify({'success': False, 'error': 'Missing event_id.'}), 400

    event = db.session.get(SecurityEvent, event_id)
    if not event:
        return jsonify({'success': False, 'error': f'Event #{event_id} not found.'}), 404

    severity = data.get('severity', event.risk_level or 'MEDIUM').upper()
    status = data.get('status', 'NEW').upper()
    notes = data.get('notes', f"Manual alert triggered for {event.event_type}.")

    alert = Alert(
        event_id=event.id,
        camera_id=event.camera_id,
        title=data.get('title', f"{severity} Incident: {event.event_type.replace('_', ' ').title()}"),
        description=data.get('description', event.description),
        severity=severity,
        status=status,
        snapshot_path=event.snapshot_path,
        notes=notes,
        alert_metadata={
            'rule_risk_score': event.risk_score,
            'ml_risk_score': 0.0,
            'final_risk_score': event.risk_score
        }
    )
    db.session.add(alert)
    db.session.flush()

    history = AlertHistory(
        alert_id=alert.id,
        previous_status=None,
        new_status=status,
        operator=data.get('operator', 'Security Operator'),
        note=notes
    )
    db.session.add(history)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Alert created successfully.',
        'alert': alert.to_dict(include_history=True)
    }), 201
