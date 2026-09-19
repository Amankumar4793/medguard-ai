from datetime import datetime, timezone
from app.extensions import db

def utc_now():
    return datetime.now(timezone.utc)


class Camera(db.Model):
    __tablename__ = 'cameras'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(255), nullable=False)  # '0', filepath, or rtsp URL
    source_type = db.Column(db.String(50), nullable=False, default='webcam')  # 'webcam', 'video_file', 'rtsp'
    location = db.Column(db.String(150), nullable=False, default='General Area')
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    configuration = db.Column(db.JSON, default=lambda: {
        "zones": [],
        "operating_hours": {"start": "08:00", "end": "20:00"},
        "fps": 15,
        "resolution": [640, 480],
        "crowd_threshold": 4,
        "loitering_threshold_seconds": 30
    })
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    events = db.relationship('SecurityEvent', backref='camera', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source': self.source,
            'source_type': self.source_type,
            'location': self.location,
            'enabled': self.enabled,
            'configuration': self.configuration or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'event_count': len(self.events) if self.events else 0
        }

    def __repr__(self):
        return f"<Camera {self.id}: {self.name} ({self.location})>"
