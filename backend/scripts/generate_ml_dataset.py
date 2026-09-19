"""
Synthetic Security Event Dataset Generator for MedGuard AI
Generates realistic multivariate hospital surveillance data for unsupervised anomaly detection.

Features generated:
 1. persons_detected
 2. unique_tracks
 3. zone_occupancy
 4. restricted_zone_entries
 5. restricted_zone_exits
 6. time_in_restricted_zone
 7. loitering_events
 8. after_hours_activity
 9. crowd_level
10. repeated_entries
11. detection_confidence_mean
12. detection_confidence_min
13. detection_confidence_max
14. movement_speed
15. event_frequency
16. events_per_minute
17. activity_hour
18. day_of_week
19. camera_activity_level
"""

import os
import random
import csv
from pathlib import Path

# Fix seed for reproducibility
random.seed(42)

FEATURE_COLUMNS = [
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
    'camera_activity_level',
    'is_anomaly',
    'scenario_type'
]


def generate_normal_daytime():
    """Steady daytime visiting traffic (08:00 - 20:00)."""
    hour = random.randint(8, 19)
    day = random.randint(0, 6)
    tracks = random.randint(1, 6)
    persons = tracks * random.randint(8, 15)
    occ = random.randint(0, min(3, tracks))
    entries = random.choice([0, 0, 1, 1, 2])
    exits = min(entries, random.choice([0, 1, 2]))
    dwell = round(random.uniform(0.0, 12.0), 1) if entries > 0 else 0.0
    loitering = 0
    after_hours = 0.0
    crowd = max(1, occ)
    repeated = random.choice([0, 0, 0, 1])

    conf_mean = round(random.uniform(0.82, 0.94), 3)
    conf_min = round(max(0.65, conf_mean - random.uniform(0.08, 0.18)), 3)
    conf_max = round(min(0.99, conf_mean + random.uniform(0.02, 0.06)), 3)
    speed = round(random.uniform(22.0, 65.0), 1)

    events = entries if entries > 0 and random.random() < 0.25 else 0
    epm = round(events * 1.0, 2)
    act_lvl = round(min(1.0, 0.15 + (tracks * 0.08) + (speed * 0.003)), 3)

    return {
        'persons_detected': persons,
        'unique_tracks': tracks,
        'zone_occupancy': occ,
        'restricted_zone_entries': entries,
        'restricted_zone_exits': exits,
        'time_in_restricted_zone': dwell,
        'loitering_events': loitering,
        'after_hours_activity': after_hours,
        'crowd_level': crowd,
        'repeated_entries': repeated,
        'detection_confidence_mean': conf_mean,
        'detection_confidence_min': conf_min,
        'detection_confidence_max': conf_max,
        'movement_speed': speed,
        'event_frequency': events,
        'events_per_minute': epm,
        'activity_hour': hour,
        'day_of_week': day,
        'camera_activity_level': act_lvl,
        'is_anomaly': 0,
        'scenario_type': 'normal_daytime'
    }


def generate_normal_night_staff():
    """Hospital staff rounds, night nurses, security patrols (21:00 - 06:00)."""
    hour = random.choice([21, 22, 23, 0, 1, 2, 3, 4, 5, 6])
    day = random.randint(0, 6)
    tracks = random.choice([1, 1, 2])
    persons = tracks * random.randint(4, 10)
    occ = random.choice([0, 1])
    entries = random.choice([0, 1])
    exits = entries
    dwell = round(random.uniform(1.0, 8.0), 1) if entries > 0 else 0.0
    loitering = 0
    after_hours = 1.0
    crowd = occ
    repeated = 0

    conf_mean = round(random.uniform(0.80, 0.92), 3)
    conf_min = round(max(0.60, conf_mean - 0.12), 3)
    conf_max = round(min(0.98, conf_mean + 0.05), 3)
    speed = round(random.uniform(25.0, 50.0), 1)

    events = 0
    epm = 0.0
    act_lvl = round(min(1.0, 0.08 + (tracks * 0.06)), 3)

    return {
        'persons_detected': persons,
        'unique_tracks': tracks,
        'zone_occupancy': occ,
        'restricted_zone_entries': entries,
        'restricted_zone_exits': exits,
        'time_in_restricted_zone': dwell,
        'loitering_events': loitering,
        'after_hours_activity': after_hours,
        'crowd_level': crowd,
        'repeated_entries': repeated,
        'detection_confidence_mean': conf_mean,
        'detection_confidence_min': conf_min,
        'detection_confidence_max': conf_max,
        'movement_speed': speed,
        'event_frequency': events,
        'events_per_minute': epm,
        'activity_hour': hour,
        'day_of_week': day,
        'camera_activity_level': act_lvl,
        'is_anomaly': 0,
        'scenario_type': 'normal_night_staff'
    }


