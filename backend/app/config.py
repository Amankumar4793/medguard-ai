import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


class Config:
    """Base configuration class."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-healthcare-security-secret-key-change-in-prod')
    
    # Project Paths
    BASE_DIR = BASE_DIR
    PROJECT_ROOT = BASE_DIR.parent

    # Database
    DEFAULT_DB_PATH = BASE_DIR / 'healthcare_security.db'
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')

    # Storage Paths
    DATA_DIR = BASE_DIR.parent / 'data'
    SNAPSHOT_DIR = os.getenv('SNAPSHOT_DIR', str(DATA_DIR / 'snapshots'))
    VIDEO_DIR = str(DATA_DIR / 'videos')
    MODEL_DIR = str(DATA_DIR / 'models')

    # Security Rules Defaults
    AFTER_HOURS_START = os.getenv('AFTER_HOURS_START', '20:00')
    AFTER_HOURS_END = os.getenv('AFTER_HOURS_END', '06:00')
    DEFAULT_COOLDOWN_SECONDS = int(os.getenv('DEFAULT_COOLDOWN_SECONDS', '15'))
    DEMO_MODE = os.getenv('DEMO_MODE', 'true').lower() in ('true', '1', 'yes')

    # Vision & Performance Defaults
    PROCESS_WIDTH = int(os.getenv('PROCESS_WIDTH', '640'))
    PROCESS_HEIGHT = int(os.getenv('PROCESS_HEIGHT', '480'))
    TARGET_FPS = int(os.getenv('TARGET_FPS', '15'))
    DETECTION_CONFIDENCE = float(os.getenv('DETECTION_CONFIDENCE', '0.45'))
    JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', '75'))
    VIDEO_LOOP_DEMO = os.getenv('VIDEO_LOOP_DEMO', 'true').lower() in ('true', '1', 'yes')
    CAMERA_RECONNECT_DELAY = int(os.getenv('CAMERA_RECONNECT_DELAY', '5'))

    # YOLO & Object Detection Defaults (Phase 3)
    YOLO_MODEL = os.getenv('YOLO_MODEL', 'yolov8n.pt')
    YOLO_CONFIDENCE = float(os.getenv('YOLO_CONFIDENCE', '0.45'))
    YOLO_IOU = float(os.getenv('YOLO_IOU', '0.45'))
    YOLO_DEVICE = os.getenv('YOLO_DEVICE', 'cpu')
    YOLO_IMAGE_SIZE = int(os.getenv('YOLO_IMAGE_SIZE', '640'))
    INFERENCE_INTERVAL_FRAMES = int(os.getenv('INFERENCE_INTERVAL_FRAMES', '2'))
    TARGET_CLASSES = [c.strip().lower() for c in os.getenv('TARGET_CLASSES', 'person,backpack,handbag,suitcase').split(',') if c.strip()]


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing environment configuration with in-memory database."""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    TESTING = False


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
