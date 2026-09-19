import time
import threading
from datetime import datetime, timezone, timedelta
from flask import current_app
from app.extensions import db, socketio
from app.models.alert import Alert, AlertHistory
from app.models.event import SecurityEvent
from app.models.settings import SystemConfiguration
from app.utils import setup_logger

logger = setup_logger('alert_service')


class AlertService:
    """
    Centralized service for managing security alert generation, multi-tier cooldown deduplication,
    incident lifecycle transitions (NEW -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED),
    audit trail recording, and real-time Socket.IO broadcasts.
    """

    # Thread-safe in-memory deduplication tracker: (camera_id, event_type, zone_id, severity) -> last_triggered_epoch
    _lock = threading.Lock()
    _cooldown_tracker = {}

    # Default cooldown intervals in seconds
    DEFAULT_COOLDOWNS = {
        'CRITICAL': 15,
        'HIGH': 30,
        'MEDIUM': 60,
        'LOW': 120
    }

    # Strict lifecycle transition matrix
    VALID_TRANSITIONS = {
        'NEW': {'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED'},
        'ACKNOWLEDGED': {'INVESTIGATING', 'RESOLVED'},
        'INVESTIGATING': {'RESOLVED', 'ACKNOWLEDGED'},
        'RESOLVED': set()  # Terminal state
    }

    @classmethod
    def get_cooldown_seconds(cls, severity):
        """
        Retrieves cooldown duration for a given severity from SystemConfiguration or defaults.
        """
        sev = str(severity).upper()
        try:
            config = SystemConfiguration.query.filter_by(key='alert_cooldowns').first()
            if config and isinstance(config.value, dict) and sev in config.value:
                return float(config.value[sev])

            # Fallback to general alert_cooldown_seconds if configured
            gen_config = SystemConfiguration.query.filter_by(key='alert_cooldown_seconds').first()
            if gen_config and gen_config.value is not None:
                base = float(gen_config.value)
                multipliers = {'CRITICAL': 0.75, 'HIGH': 1.0, 'MEDIUM': 2.0, 'LOW': 4.0}
                return max(5.0, base * multipliers.get(sev, 1.0))
        except Exception as e:
            logger.debug(f"Could not read alert_cooldowns from DB: {e}")

        return cls.DEFAULT_COOLDOWNS.get(sev, 30)

    @classmethod
    def is_deduplicated(cls, camera_id, event_type, zone_id, severity):
        """
        Checks if an alert for the same camera, event type, zone, and severity
        is currently in a cooldown window to prevent alert fatigue.

        Returns:
            bool: True if duplicate (suppress alert), False if allowed.
        """
        now = time.time()
        key = (camera_id, str(event_type), str(zone_id), str(severity).upper())
        cooldown = cls.get_cooldown_seconds(severity)

        with cls._lock:
            # Memory leak protection: bound tracker size and prune expired entries
            if len(cls._cooldown_tracker) > 500:
                cls._cooldown_tracker = {
                    k: t for k, t in cls._cooldown_tracker.items()
                    if (now - t) < 300.0
                }
                if len(cls._cooldown_tracker) > 500:
                    sorted_items = sorted(cls._cooldown_tracker.items(), key=lambda item: item[1], reverse=True)
                    cls._cooldown_tracker = dict(sorted_items[:400])

            last_time = cls._cooldown_tracker.get(key)
            if last_time is not None and (now - last_time) < cooldown:
                remaining = cooldown - (now - last_time)
                logger.debug(f"Alert suppressed by cooldown ({remaining:.1f}s remaining) for key {key}")
                return True

            cls._cooldown_tracker[key] = now
            return False

    @classmethod
    def reset_cooldowns(cls):
        """Resets the in-memory cooldown cache (primarily used in test suites)."""
        with cls._lock:
            cls._cooldown_tracker.clear()
        logger.debug("Alert cooldown tracker reset.")

    @staticmethod
    def determine_severity(risk_score, risk_level=None):
        """
        Determines standard severity level from risk level or continuous risk score.
        """
        if risk_level:
            level = str(risk_level).upper()
            if level in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW'):
                return level

        score = float(risk_score or 0.0)
        if score >= 85.0:
            return 'CRITICAL'
        elif score >= 65.0:
            return 'HIGH'
        elif score >= 40.0:
            return 'MEDIUM'
        else:
            return 'LOW'

    @classmethod
    def create_alert_from_event(cls, event, event_dict=None, app=None):
        """
        Evaluates a SecurityEvent and generates an Alert if threat thresholds are met
        and cooldown deduplication permits.

        Args:
            event (SecurityEvent): The recorded security event.
            event_dict (dict, optional): Original event dictionary with extra metadata.
            app (Flask, optional): Flask application instance for context.

        Returns:
            Alert or None: Created Alert record or None if suppressed/skipped.
        """
        ctx_app = app or (current_app._get_current_object() if current_app else None)
        if ctx_app:
            with ctx_app.app_context():
                return cls._create_alert_internal(event, event_dict)
        else:
            return cls._create_alert_internal(event, event_dict)

    @classmethod
    def _create_alert_internal(cls, event, event_dict=None):
        if not event:
            return None

        event_metadata = dict(event.event_metadata or {})
        camera_id = event.camera_id
        event_type = event.event_type
        zone_id = event_metadata.get('zone_id', 'facility')
        zone_name = event_metadata.get('zone_name', 'Monitored Zone')
        risk_score = float(event.risk_score or 0.0)
        severity = cls.determine_severity(risk_score, event.risk_level)

        # Alerts generated for HIGH, CRITICAL, or risk_score >= 60
        if severity not in ('HIGH', 'CRITICAL') and risk_score < 60.0:
            logger.debug(f"Event #{event.id} ({severity}, score {risk_score}) below alert trigger threshold.")
            return None

        # Check multi-tier cooldown deduplication
        if cls.is_deduplicated(camera_id, event_type, zone_id, severity):
            logger.info(f"Suppressed duplicate alert for {event_type} on Camera #{camera_id} in {zone_name}")
            return None

        title = f"{severity} Incident: {event_type.replace('_', ' ').title()} - {zone_name}"
        description = event.description or f"Suspicious activity detected in {zone_name}."


        is_ml_anom = bool(event_metadata.get('ml_anomaly', event_metadata.get('ml_anomalous', False)))
        alert_meta = {
            'rule_risk_score': event_metadata.get('rule_risk_score', risk_score),
            'ml_risk_score': event_metadata.get('ml_risk_score', 0.0),
            'final_risk_score': risk_score,
            'zone_id': zone_id,
            'zone_name': zone_name,
            'track_id': event_metadata.get('track_id'),
            'ml_anomaly': is_ml_anom,
            'ml_anomalous': is_ml_anom,
            'ml_indicators': event_metadata.get('ml_indicators', [])
        }

        try:
            alert = Alert(
                event_id=event.id,
                camera_id=camera_id,
                title=title,
                description=description,
                severity=severity,
                status='NEW',
                snapshot_path=event.snapshot_path,
                notes=f"Automated incident alert generated by AI Security Engine for {event_type.replace('_', ' ')} in {zone_name}.",
                alert_metadata=alert_meta
            )
            db.session.add(alert)
            db.session.flush()

            # Record initial history entry
            initial_history = AlertHistory(
                alert_id=alert.id,
                previous_status=None,
                new_status='NEW',
                operator='System (AI Engine)',
                note='Alert automatically triggered by Security Engine'
            )
            db.session.add(initial_history)
            db.session.commit()

            logger.info(f"Created Alert #{alert.id} [{severity}] for Event #{event.id}")

            # Real-Time Socket.IO notification broadcast
            cls._broadcast_socket_event('alert_new', alert.to_dict(include_history=True))

            return alert
        except Exception as e:
            logger.error(f"Failed to persist Alert for Event #{event.id}: {e}")
            db.session.rollback()
            return None

    @classmethod
    def transition_alert(cls, alert_id, new_status, operator='Security Operator', note=''):
        """
        Transitions an alert to a new status according to strict lifecycle rules,
        updating operator timestamps and recording an immutable audit history log.

        Returns:
            tuple: (Alert, None) on success, or (None, str) on validation/database failure.
        """
        alert = db.session.get(Alert, alert_id)
        if not alert:
            return None, f"Alert #{alert_id} not found."

        new_status = str(new_status).upper()
        current_status = alert.status

        # If already in the target status, just add note if provided
        if current_status == new_status:
            if note:
                return cls.add_note(alert_id, operator, note)
            return alert, None

        valid_targets = cls.VALID_TRANSITIONS.get(current_status, set())
        if new_status not in valid_targets:
            return None, f"Invalid transition: Alert #{alert_id} cannot move from '{current_status}' to '{new_status}'."

        now = datetime.now(timezone.utc)

        # Update lifecycle metadata
        if new_status == 'ACKNOWLEDGED':
            alert.acknowledged_at = now
            alert.acknowledged_by = operator
        elif new_status == 'INVESTIGATING':
            alert.investigating_at = now
            alert.investigating_by = operator
        elif new_status == 'RESOLVED':
            alert.resolved_at = now
            alert.resolved_by = operator

        alert.status = new_status
        if note:
            existing_notes = alert.notes or ''
            alert.notes = f"{existing_notes}\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] {operator}: {note}".strip()

        history_entry = AlertHistory(
            alert_id=alert.id,
            previous_status=current_status,
            new_status=new_status,
            operator=operator,
            note=note or f"Status changed to {new_status}"
        )
        db.session.add(history_entry)

        try:
            db.session.commit()
            logger.info(f"Alert #{alert.id} transitioned from {current_status} to {new_status} by {operator}")
            cls._broadcast_socket_event('alert_updated', alert.to_dict(include_history=True))
            return alert, None
        except Exception as e:
            logger.error(f"Error updating alert status: {e}")
            db.session.rollback()
            return None, str(e)

    @classmethod
    def acknowledge_alert(cls, alert_id, operator='Security Operator', note=''):
        """Convenience method for transitioning to ACKNOWLEDGED."""
        return cls.transition_alert(alert_id, 'ACKNOWLEDGED', operator, note)

    @classmethod
    def investigate_alert(cls, alert_id, operator='Security Operator', note=''):
        """Convenience method for transitioning to INVESTIGATING."""
        return cls.transition_alert(alert_id, 'INVESTIGATING', operator, note)

    @classmethod
    def resolve_alert(cls, alert_id, operator='Security Operator', note=''):
        """Convenience method for transitioning to RESOLVED."""
        return cls.transition_alert(alert_id, 'RESOLVED', operator, note)

    @classmethod
    def add_note(cls, alert_id, operator='Security Operator', note=''):
        """
        Appends an investigation/triage note to an alert and records an audit log entry.
        """
        if not note:
            return None, "Note content cannot be empty."

        alert = db.session.get(Alert, alert_id)
        if not alert:
            return None, f"Alert #{alert_id} not found."

        now = datetime.now(timezone.utc)
        existing_notes = alert.notes or ''
        alert.notes = f"{existing_notes}\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] {operator}: {note}".strip()

        history_entry = AlertHistory(
            alert_id=alert.id,
            previous_status=alert.status,
            new_status=alert.status,
            operator=operator,
            note=note
        )
        db.session.add(history_entry)

        try:
            db.session.commit()
            logger.info(f"Added note to Alert #{alert.id} by {operator}")
            cls._broadcast_socket_event('alert_updated', alert.to_dict(include_history=True))
            return alert, None
        except Exception as e:
            logger.error(f"Error appending note to alert: {e}")
            db.session.rollback()
            return None, str(e)

    @classmethod
    def get_alert(cls, alert_id, include_history=True):
        """Retrieves a single alert with optional audit history."""
        return db.session.get(Alert, alert_id)


    @classmethod
    def get_alerts(cls, camera_id=None, severity=None, status=None, limit=50, offset=0):
        """
        Queries alerts with optional filtering and pagination.
        """
        query = Alert.query

        if camera_id is not None:
            query = query.filter_by(camera_id=camera_id)
        if severity:
            query = query.filter_by(severity=severity.upper())
        if status:
            query = query.filter_by(status=status.upper())

        total = query.count()
        alerts = query.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()

        return alerts, total

    @classmethod
    def get_statistics(cls):
        """
        Calculates aggregate metrics across alerts for SOC KPI monitoring.
        """
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(hours=24)

        total = Alert.query.count()
        new_count = Alert.query.filter_by(status='NEW').count()
        acknowledged_count = Alert.query.filter_by(status='ACKNOWLEDGED').count()
        investigating_count = Alert.query.filter_by(status='INVESTIGATING').count()
        resolved_count = Alert.query.filter_by(status='RESOLVED').count()

        critical_count = Alert.query.filter_by(severity='CRITICAL').count()
        high_count = Alert.query.filter_by(severity='HIGH').count()
        medium_count = Alert.query.filter_by(severity='MEDIUM').count()
        low_count = Alert.query.filter_by(severity='LOW').count()

        recent_24h = Alert.query.filter(Alert.created_at >= yesterday).count()

        # Calculate average resolution time for resolved alerts
        resolved_alerts = Alert.query.filter(
            Alert.status == 'RESOLVED',
            Alert.resolved_at.isnot(None),
            Alert.created_at.isnot(None)
        ).all()

        avg_resolution_seconds = 0
        if resolved_alerts:
            total_time = sum((a.resolved_at - a.created_at).total_seconds() for a in resolved_alerts if a.resolved_at > a.created_at)
            avg_resolution_seconds = round(total_time / len(resolved_alerts), 1)

        return {
            'total_alerts': total,
            'active_alerts': new_count + acknowledged_count + investigating_count,
            'status_counts': {
                'NEW': new_count,
                'ACKNOWLEDGED': acknowledged_count,
                'INVESTIGATING': investigating_count,
                'RESOLVED': resolved_count
            },
            'severity_counts': {
                'CRITICAL': critical_count,
                'HIGH': high_count,
                'MEDIUM': medium_count,
                'LOW': low_count
            },
            'recent_24h_count': recent_24h,
            'avg_resolution_seconds': avg_resolution_seconds
        }

    @staticmethod
    def _broadcast_socket_event(event_name, payload):
        """Safely broadcasts a Socket.IO message without raising exceptions."""
        try:
            socketio.emit(event_name, payload)
            logger.debug(f"Broadcasted Socket.IO event '{event_name}'")
        except Exception as e:
            logger.debug(f"Socket.IO emission '{event_name}' skipped: {e}")
