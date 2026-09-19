import numpy as np
import pytest
from app.detection.zones import Zone, ZoneEvaluator, is_point_in_polygon_raycasting
from app.detection.tracker import TrackedObject


def test_zone_polygon_normalization_and_containment():
    # Normalized square from (0.2, 0.2) to (0.8, 0.8)
    z_dict = {
        'id': 'zone_icu',
        'name': 'ICU Sterile Airlock',
        'type': 'restricted',
        'severity': 'HIGH',
        'polygon': [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
    }
    zone = Zone(z_dict)
    assert zone.id == 'zone_icu'
    assert zone.type == 'restricted'
    assert zone.severity == 'HIGH'

    # Width: 640, Height: 480
    # Expected pixel bounds: x in [128, 512], y in [96, 384]
    assert zone.contains_point((320, 240), width=640, height=480) is True   # Center: inside
    assert zone.contains_point((50, 50), width=640, height=480) is False    # Top-left: outside
    assert zone.contains_point((600, 400), width=640, height=480) is False  # Bottom-right: outside


def test_raycasting_point_in_polygon():
    polygon = [(100, 100), (300, 100), (300, 300), (100, 300)]
    assert is_point_in_polygon_raycasting((200, 200), polygon) is True
    assert is_point_in_polygon_raycasting((50, 50), polygon) is False
    assert is_point_in_polygon_raycasting((350, 200), polygon) is False


def test_zone_evaluator_bottom_center_ground_contact():
    """
    Verifies that standing person reference point is bottom_center (feet ground contact point).
    Head/torso overlapping the polygon must NOT trigger false intrusion alarms.
    """
    zones_cfg = [{
        'id': 'zone_pharma',
        'name': 'Pharmacy Safe',
        'type': 'restricted',
        'severity': 'CRITICAL',
        'polygon': [[200, 200], [400, 200], [400, 400], [200, 400]]
    }]
    evaluator = ZoneEvaluator(zones_cfg)

    # Person standing ABOVE the zone:
    # Bbox: x1=250, y1=100, x2=350, y2=190
    # Bottom center is (300, 190) -> OUTSIDE the zone (zone starts at y=200)
    # Even though x is within [200, 400], feet are outside.
    trk_outside = TrackedObject(track_id=1, class_name="person", confidence=0.9, bbox=[250, 100, 350, 190])
    res_outside = evaluator.evaluate_tracks([trk_outside], frame_width=640, frame_height=480)
    assert len(res_outside['entries']) == 0
    assert len(res_outside['violations']) == 0
    assert trk_outside.current_zone_id is None

    # Person steps FORWARD: feet cross into zone at y=210
    # Bbox: x1=250, y1=120, x2=350, y2=210
    # Bottom center is (300, 210) -> INSIDE zone
    trk_outside.update({'bbox': [250, 120, 350, 210]})
    res_inside = evaluator.evaluate_tracks([trk_outside], frame_width=640, frame_height=480)
    assert len(res_inside['entries']) == 1
    assert res_inside['entries'][0]['zone'].id == 'zone_pharma'
    assert trk_outside.current_zone_id == 'zone_pharma'


def test_zone_transitions_entry_and_exit():
    zones_cfg = [{
        'id': 'zone_lab',
        'name': 'Biosafety Lab 3',
        'type': 'restricted',
        'severity': 'HIGH',
        'polygon': [[100, 100], [300, 100], [300, 300], [100, 300]]
    }]
    evaluator = ZoneEvaluator(zones_cfg)

    trk = TrackedObject(track_id=5, class_name="person", confidence=0.85, bbox=[150, 150, 250, 250])

    # 1. Entry
    res1 = evaluator.evaluate_tracks([trk], frame_width=640, frame_height=480, timestamp=100.0)
    assert len(res1['entries']) == 1
    assert len(res1['exits']) == 0
    assert trk.current_zone_id == 'zone_lab'
    assert len(res1['occupancy']['zone_lab']) == 1

    # 2. Stay inside
    res2 = evaluator.evaluate_tracks([trk], frame_width=640, frame_height=480, timestamp=105.0)
    assert len(res2['entries']) == 0  # No redundant entry transition
    assert len(res2['exits']) == 0

    # 3. Exit zone
    trk.update({'bbox': [400, 400, 500, 500]})  # Moved outside
    res3 = evaluator.evaluate_tracks([trk], frame_width=640, frame_height=480, timestamp=115.0)
    assert len(res3['exits']) == 1
    assert res3['exits'][0]['zone_id'] == 'zone_lab'
    assert trk.current_zone_id is None


def test_draw_zones_rendering():
    zones_cfg = [{
        'id': 'zone_test',
        'name': 'Test Zone',
        'type': 'warning',
        'severity': 'MEDIUM',
        'polygon': [[50, 50], [200, 50], [200, 200], [50, 200]]
    }]
    evaluator = ZoneEvaluator(zones_cfg)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Draw normal
    rendered = evaluator.draw_zones(frame)
    assert rendered.shape == (480, 640, 3)

    # Draw with active breach highlight
    rendered_breach = evaluator.draw_zones(frame, active_violation_zone_ids={'zone_test'})
    assert rendered_breach.shape == (480, 640, 3)
