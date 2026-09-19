import time
from pathlib import Path
import pytest
from app.monitoring.video_processor import VideoProcessor
from app.monitoring.camera_manager import CameraManager, camera_manager
from app.models.camera import Camera
from app.routes.monitoring import stream_camera

SAMPLE_VIDEO_PATH = 'data/videos/sample.mp4'


def test_video_processor_synthetic_stream():
    """Verify VideoProcessor opens synthetic video, captures frames, and tracks telemetry."""
    base_dir = Path(__file__).resolve().parent.parent.parent

    processor = VideoProcessor(
        camera_id=99,
        name="Test Corridor Cam",
        source=SAMPLE_VIDEO_PATH,
        source_type="video_file",
        target_fps=15,
        width=640,
        height=480,
        loop_demo=True,
        project_root=base_dir,
        enable_detection=False
    )

    started = processor.start()
    assert started is True
    time.sleep(0.5)  # Allow background worker to process several frames

    assert processor.status == 'RUNNING'
    telemetry = processor.get_telemetry()
    assert telemetry['camera_id'] == 99
    assert telemetry['frame_count'] > 0
    assert telemetry['status'] == 'RUNNING'
    assert telemetry['resolution'] == [640, 480]

    # Verify latest frame and JPEG encoding
    frame = processor.get_latest_frame()
    assert frame is not None
    assert frame.shape == (480, 640, 3)

    jpeg_bytes = processor.get_latest_jpeg()
    assert jpeg_bytes is not None
    # Standard JPEG header check
    assert jpeg_bytes[:2] == b'\xff\xd8'

    stopped = processor.stop(timeout=2.0)
    assert stopped is True
    assert processor.status == 'OFFLINE'


def test_video_processor_invalid_source():
    """Verify VideoProcessor transitions gracefully to ERROR state on missing/invalid source."""
    base_dir = Path(__file__).resolve().parent.parent.parent

    processor = VideoProcessor(
        camera_id=98,
        name="Broken Source Cam",
        source="data/videos/non_existent_file.mp4",
        source_type="video_file",
        project_root=base_dir
    )

    processor.start()
    time.sleep(0.3)

    assert processor.status == 'ERROR'
    assert processor.error_message is not None
    processor.stop()


def test_camera_manager_lifecycle(db_session):
    """Verify CameraManager register, start, restart, and shutdown with multi-camera isolation."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    manager = CameraManager({
        'process_width': 640,
        'process_height': 480,
        'target_fps': 15,
        'jpeg_quality': 75,
        'loop_demo': True,
        'project_root': base_dir
    })

    cam1 = Camera(
        name="ICU Cam",
        source=SAMPLE_VIDEO_PATH,
        source_type="video_file",
        location="ICU Ward"
    )
    cam2 = Camera(
        name="Pharmacy Cam",
        source=SAMPLE_VIDEO_PATH,
        source_type="video_file",
        location="Pharmacy"
    )
    db_session.add_all([cam1, cam2])
    db_session.commit()

    # Register and start both
    manager.register_camera(cam1)
    manager.register_camera(cam2)

    manager.start_camera(cam1.id)
    manager.start_camera(cam2.id)
    time.sleep(0.4)

    status1, _ = manager.get_camera_status(cam1.id)
    status2, _ = manager.get_camera_status(cam2.id)
    assert status1 == 'RUNNING'
    assert status2 == 'RUNNING'

    # Restart cam1
    restarted = manager.restart_camera(cam1.id, cam1)
    assert restarted is True
    time.sleep(0.3)
    assert manager.get_camera_status(cam1.id)[0] == 'RUNNING'

    # Stop cam2
    manager.stop_camera(cam2.id)
    assert manager.get_camera_status(cam2.id)[0] == 'OFFLINE'
    # cam1 must remain RUNNING (independent isolation)
    assert manager.get_camera_status(cam1.id)[0] == 'RUNNING'

    # Clean shutdown
    manager.shutdown_all()
    assert manager.get_camera_status(cam1.id)[0] == 'OFFLINE'


def test_monitoring_api_endpoints(client, db_session):
    """Test /api/monitoring REST endpoints (status, start, telemetry, restart, stop)."""
    camera = Camera(
        name="API Test Camera",
        source=SAMPLE_VIDEO_PATH,
        source_type="video_file",
        location="Test Area",
        enabled=True
    )
    db_session.add(camera)
    db_session.commit()

    # 1. GET /api/monitoring/status
    res = client.get('/api/monitoring/status')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert any(c['camera_id'] == camera.id for c in data['cameras'])

    # 2. POST /api/monitoring/start
    start_res = client.post('/api/monitoring/start', json={'camera_id': camera.id})
    assert start_res.status_code == 200
    assert start_res.get_json()['success'] is True

    time.sleep(0.4)

    # 3. GET /api/monitoring/telemetry/<camera_id>
    tel_res = client.get(f'/api/monitoring/telemetry/{camera.id}')
    assert tel_res.status_code == 200
    tel_data = tel_res.get_json()
    assert tel_data['success'] is True
    assert tel_data['telemetry']['camera_id'] == camera.id

    # 4. POST /api/monitoring/restart
    restart_res = client.post('/api/monitoring/restart', json={'camera_id': camera.id})
    assert restart_res.status_code == 200
    assert restart_res.get_json()['success'] is True

    # 5. POST /api/monitoring/stop
    stop_res = client.post('/api/monitoring/stop', json={'camera_id': camera.id})
    assert stop_res.status_code == 200
    assert stop_res.get_json()['success'] is True


def test_mjpeg_stream_response(app, db_session):
    """Test /api/monitoring/stream/<camera_id> yields MJPEG multipart content via route function."""
    camera = Camera(
        name="Stream Test Cam",
        source=SAMPLE_VIDEO_PATH,
        source_type="video_file",
        location="Stream Bay",
        enabled=True
    )
    db_session.add(camera)
    db_session.commit()

    with app.test_request_context():
        response = stream_camera(camera.id)
        assert response.status_code == 200
        assert 'multipart/x-mixed-replace; boundary=frame' in response.headers['Content-Type']

        # Read first chunk from generator
        first_chunk = next(response.response)
        assert b'--frame' in first_chunk
        assert b'Content-Type: image/jpeg' in first_chunk

        # Clean shutdown
        camera_manager.stop_camera(camera.id)
