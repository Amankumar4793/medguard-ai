import time
import math
import threading
from datetime import datetime, time as dtime
from app.utils import setup_logger

logger = setup_logger('security_engine')


def is_time_after_hours(current_dt, hours_cfg):
    """
    Determines whether current_dt is outside normal operating hours.
    hours_cfg: dict with 'start' and 'end' as 'HH:MM' strings (e.g. {'start': '08:00', 'end': '20:00'})
    Supports overnight operational spans (e.g. start: 22:00, end: 06:00).
    """
    if not hours_cfg or 'start' not in hours_cfg or 'end' not in hours_cfg:
        return False

    try:
        sh, sm = [int(x) for x in hours_cfg['start'].split(':')]
        eh, em = [int(x) for x in hours_cfg['end'].split(':')]
        start_time = dtime(sh, sm)
        end_time = dtime(eh, em)
        cur_time = current_dt.time()

        if start_time <= end_time:
            # Normal day hours (e.g. 08:00 to 20:00)
            return not (start_time <= cur_time <= end_time)
        else:
            # Overnight shift (e.g. 20:00 to 06:00)
            return not (cur_time >= start_time or cur_time <= end_time)
    except Exception as e:
        logger.warning(f"Error checking after-hours schedule: {e}")
        return False


def calculate_risk_level(risk_score):
    """Maps continuous 0-100 risk score to discrete risk categories."""
    score = max(0.0, min(100.0, float(risk_score)))
    if score >= 75.0:
        return 'CRITICAL'
    elif score >= 50.0:
        return 'HIGH'
    elif score >= 25.0:
        return 'MEDIUM'
    return 'LOW'


