import cv2
import numpy as np
from app.utils import setup_logger

logger = setup_logger('zones')

# Color palette for zone boundaries and overlays (BGR format)
ZONE_COLORS = {
    'CRITICAL': (0, 0, 230),    # Bright Red
    'HIGH': (0, 140, 255),       # Vibrant Amber / Orange
    'MEDIUM': (0, 215, 255),     # Yellow / Gold
    'LOW': (0, 200, 100),        # Green / Emerald
    'DEFAULT': (180, 180, 180)   # Light Gray
}


def is_point_in_polygon_raycasting(point, polygon):
    """
    Standard Ray Casting algorithm for point-in-polygon determination.
    Compatible with any list of (x, y) vertices.
    """
    x, y = point
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


class Zone:
    """Represents a defined physical security zone on a camera feed."""

    def __init__(self, zone_dict):
        self.id = str(zone_dict.get('id', 'default_zone'))
        self.name = str(zone_dict.get('name', 'Restricted Area'))
        self.type = str(zone_dict.get('type', 'restricted')).lower()  # 'restricted', 'warning', 'monitored'
        self.severity = str(zone_dict.get('severity', 'HIGH')).upper()
        self.enabled = bool(zone_dict.get('enabled', True))
        self.raw_polygon = zone_dict.get('polygon', [])
        self.color = ZONE_COLORS.get(self.severity, ZONE_COLORS['DEFAULT'])

    def get_pixel_polygon(self, width, height):
        """
        Converts normalized (0.0 to 1.0) or raw coordinates into absolute integer pixels.
        Returns:
            np.ndarray: Array of shape (N, 1, 2) suitable for OpenCV polygon functions.
        """
        if not self.raw_polygon or len(self.raw_polygon) < 3:
            return None

        # Check if coordinates are normalized (< 1.0)
        is_normalized = all(
            0.0 <= pt[0] <= 1.0 and 0.0 <= pt[1] <= 1.0
            for pt in self.raw_polygon
        )

        pts = []
        for pt in self.raw_polygon:
            if is_normalized:
                px = int(pt[0] * width)
                py = int(pt[1] * height)
            else:
                px = int(pt[0])
                py = int(pt[1])
            pts.append([px, py])

        return np.array(pts, dtype=np.int32)

    def contains_point(self, point, width=640, height=480):
        """
        Determines whether point (x, y) is inside the zone polygon.
        Uses OpenCV cv2.pointPolygonTest with fallback to raycasting.
        """
        pixel_poly = self.get_pixel_polygon(width, height)
        if pixel_poly is None:
            return False

        try:
            # cv2.pointPolygonTest returns > 0 (inside), 0 (on edge), < 0 (outside)
            res = cv2.pointPolygonTest(pixel_poly, (float(point[0]), float(point[1])), False)
            return res >= 0
        except Exception:
            # Fallback to ray casting
            pts_list = [(int(p[0]), int(p[1])) for p in pixel_poly]
            return is_point_in_polygon_raycasting(point, pts_list)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'severity': self.severity,
            'enabled': self.enabled,
            'polygon': self.raw_polygon
        }


