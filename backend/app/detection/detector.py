import time
import threading
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from app.utils import setup_logger

logger = setup_logger('object_detector')

# Default target classes for healthcare security surveillance
HEALTHCARE_TARGET_CLASSES = {'person', 'backpack', 'handbag', 'suitcase'}

# Palette for high-contrast SOC bounding boxes (BGR format)
CLASS_COLORS = {
    'person': (255, 200, 30),      # Vivid Cyan / Teal in BGR
    'backpack': (30, 160, 255),    # High-vis Amber / Orange
    'handbag': (220, 100, 255),    # Soft Magenta
    'suitcase': (50, 220, 120),    # Emerald
}
DEFAULT_BOX_COLOR = (200, 200, 200)


class ObjectDetector:
    """
    Real-time Object Detection engine powered by Ultralytics YOLO.
    Optimized for healthcare security surveillance, detecting personnel,
    visitors, patients, and unattended bags/objects.
    """

    def __init__(self, model_name='yolov8n.pt', confidence=0.45, iou=0.45,
                 device='cpu', imgsz=640, target_classes=None, model_dir=None):
        self.model_name = model_name
        self.confidence = float(confidence)
        self.iou = float(iou)
        self.device = str(device).lower()
        self.imgsz = int(imgsz)
        self.target_classes = set(target_classes) if target_classes else HEALTHCARE_TARGET_CLASSES

        self.model = None
        self.is_loaded = False
        self._lock = threading.Lock()

        # Telemetry metrics
        self._total_inferences = 0
        self._total_inference_ms = 0.0
        self._avg_inference_ms = 0.0
        self._last_inference_ms = 0.0

        # Model storage directory
        if model_dir:
            self.model_path = Path(model_dir) / self.model_name
        else:
            self.model_path = self.model_name

        self._initialize_model()

    def _initialize_model(self):
        """Loads YOLO weights and executes a warmup inference."""
        try:
            from ultralytics import YOLO

            logger.info(f"Loading YOLO model '{self.model_name}' on device '{self.device}'...")
            self.model = YOLO(str(self.model_path))

            # Validate / fallback device
            if self.device != 'cpu':
                try:
                    import torch
                    if not torch.cuda.is_available():
                        logger.warning(f"CUDA device '{self.device}' requested but unavailable. Falling back to 'cpu'.")
                        self.device = 'cpu'
                except Exception:
                    self.device = 'cpu'

            # Warmup inference to eliminate initial latency
            self._warmup()
            self.is_loaded = True
            logger.info(f"YOLO model '{self.model_name}' initialized successfully (Device: {self.device}).")

        except Exception as e:
            logger.error(f"Failed to initialize YOLO model: {e}")
            self.is_loaded = False
            self.model = None

    def _warmup(self):
        """Executes a single dummy inference on a blank frame to warm up PyTorch/YOLO."""
        if self.model is None:
            return
        try:
            dummy_frame = np.zeros((320, 320, 3), dtype=np.uint8)
            self.model.predict(
                source=dummy_frame,
                conf=self.confidence,
                iou=self.iou,
                device=self.device,
                imgsz=320,
                verbose=False
            )
            logger.debug("YOLO warmup completed.")
        except Exception as e:
            logger.warning(f"YOLO warmup skipped or failed: {e}")

    def detect(self, frame, custom_classes=None, min_confidence=None):
        """
        Runs object detection on a single BGR OpenCV frame.

        Args:
            frame (np.ndarray): BGR video frame.
            custom_classes (set/list, optional): Override target classes.
            min_confidence (float, optional): Override confidence threshold.

        Returns:
            dict: Structured detection summary containing detections list and counts.
        """
        if frame is None or not self.is_loaded or self.model is None:
            return {
                'detections': [],
                'person_count': 0,
                'object_count': 0,
                'total_count': 0,
                'inference_ms': 0.0,
                'timestamp': datetime.now().isoformat()
            }

        conf_thresh = float(min_confidence) if min_confidence is not None else self.confidence
        classes_filter = set(custom_classes) if custom_classes is not None else self.target_classes

        t_start = time.perf_counter()
        detections = []
        person_count = 0

        with self._lock:
            try:
                results = self.model.predict(
                    source=frame,
                    conf=conf_thresh,
                    iou=self.iou,
                    device=self.device,
                    imgsz=self.imgsz,
                    verbose=False
                )

                if results and len(results) > 0:
                    result = results[0]
                    boxes = result.boxes

                    if boxes is not None and len(boxes) > 0:
                        names = result.names or {}
                        xyxy = boxes.xyxy.cpu().numpy()
                        confs = boxes.conf.cpu().numpy()
                        cls_ids = boxes.cls.cpu().numpy()

                        for i in range(len(xyxy)):
                            cls_id = int(cls_ids[i])
                            class_name = str(names.get(cls_id, cls_id)).lower()
                            confidence = float(confs[i])

                            # Filter to monitored healthcare target classes
                            if classes_filter and class_name not in classes_filter:
                                continue

                            x1, y1, x2, y2 = [int(v) for v in xyxy[i]]
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            area = int((x2 - x1) * (y2 - y1))
                            is_person = (class_name == 'person')

                            if is_person:
                                person_count += 1

                            detections.append({
                                'class_id': cls_id,
                                'class_name': class_name,
                                'confidence': round(confidence, 3),
                                'bbox': [x1, y1, x2, y2],
                                'center': [center_x, center_y],
                                'area': area,
                                'is_person': is_person
                            })

            except Exception as e:
                logger.error(f"Inference error during detect(): {e}")

        t_end = time.perf_counter()
        inference_ms = round((t_end - t_start) * 1000, 2)

        # Update telemetry
        self._total_inferences += 1
        self._total_inference_ms += inference_ms
        self._last_inference_ms = inference_ms
        self._avg_inference_ms = round(self._total_inference_ms / self._total_inferences, 2)

        return {
            'detections': detections,
            'person_count': person_count,
            'object_count': len(detections) - person_count,
            'total_count': len(detections),
            'inference_ms': inference_ms,
            'timestamp': datetime.now().isoformat()
        }

    def draw_detections(self, frame, detection_result, show_labels=True, show_conf=True):
        """
        Draws high-contrast bounding boxes, centroids, and labels on frame in-place.

        Args:
            frame (np.ndarray): BGR video frame to draw on.
            detection_result (dict or list): Either detect() output dict or list of detection items.
            show_labels (bool): Whether to render class text labels.
            show_conf (bool): Whether to include confidence percentage.

        Returns:
            np.ndarray: The modified frame.
        """
        if frame is None:
            return frame

        if isinstance(detection_result, dict):
            detections = detection_result.get('detections', [])
        elif isinstance(detection_result, list):
            detections = detection_result
        else:
            detections = []

        h, w = frame.shape[:2]

        for det in detections:
            bbox = det.get('bbox')
            if not bbox or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            # Clamp to frame boundaries
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w - 1))
            y2 = max(0, min(y2, h - 1))

            cls_name = det.get('class_name', 'object')
            conf = det.get('confidence', 0.0)
            color = CLASS_COLORS.get(cls_name, DEFAULT_BOX_COLOR)

            # Draw outer high-contrast bounding box (2px border)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

            # Draw corner accents for high-tech SOC HUD aesthetic
            corner_len = min(12, int((x2 - x1) * 0.2), int((y2 - y1) * 0.2))
            if corner_len > 3:
                # Top-Left
                cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, 3, cv2.LINE_AA)
                # Top-Right
                cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, 3, cv2.LINE_AA)
                # Bottom-Left
                cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, 3, cv2.LINE_AA)
                # Bottom-Right
                cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, 3, cv2.LINE_AA)
                cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, 3, cv2.LINE_AA)

            # Draw centroid crosshair
            cx, cy = det.get('center', (int((x1 + x2) / 2), int((y1 + y2) / 2)))
            cv2.circle(frame, (cx, cy), 3, color, -1, cv2.LINE_AA)

            # Render label tag
            if show_labels:
                label = cls_name.upper()
                if show_conf:
                    label = f"{label} {int(conf * 100)}%"

                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.38
                thickness = 1
                (txt_w, txt_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

                # Position label tag above box if room, otherwise inside
                tag_y2 = y1 if (y1 - txt_h - 6) >= 24 else y1 + txt_h + 6
                tag_y1 = tag_y2 - txt_h - 4
                tag_x2 = min(w - 1, x1 + txt_w + 6)

                # Filled badge background
                cv2.rectangle(frame, (x1, tag_y1), (tag_x2, tag_y2), color, -1)
                # Dark text for contrast against vibrant badge
                cv2.putText(frame, label, (x1 + 3, tag_y2 - 3), font, font_scale, (10, 15, 25), thickness, cv2.LINE_AA)

        return frame

    def get_telemetry(self):
        """Returns runtime performance and operational diagnostics."""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'confidence': self.confidence,
            'iou': self.iou,
            'image_size': self.imgsz,
            'target_classes': list(self.target_classes),
            'is_loaded': self.is_loaded,
            'total_inferences': self._total_inferences,
            'last_inference_ms': self._last_inference_ms,
            'avg_inference_ms': self._avg_inference_ms
        }