def generate_normal_lobby_transit():
    """Main corridor transit (steady walking, zero loitering)."""
    hour = random.randint(7, 20)
    day = random.randint(0, 6)
    tracks = random.randint(2, 7)
    persons = tracks * random.randint(10, 20)
    occ = random.randint(0, 2)
    entries = 0
    exits = 0
    dwell = 0.0
    loitering = 0
    after_hours = 0.0
    crowd = random.randint(1, 3)
    repeated = 0

    conf_mean = round(random.uniform(0.85, 0.95), 3)
    conf_min = round(max(0.70, conf_mean - 0.10), 3)
    conf_max = round(min(0.99, conf_mean + 0.04), 3)
    speed = round(random.uniform(35.0, 75.0), 1)

    events = 0
    epm = 0.0
    act_lvl = round(min(1.0, 0.20 + (tracks * 0.07)), 3)

    return {
        'persons_detected': persons,
        'unique_tracks': tracks,
        'zone_occupancy': occ,
        'restricted_zone_entries': entries,
        'restricted_zone_exits': exits,
        'time_in_restricted_zone': dwell,
        'loitering_events': loitering,
        'after_hours_activity': after_hours,
        'crowd_level': crowd,
        'repeated_entries': repeated,
        'detection_confidence_mean': conf_mean,
        'detection_confidence_min': conf_min,
        'detection_confidence_max': conf_max,
        'movement_speed': speed,
        'event_frequency': events,
        'events_per_minute': epm,
        'activity_hour': hour,
        'day_of_week': day,
        'camera_activity_level': act_lvl,
        'is_anomaly': 0,
        'scenario_type': 'normal_lobby_transit'
    }


def generate_anomalous_after_hours_breach():
    """Intruder breaching restricted zone deep in the night (01:00 - 04:00)."""
    hour = random.choice([0, 1, 2, 3, 4])
    day = random.randint(0, 6)
    tracks = random.choice([1, 2])
    persons = tracks * random.randint(15, 35)
    occ = tracks
    entries = random.randint(2, 4)
    exits = random.randint(0, 1)
    dwell = round(random.uniform(45.0, 160.0), 1)
    loitering = random.choice([1, 2])
    after_hours = 1.0
    crowd = occ
    repeated = random.randint(1, 3)

    conf_mean = round(random.uniform(0.74, 0.86), 3)
    conf_min = round(max(0.55, conf_mean - 0.18), 3)
    conf_max = round(min(0.95, conf_mean + 0.06), 3)
    speed = round(random.uniform(6.0, 20.0), 1)  # stealthy/hesitant

    events = random.randint(2, 5)
    epm = round(events * 1.5, 2)
    act_lvl = round(min(1.0, 0.65 + (dwell * 0.002)), 3)

    return {
        'persons_detected': persons,
        'unique_tracks': tracks,
        'zone_occupancy': occ,
        'restricted_zone_entries': entries,
        'restricted_zone_exits': exits,
        'time_in_restricted_zone': dwell,
        'loitering_events': loitering,
        'after_hours_activity': after_hours,
        'crowd_level': crowd,
        'repeated_entries': repeated,
        'detection_confidence_mean': conf_mean,
        'detection_confidence_min': conf_min,
        'detection_confidence_max': conf_max,
        'movement_speed': speed,
        'event_frequency': events,
        'events_per_minute': epm,
        'activity_hour': hour,
        'day_of_week': day,
        'camera_activity_level': act_lvl,
        'is_anomaly': 1,
        'scenario_type': 'after_hours_breach'
    }