class ZoneEvaluator:
    """
    Evaluates spatial relationships between tracked physical entities and configured camera zones.
    Detects entry transitions, exits, continuous loitering durations, and crowd occupancy.
    """

    def __init__(self, zones_config=None):
        self.zones = []
        self.update_zones(zones_config or [])

    def update_zones(self, zones_config):
        """Updates internal zone definitions."""
        self.zones = []
        for z_data in zones_config:
            if isinstance(z_data, dict):
                self.zones.append(Zone(z_data))
        logger.debug(f"ZoneEvaluator loaded {len(self.zones)} zones.")

    def evaluate_tracks(self, tracks, frame_width=640, frame_height=480, timestamp=None):
        """
        Tests tracks against enabled zones using bottom-center (feet ground contact) point.

        Returns:
            dict: {
                'entries': list of {'track': TrackedObject, 'zone': Zone},
                'exits': list of {'track': TrackedObject, 'zone_id': str, 'zone_name': str, 'duration': float},
                'occupancy': dict[str, list[TrackedObject]],
                'violations': list of {'track': TrackedObject, 'zone': Zone}
            }
        """
        entries = []
        exits = []
        occupancy = {z.id: [] for z in self.zones}
        violations = []

        for track in tracks:
            # Standing person reference point is bottom_center (ground contact point)
            test_pt = track.bottom_center

            matched_zone = None
            for zone in self.zones:
                if not zone.enabled:
                    continue

                if zone.contains_point(test_pt, width=frame_width, height=frame_height):
                    matched_zone = zone
                    occupancy[zone.id].append(track)
                    break  # Associate with first containing zone

            # Update track state and check transition
            new_zone_id = matched_zone.id if matched_zone else None
            new_zone_name = matched_zone.name if matched_zone else None
            is_entry, is_exit, prev_zone_id = track.set_zone(new_zone_id, new_zone_name, timestamp=timestamp)

            if is_entry and matched_zone:
                entries.append({
                    'track': track,
                    'zone': matched_zone
                })

            if is_exit and prev_zone_id:
                prev_zone = next((z for z in self.zones if z.id == prev_zone_id), None)
                exits.append({
                    'track': track,
                    'zone_id': prev_zone_id,
                    'zone_name': prev_zone.name if prev_zone else prev_zone_id,
                    'duration': track.time_in_current_zone
                })

            if matched_zone and matched_zone.type in ('restricted', 'warning'):
                violations.append({
                    'track': track,
                    'zone': matched_zone
                })

        return {
            'entries': entries,
            'exits': exits,
            'occupancy': occupancy,
            'violations': violations
        }

    def draw_zones(self, frame, active_violation_zone_ids=None):
        """
        Renders configured zone boundaries and occupancy banners onto video frame.

        Args:
            frame (np.ndarray): BGR video frame.
            active_violation_zone_ids (set, optional): Set of zone IDs currently breached.
        """
        if frame is None or not self.zones:
            return frame

        h, w = frame.shape[:2]
        violation_set = set(active_violation_zone_ids or [])

        # Create overlay layer for translucent violation highlights
        overlay = frame.copy()
        has_translucent_draw = False

        for zone in self.zones:
            if not zone.enabled:
                continue

            pixel_poly = zone.get_pixel_polygon(w, h)
            if pixel_poly is None:
                continue

            is_active_violation = zone.id in violation_set
            color = (0, 0, 240) if is_active_violation else zone.color
            thickness = 3 if is_active_violation else 2

            # If breached, fill polygon with semi-transparent tint
            if is_active_violation:
                cv2.fillPoly(overlay, [pixel_poly], (0, 0, 220))
                has_translucent_draw = True

            # Draw outer polygon boundary
            cv2.polylines(frame, [pixel_poly], isClosed=True, color=color, thickness=thickness, lineType=cv2.LINE_AA)

            # Draw zone badge header
            first_pt = pixel_poly[0]
            bx, by = int(first_pt[0]), max(20, int(first_pt[1]) - 6)

            tag_text = f"[{zone.type.upper()}] {zone.name}"
            if is_active_violation:
                tag_text += " ! BREACH"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.36
            (tw, th), _ = cv2.getTextSize(tag_text, font, font_scale, 1)

            cv2.rectangle(frame, (bx, by - th - 4), (bx + tw + 6, by + 2), color, -1)
            cv2.putText(frame, tag_text, (bx + 3, by - 2), font, font_scale, (10, 15, 25), 1, cv2.LINE_AA)

        # Blend semi-transparent highlight if active violations exist
        if has_translucent_draw:
            cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)

        return frame

    def get_zones_summary(self, occupancy_map=None):
        """Returns JSON-serializable zone information including occupancy."""
        occ = occupancy_map or {}
        summary = []
        for z in self.zones:
            tracks_in_zone = occ.get(z.id, [])
            summary.append({
                'id': z.id,
                'name': z.name,
                'type': z.type,
                'severity': z.severity,
                'enabled': z.enabled,
                'occupant_count': len(tracks_in_zone),
                'occupant_track_ids': [t.track_id for t in tracks_in_zone]
            })
        return summary