# Global singleton cache
_detector_instance = None
_detector_lock = threading.Lock()


def get_detector(config=None, model_name=None, confidence=None, iou=None, device=None):
    """
    Thread-safe factory / singleton accessor for the shared ObjectDetector.
    Ensures model weights are loaded once in memory.
    """
    global _detector_instance
    with _detector_lock:
        if _detector_instance is None:
            cfg = config or {}
            m_name = model_name or cfg.get('YOLO_MODEL') or 'yolov8n.pt'
            conf = confidence if confidence is not None else cfg.get('YOLO_CONFIDENCE', 0.45)
            iou_val = iou if iou is not None else cfg.get('YOLO_IOU', 0.45)
            dev = device or cfg.get('YOLO_DEVICE') or 'cpu'
            imgsz = cfg.get('YOLO_IMAGE_SIZE', 640)
            targets = cfg.get('TARGET_CLASSES')
            m_dir = cfg.get('MODEL_DIR')

            _detector_instance = ObjectDetector(
                model_name=m_name,
                confidence=conf,
                iou=iou_val,
                device=dev,
                imgsz=imgsz,
                target_classes=targets,
                model_dir=m_dir
            )
        return _detector_instance


def reset_detector():
    """Resets the singleton instance (useful for testing or reloading weights)."""
    global _detector_instance
    with _detector_lock:
        _detector_instance = None
