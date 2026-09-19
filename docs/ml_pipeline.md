# Machine Learning Anomaly Detection & Risk Fusion Pipeline (Phase 5)

## 1. Vision Layer: Real-Time Object Detection (YOLO)

### Architecture & Engine
- **Framework**: Ultralytics YOLO (`yolov8n.pt` / `yolo11n.pt` nano models)
- **Execution Strategy**:
  - Model weights loaded once into RAM via thread-safe singleton (`get_detector()`).
  - Warmup inference on dummy frame during initialization eliminates first-inference latency spikes.
  - Automatic CPU fallback if CUDA / GPU acceleration is unavailable.
  - Frame pacing and throttled inference (`inference_interval = 2`) reuses cached detections on intermediate frames, achieving smooth 15+ FPS streaming on standard CPUs.
- **Target Surveillance Classes**:
  - `person` (Patients, staff, visitors)
  - `backpack`, `handbag`, `suitcase` (Unattended bags / objects)
  - All non-surveillance classes (cars, animals, furniture) are filtered out automatically.
- **Bounding Box & Metadata Extraction**:
  - Bounding Box coordinates: `[x1, y1, x2, y2]`
  - Centroid: `[cx, cy]`
  - Bottom-Center ground contact point: `[(x1+x2)//2, y2]`
  - Confidence Score: `[0.0 - 1.0]`
  - Real-time inference latency tracking (`inference_ms`)

---

## 2. Temporal Feature Extraction Layer (19 Surveillance Features)

The `SecurityFeatureExtractor` (`backend/app/ml/features.py`) maintains an in-memory, thread-safe sliding temporal window (default: 60 seconds) per camera feed. Every frame observation buffers detection counts, track lifetimes, zone entries/exits, and velocity telemetry.

### Complete 19-Dimensional Feature Vector Schema

| # | Feature Key | Data Type | Physical Surveillance Interpretation |
|---|-------------|-----------|--------------------------------------|
| 1 | `persons_detected` | float | Total raw person detections observed across the temporal window. |
| 2 | `unique_tracks` | float | Count of distinct tracked individuals observed in the window. |
| 3 | `zone_occupancy` | float | Instantaneous count of people currently inside designated zones. |
| 4 | `restricted_zone_entries` | float | Ingress transitions into restricted/warning zones. |
| 5 | `restricted_zone_exits` | float | Egress transitions out of restricted/warning zones. |
| 6 | `time_in_restricted_zone` | float | Maximum continuous dwell time (seconds) in restricted areas. |
| 7 | `loitering_events` | float | Count of individuals exceeding stationary loitering duration cutoffs. |
| 8 | `after_hours_activity` | float | Binary flag (1.0 or 0.0) indicating activity during closed hours. |
| 9 | `crowd_level` | float | Peak simultaneous occupancy in any single surveillance zone. |
| 10 | `repeated_entries` | float | Ingress events by previously observed individuals (reconnaissance indicator). |
| 11 | `detection_confidence_mean` | float | Average YOLO confidence score across detections in window. |
| 12 | `detection_confidence_min` | float | Minimum YOLO confidence score observed in window. |
| 13 | `detection_confidence_max` | float | Maximum YOLO confidence score observed in window. |
| 14 | `movement_speed` | float | Mean centroid displacement velocity (pixels/second) across tracks. |
| 15 | `event_frequency` | float | Total security rule violations triggered within the temporal window. |
| 16 | `events_per_minute` | float | Normalized violation frequency scaled to a 60-second window. |
| 17 | `activity_hour` | float | Hour of day (0 to 23), capturing circadian hospital shifts. |
| 18 | `day_of_week` | float | Day of week (0=Mon to 6=Sun), capturing weekend vs weekday patterns. |
| 19 | `camera_activity_level` | float | Composite density and velocity index normalized to 0.0 – 1.0. |

---

## 3. Machine Learning Anomaly Detection Layer: Isolation Forest

### Model Architecture & Choice
- **Algorithm**: `sklearn.ensemble.IsolationForest` with `sklearn.preprocessing.StandardScaler`
- **Why Isolation Forest?**
  - **Unsupervised Learning**: Does not require labeled security incidents, learning purely what standard hospital foot traffic and zone occupancy looks like.
  - **Sub-Millisecond Inference**: Employs an ensemble of 100 binary isolation trees ($O(t \log n)$), allowing seamless background CPU execution without dropping video frames.
  - **Tree Partitioning Principle**: Anomalous events (rare off-hours ingress, extreme dwell times, rapid repeated entries) require significantly fewer random splits to isolate than normal crowd patterns.
