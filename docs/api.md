# REST & WebSocket API Reference: MedGuard AI

All REST API endpoints are prefixed with `/api`. Standard responses return structured JSON. Bounded pagination, float sanitization, and descriptive HTTP status codes are enforced across all endpoints.

---

## 1. System & Health

### `GET /api/health`
Returns comprehensive health telemetry across all five core subsystems.
- **Response `200 OK`**:
```json
{
  "status": "healthy",
  "service": "AI-Based Security System in Healthcare",
  "version": "1.0.0",
  "environment": "development",
  "uptime_seconds": 342,
  "subsystems": {
    "backend": {"status": "HEALTHY", "version": "1.0.0"},
    "database": {"status": "HEALTHY", "engine": "sqlite"},
    "camera_system": {"status": "HEALTHY", "active_cameras": 2, "total_cameras": 4},
    "ml_subsystem": {"status": "READY", "model": "IsolationForest", "features": 19},
    "alert_engine": {"status": "HEALTHY", "active_cooldowns": 0}
  }
}
```

---

## 2. Camera Management

### `GET /api/cameras/`
Retrieve all registered cameras, configurations, and spatial zones.
- **Response `200 OK`**: Array of camera objects.

### `POST /api/cameras/`
Register a new camera configuration.
- **Request Body**:
```json
{
  "name": "CAM-05: Pharmacy Annex",
  "source": "0",
  "source_type": "webcam",
  "location": "Ground Floor Pharmacy",
  "enabled": true,
  "configuration": {
    "zones": [
      {
        "id": "zone_safe",
        "name": "Narcotics Safe Area",
        "type": "restricted",
        "severity": "CRITICAL",
        "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
      }
    ],
    "operating_hours": {"start": "08:00", "end": "20:00"},
    "fps": 15,
    "loitering_threshold_seconds": 25,
    "crowd_threshold": 4
  }
}
```

### `GET /api/cameras/<id>`
Fetch details for a specific camera.
- **Response `200 OK`** or **`404 Not Found`**.

### `PUT /api/cameras/<id>`
Update an existing camera's metadata, source, or zone definitions.
- **Response `200 OK`** or **`400 Bad Request`**.

### `DELETE /api/cameras/<id>`
Delete a camera configuration. Automatically terminates active video processor daemon threads and cascades deletion of associated security events and alerts.
- **Response `200 OK`**.

---

## 3. Monitoring & Video Ingestion

### `GET /api/monitoring/status`
Returns real-time processing status and frame counts across all active video processors.

### `POST /api/monitoring/start`
Start video ingestion and AI detection on a camera.
- **Request Body**: `{"camera_id": 1}`
- **Response `200 OK`** or **`400 Bad Request`**.

### `POST /api/monitoring/stop`
Stop video ingestion and terminate worker thread on a camera.
- **Request Body**: `{"camera_id": 1}`
- **Response `200 OK`**.

### `POST /api/monitoring/restart`
Restart video processor and reset tracking session for a camera.
- **Request Body**: `{"camera_id": 1}`
- **Response `200 OK`**.

### `GET /api/monitoring/telemetry/<camera_id>`
Get live processing metrics: FPS, frame count, dropped frames, and detector latency.

### `GET /api/monitoring/detections/<camera_id>`
Get current raw YOLO detections with bounding boxes, confidence scores, and class names.

### `GET /api/monitoring/tracks/<camera_id>`
Get active tracked entities with track IDs, ground contact points, velocities, and visit histories.

### `GET /api/monitoring/zones/<camera_id>`
Get real-time spatial zone occupancy counts and active occupant track IDs.

### `GET /api/monitoring/stream/<camera_id>`
MJPEG live stream (`multipart/x-mixed-replace; boundary=frame`) rendering live video with bounding boxes, track IDs, motion trails, ground contact points, and zone breach highlights.

---

## 4. Security Events

### `GET /api/events/`
Retrieve historical security events.
- **Query Parameters**:
  - `limit`: Integer $[1, 100]$ (default 50).
  - `offset`: Non-negative integer (default 0).
  - `camera_id`: Filter by camera ID.
  - `event_type`: Filter by type (`zone_intrusion`, `loitering`, `crowd_density`, `after_hours`, `unattended_object`).
  - `risk_level`: Filter by level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Response `200 OK`**:
