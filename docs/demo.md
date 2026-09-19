# Final Year Project Demonstration Guide (MedGuard AI)

This guide provides instructions for evaluating and demonstrating the **AI-Based Security System in Healthcare** during academic presentations and project evaluations.

---

## 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Node.js 18+ (tested on Node.js 22)
- Laptop webcam or bundled demonstration videos in `data/videos/`

---

## 2. Launch Sequence

### Step 1: Database Initialization & ML Model Training
Run from `backend/`:
```bash
cd backend
.\.venv\Scripts\python scripts/init_db.py
.\.venv\Scripts\python scripts/generate_ml_dataset.py
.\.venv\Scripts\python scripts/train_anomaly_model.py
```
This prepares SQLite tables, generates 2,200 synthetic hospital surveillance samples, trains the Isolation Forest anomaly detector, and serializes production model artifacts to `data/models/`.

### Step 2: Start Backend
```bash
cd backend
.\.venv\Scripts\python run.py
```
Backend starts on `http://127.0.0.1:5000` with Flask-SocketIO and active ML subsystem (`READY`).

### Step 3: Start Frontend
```bash
cd frontend
npm run dev
```
Open your browser at `http://127.0.0.1:5173`.

---

## 3. Step-by-Step Demonstration Workflow

### 3.1 SOC Overview (`/`)
- Point out real-time KPI metrics: Active Cameras, Audited Security Events, High Risk Threats, Pending Triage Alerts.
- Review the Monitored Healthcare Zones preview cards and recent alerts table.

### 3.2 Live Monitoring & AI Anomaly Detection (`/monitoring`)
1. **Camera Feed Selection**:
   - Select a surveillance feed (e.g., CAM-02 Central Pharmacy or CAM-01 ICU Corridor).
   - Click **"Start Stream"** to activate the background OpenCV video processing worker.
2. **AI Vision & Object Tracking HUD**:
   - Point out real-time bounding boxes around detected persons with persistent Track IDs (`Person #1`, `Person #2`).
   - Highlight **motion trajectory trails** showing the path taken by individuals over the last 15 frames.
   - Point out the **ground contact point marker** (feet) used for accurate point-in-polygon containment without perspective distortion.
3. **Spatial Zone Intrusion**:
   - Show configured zone boundary lines (`RESTRICTED` in Red, `WARNING` in Yellow).
   - When a tracked individual steps across the boundary, note the **translucent red breach highlight** and `! BREACH` tag.
4. **Loitering Violation**:
   - When a person remains stationary in a restricted zone beyond the configured cutoff, the bounding box shifts to **Orange** and displays `[LOITERING Xs]`.
5. **Phase 5 AI Anomaly Detection Card (Isolation Forest)**:
   - Point out the dedicated ML Anomaly Threat Score gauge (`0–100`) updating in real time.
   - Note the status indicator (`NORMAL` vs `ANOMALOUS`).
   - Highlight the **Explainable Behavioral Indicators** explaining exactly which surveillance metrics contributed to the ML score (e.g. *"Elevated restricted zone dwell time: +3.2σ"*).
6. **Live Security Events Feed**:
   - Show the real-time audit feed underneath the video stream. Events arrive automatically via WebSocket without page refresh.
   - Click the **"Snapshot"** button to view the high-resolution evidence frame captured by the system at the moment of intrusion.

### 3.3 Real-Time Incident Command Center (`/alerts`) & Notifications
1. **Live Audio & Toast Notifications**:
   - Point out the persistent notification bell in the top navigation bar with unread incident counter badge.
   - When a HIGH or CRITICAL breach occurs, note the real-time slide-in toast notification in the bottom-right viewport and the dual-tone audio chime synthesized via Web Audio API.
   - Click the audio mute toggle in the notification dropdown to demonstrate audio control.
