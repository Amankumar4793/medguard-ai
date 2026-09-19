import time
import pytest
from app.detection.tracker import TrackedObject, CentroidIoUTracker, compute_iou, euclidean_distance


def test_tracked_object_lifecycle():
    now = time.time()
    bbox = [100, 100, 200, 300]
    track = TrackedObject(track_id=1, class_name="person", confidence=0.88, bbox=bbox, timestamp=now)

    assert track.track_id == 1
    assert track.class_name == "person"
    assert track.confidence == 0.88
    assert track.bbox == [100, 100, 200, 300]
    assert track.center == [150, 200]
    assert track.bottom_center == [150, 300]
    assert len(track.trajectory) == 1
    assert track.missed_frames == 0
    assert track.current_zone_id is None

    # Update with new detection
    new_bbox = [110, 105, 210, 305]
    track.update({'bbox': new_bbox, 'confidence': 0.92}, timestamp=now + 1.0)

    assert track.bbox == new_bbox
    assert track.center == [160, 205]
    assert track.bottom_center == [160, 305]
    assert track.duration_seconds == 1.0
    assert len(track.trajectory) == 2

    # Missed frames
    track.mark_missed()
    assert track.missed_frames == 1


def test_iou_computation():
    boxA = [100, 100, 200, 200]
    boxB = [100, 100, 200, 200]
    # Identical boxes
    assert compute_iou(boxA, boxB) == 1.0

    # Non-overlapping boxes
    boxC = [300, 300, 400, 400]
    assert compute_iou(boxA, boxC) == 0.0

    # Partial overlap (50% area overlap)
    boxD = [150, 100, 250, 200]
    iou = compute_iou(boxA, boxD)
    assert 0.3 < iou < 0.4


def test_tracker_matching_iou():
    tracker = CentroidIoUTracker(max_lost_frames=5, iou_threshold=0.3, distance_threshold=80.0)

    # Frame 1: Single detection
    dets_f1 = [{'bbox': [100, 100, 200, 300], 'class_name': 'person', 'confidence': 0.85}]
    tracks_f1 = tracker.update(dets_f1)

    assert len(tracks_f1) == 1
    track_id = tracks_f1[0].track_id

    # Frame 2: Slightly moved detection (high IoU match)
    dets_f2 = [{'bbox': [104, 102, 204, 302], 'class_name': 'person', 'confidence': 0.89}]
    tracks_f2 = tracker.update(dets_f2)

    assert len(tracks_f2) == 1
    assert tracks_f2[0].track_id == track_id  # Track ID maintained
    assert tracks_f2[0].center == [154, 202]


def test_tracker_centroid_distance_fallback():
    tracker = CentroidIoUTracker(max_lost_frames=5, iou_threshold=0.5, distance_threshold=70.0)

    # Frame 1
    dets_f1 = [{'bbox': [100, 100, 160, 240], 'class_name': 'person', 'confidence': 0.85}]
    tracks_f1 = tracker.update(dets_f1)
    track_id = tracks_f1[0].track_id

    # Frame 2: Shifted so IoU is below 0.5, but centroid is within 70px
    dets_f2 = [{'bbox': [145, 100, 205, 240], 'class_name': 'person', 'confidence': 0.87}]
    tracks_f2 = tracker.update(dets_f2)

    assert len(tracks_f2) == 1
    assert tracks_f2[0].track_id == track_id  # Matched via distance fallback


def test_tracker_occlusion_and_purge():
    tracker = CentroidIoUTracker(max_lost_frames=3)

    dets = [{'bbox': [100, 100, 200, 300], 'class_name': 'person', 'confidence': 0.85}]
    tracks = tracker.update(dets)
    assert len(tracks) == 1

    # Empty frames (occlusion)
    tracks = tracker.update([])
    assert len(tracks) == 1  # Still visible within tolerance (missed_frames = 1)
    tracks = tracker.update([])
    assert len(tracks) == 1  # missed_frames = 2
    tracks = tracker.update([])
    assert len(tracks) == 0  # missed_frames = 3 (beyond display tolerance)

    # Exceed max_lost_frames (4th missed frame purges track from memory)
    tracker.update([])
    assert len(tracker.tracks) == 0


def test_tracker_reset():
    tracker = CentroidIoUTracker()
    dets = [
        {'bbox': [50, 50, 100, 150], 'class_name': 'person', 'confidence': 0.8},
        {'bbox': [200, 200, 260, 320], 'class_name': 'person', 'confidence': 0.9}
    ]
    tracker.update(dets)
    assert len(tracker.tracks) == 2

    tracker.reset()
    assert len(tracker.tracks) == 0

    # New tracks start with ID 1
    new_tracks = tracker.update([dets[0]])
    assert new_tracks[0].track_id == 1