def generate_anomalous_pharmacy_loitering():
    """Stationary individual lingering in sensitive medicine storage area."""
    hour = random.randint(10, 22)
    day = random.randint(0, 6)
    tracks = 1
    persons = random.randint(20, 45)
    occ = 1
    entries = 1
    exits = 0
    dwell = round(random.uniform(65.0, 240.0), 1)
    loitering = 1
    after_hours = 1.0 if (hour >= 20 or hour < 8) else 0.0
    crowd = 1
    repeated = random.choice([0, 1])

    conf_mean = round(random.uniform(0.85, 0.93), 3)
    conf_min = round(conf_mean - 0.08, 3)
    conf_max = round(conf_mean + 0.05, 3)
    speed = round(random.uniform(1.5, 9.0), 1)  # stationary linger

    events = random.randint(1, 3)
    epm = round(events * 1.0, 2)
    act_lvl = round(min(1.0, 0.55 + (dwell * 0.002)), 3)

    return {
        'persons_detected': persons,
        'unique_tracks': tracks,
        'zone_occupancy': occ,
        'restricted_zone_entries': entries,
        'restricted_zone_exits': exits,
        'time_in_restricted_zone': dwell,
        'loitering_events': loitering,
        'after_hours_activity': after_hours,
        'crowd_level': crowd,
        'repeated_entries': repeated,
        'detection_confidence_mean': conf_mean,
        'detection_confidence_min': conf_min,
        'detection_confidence_max': conf_max,
        'movement_speed': speed,
        'event_frequency': events,
        'events_per_minute': epm,
        'activity_hour': hour,
        'day_of_week': day,
        'camera_activity_level': act_lvl,
        'is_anomaly': 1,
        'scenario_type': 'pharmacy_loitering'
    }


def generate_anomalous_crowd_surge():
    """Unusual crowd accumulation in restricted corridor or triage area."""
    hour = random.randint(11, 23)
    day = random.randint(0, 6)
    tracks = random.randint(7, 16)
    persons = tracks * random.randint(12, 28)
    occ = random.randint(5, 12)
    entries = random.randint(4, 9)
    exits = random.randint(1, 3)
    dwell = round(random.uniform(20.0, 75.0), 1)
    loitering = random.randint(1, 4)
    after_hours = 1.0 if (hour >= 20 or hour < 8) else 0.0
    crowd = occ
    repeated = random.randint(1, 4)

    conf_mean = round(random.uniform(0.78, 0.88), 3)
    conf_min = round(max(0.50, conf_mean - 0.20), 3)
    conf_max = round(min(0.97, conf_mean + 0.06), 3)
    speed = round(random.uniform(12.0, 32.0), 1)

    events = random.randint(3, 7)
    epm = round(events * 2.0, 2)
    act_lvl = round(min(1.0, 0.80 + (tracks * 0.015)), 3)

    return {
        'persons_detected': persons,
        'unique_tracks': tracks,
        'zone_occupancy': occ,
        'restricted_zone_entries': entries,
        'restricted_zone_exits': exits,
        'time_in_restricted_zone': dwell,
        'loitering_events': loitering,
        'after_hours_activity': after_hours,
        'crowd_level': crowd,
        'repeated_entries': repeated,
        'detection_confidence_mean': conf_mean,
        'detection_confidence_min': conf_min,
        'detection_confidence_max': conf_max,
        'movement_speed': speed,
        'event_frequency': events,
        'events_per_minute': epm,
        'activity_hour': hour,
        'day_of_week': day,
        'camera_activity_level': act_lvl,
        'is_anomaly': 1,
        'scenario_type': 'crowd_surge'
    }


