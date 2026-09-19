from datetime import datetime, timezone
from app.extensions import db

def utc_now():
    return datetime.now(timezone.utc)


class SystemConfiguration(db.Model):
    __tablename__ = 'system_configurations'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.JSON, nullable=False)  # Supports string, dict, list, number, boolean
    category = db.Column(db.String(50), nullable=False, default='general')  # 'hours', 'thresholds', 'cooldown', 'anomaly', 'general'
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'category': self.category,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<SystemConfiguration {self.key}={self.value}>"
