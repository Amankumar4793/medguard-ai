# AI & Computer Vision Pipeline Specification: MedGuard AI

## 1. Overview & Pipeline Philosophy
The **MedGuard AI** intelligence layer operates as a multi-stage real-time vision and machine learning pipeline. It transforms raw video streams into actionable, explainable physical security intelligence.

```
Camera Frame (640x480)
       │
       ▼
Ultralytics YOLOv8n (Throttled Cadence) ──▶ Bounding Boxes & Class Confidences
       │
       ▼
CentroidIoU Multi-Object Tracker ───────▶ Ephemeral Track IDs & Trajectories
       │
       ▼
Zone Spatial Evaluator ─────────────────▶ Ground-Contact Floor Point-in-Polygon
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
Rule-Based Security Engine         19-D Temporal Feature Extractor
(Intrusion, Loitering, Crowd)      (60s Sliding Temporal Window)
       │                                 │
       ▼                                 ▼
Rule Risk Score (0-100)            Isolation Forest Anomaly Detector
       │                                 │
       │                                 ▼
       │                           Calibrated ML Score (0-100) & Indicators
       │                                 │
       └────────────────┬────────────────┘
                        ▼
             Weighted Risk Fusion Engine
         Final = 0.70 * Rule + 0.30 * ML
```

---

## 2. Stage 1: Object Detection (Ultralytics YOLOv8n)

### Model & Configuration
- **Model Architecture**: Ultralytics YOLOv8n (`yolov8n.pt`, ~3.2M parameters, 6.5 MB file size).
- **Execution Target**: CPU inference by default via PyTorch (seamless CUDA acceleration if GPU is available).
- **Input Resolution**: Standardized $640 \times 480$ RGB.
- **Inference Warmup**: On application startup, the detector executes a dummy zero-tensor inference pass to warm up weights and initialize PyTorch memory, eliminating runtime video stutter.

### Target Filtering for Healthcare Security
To maintain high throughput and minimize false alarms, the detector strictly filters bounding boxes for classes relevant to physical healthcare security:
- `person` (Class ID `0`): Security staff, healthcare workers, visitors, or intruders.
- `backpack` (Class ID `24`): Bags or luggage left unattended.
- `handbag` (Class ID `26`): Unattended personal items.
- `suitcase` (Class ID `28`): Large unattended baggage.

All other COCO classes (vehicles, animals, furniture) are discarded at the detection boundary.

### Throttled Inference Cadence
Running deep learning inference on every frame can overload consumer CPUs. MedGuard AI employs an intelligent alternating cadence:
- Full YOLO inference executes every $N=2$ frames (`inference_interval_frames`).
- On intermediate frames, the multi-object tracker extrapolates trajectories based on velocity vectors.
- This hybrid approach achieves **25.8 FPS CPU throughput** while maintaining tracking continuity.

---

## 3. Stage 2: Multi-Object Tracking (`CentroidIoUTracker`)

Standard Kalman-filter trackers introduce heavy computational overhead. MedGuard AI implements an optimized two-stage bipartite association tracker:

### Stage 2.1: IoU Association (Stage 1)
- Computes Intersection-over-Union (IoU) between active predicted tracks and new YOLO detections.
- Bipartite matching matches pairs where $\text{IoU} \ge 0.25$.

### Stage 2.2: Centroid Distance Fallback (Stage 2)
- Fast-moving entities or sudden camera shifts may cause bounding boxes to lose IoU overlap.
- For unmatched tracks and detections, Euclidean distance between bounding box centroids is computed:
  $$d = \sqrt{(c_{x1} - c_{x2})^2 + (c_{y1} - c_{y2})^2}$$
- Matches are accepted if $d \le 90$ pixels.

### Occlusion Handling & Life Cycle
- **New Tracks**: Created when a detection cannot be matched to an existing track.
- **Occlusion Survival**: If an entity is briefly occluded (e.g. walking behind a pillar), its track is retained for up to `max_lost_frames = 15` (1.0 second at 15 FPS).
- **Motion History**: Maintains the last 30 center coordinates for rendering motion vectors on the SOC HUD.
- **Session Purge**: Active tracks and ID counters are cleanly purged when a camera stream stops or restarts.

---

## 4. Stage 3: Spatial Zone Logic & Ground Contact Geometry

### The Perspective Overlap Problem
In wide-angle camera perspectives, a standing person's head or upper torso frequently leans across zone boundaries in image space, even when their feet are firmly planted outside the zone. Evaluating bounding box centroids results in frequent false alarms.

### Ground Contact Floor Point
MedGuard AI evaluates containment strictly at the **bottom-center point of the bounding box**:
$$P_{\text{ground}} = \left( \frac{x_1 + x_2}{2}, \; y_2 \right)$$
This represents the physical point of contact between the individual and the hospital floor.

### Point-in-Polygon Engine
1. **Polygon Normalization**: Zone polygons are defined in normalized coordinates $[(x, y) \in [0.0, 1.0]]$, making them independent of frame resolution.
2. **Evaluation**: Normalized points are scaled to pixel space ($640 \times 480$) and tested using OpenCV's `cv2.pointPolygonTest`. An internal raycasting algorithm serves as a fallback.
3. **State Transitions**: The `ZoneEvaluator` tracks state transitions per entity:
   - `is_entry`: Fired on first frame of containment.
   - `stay`: Continuously records elapsed dwell time in seconds.
   - `is_exit`: Fired when entity leaves zone, recording total dwell duration.

---

## 5. Stage 4: Rule-Based Security Engine (`SecurityEngine`)

