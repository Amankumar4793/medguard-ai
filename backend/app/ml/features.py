import time
import math
import threading
from datetime import datetime, timezone
from collections import deque
from app.utils import setup_logger

logger = setup_logger('ml_features')

FEATURE_NAMES = [
    'persons_detected',
    'unique_tracks',
    'zone_occupancy',
    'restricted_zone_entries',
    'restricted_zone_exits',
    'time_in_restricted_zone',
    'loitering_events',
    'after_hours_activity',
    'crowd_level',
    'repeated_entries',
    'detection_confidence_mean',
    'detection_confidence_min',
    'detection_confidence_max',
    'movement_speed',
    'event_frequency',
    'events_per_minute',
    'activity_hour',
    'day_of_week',
    'camera_activity_level'
]

FEATURE_DESCRIPTIONS = {
    'persons_detected': 'Total number of person detections recorded across the sliding temporal window.',
    'unique_tracks': 'Count of distinct tracked individuals observed within the window.',
    'zone_occupancy': 'Total instantaneous count of people currently inside designated surveillance zones.',
    'restricted_zone_entries': 'Number of discrete ingress transitions into restricted or warning zones.',
    'restricted_zone_exits': 'Number of egress transitions out of restricted or warning zones.',
    'time_in_restricted_zone': 'Maximum dwell time (in seconds) spent by any individual inside a restricted zone.',
    'loitering_events': 'Count of individuals whose stationary presence exceeded the loitering duration cutoff.',
    'after_hours_activity': 'Binary indicator (1.0 or 0.0) indicating activity detected outside standard operational hours.',
    'crowd_level': 'Highest simultaneous person count concentrated within any single surveillance zone.',
    'repeated_entries': 'Count of repeated ingress events performed by individuals previously observed in the area.',
    'detection_confidence_mean': 'Average YOLO detection confidence score across all person detections in the window.',
    'detection_confidence_min': 'Minimum YOLO detection confidence score observed in the window.',
    'detection_confidence_max': 'Maximum YOLO detection confidence score observed in the window.',
    'movement_speed': 'Average estimated movement velocity (pixels/second) across active tracked individuals.',
    'event_frequency': 'Total number of security rule violations triggered within the temporal window.',
    'events_per_minute': 'Normalized frequency of security violations scaled to a 60-second operational rate.',
    'activity_hour': 'Hour of the day (0 to 23) when activity was observed, capturing circadian facility rhythms.',
    'day_of_week': 'Day of the week (0=Monday to 6=Sunday), capturing weekend vs weekday security profiles.',
    'camera_activity_level': 'Composite normalized activity index (0.0 to 1.0) based on overall scene dynamics.'
}


def get_feature_names():
    """Returns the ordered list of all 19 feature names."""
    return list(FEATURE_NAMES)


def get_feature_descriptions():
    """Returns human-readable descriptions for all 19 features."""
    return dict(FEATURE_DESCRIPTIONS)


