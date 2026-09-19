import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.extensions import db
from app.models.camera import Camera
from app.models.event import SecurityEvent
from app.models.alert import Alert
from app.models.settings import SystemConfiguration


def seed_database(reset=False):
    """Initializes tables and seeds default healthcare security configurations."""
    app = create_app()
    with app.app_context():
        if reset:
            print("Resetting all database tables...")
            db.drop_all()

        print("Creating all database tables...")
        db.create_all()

        # Seed System Configurations if empty
        if SystemConfiguration.query.count() == 0:
            print("Seeding default system settings...")
            default_settings = [
                SystemConfiguration(
                    key="operating_hours",
                    value={"start": "08:00", "end": "20:00"},
                    category="hours",
                    description="Normal hospital operational visiting hours"
                ),
                SystemConfiguration(
                    key="after_hours_risk_multiplier",
                    value=1.5,
                    category="hours",
                    description="Multiplier applied to risk scores during after-hours"
                ),
                SystemConfiguration(
                    key="crowd_threshold_count",
                    value=4,
                    category="thresholds",
                    description="Number of persons in zone before triggering crowd density alert"
                ),
                SystemConfiguration(
                    key="crowd_duration_seconds",
                    value=15,
                    category="thresholds",
                    description="Duration in seconds crowd density must persist"
                ),
                SystemConfiguration(
                    key="loitering_threshold_seconds",
                    value=30,
                    category="thresholds",
                    description="Time in seconds person remains stationary in restricted area"
                ),
                SystemConfiguration(
                    key="alert_cooldown_seconds",
                    value=15,
                    category="alerts",
                    description="Cooldown period in seconds before repeating identical alerts"
                ),
                SystemConfiguration(
                    key="detection_confidence_threshold",
                    value=0.45,
                    category="thresholds",
                    description="Minimum object detection confidence required"
                ),
                SystemConfiguration(
                    key="ml_anomaly_threshold",
                    value=-0.15,
                    category="anomaly",
                    description="Isolation Forest decision function cutoff for anomaly"
                ),
                SystemConfiguration(
                    key="rule_risk_weight",
                    value=0.70,
                    category="ml",
                    description="Weight assigned to rule-based risk score in final risk fusion"
                ),
                SystemConfiguration(
                    key="ml_risk_weight",
                    value=0.30,
                    category="ml",
                    description="Weight assigned to ML anomaly risk score in final risk fusion"
                )
            ]
            db.session.bulk_save_objects(default_settings)
            db.session.commit()
            print("System configurations seeded.")

        # Seed Default Cameras if empty
        if Camera.query.count() == 0:
            print("Seeding default healthcare cameras and restricted zones...")
            cameras = [
                Camera(
                    name="CAM-01: ICU Entrance Corridor",
                    source="0",
                    source_type="webcam",
                    location="Main Hospital Wing - Floor 3, Intensive Care Unit",
                    enabled=True,
                    configuration={
                        "zones": [
                            {
                                "id": "zone_icu_airlock",
                                "name": "ICU Airlock Sterile Zone",
                                "type": "restricted",
                                "polygon": [[0.2, 0.15], [0.8, 0.15], [0.8, 0.85], [0.2, 0.85]],
                                "severity": "HIGH"
                            }
                        ],
                        "operating_hours": {"start": "08:00", "end": "20:00"},
                        "fps": 15,
                        "resolution": [640, 480],
                        "crowd_threshold": 3,
                        "loitering_threshold_seconds": 20
                    }
                ),
                Camera(
                    name="CAM-02: Central Pharmacy & Narcotics Storage",
                    source="data/videos/pharmacy_sample.mp4",
                    source_type="video_file",
                    location="West Wing - Level 1, Inpatient Pharmacy Vault",
                    enabled=True,
                    configuration={
                        "zones": [
                            {
                                "id": "zone_narcotics_vault",
                                "name": "Schedule II Narcotics Vault",
                                "type": "restricted",
                                "polygon": [[0.3, 0.25], [0.7, 0.25], [0.7, 0.75], [0.3, 0.75]],
                                "severity": "CRITICAL"
                            }
                        ],
                        "operating_hours": {"start": "07:00", "end": "19:00"},
                        "fps": 15,
                        "resolution": [640, 480],
                        "crowd_threshold": 2,
                        "loitering_threshold_seconds": 15
                    }
                ),
                Camera(
                    name="CAM-03: Emergency Department Triage Bay",
                    source="data/videos/emergency_sample.mp4",
                    source_type="video_file",
                    location="Ground Floor - Emergency Trauma Intake",
                    enabled=True,
                    configuration={
                        "zones": [
                            {
                                "id": "zone_resus_sterile",
                                "name": "Trauma Resuscitation Sterile Area",
                                "type": "warning",
                                "polygon": [[0.15, 0.2], [0.85, 0.2], [0.85, 0.8], [0.15, 0.8]],
                                "severity": "MEDIUM"
                            }
                        ],
                        "operating_hours": {"start": "00:00", "end": "23:59"},
                        "fps": 15,
                        "resolution": [640, 480],
                        "crowd_threshold": 6,
                        "loitering_threshold_seconds": 45
                    }
                ),
                Camera(
                    name="CAM-04: Pathology & Biosecurity Laboratory",
                    source="data/videos/lab_sample.mp4",
                    source_type="video_file",
                    location="Research Wing - Basement Level 1, Biosafety Lab",
                    enabled=False,
                    configuration={
                        "zones": [
                            {
                                "id": "zone_bsl_airlock",
                                "name": "BSL-3 Containment Access",
                                "type": "restricted",
                                "polygon": [[0.25, 0.2], [0.75, 0.2], [0.75, 0.8], [0.25, 0.8]],
                                "severity": "CRITICAL"
                            }
                        ],
                        "operating_hours": {"start": "09:00", "end": "17:00"},
                        "fps": 15,
                        "resolution": [640, 480],
                        "crowd_threshold": 2,
                        "loitering_threshold_seconds": 10
                    }
                )
            ]
            db.session.bulk_save_objects(cameras)
            db.session.commit()
            print("Default cameras seeded successfully.")

        # Seed sample initial event and alert for verification
        if SecurityEvent.query.count() == 0:
            print("Seeding initial demonstration event & alert...")
            cam1 = Camera.query.first()
            if cam1:
                event = SecurityEvent(
                    camera_id=cam1.id,
                    event_type="restricted_area_intrusion",
                    timestamp=datetime.now(timezone.utc) - timedelta(minutes=12),
                    confidence=0.92,
                    risk_score=78.5,
                    risk_level="HIGH",
                    description="Individual detected crossing into restricted ICU Airlock Sterile Zone without scheduled authorization badge check.",
                    snapshot_path=None,
                    status="NEW",
                    event_metadata={
                        "zone_id": "zone_icu_airlock",
                        "object_class": "person",
                        "bbox": [140, 95, 230, 310],
                        "ml_anomaly_score": -0.28,
                        "is_after_hours": False
                    }
                )
                db.session.add(event)
                db.session.commit()

                alert = Alert(
                    event_id=event.id,
                    camera_id=cam1.id,
                    title="High-Risk Zone Intrusion - ICU Airlock",
                    description=event.description,
                    severity="HIGH",
                    status="NEW",
                    notes="Automated event engine triage flagged high-risk zone breach."
                )
                db.session.add(alert)
                db.session.commit()
                print("Initial event and alert seeded.")

        print("Database initialization complete.")


if __name__ == '__main__':
    reset_flag = '--reset' in sys.argv
    seed_database(reset=reset_flag)
