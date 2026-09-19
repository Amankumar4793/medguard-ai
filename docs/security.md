# Security & Privacy Architecture: MedGuard AI

## 1. System Threat Model & Healthcare Context

**MedGuard AI** operates as a cyber-physical surveillance platform deployed within sensitive healthcare environments. Its security architecture addresses both physical security risks (unauthorized access, loitering, after-hours intrusion, crowd surges) and application-layer security threats (injection, unauthorized API access, denial of service, memory exhaustion).

---

## 2. Ethical & Non-Biometric Privacy Boundaries

> [!IMPORTANT]
> **Strict Physical Surveillance Boundary**:
> MedGuard AI is engineered to protect hospital facilities, assets, and sterile boundaries. It is **NOT** a biometric identity or clinical monitoring system.

### Privacy Safeguards:
1. **Zero Facial Recognition**: The computer vision model (Ultralytics YOLOv8n) is trained exclusively to recognize general object classes (`person`, `backpack`, `handbag`, `suitcase`). It contains no facial detection, facial landmark estimation, or biometric feature extraction layers.
2. **Zero Demographic or Clinical Profiling**: The system does not classify individuals by age, gender, ethnicity, physical condition, emotional state, or medical symptoms.
3. **Session-Scoped Ephemeral Track IDs**: Track IDs are simple integer counters ($1, 2, 3\dots$) initialized in memory per camera session. They exist solely to calculate frame-to-frame velocity and zone dwell time. When a camera stream stops or restarts, all track IDs are purged.
4. **No Biometric Data Storage**: Database schemas (`SecurityEvent`, `Alert`, `Camera`) store only spatial bounding boxes, normalized coordinates, timestamps, and threat levels. No biometric embeddings, facial crops, or personal identifiable information (PII) are recorded.

---

## 3. Application & API Defensive Hardening

### 3.1 Bounded Pagination Sanitization
Unbounded query parameters can lead to database exhaustion and Denial of Service (DoS). The `/api/events/` and `/api/alerts/` endpoints enforce bounded pagination:
$$\text{limit} = \min(\max(1, \text{limit}), 100), \quad \text{offset} = \max(0, \text{offset})$$
- Non-integer or malformed inputs automatically fall back to safe defaults ($50$ limit, $0$ offset) without raising unhandled 500 exceptions.

### 3.2 Input Validation & Strict Type Bounds
- **Event Submission (`POST /api/events/`)**: Validates that `confidence` is bounded in $[0.0, 1.0]$, `risk_score` is in $[0.0, 100.0]$, and `risk_level` strictly belongs to `{'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}`.
- **Settings Modification (`PUT /api/settings/`)**: Validates that the sum of risk weights $(W_{\text{rule}} + W_{\text{ml}}) > 0.0$ to prevent degenerate zero-risk fusion. Validates that cooldown durations and thresholds are non-negative. Strictly validates 24-hour time strings (`HH:MM`) using regex and hour/minute range checks.
- **Camera Controls (`POST /api/monitoring/*`)**: Validates camera ID existence and type, returning structured JSON 400/404 errors instead of crashing worker threads.

### 3.3 Directory Traversal Defense
The evidence snapshot serving endpoint (`GET /api/snapshots/<filename>`) strictly sanitizes incoming filenames. Any attempt to use relative traversal paths (`../`, `..\`, `%2e%2e/`) is rejected, ensuring only files residing directly within `data/snapshots/` can be retrieved.

---

## 4. Database Security, Integrity & Concurrency

### 4.1 Scoped Sessions & Connection Pool Hygiene
Background worker threads (`VideoProcessor`, `EventService`, `AlertService`) execute database operations within explicit `try...finally: db.session.close()` blocks. This guarantees that database connections are returned to the pool immediately upon transaction completion, preventing connection pool exhaustion under 24/7 continuous operation.

### 4.2 Multithreaded Concurrency
The database layer was stress-tested with 10 concurrent threads simultaneously inserting security events and querying aggregated dashboard metrics. The system handled all transactions with zero SQLite `database is locked` errors.

### 4.3 Referential Integrity & Cascade Deletion
- Foreign key constraints enforce relational integrity:
  $$\text{Camera} \xrightarrow{\text{cascade}} \text{SecurityEvent} \xrightarrow{\text{cascade}} \text{Alert} \xrightarrow{\text{cascade}} \text{AlertHistory}$$
- Deleting a camera cleanly cleans up associated security events and alerts, leaving zero orphaned database records.

---

## 5. Memory Safety & Bounded Resource Allocation

### 5.1 Bounded Cooldown Cache Pruning
`AlertService` maintains an in-memory dictionary to track incident deduplication cooldowns per `(camera_id, event_type, zone_id, severity)`. Under high-incident burst conditions, unbounded dictionary growth could cause memory leaks.
- **Capacity Slicing**: When the cache exceeds 500 keys, it automatically purges the oldest timestamps, bounding the cache to the most recent 400 entries.
- **Thread Safety**: All reads and writes to the cooldown cache are guarded by a dedicated `threading.Lock()`.

### 5.2 Video Buffer Bounding
The `VideoProcessor` daemon thread maintains a single-frame atomic buffer. New frames overwrite old frames, preventing video queue build-up and ensuring that visual latency remains under 50 ms.

---

## 6. Network & WebSocket Security

### 6.1 Strict CORS Filtering
Cross-Origin Resource Sharing (CORS) is strictly configured via `CORS_ORIGINS` in `config.py`. Flask-CORS and Flask-SocketIO reject cross-origin requests originating from unauthorized domains.

### 6.2 Frontend Socket Guarding
The React frontend components (`NotificationCenter.jsx`, `DashboardPage.jsx`, `LiveMonitoringPage.jsx`) enforce defensive null-guards on all incoming WebSocket payloads, preventing client-side crashes if an incomplete packet is received over an unstable network.

---

## 7. Audit Trails & Non-Repudiation

All physical security actions are permanently audited:
- **Incident Audit Trail (`AlertHistory`)**: Every alert state change (`NEW` $\to$ `ACKNOWLEDGED` $\to$ `INVESTIGATING` $\to$ `RESOLVED`) persists an immutable record containing:
  - Exact UTC timestamp.
  - Previous status and new status.
  - Identity/callsign of the acting security operator.
  - Optional investigation or resolution notes.
- This immutable audit log ensures compliance with healthcare physical safety and accreditation standards.