The deterministic engine evaluates active tracks against predefined security policies:

| Rule | Detection Trigger | Default Threshold | Severity |
|---|---|---|---|
| **Restricted Zone Intrusion** | Ground contact point enters restricted zone | Immediate ($0.0$s) | HIGH / CRITICAL |
| **After-Hours Movement** | Any movement inside facility during off-hours | Outside operational schedule | HIGH |
| **Loitering** | Continuous dwell time inside restricted area | $> 25.0$ seconds | MEDIUM / HIGH |
| **Crowd Density** | Multiple occupants inside single zone | $\ge 4$ persons for $> 5.0$s | HIGH |
| **Repeated Entry** | Same entity enters restricted zones repeatedly | $\ge 3$ visits in 300s window | HIGH |
| **Unattended Object** | Stationary bag without person within 120px | $> 35.0$ seconds | HIGH |

Each rule computes an explainable rule risk score ($0–100$) based on severity and breach parameters.

---

## 6. Stage 5: 19-Dimensional Temporal Feature Extraction

To enable unsupervised machine learning, `SecurityFeatureExtractor` compiles a 19-dimensional numerical feature vector over a 60-second sliding temporal window:

| Index | Feature Name | Description & Interpretation |
|---|---|---|
| 0 | `persons_detected` | Total number of person detections in the temporal window. |
| 1 | `unique_tracks` | Number of distinct active track IDs identified. |
| 2 | `time_in_restricted_zone` | Maximum single-track dwell time in restricted zones (seconds). |
| 3 | `avg_time_in_restricted_zone` | Average dwell time across all entities in restricted zones (seconds). |
| 4 | `restricted_zone_entries` | Total entry transitions into restricted zones. |
| 5 | `loitering_events` | Number of loitering violations logged. |
| 6 | `after_hours_activity` | Binary indicator ($1.0$ if current timestamp is after-hours, else $0.0$). |
| 7 | `crowd_density` | Maximum concurrent occupants detected in any single zone. |
| 8 | `max_crowd_count` | Peak crowd count observed in the camera scene. |
| 9 | `repeated_entry_count` | Maximum repeat entries by any single entity. |
| 10 | `unattended_object_count` | Number of unattended bags/objects detected. |
| 11 | `movement_speed` | Mean pixel displacement per frame across active tracks. |
| 12 | `max_speed` | Maximum single-frame pixel displacement observed. |
| 13 | `direction_changes` | Frequency of directional trajectory reversals (erratic motion). |
| 14 | `detection_confidence_mean` | Mean confidence score across all person detections. |
| 15 | `zone_occupancy_ratio` | Ratio of occupants in restricted zones vs. total scene occupants. |
| 16 | `spatial_spread` | Bounding box variance across tracks (crowd dispersion measure). |
| 17 | `loitering_ratio` | Proportion of total tracks exhibiting loitering behavior. |
| 18 | `high_risk_rule_count` | Number of deterministic rule breaches with severity $\ge \text{HIGH}$. |

---

## 7. Stage 6: Machine Learning Anomaly Detection (`IsolationForest`)

### Unsupervised Model Architecture
- **Algorithm**: `sklearn.ensemble.IsolationForest`.
- **Hyperparameters**:
  - `n_estimators`: 100 decision trees.
  - `contamination`: 0.12 (calibrated for low false-alarm tolerance in security monitoring).
  - `max_samples`: Auto.
- **Preprocessing**: `StandardScaler` fitted on baseline normal surveillance feature vectors.

### Continuous Score Calibration
Raw Isolation Forest decision function values $s \in (-\infty, +\infty)$ are mapped to an intuitive continuous percentage threat score $S_{\text{ml}} \in [0.0, 100.0]$:
$$S_{\text{ml}} = \min\left(100.0, \; \max\left(0.0, \; \frac{s_{\text{offset}} - s}{s_{\text{scale}}} \times 100.0\right)\right)$$

### Explainable Anomaly Indicators
Rather than outputting an opaque prediction, the engine identifies the specific features causing the anomaly:
1. Calculates normalized deviations: $Z_i = \frac{x_i - \mu_i}{\sigma_i}$.
2. Ranks features where $Z_i \ge 2.0$ (statistically significant deviations).
3. Produces human-readable explanations (e.g., *"Elevated restricted zone dwell time (45.2s vs normal 2.1s)"*).

---

## 8. Stage 7: Weighted Risk Fusion Engine

The deterministic rule score ($S_{\text{rule}}$) and the machine learning anomaly score ($S_{\text{ml}}$) are fused using weighted linear combination:

$$\text{Final Risk} = \text{round}\left(w_{\text{rule}} \times S_{\text{rule}} + w_{\text{ml}} \times S_{\text{ml}}, 1\right)$$

- **Default Parameters**: $w_{\text{rule}} = 0.70$, $w_{\text{ml}} = 0.30$.
- **Severity Classification**:
  - $[75.0, 100.0] \implies \text{CRITICAL}$
  - $[50.0, 74.9] \implies \text{HIGH}$
  - $[25.0, 49.9] \implies \text{MEDIUM}$
  - $[0.0, 24.9] \implies \text{LOW}$

### Fault Tolerance & Graceful Degradation
If the Isolation Forest model artifact is unreadable or corrupted:
1. The detector catches the exception and logs an operational warning.
2. `ml_status` transitions to `DEGRADED` or `UNAVAILABLE`.
3. The fusion engine dynamically adjusts weights to $w_{\text{rule}} = 1.0, w_{\text{ml}} = 0.0$.
4. The system continues operating at 100% video processing throughput with zero downtime.
