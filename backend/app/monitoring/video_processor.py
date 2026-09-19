import time
import threading
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
from datetime import timezone
from app.utils import setup_logger
from app.detection import get_detector
from app.detection.tracker import CentroidIoUTracker
from app.detection.zones import ZoneEvaluator
from app.services.security_engine import security_engine, is_time_after_hours
from app.services.event_service import EventService
from app.services.ml_service import ml_service
from app.ml.features import SecurityFeatureExtractor
from app.extensions import socketio

logger = setup_logger('video_processor')


class VideoProcessor:
    """
    Dedicated video processing worker for a single camera feed.
    Runs frame capture, AI object detection, multi-object tracking,
    spatial zone analysis, and security rule evaluation in an isolated background thread.
    """

    def __init__(self, camera_id, name, source, source_type='webcam', location='General Area',
                 target_fps=15, width=640, height=480, jpeg_quality=75, loop_demo=True,
                 zones=None, project_root=None, enable_detection=True, inference_interval=2,
                 detector_config=None, camera_config=None, app=None):
        self.camera_id = camera_id
        self.name = name
        self.source = str(source).strip()
        self.source_type = source_type.lower()
        self.location = location
        self.target_fps = max(1, min(int(target_fps), 60))
        self.width = max(160, int(width))
        self.height = max(120, int(height))
        self.jpeg_quality = max(30, min(int(jpeg_quality), 95))
        self.loop_demo = bool(loop_demo)
        self.camera_config = camera_config or {}
        self.zones = zones or self.camera_config.get('zones', [])
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent.parent.parent
        self.app = app

        # Phase 3 AI Object Detection integration
        self.enable_detection = bool(enable_detection)
        self.inference_interval = max(1, int(inference_interval))
        self.detector_config = detector_config or {}
        self._detector = None
        self._detection_counter = 0
        self._latest_detections = {
            'detections': [],
            'person_count': 0,
            'object_count': 0,
            'total_count': 0,
            'inference_ms': 0.0,
            'timestamp': None
        }
        self._last_socket_emit_time = 0.0

        # Phase 4 Object Tracking & Zone Spatial Logic
        self.tracker = CentroidIoUTracker(
            max_lost_frames=self.camera_config.get('tracker_max_lost', 15),
            iou_threshold=self.camera_config.get('tracker_iou_thresh', 0.25),
            distance_threshold=self.camera_config.get('tracker_dist_thresh', 90.0)
        )
        self.zone_evaluator = ZoneEvaluator(zones_config=self.zones)
        self._active_tracks = []
        self._zone_eval_result = {
            'entries': [],
            'exits': [],
            'occupancy': {},
            'violations': []
        }

        # Phase 5 ML Anomaly Detection & Temporal Feature Extraction
        self.feature_extractor = SecurityFeatureExtractor(
            window_seconds=int(self.camera_config.get('ml_feature_window_seconds', 60))
        )
        self.ml_inference_interval = float(self.camera_config.get('ml_inference_interval_seconds', 10.0))
        self.rule_risk_weight = float(self.camera_config.get('rule_risk_weight', 0.70))
        self.ml_risk_weight = float(self.camera_config.get('ml_risk_weight', 0.30))
        self._latest_ml_analysis = None
        self._last_ml_inference_time = 0.0

        # State management
        self._status = 'OFFLINE'  # OFFLINE, STARTING, RUNNING, STOPPING, ERROR
        self._error_message = None
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Frame buffers
        self._latest_frame = None
        self._latest_jpeg = None
        self._frame_condition = threading.Condition(self._lock)

        # Telemetry metrics
        self._start_time = None
        self._frame_count = 0
        self._measured_fps = 0.0
        self._last_frame_time = None
        self._fps_history = []

    @property
    def status(self):
        with self._lock:
            return self._status

    @property
    def error_message(self):
        with self._lock:
            return self._error_message

    def _resolve_source(self):
        """Resolves source string to OpenCV VideoCapture input format."""
        if self.source_type == 'webcam' or self.source.isdigit():
            try:
                return int(self.source)
            except ValueError:
                return 0

        # Video file or RTSP stream
        if self.source.startswith(('rtsp://', 'http://', 'https://')):
            return self.source

        # Local file path resolution
        source_path = Path(self.source)
        if not source_path.is_absolute():
            # Check relative to project_root
            source_path = (self.project_root / self.source).resolve()

        # Path traversal guard: verify that path stays within allowed workspace
        try:
            source_path.relative_to(self.project_root)
        except ValueError:
            logger.warning(f"Rejected path traversal attempt for camera {self.camera_id}: {self.source}")
            raise ValueError(f"Unsafe video filepath outside project directory: {self.source}")

        if not source_path.exists():
            raise FileNotFoundError(f"Video file not found: {source_path}")

        return str(source_path)

    def start(self):
        """Starts background video capture thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning(f"Camera {self.camera_id} is already running.")
                return True

            self._status = 'STARTING'
            self._error_message = None
            self._stop_event.clear()
            self._frame_count = 0
            self._start_time = time.time()
            self._last_frame_time = None
            self._fps_history = []

            self._thread = threading.Thread(
                target=self._worker_loop,
                name=f"CameraWorker-{self.camera_id}",
                daemon=True
            )
            self._thread.start()
            logger.info(f"Started video processor thread for camera #{self.camera_id} ({self.name}).")
            return True

    def stop(self, timeout=2.5):
        """Stops background video capture thread gracefully and flushes tracking/engine state."""
        with self._lock:
            if self._status in ('OFFLINE', 'STOPPING'):
                return True
            self._status = 'STOPPING'

        self._stop_event.set()

        # Wake up any waiting stream readers
        with self._lock:
            self._frame_condition.notify_all()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        with self._lock:
            self._status = 'OFFLINE'
            self._thread = None
            self.tracker.reset()
            self._active_tracks = []
            self._zone_eval_result = {
                'entries': [],
                'exits': [],
                'occupancy': {},
                'violations': []
            }
            security_engine.reset_camera(self.camera_id)
            self.feature_extractor.reset_camera(self.camera_id)
            self._latest_ml_analysis = None
            logger.info(f"Camera #{self.camera_id} worker stopped cleanly.")
        return True

    def restart(self, timeout=2.5):
        """Restarts the processor."""
        self.stop(timeout=timeout)
        time.sleep(0.1)
        return self.start()

    def _worker_loop(self):
        """Internal background thread loop."""
        cap = None
        try:
            resolved_source = self._resolve_source()
            logger.info(f"Opening camera #{self.camera_id} source: {resolved_source}")
            
            cap = cv2.VideoCapture(resolved_source)
            if not cap.isOpened():
                raise RuntimeError(f"OpenCV could not open video source: {self.source}")

            # Verify first frame read
            ret, test_frame = cap.read()
            if not ret or test_frame is None:
                raise RuntimeError(f"Could not read initial frame from camera source: {self.source}")

            with self._lock:
                self._status = 'RUNNING'

            # Frame pacing interval
            frame_interval = 1.0 / self.target_fps
            fps_window_start = time.time()
            fps_frame_counter = 0

            while not self._stop_event.is_set():
                loop_start = time.time()

                ret, frame = cap.read()
                if not ret or frame is None:
                    # Check for video file looping
                    if self.source_type == 'video_file' and self.loop_demo:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            logger.error(f"Failed to loop video for camera #{self.camera_id}")
                            break
                    else:
                        logger.info(f"End of stream reached for camera #{self.camera_id}")
                        break

                # 1. Resize frame if needed
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)

                # 2. Measure actual FPS
                now = time.time()
                fps_frame_counter += 1
                elapsed = now - fps_window_start
                if elapsed >= 1.0:
                    self._measured_fps = round(fps_frame_counter / elapsed, 1)
                    fps_frame_counter = 0
                    fps_window_start = now

                # 3. Hook for Phase 3 Detection (modular extension)
                processed_frame = self.process_frame(frame)

                # 4. Render system video overlays
                self._draw_overlay(processed_frame)

                # 5. JPEG encode for streaming
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
                success, jpeg_bytes = cv2.imencode('.jpg', processed_frame, encode_param)

                if success:
                    with self._lock:
                        self._latest_frame = processed_frame
                        self._latest_jpeg = jpeg_bytes.tobytes()
                        self._frame_count += 1
                        self._last_frame_time = now
                        self._frame_condition.notify_all()

                # 6. Throttle frame rate
                work_time = time.time() - loop_start
                sleep_time = frame_interval - work_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            with self._lock:
                self._status = 'ERROR'
                self._error_message = str(e)
            logger.error(f"Error in camera #{self.camera_id} processor: {e}")
            try:
                socketio.emit('camera_status_changed', {
                    'camera_id': self.camera_id,
                    'status': 'ERROR',
                    'fps': 0.0,
                    'error': str(e)
                })
            except Exception as se:
                logger.debug(f"Socket emit error skipped: {se}")
        finally:
            if cap is not None:
                cap.release()
            final_status = 'OFFLINE'
            with self._lock:
                if self._status != 'ERROR':
                    self._status = 'OFFLINE'
                final_status = self._status
                self._frame_condition.notify_all()
            if final_status == 'OFFLINE':
                try:
                    socketio.emit('camera_status_changed', {
                        'camera_id': self.camera_id,
                        'status': 'OFFLINE',
                        'fps': 0.0
                    })
                except Exception as se:
                    logger.debug(f"Socket emit offline skipped: {se}")
            logger.info(f"Camera #{self.camera_id} capture loop exited.")

    def _get_detector(self):
        """Retrieves or creates shared ObjectDetector instance."""
        if self._detector is None:
            self._detector = get_detector(config=self.detector_config)
        return self._detector

    def process_frame(self, frame):
        """
        Applies real-time AI Object Detection (Phase 3),
        Centroid/IoU Object Tracking (Phase 4),
        Spatial Zone Analysis, and Security Rules (Phase 4).
        """
        if not self.enable_detection or frame is None:
            return frame

        self._detection_counter += 1
        detector = self._get_detector()
        now = time.time()

        # 1. Run YOLO inference every inference_interval frames
        is_detection_frame = (
            self._detection_counter % self.inference_interval == 0
            or self._latest_detections['timestamp'] is None
        )

        if is_detection_frame:
            try:
                det_result = detector.detect(frame)
                with self._lock:
                    self._latest_detections = det_result
            except Exception as e:
                logger.error(f"Detection failed for camera #{self.camera_id}: {e}")

        with self._lock:
            current_detections = self._latest_detections
            raw_dets = current_detections.get('detections', [])

        # 2. Phase 4 Object Tracking
        person_dets = [d for d in raw_dets if d.get('class_name') == 'person']

        if is_detection_frame:
            active_tracks = self.tracker.update(person_dets, frame_time=now)
            with self._lock:
                self._active_tracks = active_tracks
        else:
            with self._lock:
                active_tracks = list(self._active_tracks)

        # 3. Spatial Zone Evaluation
        zone_eval = self.zone_evaluator.evaluate_tracks(
            active_tracks, frame_width=self.width, frame_height=self.height
        )
        with self._lock:
            self._zone_eval_result = zone_eval

        # 3.5 Phase 5 Feature Extraction & Temporal Observation Buffering
        operating_hours = self.camera_config.get('operating_hours', {'start': '08:00', 'end': '20:00'})
        is_after_hours = is_time_after_hours(datetime.now(), operating_hours)

        self.feature_extractor.update(
            camera_id=self.camera_id,
            tracks=active_tracks,
            raw_detections=raw_dets,
            zone_eval_result=zone_eval,
            current_dt=datetime.now(timezone.utc),
            is_after_hours=is_after_hours
        )

        # Periodic ML Inference (every ml_inference_interval seconds)
        if (now - self._last_ml_inference_time) >= self.ml_inference_interval:
            self._last_ml_inference_time = now
            try:
                feat_vec = self.feature_extractor.extract_features(self.camera_id)
                ml_res = ml_service.analyze_camera(self.camera_id, feat_vec)
                with self._lock:
                    self._latest_ml_analysis = ml_res
            except Exception as e:
                logger.error(f"Periodic ML inference error on camera #{self.camera_id}: {e}")

        # 4. Security Engine Evaluation & Automated Event Persistence with Risk Fusion
        if is_detection_frame and active_tracks:
            try:
                sec_events = security_engine.evaluate(
                    camera_id=self.camera_id,
                    camera_name=self.name,
                    camera_location=self.location,
                    tracks=active_tracks,
                    zone_eval_result=zone_eval,
                    camera_config=self.camera_config,
                    raw_detections=raw_dets
                )

                if sec_events:
                    # Retrieve or trigger fresh ML analysis for risk fusion
                    with self._lock:
                        current_ml = self._latest_ml_analysis

                    if not current_ml:
                        try:
                            feat_vec = self.feature_extractor.extract_features(self.camera_id)
                            current_ml = ml_service.analyze_camera(self.camera_id, feat_vec)
                            with self._lock:
                                self._latest_ml_analysis = current_ml
                        except Exception:
                            current_ml = None

                    ml_score = current_ml.get('anomaly_score', 0.0) if current_ml else 0.0
                    is_anom = current_ml.get('is_anomaly', False) if current_ml else False
                    ml_indics = current_ml.get('indicators', []) if current_ml else []
                    ml_feats = current_ml.get('features', {}) if current_ml else {}

                    # Fuse deterministic rule risk with ML anomaly score
                    for event_dict in sec_events:
                        rule_score = float(event_dict.get('risk_score', 50.0))
                        final_score, final_level = ml_service.fuse_risk(
                            rule_risk=rule_score,
                            ml_risk=ml_score,
                            rule_weight=self.rule_risk_weight,
                            ml_weight=self.ml_risk_weight
                        )

                        # Update event with fused risk
                        event_dict['risk_score'] = final_score
                        event_dict['risk_level'] = final_level

                        # Enrich event metadata with full ML breakdown
                        event_dict['metadata']['rule_risk_score'] = rule_score
                        event_dict['metadata']['ml_risk_score'] = ml_score
                        event_dict['metadata']['final_risk_score'] = final_score
                        event_dict['metadata']['ml_anomaly'] = is_anom
                        event_dict['metadata']['ml_indicators'] = ml_indics
                        event_dict['metadata']['ml_feature_vector'] = ml_feats

                        # Persist candidate security events and generate automated alerts
                        EventService.record_security_event(event_dict, frame=frame, app=self.app)

            except Exception as e:
                logger.error(f"SecurityEngine evaluation error on camera #{self.camera_id}: {e}")

        # 5. Emit throttled Socket.IO update (~3 Hz)
        if now - self._last_socket_emit_time >= 0.33:
            self._last_socket_emit_time = now
            self._emit_telemetry_socket(current_detections, active_tracks, zone_eval)

        # 6. Render HUD: Zones, Tracking Boxes, Bag Overlays
        breached_zones = {v['zone'].id for v in zone_eval.get('violations', [])}
        for trk in active_tracks:
            if trk.is_loitering and trk.current_zone_id:
                breached_zones.add(trk.current_zone_id)

        # Render zones with breach highlights
        frame = self.zone_evaluator.draw_zones(frame, active_violation_zone_ids=breached_zones)

        # Render detected bags / objects
        bag_classes = {'backpack', 'handbag', 'suitcase'}
        for det in raw_dets:
            if det.get('class_name') in bag_classes:
                bx1, by1, bx2, by2 = det.get('bbox', [0, 0, 0, 0])
                conf = det.get('confidence', 0.0)
                cls_name = det.get('class_name', 'item')
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 215, 255), 2)
                tag = f"{cls_name.upper()} {int(conf * 100)}%"
                (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
                cv2.rectangle(frame, (bx1, max(0, by1 - th - 6)), (bx1 + tw + 6, max(th + 6, by1)), (0, 215, 255), -1)
                cv2.putText(frame, tag, (bx1 + 3, max(th + 2, by1 - 3)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.36, (15, 15, 20), 1, cv2.LINE_AA)

        # Render tracked persons with tracking IDs, status, trajectory, and foot contact point
        frame = self._draw_tracks(frame, active_tracks)

        return frame

    def _draw_tracks(self, frame, tracks):
        """
        Renders Phase 4 Tracking HUD:
        - Track trajectory trails
        - Ground contact reference point marker (feet)
        - Color-coded bounding box depending on security state:
            - Normal/Unrestricted: Cyan (255, 200, 0)
            - Inside Warning: Yellow/Amber (0, 215, 255)
            - Inside Restricted: Red (0, 0, 230)
            - Loitering: Orange (0, 140, 255)
        - High-contrast tag label: e.g. "Person #17 [RESTRICTED]" or "Person #17 [LOITERING 32s]"
        """
        for trk in tracks:
            x1, y1, x2, y2 = trk.bbox

            # Trajectory trail (last 15 points)
            pts = trk.trajectory[-15:]
            if len(pts) >= 2:
                for i in range(1, len(pts)):
                    alpha = i / len(pts)
                    color_bgr = (int(255 * alpha), int(200 * alpha), 0)
                    cv2.line(frame, tuple(pts[i - 1]), tuple(pts[i]), color_bgr, 1, cv2.LINE_AA)

            # Ground contact reference point marker (feet)
            gx, gy = trk.bottom_center
            cv2.circle(frame, (gx, gy), 3, (0, 255, 180), -1, cv2.LINE_AA)

            # Determine color & badge text
            if trk.is_loitering:
                box_color = (0, 140, 255)  # Orange
                status_badge = f" [LOITERING {int(trk.time_in_current_zone)}s]"
            elif trk.current_zone_id:
                z_name = trk.current_zone_name or "ZONE"
                box_color = (0, 0, 230)  # Red / restricted
                status_badge = f" [{z_name[:12].upper()}]"
            else:
                box_color = (255, 200, 0)  # Cyan
                status_badge = f" {int(trk.confidence * 100)}%"

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

            # Draw corner accents for high-tech HUD look
            corner_len = min(12, max(4, (x2 - x1) // 4), max(4, (y2 - y1) // 4))
            # Top-left
            cv2.line(frame, (x1, y1), (x1 + corner_len, y1), (255, 255, 255), 2)
            cv2.line(frame, (x1, y1), (x1, y1 + corner_len), (255, 255, 255), 2)
            # Bottom-right
            cv2.line(frame, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), 2)
            cv2.line(frame, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), 2)

            # Label badge
            label = f"Person #{trk.track_id}{status_badge}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.38
            (tw, th), _ = cv2.getTextSize(label, font, font_scale, 1)

            by = max(th + 4, y1 - 4)
            cv2.rectangle(frame, (x1, by - th - 4), (x1 + tw + 6, by + 2), box_color, -1)
            cv2.putText(frame, label, (x1 + 3, by - 2), font, font_scale, (15, 15, 20), 1, cv2.LINE_AA)

        return frame

    def _emit_telemetry_socket(self, det_result, active_tracks, zone_eval):
        """Emits detection and tracking update via SocketIO."""
        try:
            tracks_summary = [t.to_dict() for t in active_tracks]
            zones_summary = self.zone_evaluator.get_zones_summary(zone_eval.get('occupancy', {}))

            socketio.emit('detection_update', {
                'camera_id': self.camera_id,
                'name': self.name,
                'location': self.location,
                'person_count': len(active_tracks),
                'object_count': det_result.get('object_count', 0),
                'total_count': len(active_tracks) + det_result.get('object_count', 0),
                'inference_ms': det_result.get('inference_ms', 0.0),
                'detections': det_result.get('detections', []),
                'tracks': tracks_summary,
                'zones': zones_summary,
                'active_violations_count': len(zone_eval.get('violations', [])),
                'timestamp': det_result.get('timestamp')
            })
        except Exception as e:
            logger.debug(f"SocketIO detection emit skipped: {e}")

    def _draw_overlay(self, frame):
        """Draws standard Healthcare SOC telemetry and security headers onto frame."""
        h, w = frame.shape[:2]

        # 1. Top Bar Overlay
        cv2.rectangle(frame, (0, 0), (w, 24), (11, 15, 25), -1)

        # System title
        cv2.putText(frame, "MEDGUARD AI - HEALTHCARE SOC", (10, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 200, 255), 1, cv2.LINE_AA)

        # Camera Identification
        cam_info = f"CAM #{self.camera_id}: {self.name[:24]}"
        cv2.putText(frame, cam_info, (w // 2 - 50, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1, cv2.LINE_AA)

        # Status badge (LIVE or DEMO)
        mode_label = "DEMO" if (self.source_type == 'video_file' or self.loop_demo) else "LIVE"
        badge_color = (0, 210, 120) if mode_label == "LIVE" else (255, 170, 0)
        cv2.putText(frame, f"[{mode_label}]", (w - 70, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, badge_color, 1, cv2.LINE_AA)

        # ML Anomaly Detection Status HUD Badge
        with self._lock:
            ml_data = self._latest_ml_analysis
        if ml_data:
            ml_sc = ml_data.get('anomaly_score', 0.0)
            is_anom = ml_data.get('is_anomaly', False)
            ml_label = f"ML:{ml_sc:.0f}% [{'ANOMALY' if is_anom else 'NORMAL'}]"
            ml_color = (0, 0, 255) if is_anom else (255, 180, 0)
            cv2.putText(frame, ml_label, (w - 235, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, ml_color, 1, cv2.LINE_AA)

        # 2. Bottom Status Bar Overlay
        cv2.rectangle(frame, (0, h - 22), (w, h), (11, 15, 25), -1)

        # FPS, AI latency, Tracking counts & Violations
        with self._lock:
            p_cnt = len(self._active_tracks)
            o_cnt = self._latest_detections.get('object_count', 0)
            inf_ms = self._latest_detections.get('inference_ms', 0.0)
            viol_cnt = len(self._zone_eval_result.get('violations', []))

        ai_status = f"FPS:{self._measured_fps:.1f} | AI:{inf_ms:.0f}ms | TRKS:{p_cnt} | OBJS:{o_cnt} | VIOL:{viol_cnt}"
        cv2.putText(frame, ai_status, (10, h - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 220, 255), 1, cv2.LINE_AA)

        # Timestamp
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, time_str, (w - 155, h - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1, cv2.LINE_AA)

    def get_latest_frame(self):
        """Returns a copy of the latest BGR frame."""
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_latest_jpeg(self):
        """Returns latest encoded JPEG bytes."""
        with self._lock:
            return self._latest_jpeg

    def get_latest_detections(self):
        """Returns latest detection results in a thread-safe dict."""
        with self._lock:
            return dict(self._latest_detections)

    def get_tracks(self):
        """Returns JSON-serializable active tracks."""
        with self._lock:
            return [t.to_dict() for t in self._active_tracks]

    def get_zones(self):
        """Returns JSON-serializable zones with current occupancy."""
        with self._lock:
            return self.zone_evaluator.get_zones_summary(self._zone_eval_result.get('occupancy', {}))

    def get_ml_analysis(self):
        """Returns latest ML anomaly analysis result or computes on demand."""
        with self._lock:
            if self._latest_ml_analysis:
                return dict(self._latest_ml_analysis)
        feat_vec = self.feature_extractor.extract_features(self.camera_id)
        res = ml_service.analyze_camera(self.camera_id, feat_vec)
        with self._lock:
            self._latest_ml_analysis = res
        return res

    def get_telemetry(self):
        """Returns runtime telemetry metrics."""
        with self._lock:
            uptime = int(time.time() - self._start_time) if self._start_time and self._status == 'RUNNING' else 0
            p_cnt = len(self._active_tracks) if self._active_tracks else self._latest_detections.get('person_count', 0)
            viol_cnt = len(self._zone_eval_result.get('violations', [])) if self._zone_eval_result else 0
            return {
                'camera_id': self.camera_id,
                'name': self.name,
                'location': self.location,
                'source': self.source,
                'source_type': self.source_type,
                'status': self._status,
                'error_message': self._error_message,
                'fps': self._measured_fps,
                'target_fps': self.target_fps,
                'frame_count': self._frame_count,
                'uptime_seconds': uptime,
                'resolution': [self.width, self.height],
                'person_count': p_cnt,
                'object_count': self._latest_detections.get('object_count', 0),
                'total_detections': p_cnt + self._latest_detections.get('object_count', 0),
                'ai_inference_ms': self._latest_detections.get('inference_ms', 0.0),
                'detections': self._latest_detections.get('detections', []),
                'detection_enabled': self.enable_detection,
                'tracked_persons': p_cnt,
                'zones_count': len(self.zone_evaluator.zones),
                'active_zone_violations': viol_cnt,
                'ml_analysis': self._latest_ml_analysis,
                'ml_status': ml_service.status,
                'ml_risk_score': self._latest_ml_analysis.get('anomaly_score', 0.0) if self._latest_ml_analysis else 0.0,
                'ml_is_anomaly': self._latest_ml_analysis.get('is_anomaly', False) if self._latest_ml_analysis else False
            }

    def generate_mjpeg(self):
        """
        Generator yielding MJPEG multipart chunks for HTTP streaming.
        Terminates cleanly when processor stops or client disconnects.
        """
        boundary = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
        last_yielded_count = -1
        interval = 1.0 / self.target_fps

        while not self._stop_event.is_set():
            jpeg_bytes = None
            with self._lock:
                # Wait for new frame
                if self._latest_jpeg is not None and self._frame_count != last_yielded_count:
                    jpeg_bytes = self._latest_jpeg
                    last_yielded_count = self._frame_count
                else:
                    self._frame_condition.wait(timeout=interval)
                    if self._latest_jpeg is not None and self._frame_count != last_yielded_count:
                        jpeg_bytes = self._latest_jpeg
                        last_yielded_count = self._frame_count

            if jpeg_bytes is not None:
                yield boundary + jpeg_bytes + b'\r\n'
            elif self._status in ('OFFLINE', 'ERROR'):
                break

            time.sleep(interval * 0.5)