class SecurityFeatureExtractor:
    """
    Extracts a standardized 19-dimensional temporal feature vector from video surveillance streams.
    Maintains a sliding temporal window of frame-level observations per camera.
    Thread-safe and resilient to empty frames or missing tracking data.
    """

    def __init__(self, window_seconds=60):
        self.window_seconds = int(window_seconds)
        self._lock = threading.Lock()

        # Sliding buffers per camera:
        # camera_id -> deque of dicts: {'timestamp', 'tracks', 'detections', 'entries', 'exits', 'occupancy', 'events'}
        self._camera_windows = {}

        # Last known positions for velocity calculation:
        # (camera_id, track_id) -> (last_time, (cx, cy))
        self._track_velocities = {}

        # Repeated entry count cache per camera:
        # (camera_id, track_id) -> list of entry timestamps
        self._entry_history = {}

    def reset_camera(self, camera_id):
        """Flushes the feature buffer when a camera stops or restarts."""
        with self._lock:
            if camera_id in self._camera_windows:
                self._camera_windows[camera_id].clear()
            self._track_velocities = {k: v for k, v in self._track_velocities.items() if k[0] != camera_id}
            self._entry_history = {k: v for k, v in self._entry_history.items() if k[0] != camera_id}
            logger.debug(f"Feature buffer cleared for camera #{camera_id}.")

    def update(self, camera_id, tracks, raw_detections=None, zone_eval_result=None,
               sec_events=None, current_dt=None, is_after_hours=False):
        """
        Appends a frame-level observation snapshot to the camera's sliding temporal window.

        Args:
            camera_id (int): Identifier of the monitored camera.
            tracks (list): List of active TrackedObject instances.
            raw_detections (list, optional): Raw detections from YOLO detector.
            zone_eval_result (dict, optional): Zone evaluator output dict (entries, exits, occupancy).
            sec_events (list, optional): Security events raised in this frame.
            current_dt (datetime, optional): Observation timestamp.
            is_after_hours (bool, optional): Whether facility is in after-hours mode.
        """
        now = time.time()
        obs_dt = current_dt or datetime.now(timezone.utc)
        dets = raw_detections or []
        zone_eval = zone_eval_result or {'entries': [], 'exits': [], 'occupancy': {}, 'violations': []}
        events = sec_events or []

        # Calculate instantaneous track velocities
        current_speeds = []
        with self._lock:
            for track in (tracks or []):
                t_key = (camera_id, track.track_id)
                cx, cy = track.center
                if t_key in self._track_velocities:
                    prev_time, (prev_cx, prev_cy) = self._track_velocities[t_key]
                    dt = now - prev_time
                    if 0.01 < dt < 2.0:
                        dist = math.hypot(cx - prev_cx, cy - prev_cy)
                        speed = dist / dt  # pixels per second
                        current_speeds.append(speed)
                self._track_velocities[t_key] = (now, (cx, cy))

            # Record repeated entries
            for entry in zone_eval.get('entries', []):
                trk = entry.get('track')
                if trk:
                    h_key = (camera_id, trk.track_id)
                    if h_key not in self._entry_history:
                        self._entry_history[h_key] = []
                    self._entry_history[h_key].append(now)

            # Clean stale velocity tracking keys
            if len(self._track_velocities) > 500:
                self._track_velocities = {
                    k: v for k, v in self._track_velocities.items()
                    if (now - v[0]) < (self.window_seconds * 2)
                }

            # Clean stale entry history
            for h_key in list(self._entry_history.keys()):
                self._entry_history[h_key] = [
                    t for t in self._entry_history[h_key]
                    if (now - t) < (self.window_seconds * 5)
                ]
                if not self._entry_history[h_key]:
                    del self._entry_history[h_key]

            # Compute integer occupancy counts
            occ_map = zone_eval.get('occupancy', {})
            total_zone_occ = sum(len(v) if isinstance(v, (list, tuple)) else int(v) for v in occ_map.values())
            zone_occ_counts = {k: (len(v) if isinstance(v, (list, tuple)) else int(v)) for k, v in occ_map.items()}

            # Append observation snapshot
            if camera_id not in self._camera_windows:
                self._camera_windows[camera_id] = deque()

            window = self._camera_windows[camera_id]
            window.append({
                'timestamp': now,
                'datetime': obs_dt,
                'person_count': len([d for d in dets if d.get('class_name') == 'person']) if dets else len(tracks or []),
                'track_ids': [t.track_id for t in (tracks or [])],
                'confidences': [d.get('confidence', 0.8) for d in dets if d.get('class_name') == 'person'],
                'zone_occupancy': total_zone_occ,
                'zone_occupancy_by_zone': zone_occ_counts,
                'restricted_entries': len([
                    e for e in zone_eval.get('entries', [])
                    if e.get('zone') and getattr(e['zone'], 'type', '') in ('restricted', 'warning')
                ]),
                'restricted_exits': len([
                    e for e in zone_eval.get('exits', [])
                ]),
                'max_restricted_dwell': max(
                    [t.time_in_current_zone for t in (tracks or []) if t.current_zone_id is not None] or [0.0]
                ),
                'loitering_count': len([
                    t for t in (tracks or [])
                    if t.time_in_current_zone >= 25.0 and t.current_zone_id is not None
                ]),
                'is_after_hours': 1.0 if is_after_hours else 0.0,
                'speeds': current_speeds,
                'event_count': len(events)
            })

            # Evict observations older than sliding window
            cutoff = now - self.window_seconds
            while window and window[0]['timestamp'] < cutoff:
                window.popleft()

    def extract_features(self, camera_id, current_dt=None):
        """
        Aggregates observations across the sliding window and computes the 19-dimensional feature vector.

        Returns:
            list[float]: 19 numerical feature values in standard order.
        """
        now_dt = current_dt or datetime.now(timezone.utc)

        with self._lock:
            window = self._camera_windows.get(camera_id)
            if not window:
                # Return neutral baseline vector for quiescent camera
                return self._default_feature_vector(now_dt)

            total_obs = len(window)
            all_confidences = []
            all_speeds = []
            all_track_ids = set()
            total_restricted_entries = 0
            total_restricted_exits = 0
            max_restricted_dwell = 0.0
            total_loitering_events = 0
            after_hours_sum = 0.0
            max_crowd_level = 0
            total_event_count = 0
            latest_occupancy = 0
            total_person_detections = 0

            for obs in window:
                total_person_detections += obs.get('person_count', 0)
                all_track_ids.update(obs.get('track_ids', []))
                all_confidences.extend(obs.get('confidences', []))
                all_speeds.extend(obs.get('speeds', []))
                total_restricted_entries += obs.get('restricted_entries', 0)
                total_restricted_exits += obs.get('restricted_exits', 0)
                max_restricted_dwell = max(max_restricted_dwell, obs.get('max_restricted_dwell', 0.0))
                total_loitering_events += obs.get('loitering_count', 0)
                after_hours_sum += obs.get('is_after_hours', 0.0)
                total_event_count += obs.get('event_count', 0)

                # Track peak single-zone crowd level
                zone_occ = obs.get('zone_occupancy_by_zone', {})
                if zone_occ:
                    max_crowd_level = max(max_crowd_level, max(zone_occ.values()))

            # Use latest observation for current occupancy
            if window:
                latest_occupancy = window[-1].get('zone_occupancy', 0)

            # Repeated entries count in this camera
            repeated_count = 0
            for (cid, trk_id), times in self._entry_history.items():
                if cid == camera_id and len(times) > 1:
                    repeated_count += (len(times) - 1)

            # Feature 1: persons_detected (average or aggregate in window)
            persons_detected = float(total_person_detections)

            # Feature 2: unique_tracks
            unique_tracks = float(len(all_track_ids))

            # Feature 3: zone_occupancy
            zone_occupancy = float(latest_occupancy)

            # Feature 4: restricted_zone_entries
            restricted_zone_entries = float(total_restricted_entries)

            # Feature 5: restricted_zone_exits
            restricted_zone_exits = float(total_restricted_exits)

            # Feature 6: time_in_restricted_zone
            time_in_restricted_zone = float(round(max_restricted_dwell, 1))

            # Feature 7: loitering_events (deduplicated by observation rate)
            # Normalize by observations: if an individual loiters for 10 frames, count as 1
            loitering_events = float(min(len(all_track_ids), total_loitering_events // max(1, total_obs // 5) if total_obs > 5 else total_loitering_events))

            # Feature 8: after_hours_activity (ratio of window spent in after-hours mode)
            after_hours_activity = 1.0 if (after_hours_sum / max(1, total_obs)) > 0.5 else 0.0

            # Feature 9: crowd_level
            crowd_level = float(max_crowd_level)

            # Feature 10: repeated_entries
            repeated_entries = float(repeated_count)

            # Features 11-13: detection confidences
            if all_confidences:
                conf_mean = float(round(sum(all_confidences) / len(all_confidences), 3))
                conf_min = float(round(min(all_confidences), 3))
                conf_max = float(round(max(all_confidences), 3))
            else:
                conf_mean = 0.85
                conf_min = 0.80
                conf_max = 0.90

            # Feature 14: movement_speed (average px/sec)
            movement_speed = float(round(sum(all_speeds) / len(all_speeds), 1)) if all_speeds else 15.0

            # Feature 15: event_frequency
            event_frequency = float(total_event_count)

            # Feature 16: events_per_minute
            elapsed_min = max(0.1, self.window_seconds / 60.0)
            events_per_minute = float(round(total_event_count / elapsed_min, 2))

            # Feature 17: activity_hour
            activity_hour = float(now_dt.hour)

            # Feature 18: day_of_week (0=Mon, 6=Sun)
            day_of_week = float(now_dt.weekday())

            # Feature 19: camera_activity_level (0.0 to 1.0 composite)
            # Derived from unique tracks, entries, and movement
            density_score = min(1.0, unique_tracks / 8.0)
            entry_score = min(1.0, (restricted_zone_entries + 1.0) / 4.0)
            speed_score = min(1.0, movement_speed / 80.0)
            camera_activity_level = float(round(0.4 * density_score + 0.4 * entry_score + 0.2 * speed_score, 3))

            return [
                persons_detected,
                unique_tracks,
                zone_occupancy,
                restricted_zone_entries,
                restricted_zone_exits,
                time_in_restricted_zone,
                loitering_events,
                after_hours_activity,
                crowd_level,
                repeated_entries,
                conf_mean,
                conf_min,
                conf_max,
                movement_speed,
                event_frequency,
                events_per_minute,
                activity_hour,
                day_of_week,
                camera_activity_level
            ]

    def extract_features_dict(self, camera_id, current_dt=None):
        """Returns the 19 features mapped to their canonical key names."""
        vec = self.extract_features(camera_id, current_dt=current_dt)
        return {name: val for name, val in zip(FEATURE_NAMES, vec)}

    def _default_feature_vector(self, now_dt):
        """Default quiescent feature vector when no activity is buffered."""
        return [
            0.0,   # persons_detected
            0.0,   # unique_tracks
            0.0,   # zone_occupancy
            0.0,   # restricted_zone_entries
            0.0,   # restricted_zone_exits
            0.0,   # time_in_restricted_zone
            0.0,   # loitering_events
            0.0,   # after_hours_activity
            0.0,   # crowd_level
            0.0,   # repeated_entries
            0.85,  # detection_confidence_mean
            0.80,  # detection_confidence_min
            0.90,  # detection_confidence_max
            0.0,   # movement_speed
            0.0,   # event_frequency
            0.0,   # events_per_minute
            float(now_dt.hour),
            float(now_dt.weekday()),
            0.0    # camera_activity_level
        ]
