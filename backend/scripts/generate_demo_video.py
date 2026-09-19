import os
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR.parent / 'data'
VIDEOS_DIR = DATA_DIR / 'videos'


def generate_synthetic_video(output_path, title="HOSPITAL CORRIDOR - DEMO FEED", zone_name="RESTRICTED ZONE", duration_seconds=8, fps=15, width=640, height=480):
    """
    Generates a deterministic synthetic demonstration MP4 video for healthcare monitoring.
    Features:
    - Clear simulated corridor with floor perspective lines
    - Monitored zone boundary marking
    - Simulated moving subject traversing across and pausing in the zone
    - Explicit 'DEMO VIDEO' watermark and timestamps
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_frames = duration_seconds * fps
    # Try mp4v codec for cross-platform compatibility
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    if not writer.isOpened():
        # Fallback to XVID / avi if mp4v fails
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    print(f"Generating synthetic video: {output_path.name} ({total_frames} frames)...")

    for frame_idx in range(total_frames):
        # 1. Background: Dark clinical corridor with perspective
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Upper walls (dark slate)
        frame[0:int(height * 0.6), :] = [35, 30, 25]  # BGR
        # Lower floor (reflective hospital floor)
        frame[int(height * 0.6):, :] = [55, 48, 40]

        # Wall dividing line
        cv2.line(frame, (0, int(height * 0.6)), (width, int(height * 0.6)), (80, 70, 60), 2)

        # Floor perspective lines
        for offset in range(-200, width + 200, 100):
            cv2.line(frame, (offset, int(height * 0.6)), (offset * 2 - width // 2, height), (70, 60, 50), 1)

        # Doorway / Restricted Vault Entrance
        door_x1, door_y1 = int(width * 0.55), int(height * 0.25)
        door_x2, door_y2 = int(width * 0.85), int(height * 0.6)
        cv2.rectangle(frame, (door_x1, door_y1), (door_x2, door_y2), (50, 45, 40), -1)
        cv2.rectangle(frame, (door_x1, door_y1), (door_x2, door_y2), (100, 90, 80), 2)
        cv2.putText(frame, "VAULT DOOR", (door_x1 + 10, door_y1 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 150, 140), 1)

        # 2. Designated Zone Outline (Simulated Restricted Zone)
        zone_x1, zone_y1 = int(width * 0.45), int(height * 0.35)
        zone_x2, zone_y2 = int(width * 0.9), int(height * 0.85)
        cv2.rectangle(frame, (zone_x1, zone_y1), (zone_x2, zone_y2), (0, 0, 180), 2)
        cv2.putText(frame, f"[ {zone_name} ]", (zone_x1 + 8, zone_y1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 1)

        # 3. Simulated Moving Subject (Walking Person)
        # Traverse from left (x=50) to right vault entrance (x=450), linger, then turn
        t = frame_idx / total_frames
        if t < 0.4:
            # Walking towards zone
            subj_x = int(50 + (t / 0.4) * 320)
        elif t < 0.7:
            # Lingering in zone (loitering)
            subj_x = int(370 + np.sin((t - 0.4) * 20) * 8)
        else:
            # Moving away
            subj_x = int(370 + ((t - 0.7) / 0.3) * 180)

        subj_y = int(height * 0.62)

        # Draw Person Silhouette: Head + Torso + Legs
        # Head
        cv2.circle(frame, (subj_x, subj_y - 65), 14, (180, 190, 200), -1)
        # Torso
        cv2.rectangle(frame, (subj_x - 16, subj_y - 50), (subj_x + 16, subj_y), (140, 150, 160), -1)
        # Legs
        cv2.line(frame, (subj_x - 8, subj_y), (subj_x - 12, subj_y + 35), (100, 110, 120), 5)
        cv2.line(frame, (subj_x + 8, subj_y), (subj_x + 12, subj_y + 35), (100, 110, 120), 5)

        # Bounding box label indication (to demonstrate subject detection)
        cv2.rectangle(frame, (subj_x - 22, subj_y - 85), (subj_x + 22, subj_y + 40), (0, 255, 128), 1)
        cv2.putText(frame, "DEMO SUBJECT", (subj_x - 30, subj_y - 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 128), 1)

        # 4. Watermark & Title Banner
        cv2.rectangle(frame, (0, 0), (width, 28), (15, 20, 30), -1)
        cv2.putText(frame, f"MEDGUARD DEMO: {title}", (12, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 200, 255), 1)

        # Bottom timestamp & synthetic notice
        cv2.rectangle(frame, (0, height - 24), (width, height), (15, 20, 30), -1)
        sec_str = f"{frame_idx / fps:.1f}s / {duration_seconds}s"
        cv2.putText(frame, f"SYNTHETIC SURVEILLANCE FEED | Frame {frame_idx + 1:03d}/{total_frames} | T+{sec_str}",
                    (10, height - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)

        writer.write(frame)

    writer.release()
    print(f"[OK] Video successfully generated at: {output_path}")


def generate_all_demo_videos():
    """Generates sample videos for all default camera feeds."""
    videos = [
        ("sample.mp4", "GENERAL DEMO CCTV FEED", "ICU AIRLOCK STERILE ZONE"),
        ("pharmacy_sample.mp4", "PHARMACY & NARCOTICS VAULT", "RESTRICTED NARCOTICS SAFE"),
        ("emergency_sample.mp4", "EMERGENCY WARD TRIAGE BAY", "AMBULANCE TRANSFER PATHWAY"),
        ("icu_sample.mp4", "ICU AIRLOCK CORRIDOR", "ICU STERILE PERIMETER"),
        ("lab_sample.mp4", "PATHOLOGY & BIOSAFETY LAB", "BSL-3 CONTAINMENT AIRLOCK")
    ]

    for filename, title, zone in videos:
        filepath = VIDEOS_DIR / filename
        generate_synthetic_video(filepath, title=title, zone_name=zone)


if __name__ == '__main__':
    generate_all_demo_videos()