2. **Incident Queue & KPI Metrics**:
   - Show aggregate KPI cards at the top: Active Incidents, Critical Breaches, High Severity, Active Investigation, and Resolved.
   - Demonstrate multi-tier search and filtering by Severity, Status (`NEW`, `ACKNOWLEDGED`, `INVESTIGATING`, `RESOLVED`), Camera, and free-text search.
3. **Multi-Tier Cooldown Deduplication**:
   - Demonstrate that continuous violations on the same camera/zone do not spam duplicate alerts; consecutive breaches within the configured window (e.g. 15s for Critical, 30s for High) are deduplicated.
4. **Interactive Incident Triage & Audit Modal**:
   - Click **"Triage & Audit"** on an alert to open the comprehensive incident inspection modal.
   - Review high-resolution snapshot evidence with timestamp, camera, and zone tags.
   - Inspect the **Explainable Risk Fusion breakdown gauge** ($70\% \text{ Rule} + 30\% \text{ ML}$) and ML indicator tags.
   - Walk through the strict 4-stage lifecycle:
     - Click **"1. Acknowledge Incident"** (moves `NEW` $\to$ `ACKNOWLEDGED`).
     - Click **"2. Initiate Investigation"** (moves `ACKNOWLEDGED` $\to$ `INVESTIGATING`).
     - Enter responding officer notes and click **"Log Note"**.
     - Click **"3. Mark Resolved"** (moves `INVESTIGATING` $\to$ `RESOLVED`).
   - Highlight the **Immutable Incident Audit Trail Timeline** at the bottom, verifying every state change, operator timestamp, and note logged permanently in `AlertHistory`.


### 3.4 Security Event Audit Trail & Risk Fusion (`/events`)
- Review historical log of security violations showing both **Rule Risk** and **ML Anomaly Threat Score** side-by-side.
- Point out the `[ML ANOMALY]` badge on events with statistically abnormal behavioral signatures.
- Click **"Inspect"** to open the audit modal:
  - Demonstrate the **Explainable Risk Fusion Breakdown** visual bar ($70\% \text{ Rule} + 30\% \text{ ML} = \text{Final Threat Score}$).
  - Inspect the top behavioral deviation indicators and snapshot evidence.

### 3.5 Security Metrics & Anomaly Analytics (`/analytics`)
- Show total ML anomalies detected across all facilities.
- Compare average Rule Risk score against average ML Anomaly score.
- Review the **Anomalies Detected by Monitored Facility** breakdown table.

### 3.6 Settings & Risk Fusion Tuning (`/settings`)
- Demonstrate adjusting the **Rule Risk Weight** (0.70) and **ML Anomaly Weight** (0.30) with automatic normalization.
- Adjust the **ML Feature Sliding Window** (60s) and **Inference Cadence** (10s).
- Click **"Save Configuration"** and show that the backend updates in real-time.

---

## 4. Academic Evaluation Talking Points
- **Why Isolation Forest over supervised classification?** Hospital security incidents are rare and varied. Supervised classifiers overfit to known attack scenarios; Isolation Forest learns normal flow unsupervised and flags rare multivariate outliers.
- **Why Risk Fusion ($0.70 \text{ Rule} + 0.30 \text{ ML}$)?** Deterministic rules guarantee zero false negatives for defined perimeter intrusions, while ML detects subtle temporal patterns (slow lingering, repeated reconnaissance, off-hours clusters) that single rules miss.
- **How is explainability maintained?** Rather than treating the ML model as a black box, the system compares incoming features against baseline statistics ($\mu_i, \sigma_i$) and outputs human-readable explanations (e.g. *"Dwell time 45.2s vs avg 2.1s"*).
- **Ethical Privacy Guarantee**: Physical security metadata only. Zero facial recognition, zero demographic profiling, zero patient medical records.
- **Graceful Degradation**: If model files are deleted, the system marks status `UNAVAILABLE` and falls back $100\%$ to rule-based security with zero video interruption.