- **Hyperparameters**:
  - `n_estimators = 100`
  - `contamination = 0.12` (empirical proportion of anomalous events)
  - `random_state = 42` (ensuring 100% reproducibility)

### Anomaly Score Calibration (0–100 Continuous Threat Score)
Isolation Forest's raw decision function $s \in [-0.35, +0.25]$ (where positive values represent normal instances and negative values represent anomalies) is mapped to a continuous, intuitive $0–100$ scale:
$$\text{ML\_RISK} = \text{clamp}\left(\frac{0.15 - s}{0.40} \times 100.0, 0.0, 100.0\right)$$
- Normal daytime activity: $\text{ML\_RISK} \approx 10–25$ (Low)
- Moderate behavioral deviations: $\text{ML\_RISK} \approx 35–55$ (Medium)
- Severe off-hours / loitering anomalies: $\text{ML\_RISK} \approx 65–95$ (High/Critical)

### Grounded Explainable Deviation Indicators
To eliminate "black-box" decision making, each incoming feature vector is standardized against baseline training statistics ($\mu_i, \sigma_i$ stored in `data/models/baseline_statistics.json`):
$$z_i = \frac{x_i - \mu_i}{\max(\sigma_i, 10^{-4})}$$
Features with significant standardized deviations ($|z_i| \ge 1.2$) are translated into human-readable explanatory indicators, such as:
- *"Elevated restricted zone dwell time (45.2s vs baseline 2.1s)"*
- *"Off-hours facility access during inactive operational schedule"*
- *"Repeated ingress attempts detected (4 visits in window)"*
- *"Abnormally sluggish/stationary movement pattern (4.2 px/s vs avg 40.7)"*

---

## 4. Rule + ML Risk Fusion Engine

The system fuses the deterministic Phase 4 rule engine with the Phase 5 unsupervised ML anomaly detector:
$$\text{FINAL\_RISK} = \text{round}(W_{\text{rule}} \times \text{RULE\_RISK} + W_{\text{ml}} \times \text{ML\_RISK}, 1)$$
- Default weights: $W_{\text{rule}} = 0.70$, $W_{\text{ml}} = 0.30$ (dynamically tunable in SOC Settings).
- Automatic weight normalization ensures $W_{\text{rule}} + W_{\text{ml}} = 1.0$.

### Categorical Threat Level Thresholds
- $\ge 75.0$: **CRITICAL** (Immediate high-priority alert generated, red badge)
- $\ge 50.0$: **HIGH** (Priority incident logged, orange badge)
- $\ge 25.0$: **MEDIUM** (Operational warning, amber badge)
- $< 25.0$: **LOW** (Standard telemetry audit event, green badge)

### Graceful Degradation Protocol
If model weights (`isolation_forest.joblib`) or preprocessing scalers (`scaler.joblib`) are missing or damaged:
1. `MLService` logs a warning and sets runtime status to `UNAVAILABLE`.
2. Risk fusion automatically falls back to pure deterministic rule scoring: $\text{FINAL\_RISK} = \text{RULE\_RISK}$.
3. Video capture, YOLO detection, object tracking, and rule-based alerts continue running with zero interruption.

---

## 5. Training Protocol & Serialized Model Artifacts

### Synthetic Dataset Generation
Executed via `backend/scripts/generate_ml_dataset.py`:
- Generates 2,200 multivariate samples across 7 distinct hospital operational scenarios:
  - Normal daytime visiting (55%)
  - Normal staff night rounds (25%)
  - Normal lobby transit (20%)
  - Anomalous: After-hours perimeter breach
  - Anomalous: Restricted pharmacy loitering
  - Anomalous: Emergency room crowd surge
  - Anomalous: Repeated reconnaissance ingress
- Output: `data/ml/synthetic_security_events.csv`

### Model Training & Validation
Executed via `backend/scripts/train_anomaly_model.py`:
- Trains `StandardScaler` and `IsolationForest`.
- Evaluates confusion matrix, precision, recall, and F1 score against synthetic ground-truth labels (**F1 Score: 0.909**).
- Serializes 4 core production artifacts to `data/models/`:
  - `isolation_forest.joblib`: Serialized scikit-learn Isolation Forest model.
  - `scaler.joblib`: Serialized StandardScaler.
  - `model_metadata.json`: Hyperparameters, training timestamps, feature list, and evaluation metrics.
  - `baseline_statistics.json`: Feature means, standard deviations, and percentiles for real-time explainability.