```json
{
  "events": [
    {
      "id": 42,
      "camera_id": 1,
      "event_type": "zone_intrusion",
      "severity": "CRITICAL",
      "risk_level": "CRITICAL",
      "risk_score": 88.5,
      "description": "Unauthorized entry into ICU Airlock Sterile Zone",
      "timestamp": "2026-09-19T10:15:30Z",
      "snapshot_path": "/api/snapshots/cam_1_intrusion_20260919_101530.jpg",
      "event_metadata": {
        "rule_risk_score": 90.0,
        "ml_risk_score": 85.0,
        "final_risk_score": 88.5,
        "ml_anomaly": true,
        "ml_indicators": ["Elevated dwell time in restricted zone"],
        "track_id": 7
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `POST /api/events/`
Manually record an external security event with input sanitization.
- **Validation Rules**: `confidence` $\in [0.0, 1.0]$, `risk_score` $\in [0.0, 100.0]$, `risk_level` $\in \{\text{LOW, MEDIUM, HIGH, CRITICAL}\}$.

### `GET /api/events/<id>`
Fetch complete event details and ML feature breakdown by event ID.

---

## 5. Incident Alerts & Triage

### `GET /api/alerts/`
Retrieve triage alert queue with bounded pagination.
- **Query Parameters**: `limit` $[1, 100]$, `offset \ge 0$, `status` (`NEW`, `ACKNOWLEDGED`, `INVESTIGATING`, `RESOLVED`), `severity`, `camera_id`.

### `GET /api/alerts/<id>`
Fetch alert details including immutable transition history trail.

### `PATCH /api/alerts/<id>`
Update alert status or add notes (backward-compatible triage endpoint).

### `POST /api/alerts/<id>/acknowledge`
Transition alert from `NEW` to `ACKNOWLEDGED`.
- **Request Body**: `{"operator": "Officer Davis", "note": "Dispatching floor team"}`

### `POST /api/alerts/<id>/investigate`
Transition alert to `INVESTIGATING`.
- **Request Body**: `{"operator": "Officer Davis"}`

### `POST /api/alerts/<id>/resolve`
Transition alert to `RESOLVED` (terminal state).
- **Request Body**: `{"operator": "Officer Davis", "resolution_notes": "Authorized nurse badge verified."}`

### `POST /api/alerts/<id>/notes`
Append an investigation note without changing alert status.

### `GET /api/alerts/statistics`
Returns alert triage counts by status (`new`, `acknowledged`, `investigating`, `resolved`) and severity.

---

## 6. Statistics & Analytics

### `GET /api/statistics/`
General system summary statistics.

### `GET /api/statistics/dashboard`
High-performance pre-aggregated 8-KPI payload for SOC dashboard (response time: ~4.4 ms):
- Total cameras, active cameras.
- Total events, today's events, active alerts.
- Average risk score, system threat level.
- Hourly incident distribution and active camera telemetry.

### `GET /api/statistics/analytics`
Historical analytics and temporal trends:
- **Query Parameters**: `range` (`today`, `24h`, `7d`, `30d`).
- Returns event breakdown by type, hourly histograms, camera risk rankings, and ML anomaly frequency.

---

## 7. Machine Learning & Anomaly Detection

### `GET /api/ml/status`
Returns runtime Isolation Forest model health, training metadata, and performance evaluation metrics.

### `GET /api/ml/analysis/<camera_id>`
Returns real-time 19-dimensional temporal feature vector, continuous ML anomaly score (0–100), classification flag, and top explainable indicators for the active feed.

### `GET /api/ml/features`
Returns detailed descriptions and physical interpretations for all 19 surveillance features.

### `POST /api/ml/reload`
Hot-reloads model weights, scaler, and baseline statistics from disk without restarting the server.

---

## 8. Settings & Rule Tuning

### `GET /api/settings/`
Get current system operational configurations.

### `PUT /api/settings/`
Update system parameters with cross-field validation:
```json
{
  "rule_risk_weight": 0.70,
  "ml_risk_weight": 0.30,
  "cooldown_critical_seconds": 15,
  "cooldown_high_seconds": 30,
  "cooldown_medium_seconds": 60,
  "cooldown_low_seconds": 120,
  "after_hours_start": "20:00",
  "after_hours_end": "06:00",
  "loitering_threshold_seconds": 25,
  "crowd_threshold": 4
}
```
*Validation: Requires $(W_{\text{rule}} + W_{\text{ml}}) > 0.0$, non-negative cooldowns, and valid 24h `HH:MM` schedule formats.*

---

## 9. Evidence Snapshots

### `GET /api/snapshots/<filename>`
Serves captured high-contrast evidence JPEG files from `data/snapshots/`.
- Enforces strict filename validation to prevent directory traversal attacks.

---

## 10. WebSocket Events (Flask-SocketIO)

The backend emits real-time events to connected browser clients:

| Event Name | Direction | Payload Description |
|---|---|---|
| `detection_update` | Server $\to$ Client | Real-time FPS, active track count, and zone occupancy (~3 Hz). |
| `security_event` | Server $\to$ Client | Instant payload on new verified security event with risk score and snapshot URL. |
| `alert_new` | Server $\to$ Client | Dispatched immediately when a high-priority incident triggers an alert. |
| `alert_updated` | Server $\to$ Client | Dispatched when an alert changes status (`ACKNOWLEDGED`, `RESOLVED`, etc.). |
| `camera_status_changed` | Server $\to$ Client | Broadcast on camera state transition (`RUNNING`, `OFFLINE`, `ERROR`). |
