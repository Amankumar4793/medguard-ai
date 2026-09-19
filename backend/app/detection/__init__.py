"""Detection package for computer vision, YOLO inference, and zone checks."""
from app.detection.detector import ObjectDetector, get_detector, reset_detector
from app.detection.tracker import TrackedObject, CentroidIoUTracker
from app.detection.zones import Zone, ZoneEvaluator

__all__ = [
    'ObjectDetector', 'get_detector', 'reset_detector',
    'TrackedObject', 'CentroidIoUTracker',
    'Zone', 'ZoneEvaluator'
]
