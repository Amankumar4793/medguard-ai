from datetime import datetime, timezone
from app.extensions import db

def utc_now():
    return datetime.now(timezone.utc)


class SecurityEvent(db.Model):
    __tablename__ = 'security_events'

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False)
    event_type = db.Column(db.String(80), nullable=False)  # 'restricted_entry', 'loitering', 'crowd_density', 'after_hours', etc.
    timestamp = db.Column(db.DateTime, default=utc_now, nullable=False)
    confidence = db.Column(db.Float, default=0.0, nullable=False)
    risk_score = db.Column(db.Float, default=0.0, nullable=False)  # 0 to 100
    risk_level = db.Column(db.String(20), default='LOW', nullable=False)  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description = db.Column(db.Text, nullable=False)
    snapshot_path = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), default='NEW', nullable=False)  # 'NEW', 'REVIEWED', 'DISMISSED'
    event_metadata = db.Column(db.JSON, default=dict)  # Stores bbox, zone_id, ML anomaly score, track_id
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    alerts = db.relationship('Alert', backref='event', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'camera_id': self.camera_id,
            'camera_name': self.camera.name if self.camera else None,
            'camera_location': self.camera.location if self.camera else None,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'confidence': round(self.confidence, 3) if self.confidence is not None else 0.0,
            'risk_score': round(self.risk_score, 1) if self.risk_score is not None else 0.0,
            'risk_level': self.risk_level,
            'description': self.description,
            'snapshot_path': self.snapshot_path,
            'status': self.status,
            'metadata': self.event_metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'has_alert': len(self.alerts) > 0 if self.alerts else False
        }

    def __repr__(self):
        return f"<SecurityEvent {self.id}: {self.event_type} [{self.risk_level}]>"
