import time
import math
import threading
from datetime import datetime
from app.utils import setup_logger

logger = setup_logger('tracker')


def compute_iou(boxA, boxB):
    """
    Computes Intersection-over-Union (IoU) between two bounding boxes.
    Format: [x1, y1, x2, y2]
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_width = max(0, xB - xA)
    inter_height = max(0, yB - yA)
    inter_area = inter_width * inter_height

    boxA_area = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    boxB_area = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])

    union_area = float(boxA_area + boxB_area - inter_area)
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def euclidean_distance(ptA, ptB):
    """Calculates Euclidean distance between two (x, y) points."""
    return math.hypot(ptA[0] - ptB[0], ptA[1] - ptB[1])


class TrackedObject:
    """Represents an active or historical tracked physical entity."""

    def __init__(self, track_id, class_name, confidence, bbox, timestamp=None):
        self.track_id = int(track_id)
        self.class_name = str(class_name).lower()
        self.confidence = float(confidence)
        self.bbox = list(bbox)  # [x1, y1, x2, y2]
        
        # Center & Bottom-Center (reference point for standing ground contact)
        x1, y1, x2, y2 = self.bbox
        self.center = [int((x1 + x2) / 2), int((y1 + y2) / 2)]
        self.bottom_center = [int((x1 + x2) / 2), int(y2)]

        # Temporal lifecycle
        now = timestamp or time.time()
        self.first_seen = now
        self.last_seen = now
        self.duration_seconds = 0.0
        self.missed_frames = 0

        # Trajectory history (last 30 points)
        self.trajectory = [self.center]

        # Spatial zone occupancy state
        self.current_zone_id = None
        self.current_zone_name = None
        self.zone_entry_time = None
        self.zone_history = []  # List of past completed visits
        self.is_loitering = False
        self.loitering_alerted = False

    def update(self, detection, timestamp=None):
        """Updates track with new detection measurements."""
        now = timestamp or time.time()
        self.confidence = float(detection.get('confidence', self.confidence))
        self.bbox = list(detection.get('bbox', self.bbox))
        
        x1, y1, x2, y2 = self.bbox
        new_center = [int((x1 + x2) / 2), int((y1 + y2) / 2)]
        self.center = new_center
        self.bottom_center = [int((x1 + x2) / 2), int(y2)]

        self.last_seen = now
        self.duration_seconds = round(self.last_seen - self.first_seen, 1)
        self.missed_frames = 0

        self.trajectory.append(new_center)
        if len(self.trajectory) > 30:
            self.trajectory.pop(0)

    def mark_missed(self):
        """Increments missed frames counter when detection is missing in current frame."""
        self.missed_frames += 1

    def set_zone(self, zone_id, zone_name=None, timestamp=None):
        """
        Updates zone containment and records zone transition.
        Returns:
            tuple: (is_entry: bool, is_exit: bool, prev_zone_id: str|None)
        """
        now = timestamp or time.time()
        prev_zone_id = self.current_zone_id
        is_entry = False
        is_exit = False

        if zone_id != prev_zone_id:
            # If exiting a previous zone, log visit history
            if prev_zone_id is not None:
                is_exit = True
                entry_t = self.zone_entry_time or self.first_seen
                visit_duration = round(now - entry_t, 1)
                self.zone_history.append({
                    'zone_id': prev_zone_id,
                    'zone_name': self.current_zone_name,
                    'entry_time': entry_t,
                    'exit_time': now,
                    'duration': visit_duration
                })

            # Transition to new zone
            self.current_zone_id = zone_id
            self.current_zone_name = zone_name
            self.is_loitering = False
            self.loitering_alerted = False

            if zone_id is not None:
                is_entry = True
                self.zone_entry_time = now
            else:
                self.zone_entry_time = None

        return is_entry, is_exit, prev_zone_id

    @property
    def time_in_current_zone(self):
        """Returns elapsed seconds spent continuously in current zone."""
        if self.current_zone_id is None or self.zone_entry_time is None:
            return 0.0
        return max(0.0, round(time.time() - self.zone_entry_time, 1))

    def to_dict(self):
        """Returns JSON-serializable dictionary representation."""
        return {
            'track_id': self.track_id,
            'class_name': self.class_name,
            'confidence': round(self.confidence, 3),
            'bbox': self.bbox,
            'center': self.center,
            'bottom_center': self.bottom_center,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'duration_seconds': self.duration_seconds,
            'current_zone_id': self.current_zone_id,
            'current_zone_name': self.current_zone_name,
            'time_in_zone': self.time_in_current_zone,
            'is_loitering': self.is_loitering,
            'missed_frames': self.missed_frames
        }


class CentroidIoUTracker:
    """
    Lightweight, high-performance object tracking engine.
    Combines Intersection-over-Union (IoU) spatial matching with
    centroid Euclidean distance fallback.
    Designed for zero extra dependencies and sub-millisecond CPU execution.
    """

    def __init__(self, max_lost_frames=20, iou_threshold=0.25, distance_threshold=90):
        self.max_lost_frames = int(max_lost_frames)
        self.iou_threshold = float(iou_threshold)
        self.distance_threshold = float(distance_threshold)

        self.tracks = {}  # track_id -> TrackedObject
        self._next_id = 1
        self._lock = threading.Lock()

    def update(self, detections, frame_time=None):
        """
        Associates incoming frame detections with existing active tracks.

        Args:
            detections (list): List of detection dicts with 'bbox', 'class_name', 'confidence'.
            frame_time (float, optional): Timestamp of frame capture.

        Returns:
            list[TrackedObject]: Currently active tracked objects.
        """
        now = frame_time or time.time()

        with self._lock:
            # 1. If no detections are provided, mark all existing tracks as missed
            if not detections:
                for track in list(self.tracks.values()):
                    track.mark_missed()
                self._purge_stale_tracks()
                return self._get_active_tracks()

            # 2. If no tracks currently exist, initialize new tracks for all detections
            if not self.tracks:
                for det in detections:
                    track = TrackedObject(
                        track_id=self._next_id,
                        class_name=det.get('class_name', 'person'),
                        confidence=det.get('confidence', 0.5),
                        bbox=det.get('bbox', [0, 0, 0, 0]),
                        timestamp=now
                    )
                    self.tracks[self._next_id] = track
                    self._next_id += 1
                return self._get_active_tracks()

            # 3. Two-stage Association:
            # Stage A: IoU-based matching
            active_track_ids = list(self.tracks.keys())
            matched_track_ids = set()
            matched_det_indices = set()

            iou_matches = []
            for t_id in active_track_ids:
                t_box = self.tracks[t_id].bbox
                t_cls = self.tracks[t_id].class_name

                for d_idx, det in enumerate(detections):
                    d_box = det.get('bbox', [0, 0, 0, 0])
                    d_cls = det.get('class_name', 'person')

                    # Same class category matching
                    if t_cls == d_cls:
                        iou = compute_iou(t_box, d_box)
                        if iou >= self.iou_threshold:
                            iou_matches.append((iou, t_id, d_idx))

            # Sort matches by highest IoU first (greedy assignment)
            iou_matches.sort(key=lambda x: x[0], reverse=True)
            for iou, t_id, d_idx in iou_matches:
                if t_id not in matched_track_ids and d_idx not in matched_det_indices:
                    self.tracks[t_id].update(detections[d_idx], timestamp=now)
                    matched_track_ids.add(t_id)
                    matched_det_indices.add(d_idx)

            # Stage B: Centroid distance fallback for remaining unmatched items
            unmatched_tracks = [t_id for t_id in active_track_ids if t_id not in matched_track_ids]
            unmatched_dets = [d_idx for d_idx in range(len(detections)) if d_idx not in matched_det_indices]

            dist_matches = []
            for t_id in unmatched_tracks:
                t_center = self.tracks[t_id].center
                t_cls = self.tracks[t_id].class_name

                for d_idx in unmatched_dets:
                    det = detections[d_idx]
                    d_cls = det.get('class_name', 'person')
                    if t_cls == d_cls:
                        d_box = det.get('bbox', [0, 0, 0, 0])
                        d_center = [(d_box[0] + d_box[2]) / 2, (d_box[1] + d_box[3]) / 2]
                        dist = euclidean_distance(t_center, d_center)
                        if dist <= self.distance_threshold:
                            dist_matches.append((dist, t_id, d_idx))

            # Sort by smallest distance first
            dist_matches.sort(key=lambda x: x[0])
            for dist, t_id, d_idx in dist_matches:
                if t_id not in matched_track_ids and d_idx not in matched_det_indices:
                    self.tracks[t_id].update(detections[d_idx], timestamp=now)
                    matched_track_ids.add(t_id)
                    matched_det_indices.add(d_idx)

            # 4. Handle unmatched tracks (mark missed)
            for t_id in active_track_ids:
                if t_id not in matched_track_ids:
                    self.tracks[t_id].mark_missed()

            # 5. Spawn new tracks for remaining unmatched detections
            for d_idx in range(len(detections)):
                if d_idx not in matched_det_indices:
                    det = detections[d_idx]
                    track = TrackedObject(
                        track_id=self._next_id,
                        class_name=det.get('class_name', 'person'),
                        confidence=det.get('confidence', 0.5),
                        bbox=det.get('bbox', [0, 0, 0, 0]),
                        timestamp=now
                    )
                    self.tracks[self._next_id] = track
                    self._next_id += 1

            # 6. Purge stale tracks exceeding max_lost_frames
            self._purge_stale_tracks()

            return self._get_active_tracks()

    def _purge_stale_tracks(self):
        """Removes tracks that have been missed for too many consecutive frames."""
        stale_ids = [t_id for t_id, t in self.tracks.items() if t.missed_frames > self.max_lost_frames]
        for t_id in stale_ids:
            del self.tracks[t_id]

    def get_active_tracks(self):
        """Returns list of active tracks (tolerates minor 2-frame occlusion for display)."""
        with self._lock:
            return [t for t in self.tracks.values() if t.missed_frames <= 2]

    def _get_active_tracks(self):
        """Internal helper returning list of active tracks."""
        return [t for t in self.tracks.values() if t.missed_frames <= 2]

    def reset(self):
        """Flushes all tracks and resets track IDs on camera restart/stop."""
        with self._lock:
            self.tracks.clear()
            self._next_id = 1
            logger.info("CentroidIoUTracker state reset.")

    def get_tracks_summary(self):
        """Returns JSON-serializable list of active tracks."""
        with self._lock:
            return [t.to_dict() for t in self._get_active_tracks()]