class SecurityEngine:
    """
    Central Rule-Based Security Engine.
    Evaluates tracked physical entities against configured zones, temporal operating hours,
    crowd density thresholds, loitering limits, and repeated entry patterns.
    Produces explainable risk scores (0-100) and deduplicated candidate security events.
    """

    def __init__(self, default_cooldown=20):
        self.default_cooldown = int(default_cooldown)
        self._lock = threading.Lock()

        # In-memory deduplication and persistence tracking
        # Key: (camera_id, rule_type, target_key) -> float timestamp of last fired event
        self._cooldown_cache = {}

        # Crowd persistence tracking
        # Key: (camera_id, zone_id) -> float timestamp when crowd was first detected
        self._crowd_start_times = {}

        # Repeated entry tracking
        # Key: (camera_id, track_id) -> list of entry timestamps [t1, t2, ...]
        self._track_entry_history = {}

        # Unattended object tracking
        # Key: (camera_id, obj_hash) -> {'first_seen': float, 'last_seen': float, 'center': (x,y), 'class_name': str, 'bbox': []}
        self._stationary_objects = {}

    def reset_camera(self, camera_id):
        """Flushes in-memory rule and cooldown state when a camera stops or restarts."""
        with self._lock:
            self._cooldown_cache = {k: v for k, v in self._cooldown_cache.items() if k[0] != camera_id}
            self._crowd_start_times = {k: v for k, v in self._crowd_start_times.items() if k[0] != camera_id}
            self._track_entry_history = {k: v for k, v in self._track_entry_history.items() if k[0] != camera_id}
            self._stationary_objects = {k: v for k, v in self._stationary_objects.items() if k[0] != camera_id}
            logger.info(f"SecurityEngine state flushed for camera #{camera_id}.")

    def _is_on_cooldown(self, camera_id, rule_type, target_key, now, cooldown_seconds=None):
        """Checks if a rule for a specific target is currently in its cooldown window."""
        cd = cooldown_seconds if cooldown_seconds is not None else self.default_cooldown
        cache_key = (camera_id, rule_type, str(target_key))
        last_time = self._cooldown_cache.get(cache_key)
        if last_time is not None and (now - last_time) < cd:
            return True
        return False

    def _set_cooldown(self, camera_id, rule_type, target_key, now):
        """Records fired event timestamp into cooldown cache."""
        cache_key = (camera_id, rule_type, str(target_key))
        self._cooldown_cache[cache_key] = now

    def evaluate(self, camera_id, camera_name, camera_location, tracks,
                 zone_eval_result, camera_config, raw_detections=None, now_dt=None):
        """
        Executes modular security rules against current frame tracking and zone telemetry.

        Returns:
            list[dict]: List of candidate security events ready for persistence.
        """
        now = time.time()
        current_dt = now_dt or datetime.now()
        events = []

        cfg = camera_config or {}
        cooldown_sec = int(cfg.get('alert_cooldown_seconds', self.default_cooldown))
        operating_hours = cfg.get('operating_hours', {'start': '08:00', 'end': '20:00'})
        loitering_limit = int(cfg.get('loitering_threshold_seconds', 30))
        crowd_threshold = int(cfg.get('crowd_threshold', 4))
        crowd_duration = int(cfg.get('crowd_duration_seconds', 10))
        repeated_threshold = int(cfg.get('repeated_entry_threshold', 3))
        repeated_window = int(cfg.get('repeated_entry_window_seconds', 300))

        with self._lock:
            # -------------------------------------------------------------
            # Rule 1: Zone Intrusion (Genuine Zone Entry Transition)
            # -------------------------------------------------------------
            for entry in zone_eval_result.get('entries', []):
                track = entry['track']
                zone = entry['zone']

                if zone.type in ('restricted', 'warning'):
                    is_after_hours = is_time_after_hours(current_dt, operating_hours)

                    # Calculate explainable risk score
                    base_risk = 55.0 if zone.type == 'restricted' else 35.0
                    severity_bonus = {'CRITICAL': 25.0, 'HIGH': 15.0, 'MEDIUM': 5.0, 'LOW': 0.0}.get(zone.severity, 10.0)
                    after_hours_bonus = 20.0 if is_after_hours else 0.0
                    conf_factor = max(0.7, min(1.0, track.confidence))

                    raw_score = (base_risk + severity_bonus + after_hours_bonus) * conf_factor
                    risk_score = round(max(0.0, min(100.0, raw_score)), 1)
                    risk_level = calculate_risk_level(risk_score)

                    # Deduplication check: 1 intrusion event per track per zone entry
                    target_key = f"{track.track_id}_{zone.id}"
                    if not self._is_on_cooldown(camera_id, 'ZONE_INTRUSION', target_key, now, cooldown_sec):
                        self._set_cooldown(camera_id, 'ZONE_INTRUSION', target_key, now)

                        desc = (
                            f"Individual (Person #{track.track_id}) entered {zone.severity.lower()}-risk "
                            f"{zone.type} zone: {zone.name}."
                        )
                        if is_after_hours:
                            desc += f" [AFTER-HOURS VIOLATION outside {operating_hours.get('start')}-{operating_hours.get('end')}]"

                        event_type = 'after_hours_intrusion' if is_after_hours else 'restricted_area_intrusion'
                        events.append({
                            'camera_id': camera_id,
                            'camera_name': camera_name,
                            'camera_location': camera_location,
                            'event_type': event_type,
                            'risk_score': risk_score,
                            'risk_level': risk_level,
                            'confidence': track.confidence,
                            'description': desc,
                            'timestamp': current_dt,
                            'metadata': {
                                'track_id': track.track_id,
                                'zone_id': zone.id,
                                'zone_name': zone.name,
                                'zone_type': zone.type,
                                'bbox': track.bbox,
                                'center': track.center,
                                'is_after_hours': is_after_hours,
                                'rule_name': 'zone_intrusion'
                            }
                        })

                        # Record for repeated entry tracking
                        hist_key = (camera_id, track.track_id)
                        if hist_key not in self._track_entry_history:
                            self._track_entry_history[hist_key] = []
                        self._track_entry_history[hist_key].append(now)

            # -------------------------------------------------------------
            # Rule 2: Zone Exit Audit Event
            # -------------------------------------------------------------
            for exit_info in zone_eval_result.get('exits', []):
                track = exit_info['track']
                zone_id = exit_info['zone_id']
                zone_name = exit_info['zone_name']
                duration = exit_info['duration']

                target_key = f"{track.track_id}_{zone_id}"
                if not self._is_on_cooldown(camera_id, 'ZONE_EXIT', target_key, now, cooldown_seconds=5):
                    self._set_cooldown(camera_id, 'ZONE_EXIT', target_key, now)

                    events.append({
                        'camera_id': camera_id,
                        'camera_name': camera_name,
                        'camera_location': camera_location,
                        'event_type': 'zone_exit',
                        'risk_score': 15.0,
                        'risk_level': 'LOW',
                        'confidence': track.confidence,
                        'description': f"Person #{track.track_id} exited {zone_name} after {duration:.1f} seconds.",
                        'timestamp': current_dt,
                        'metadata': {
                            'track_id': track.track_id,
                            'zone_id': zone_id,
                            'zone_name': zone_name,
                            'duration_seconds': duration,
                            'rule_name': 'zone_exit'
                        }
                    })

            # -------------------------------------------------------------
            # Rule 3: Loitering Detection
            # -------------------------------------------------------------
            for track in tracks:
                if track.current_zone_id is not None:
                    time_in_zone = track.time_in_current_zone
                    if time_in_zone >= loitering_limit and not track.loitering_alerted:
                        track.is_loitering = True
                        track.loitering_alerted = True

                        target_key = f"{track.track_id}_{track.current_zone_id}"
                        if not self._is_on_cooldown(camera_id, 'LOITERING', target_key, now, cooldown_sec * 2):
                            self._set_cooldown(camera_id, 'LOITERING', target_key, now)

                            risk_score = min(95.0, 50.0 + min(35.0, (time_in_zone - loitering_limit) * 1.5))
                            risk_level = calculate_risk_level(risk_score)

                            desc = (
                                f"Loitering violation: Person #{track.track_id} remained stationary in "
                                f"{track.current_zone_name} for {time_in_zone:.0f} seconds "
                                f"(configured limit: {loitering_limit}s)."
                            )

                            events.append({
                                'camera_id': camera_id,
                                'camera_name': camera_name,
                                'camera_location': camera_location,
                                'event_type': 'loitering',
                                'risk_score': round(risk_score, 1),
                                'risk_level': risk_level,
                                'confidence': track.confidence,
                                'description': desc,
                                'timestamp': current_dt,
                                'metadata': {
                                    'track_id': track.track_id,
                                    'zone_id': track.current_zone_id,
                                    'zone_name': track.current_zone_name,
                                    'duration_seconds': time_in_zone,
                                    'loitering_limit': loitering_limit,
                                    'rule_name': 'loitering'
                                }
                            })

            # -------------------------------------------------------------
            # Rule 4: Crowd Density Detection
            # -------------------------------------------------------------
            occupancy = zone_eval_result.get('occupancy', {})
            for zone_id, occupant_tracks in occupancy.items():
                crowd_key = (camera_id, zone_id)
                count = len(occupant_tracks)

                if count >= crowd_threshold:
                    if crowd_key not in self._crowd_start_times:
                        self._crowd_start_times[crowd_key] = now

                    elapsed_crowd = now - self._crowd_start_times[crowd_key]
                    if elapsed_crowd >= crowd_duration:
                        # Trigger crowd density event if not on cooldown
                        if not self._is_on_cooldown(camera_id, 'CROWD_DETECTED', zone_id, now, cooldown_sec * 2):
                                self._set_cooldown(camera_id, 'CROWD_DETECTED', zone_id, now)

                                risk_score = min(90.0, 55.0 + (count - crowd_threshold) * 8.0)
                                risk_level = calculate_risk_level(risk_score)

                                z_name = occupant_tracks[0].current_zone_name if occupant_tracks else zone_id
                                desc = (
                                    f"High crowd density detected in {z_name}: {count} individuals present "
                                    f"(threshold: {crowd_threshold} persons, sustained for {elapsed_crowd:.0f}s)."
                                )

                                events.append({
                                    'camera_id': camera_id,
                                    'camera_name': camera_name,
                                    'camera_location': camera_location,
                                    'event_type': 'crowd_density',
                                    'risk_score': round(risk_score, 1),
                                    'risk_level': risk_level,
                                    'confidence': 0.90,
                                    'description': desc,
                                    'timestamp': current_dt,
                                    'metadata': {
                                        'zone_id': zone_id,
                                        'zone_name': z_name,
                                        'occupant_count': count,
                                        'crowd_threshold': crowd_threshold,
                                        'occupant_track_ids': [t.track_id for t in occupant_tracks],
                                        'rule_name': 'crowd_density'
                                    }
                                })
                else:
                    # Reset crowd timer when crowd disperses below threshold
                    if crowd_key in self._crowd_start_times:
                        del self._crowd_start_times[crowd_key]

            # -------------------------------------------------------------
            # Rule 5: Repeated Zone Entry
            # -------------------------------------------------------------
            for track in tracks:
                hist_key = (camera_id, track.track_id)
                if hist_key in self._track_entry_history:
                    # Filter history to sliding window
                    recent_entries = [t for t in self._track_entry_history[hist_key] if (now - t) <= repeated_window]
                    self._track_entry_history[hist_key] = recent_entries

                    if len(recent_entries) >= repeated_threshold:
                        target_key = f"{track.track_id}_repeat"
                        if not self._is_on_cooldown(camera_id, 'REPEATED_ENTRY', target_key, now, cooldown_sec * 3):
                            self._set_cooldown(camera_id, 'REPEATED_ENTRY', target_key, now)

                            events.append({
                                'camera_id': camera_id,
                                'camera_name': camera_name,
                                'camera_location': camera_location,
                                'event_type': 'repeated_zone_entry',
                                'risk_score': 72.0,
                                'risk_level': 'HIGH',
                                'confidence': track.confidence,
                                'description': (
                                    f"Repeated perimeter ingress: Person #{track.track_id} entered restricted zones "
                                    f"{len(recent_entries)} times within {repeated_window // 60} minutes."
                                ),
                                'timestamp': current_dt,
                                'metadata': {
                                    'track_id': track.track_id,
                                    'entry_count': len(recent_entries),
                                    'window_seconds': repeated_window,
                                    'rule_name': 'repeated_zone_entry'
                                }
                            })

            # -------------------------------------------------------------
            # Rule 6: Potential Unattended / Abandoned Object
            # -------------------------------------------------------------
            if raw_detections:
                bag_classes = {'backpack', 'handbag', 'suitcase'}
                current_bags = [d for d in raw_detections if d.get('class_name') in bag_classes]

                # Match with tracked stationary objects
                for bag in current_bags:
                    bx, by = bag.get('center', [0, 0])
                    b_cls = bag.get('class_name')
                    obj_key = f"{b_cls}_{int(bx/40)}_{int(by/40)}"  # Spatial binning
                    full_key = (camera_id, obj_key)

                    if full_key not in self._stationary_objects:
                        self._stationary_objects[full_key] = {
                            'first_seen': now,
                            'last_seen': now,
                            'center': [bx, by],
                            'class_name': b_cls,
                            'bbox': bag.get('bbox', [0, 0, 0, 0])
                        }
                    else:
                        self._stationary_objects[full_key]['last_seen'] = now

                # Check stationary duration and person proximity
                stale_keys = []
                for full_key, bag_state in self._stationary_objects.items():
                    if full_key[0] != camera_id:
                        continue
                    if (now - bag_state['last_seen']) > 4.0:
                        stale_keys.append(full_key)
                        continue

                    stationary_time = now - bag_state['first_seen']
                    if stationary_time >= 35.0:  # 35 seconds stationary
                        # Check distance to closest person track
                        closest_dist = float('inf')
                        for track in tracks:
                            dist = math.hypot(track.center[0] - bag_state['center'][0],
                                              track.center[1] - bag_state['center'][1])
                            closest_dist = min(closest_dist, dist)

                        # If no person is within 120 pixels of the stationary bag
                        if closest_dist > 120:
                            target_key = full_key[1]
                            if not self._is_on_cooldown(camera_id, 'ABANDONED_OBJECT', target_key, now, cooldown_sec * 3):
                                self._set_cooldown(camera_id, 'ABANDONED_OBJECT', target_key, now)

                                events.append({
                                    'camera_id': camera_id,
                                    'camera_name': camera_name,
                                    'camera_location': camera_location,
                                    'event_type': 'potential_abandoned_object',
                                    'risk_score': 62.0,
                                    'risk_level': 'MEDIUM',
                                    'confidence': 0.85,
                                    'description': (
                                        f"Potential unattended object: {bag_state['class_name'].capitalize()} "
                                        f"stationary for {stationary_time:.0f}s with no personnel nearby."
                                    ),
                                    'timestamp': current_dt,
                                    'metadata': {
                                        'object_class': bag_state['class_name'],
                                        'center': bag_state['center'],
                                        'bbox': bag_state['bbox'],
                                        'stationary_seconds': round(stationary_time, 1),
                                        'nearest_person_distance': round(closest_dist, 1),
                                        'rule_name': 'abandoned_object'
                                    }
                                })

                for sk in stale_keys:
                    del self._stationary_objects[sk]

        return events


# Global security engine singleton
security_engine = SecurityEngine()
