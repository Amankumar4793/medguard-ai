from datetime import datetime, timezone
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('security_events.id', ondelete='CASCADE'), nullable=False)
    camera_id = db.Column(db.Integer, db.ForeignKey('cameras.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(150), default='', nullable=True)
    description = db.Column(db.Text, default='', nullable=True)
    severity = db.Column(db.String(20), default='MEDIUM', nullable=False)  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    status = db.Column(db.String(30), default='NEW', nullable=False)  # 'NEW', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED'
    snapshot_path = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, default='', nullable=True)

    # Lifecycle Timestamps & Operators
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    investigating_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    acknowledged_by = db.Column(db.String(100), nullable=True)
    investigating_by = db.Column(db.String(100), nullable=True)
    resolved_by = db.Column(db.String(100), nullable=True)

    # Extended threat & risk fusion metadata
    alert_metadata = db.Column(db.JSON, default=dict, nullable=True)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    camera = db.relationship('Camera', backref=db.backref('alerts', lazy=True), foreign_keys=[camera_id], lazy=True)
    history = db.relationship(
        'AlertHistory',
        backref='alert',
        cascade='all, delete-orphan',
        lazy=True,
        order_by='AlertHistory.timestamp.asc()'
    )

    def to_dict(self, include_history=False):
        camera_name = None
        camera_location = None
        if self.camera:
            camera_name = self.camera.name
            camera_location = self.camera.location
        elif self.event and self.event.camera:
            camera_name = self.event.camera.name
            camera_location = self.event.camera.location

        data = {
            'id': self.id,
            'event_id': self.event_id,
            'camera_id': self.camera_id,
            'camera_name': camera_name,
            'camera_location': camera_location,
            'title': self.title or (f"{self.severity} Security Alert" if self.severity else "Security Alert"),
            'description': self.description or (self.event.description if self.event else ''),
            'severity': self.severity,
            'status': self.status,
            'snapshot_path': self.snapshot_path or (self.event.snapshot_path if self.event else None),
            'notes': self.notes or '',
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'investigating_at': self.investigating_at.isoformat() if self.investigating_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'acknowledged_by': self.acknowledged_by,
            'investigating_by': self.investigating_by,
            'resolved_by': self.resolved_by,
            'alert_metadata': self.alert_metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'event': self.event.to_dict() if self.event else None
        }

        if include_history:
            data['history'] = [h.to_dict() for h in self.history]

        return data

    def __repr__(self):
        return f"<Alert {self.id}: Event {self.event_id} [{self.severity} - {self.status}]>"


class AlertHistory(db.Model):
    __tablename__ = 'alert_history'

    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.Integer, db.ForeignKey('alerts.id', ondelete='CASCADE'), nullable=False)
    previous_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    operator = db.Column(db.String(100), default='Security Operator', nullable=False)
    note = db.Column(db.Text, default='', nullable=True)
    timestamp = db.Column(db.DateTime, default=utc_now, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'previous_status': self.previous_status,
            'new_status': self.new_status,
            'operator': self.operator,
            'note': self.note or '',
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

    def __repr__(self):
        return f"<AlertHistory {self.id}: Alert #{self.alert_id} {self.previous_status} -> {self.new_status} by {self.operator}>"
