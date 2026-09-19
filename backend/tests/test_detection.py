from unittest.mock import MagicMock, patch
import numpy as np
import pytest
import torch
from app import create_app
from app.extensions import db
from app.models.camera import Camera
from app.detection.detector import ObjectDetector, reset_detector
from app.monitoring.video_processor import VideoProcessor
from app.monitoring import camera_manager


@pytest.fixture
def dummy_frame():
    """Returns a dummy 480x640 BGR image."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


class MockBoxes:
    """Mock PyTorch tensor boxes returned by Ultralytics YOLO."""
    def __init__(self, xyxy, confs, cls_ids):
        self.xyxy = torch.tensor(xyxy, dtype=torch.float32)
        self.conf = torch.tensor(confs, dtype=torch.float32)
        self.cls = torch.tensor(cls_ids, dtype=torch.float32)

    def __len__(self):
        return len(self.xyxy)


class MockResult:
    """Mock single frame YOLO Results object."""
    def __init__(self, boxes, names):
        self.boxes = boxes
        self.names = names


def test_detector_initialization_defaults():
    """Verify detector initializes with standard defaults."""
    with patch('ultralytics.YOLO'):
        detector = ObjectDetector(model_name='yolov8n.pt', confidence=0.5, iou=0.4)
        assert detector.model_name == 'yolov8n.pt'
        assert detector.confidence == 0.5
        assert detector.iou == 0.4
        assert 'person' in detector.target_classes
        assert 'backpack' in detector.target_classes


def test_detector_class_filtering_and_parsing(dummy_frame):
    """Verify detector correctly filters target classes and calculates bounding box metadata."""
    mock_yolo = MagicMock()
    
    # 3 detections:
    # 0: person (conf 0.92, [100, 100, 200, 300])
    # 1: backpack (conf 0.78, [220, 250, 280, 310])
    # 2: car (conf 0.85, [50, 50, 150, 150]) -> Should be filtered OUT!
    mock_boxes = MockBoxes(
        xyxy=[[100, 100, 200, 300], [220, 250, 280, 310], [50, 50, 150, 150]],
        confs=[0.92, 0.78, 0.85],
        cls_ids=[0, 24, 2]
    )
    mock_names = {0: 'person', 24: 'backpack', 2: 'car'}
    mock_yolo.predict.return_value = [MockResult(mock_boxes, mock_names)]

    with patch('ultralytics.YOLO', return_value=mock_yolo):
        detector = ObjectDetector(model_name='yolov8n.pt', confidence=0.45)
        res = detector.detect(dummy_frame)

        assert res['total_count'] == 2  # car was filtered out
        assert res['person_count'] == 1
        assert res['object_count'] == 1
        assert res['inference_ms'] >= 0.0

        person_det = res['detections'][0]
        assert person_det['class_name'] == 'person'
        assert person_det['confidence'] == 0.92
        assert person_det['bbox'] == [100, 100, 200, 300]
        assert person_det['center'] == [150, 200]
        assert person_det['is_person'] is True

        obj_det = res['detections'][1]
        assert obj_det['class_name'] == 'backpack'
        assert obj_det['confidence'] == 0.78
        assert obj_det['is_person'] is False


def test_draw_detections(dummy_frame):
    """Verify high-contrast annotations are drawn onto frame."""
    with patch('ultralytics.YOLO'):
        detector = ObjectDetector(model_name='yolov8n.pt')
        mock_detections = [
            {
                'class_id': 0,
                'class_name': 'person',
                'confidence': 0.89,
                'bbox': [50, 50, 150, 200],
                'center': [100, 125],
                'is_person': True
            }
        ]

        initial_pixel_sum = int(np.sum(dummy_frame))
        annotated = detector.draw_detections(dummy_frame, mock_detections)

        assert annotated.shape == (480, 640, 3)
        # Drawing bounding box should modify pixels from pure black
        assert int(np.sum(annotated)) > initial_pixel_sum


def test_video_processor_detection_pipeline(dummy_frame):
    """Verify VideoProcessor integrates detection into its processing pipeline."""
    mock_detector = MagicMock()
    mock_detector.detect.return_value = {
        'detections': [
            {'class_id': 0, 'class_name': 'person', 'confidence': 0.95, 'bbox': [10, 10, 50, 100], 'center': [30, 55], 'is_person': True}
        ],
        'person_count': 1,
        'object_count': 0,
        'total_count': 1,
        'inference_ms': 12.5,
        'timestamp': '2026-09-18T21:00:00'
    }
    mock_detector.draw_detections.side_effect = lambda frame, dets: frame

    proc = VideoProcessor(
        camera_id=99,
        name='Test Cam',
        source='0',
        enable_detection=True,
        inference_interval=1
    )
    proc._detector = mock_detector

    # Process frame
    processed = proc.process_frame(dummy_frame)
    assert processed is not None
    assert mock_detector.detect.called

    dets = proc.get_latest_detections()
    assert dets['person_count'] == 1
    assert dets['total_count'] == 1

    telemetry = proc.get_telemetry()
    assert telemetry['person_count'] == 1
    assert telemetry['ai_inference_ms'] == 12.5
    assert telemetry['detection_enabled'] is True


def test_monitoring_detections_endpoint(client, db_session):
    """Verify GET /api/monitoring/detections/<camera_id> endpoint."""
    cam = Camera(
        name="Pharmacy Entrance",
        location="Zone B - Pharmacy",
        source="data/videos/sample.mp4",
        source_type="video_file",
        enabled=True
    )
    db_session.add(cam)
    db_session.commit()

    res = client.get(f'/api/monitoring/detections/{cam.id}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['camera_id'] == cam.id
    assert 'person_count' in data
    assert 'object_count' in data
    assert 'detections' in data

    # Non-existent camera
    res_404 = client.get('/api/monitoring/detections/99999')
    assert res_404.status_code == 404