def generate_anomalous_repeated_reconnaissance():
    """Suspicious individual entering and exiting restricted zone multiple times."""
    hour = random.randint(12, 23)
    day = random.randint(0, 6)
    tracks = random.choice([1, 2])
    persons = tracks * random.randint(15, 30)
    occ = 1
    entries = random.randint(4, 8)
    exits = entries - 1
    dwell = round(random.uniform(15.0, 45.0), 1)
    loitering = random.choice([0, 1])
    after_hours = 1.0 if (hour >= 20 or hour < 8) else 0.0
    crowd = 1
    repeated = entries - 1

    conf_mean = round(random.uniform(0.82, 0.91), 3)
    conf_min = round(conf_mean - 0.10, 3)
    conf_max = round(conf_mean + 0.05, 3)
    speed = round(random.uniform(30.0, 65.0), 1)

    events = random.randint(2, 5)
    epm = round(events * 1.5, 2)
    act_lvl = round(min(1.0, 0.70 + (entries * 0.04)), 3)

    return {
        'persons_detected': persons,
        'unique_tracks': tracks,
        'zone_occupancy': occ,
        'restricted_zone_entries': entries,
        'restricted_zone_exits': exits,
        'time_in_restricted_zone': dwell,
        'loitering_events': loitering,
        'after_hours_activity': after_hours,
        'crowd_level': crowd,
        'repeated_entries': repeated,
        'detection_confidence_mean': conf_mean,
        'detection_confidence_min': conf_min,
        'detection_confidence_max': conf_max,
        'movement_speed': speed,
        'event_frequency': events,
        'events_per_minute': epm,
        'activity_hour': hour,
        'day_of_week': day,
        'camera_activity_level': act_lvl,
        'is_anomaly': 1,
        'scenario_type': 'repeated_reconnaissance'
    }


def generate_dataset(output_path, num_samples=2200):
    """
    Generates a full synthetic dataset with ~88% normal and ~12% anomalous samples.
    """
    normal_generators = [
        (generate_normal_daytime, 0.55),
        (generate_normal_night_staff, 0.25),
        (generate_normal_lobby_transit, 0.20)
    ]

    anomaly_generators = [
        (generate_anomalous_after_hours_breach, 0.35),
        (generate_anomalous_pharmacy_loitering, 0.30),
        (generate_anomalous_crowd_surge, 0.20),
        (generate_anomalous_repeated_reconnaissance, 0.15)
    ]

    num_anomalies = int(num_samples * 0.12)
    num_normals = num_samples - num_anomalies

    records = []

    # Generate normal records
    for _ in range(num_normals):
        r = random.random()
        cum = 0.0
        for gen_fn, weight in normal_generators:
            cum += weight
            if r <= cum:
                records.append(gen_fn())
                break
        else:
            records.append(generate_normal_daytime())

    # Generate anomaly records
    for _ in range(num_anomalies):
        r = random.random()
        cum = 0.0
        for gen_fn, weight in anomaly_generators:
            cum += weight
            if r <= cum:
                records.append(gen_fn())
                break
        else:
            records.append(generate_anomalous_after_hours_breach())

    # Shuffle records
    random.shuffle(records)

    # Save to CSV
    output_dir = Path(output_path).parent
    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(records)

    print(f"Successfully generated {len(records)} samples -> {output_path}")
    print(f"  - Normal samples:  {num_normals} ({num_normals / len(records) * 100:.1f}%)")
    print(f"  - Anomaly samples: {num_anomalies} ({num_anomalies / len(records) * 100:.1f}%)")


if __name__ == '__main__':
    # Resolve target path relative to project root
    base_dir = Path(__file__).resolve().parent.parent.parent
    target_csv = base_dir / 'data' / 'ml' / 'synthetic_security_events.csv'
    generate_dataset(str(target_csv), num_samples=2200)
