# Installation & Setup Guide: MedGuard AI

This document provides step-by-step instructions for installing, configuring, running, and testing the **MedGuard AI** Physical Security Monitoring System.

---

## 1. Prerequisites & System Requirements

### Hardware Requirements
- **CPU**: Intel Core i5 / AMD Ryzen 5 or better (tested on Intel Core i7-13700H).
- **RAM**: Minimum 4 GB available RAM (8 GB+ recommended).
- **Storage**: Minimum 1 GB available disk space for dependencies, models, and snapshots.
- **Camera (Optional)**: Built-in laptop webcam or USB webcam for live camera testing. (System includes sample MP4 videos for offline demonstration).

### Software Requirements
- **Operating System**: Windows 10/11, Linux (Ubuntu 20.04+), or macOS 12+.
- **Python**: Version 3.10, 3.11, or 3.12 (tested on Python 3.12.5).
- **Node.js**: Version 18.x, 20.x, or 22.x with `npm` (tested on Node v22).
- **Web Browser**: Modern Chromium-based browser (Chrome, Edge, Brave) or Firefox.

---

## 2. Repository Layout

```
Project!/
├── backend/
│   ├── app/                  # Flask application package
│   ├── scripts/              # Setup, dataset, and benchmark scripts
│   ├── tests/                # Pytest regression and hardening suites
│   ├── healthcare_security.db# SQLite database
│   ├── requirements.txt      # Python dependencies
│   ├── run.py                # Server entry point
│   └── .env.example          # Backend environment template
├── frontend/
│   ├── src/                  # React source code (pages, components, services)
│   ├── package.json          # Node dependencies
│   ├── vite.config.js        # Vite build configuration
│   └── .env.example          # Frontend environment template
├── data/
│   ├── models/               # YOLO and Isolation Forest model weights
│   ├── videos/               # Sample MP4 demo surveillance footage
│   ├── snapshots/            # High-resolution evidence snapshot output
│   └── ml/                   # Synthetic surveillance feature dataset
└── docs/                     # Technical specifications and guides
```

---

## 3. Backend Setup

### Step 3.1: Create Virtual Environment
Open a terminal (PowerShell or Bash) and navigate to `backend/`:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:
- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Linux / macOS**:
  ```bash
  source .venv/bin/activate
  ```

### Step 3.2: Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3.3: Configure Environment Variables
Copy `.env.example` to `.env`:
- **Windows (PowerShell)**:
  ```powershell
  Copy-Item .env.example .env
  ```
- **Linux / macOS**:
  ```bash
  cp .env.example .env
  ```

Default development configuration:
```ini
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=dev-healthcare-security-secret-key-change-in-prod
DATABASE_URL=sqlite:///healthcare_security.db
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
SNAPSHOT_DIR=../data/snapshots
AFTER_HOURS_START=20:00
AFTER_HOURS_END=06:00
DEFAULT_COOLDOWN_SECONDS=15
DEMO_MODE=true
TARGET_FPS=15
YOLO_MODEL=yolov8n.pt
YOLO_CONFIDENCE=0.45
YOLO_DEVICE=cpu
```

### Step 3.4: Verify AI Models & Seed Database
Initialize the database with default healthcare cameras and restricted zones:
```bash
python scripts/init_db.py
```

Ensure the Isolation Forest model and baseline statistics are generated:
```bash
python scripts/train_anomaly_model.py
```
*(Model artifacts are saved to `data/models/isolation_forest.joblib`, `scaler.joblib`, and `baseline_statistics.json`)*.

---

## 4. Frontend Setup

In a second terminal window, navigate to `frontend/`:

```bash
cd frontend
```

### Step 4.1: Install Node Dependencies
```bash
npm install
```

### Step 4.2: Optional Environment Variables
Copy `.env.example` to `.env` if configuring custom backend URLs:
```bash
# Windows
Copy-Item .env.example .env
# Linux/macOS
cp .env.example .env
```
*(Leave values empty for default Vite proxying to `http://127.0.0.1:5000`)*.

---

## 5. Running the Application

### Running in Development Mode
1. **Start Backend Service**:
   ```bash
   cd backend
   .\.venv\Scripts\python run.py
   ```
   *Output indicates: `[*] AI Healthcare Security System running on http://127.0.0.1:5000`*

2. **Start Frontend Development Server**:
   ```bash
   cd frontend
   npm run dev
   ```
   *Frontend is accessible at `http://localhost:5173`*.

### Compiling Frontend for Production
```bash
cd frontend
npm run build
```
Compiled production assets are written to `frontend/dist/`.

---

## 6. Configuring Camera Feeds (Demo, Webcam, RTSP)

MedGuard AI supports three camera ingestion modes without requiring code changes:

### Mode 1: Pre-Packaged Demo Video Files (No Hardware Required)
Sample healthcare security MP4 files are included in `data/videos/`:
- `icu_sample.mp4`: ICU ward surveillance feed.
- `emergency_sample.mp4`: Emergency room trauma bay entrance.
- `pharmacy_sample.mp4`: Pharmacy storage vault.
- `lab_sample.mp4`: Pathology and biosecurity laboratory.

To configure a camera with a video file, set:
- `source_type`: `video_file`
- `source`: `data/videos/icu_sample.mp4`

### Mode 2: Physical Laptop / USB Webcam
Connect your USB webcam or use your built-in laptop camera:
- `source_type`: `webcam`
- `source`: `0` (or `1` for secondary external webcam)

*Note: The physical webcam feed will immediately process live persons standing in front of your camera, evaluating spatial zones and ground-contact points in real time.*

### Mode 3: Network RTSP IP Camera
For commercial IP cameras:
- `source_type`: `rtsp`
- `source`: `rtsp://username:password@192.168.1.100:554/stream1`

*Note: Ensure the RTSP URL is reachable over the local network from the machine running the backend.*

---

## 7. Running Automated Tests

Run the complete regression test suite:
```bash
cd backend
.\.venv\Scripts\pytest -v tests/
```
**Expected Result**: All 82 tests pass in ~11 seconds across 12 test suites.

---

## 8. Running Empirical Benchmarks

Measure real hardware inference throughput and API latencies:
```bash
cd backend
.\.venv\Scripts\python scripts/benchmark_performance.py
```
This measures YOLO inference FPS on CPU, ML Isolation Forest inference speed, process memory footprint, and REST API response times.
