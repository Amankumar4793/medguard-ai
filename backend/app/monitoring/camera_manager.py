import threading
from app.monitoring.video_processor import VideoProcessor
from app.extensions import socketio
from app.utils import setup_logger

logger = setup_logger('camera_manager')


class CameraManager:
    """
    Central manager for multiple independent camera stream processors.
    Thread-safe lifecycle coordination and telemetry aggregation.
    """

    def __init__(self, config=None):
        self._processors = {}  # camera_id -> VideoProcessor
        self._lock = threading.RLock()
        self._config = config or {}
        self._app = None

    def init_app(self, app):
        """Initialize with Flask app configuration."""
        self._app = app
        self._config = {
            'process_width': app.config.get('PROCESS_WIDTH', 640),
            'process_height': app.config.get('PROCESS_HEIGHT', 480),
            'target_fps': app.config.get('TARGET_FPS', 15),
            'jpeg_quality': app.config.get('JPEG_QUALITY', 75),
            'loop_demo': app.config.get('VIDEO_LOOP_DEMO', True),
            'project_root': app.config.get('PROJECT_ROOT'),
            'yolo_model': app.config.get('YOLO_MODEL', 'yolov8n.pt'),
            'yolo_confidence': app.config.get('YOLO_CONFIDENCE', 0.45),
            'yolo_iou': app.config.get('YOLO_IOU', 0.45),
            'yolo_device': app.config.get('YOLO_DEVICE', 'cpu'),
            'yolo_image_size': app.config.get('YOLO_IMAGE_SIZE', 640),
            'inference_interval': app.config.get('INFERENCE_INTERVAL_FRAMES', 2),
            'target_classes': app.config.get('TARGET_CLASSES'),
            'model_dir': app.config.get('MODEL_DIR')
        }
        logger.info("CameraManager initialized with application and detection settings.")

    def register_camera(self, camera_model):
        """Registers or reconfigures a camera processor based on database model."""
        with self._lock:
            cam_id = camera_model.id
            # Stop existing processor if running
            if cam_id in self._processors:
                self._processors[cam_id].stop()

            cfg = camera_model.configuration or {}
            width = cfg.get('resolution', [self._config.get('process_width', 640), 480])[0]
            height = cfg.get('resolution', [640, self._config.get('process_height', 480)])[1]
            fps = cfg.get('fps', self._config.get('target_fps', 15))
            enable_detection = cfg.get('enable_detection', True)

            detector_cfg = {
                'YOLO_MODEL': self._config.get('yolo_model', 'yolov8n.pt'),
                'YOLO_CONFIDENCE': self._config.get('yolo_confidence', 0.45),
                'YOLO_IOU': self._config.get('yolo_iou', 0.45),
                'YOLO_DEVICE': self._config.get('yolo_device', 'cpu'),
                'YOLO_IMAGE_SIZE': self._config.get('yolo_image_size', 640),
                'TARGET_CLASSES': self._config.get('target_classes'),
                'MODEL_DIR': self._config.get('model_dir')
            }

            processor = VideoProcessor(
                camera_id=cam_id,
                name=camera_model.name,
                source=camera_model.source,
                source_type=camera_model.source_type,
                location=camera_model.location,
                target_fps=fps,
                width=width,
                height=height,
                jpeg_quality=self._config.get('jpeg_quality', 75),
                loop_demo=self._config.get('loop_demo', True),
                zones=cfg.get('zones', []),
                project_root=self._config.get('project_root'),
                enable_detection=enable_detection,
                inference_interval=self._config.get('inference_interval', 2),
                detector_config=detector_cfg,
                camera_config=cfg,
                app=self._app
            )
            self._processors[cam_id] = processor
            logger.info(f"Registered camera #{cam_id} ({camera_model.name}) with AI object detection.")
            return processor

    def start_camera(self, camera_id, camera_model=None):
        """Starts video processor for specified camera ID."""
        with self._lock:
            if camera_id not in self._processors:
                if camera_model is None:
                    raise KeyError(f"Camera #{camera_id} is not registered in CameraManager.")
                self.register_camera(camera_model)

            processor = self._processors[camera_id]

        started = processor.start()
        self._emit_status_change(camera_id, processor.status, processor.get_telemetry().get('fps', 0.0))
        return started

    def stop_camera(self, camera_id):
        """Stops video processor for specified camera ID."""
        with self._lock:
            processor = self._processors.get(camera_id)

        if not processor:
            return True

        stopped = processor.stop()
        self._emit_status_change(camera_id, 'OFFLINE', 0.0)
        return stopped

    def restart_camera(self, camera_id, camera_model=None):
        """Restarts a camera processor, optionally updating configuration."""
        if camera_model is not None:
            self.register_camera(camera_model)
        with self._lock:
            processor = self._processors.get(camera_id)

        if not processor:
            if camera_model:
                return self.start_camera(camera_id, camera_model)
            raise KeyError(f"Camera #{camera_id} not registered.")

        restarted = processor.restart()
        self._emit_status_change(camera_id, processor.status, 0.0)
        return restarted

    def get_processor(self, camera_id):
        """Retrieves VideoProcessor instance for streaming."""
        with self._lock:
            return self._processors.get(camera_id)

    def get_camera_status(self, camera_id):
        """Retrieves current runtime status and error for a single camera."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor:
                return processor.status, processor.error_message
            return 'OFFLINE', None

    def get_telemetry(self, camera_id):
        """Retrieves full telemetry dictionary for camera."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor:
                return processor.get_telemetry()
            return None

    def get_detections(self, camera_id):
        """Retrieves latest detection results dictionary for specified camera ID."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor:
                return processor.get_latest_detections()
            return {
                'camera_id': camera_id,
                'detections': [],
                'person_count': 0,
                'object_count': 0,
                'total_count': 0,
                'inference_ms': 0.0,
                'timestamp': None
            }

    def get_tracks(self, camera_id):
        """Retrieves active tracked objects for specified camera ID."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor:
                return processor.get_tracks()
            return []

    def get_zones(self, camera_id):
        """Retrieves configured zones and occupancy for specified camera ID."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor:
                return processor.get_zones()
            return []

    def get_ml_analysis(self, camera_id):
        """Retrieves latest ML anomaly analysis result for specified camera ID."""
        with self._lock:
            processor = self._processors.get(camera_id)
            if processor:
                return processor.get_ml_analysis()
            return None

    def get_all_statuses(self):
        """Returns telemetry summaries for all registered camera processors."""
        with self._lock:
            return {
                cam_id: proc.get_telemetry()
                for cam_id, proc in self._processors.items()
            }

    def shutdown_all(self):
        """Stops and cleans up all running video processors."""
        with self._lock:
            processors = list(self._processors.values())

        for proc in processors:
            try:
                proc.stop(timeout=1.5)
            except Exception:
                pass

    def _emit_status_change(self, camera_id, status, fps=0.0):
        """Emits camera_status_changed event to SocketIO clients."""
        try:
            socketio.emit('camera_status_changed', {
                'camera_id': camera_id,
                'status': status,
                'fps': fps
            })
        except Exception as e:
            logger.debug(f"SocketIO status emit skipped: {e}")


# Global CameraManager singleton
camera_manager = CameraManager()
