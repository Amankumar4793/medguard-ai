# Production Deployment Guide: MedGuard AI

This document provides architectural guidance and instructions for deploying **MedGuard AI** in a production healthcare environment.

---

## 1. Architectural Overview: Development vs. Production

### Development Topology (Local Workstation)
```
Browser (React on Vite :5173)
       │ Proxy (/api, /socket.io)
       ▼
Flask + Socket.IO Server (:5000)
       ├── OpenCV VideoProcessor Threads
       ├── Ultralytics YOLOv8n (CPU Inference)
       ├── Isolation Forest ML Engine
       └── SQLite Database (healthcare_security.db)
```

### Production Topology (Hospital Surveillance Network)
```
React SOC Dashboard (Nginx / HTTPS Static Hosting)
       │
       │ HTTPS REST / WSS WebSocket
       ▼
Reverse Proxy / SSL Termination (Nginx / Traefik)
       │
       ▼
Flask WSGI/ASGI Application Server (Gunicorn + Eventlet Workers)
       ├── OpenCV Video Ingestion Threads (Per Camera)
       ├── YOLOv8n Object Detector (NVIDIA GPU / Multi-core CPU)
       ├── Isolation Forest Anomaly Detection Service
       └── PostgreSQL High-Availability Database Cluster
       │
       ▼ High-Bandwidth Dedicated VLAN / CCTV Subnet
Physical Camera Feeds (Axis, Hikvision, Hanwha RTSP Streams)
```

---

## 2. Frontend vs. Backend AI Worker Separation

A critical consideration when deploying computer vision platforms:
- **Frontend (React Dashboard)**: Consists purely of static JavaScript, HTML, and CSS assets. It can be hosted on standard web servers (Nginx, Apache) or static cloud storage (AWS S3, Cloudflare Pages, Vercel). The frontend consumes negligible CPU/RAM.
- **Backend (AI Video Pipeline)**: Continuously decodes H.264/H.265 RTSP streams, executes PyTorch neural network tensor operations, and runs machine learning inference. **It requires dedicated compute infrastructure** (server with modern multi-core CPU or NVIDIA Tensor Core GPU) positioned close to the video sources on the local network.

---

## 3. Camera Networking & Ingestion Considerations

> [!WARNING]
> **Camera Accessibility in Cloud vs. Local Deployments**:
> - **Local Workstation / On-Premise Server**: Can directly access physical USB webcams (`source="0"`) and local network RTSP cameras (`rtsp://192.168.1.x`).
> - **Cloud Hosted Backend (AWS/GCP/Azure)**: Cannot directly connect to a local laptop webcam or cameras behind hospital NAT firewalls without an encrypted VPN tunnel (WireGuard/Site-to-Site IPsec).
> - **Cloud Demonstrations**: For cloud-hosted demonstration instances, use the pre-packaged MP4 surveillance video files in `data/videos/` (`emergency_sample.mp4`, `icu_sample.mp4`), which loop seamlessly without requiring physical camera hardware.

---

## 4. Production Database Configuration (PostgreSQL)

While SQLite is optimal for local development and standalone appliance testing, enterprise deployments should utilize PostgreSQL:

### Step 4.1: Install PostgreSQL Driver
```bash
pip install psycopg2-binary>=2.9.0
```

### Step 4.2: Set Database Environment Variable
In production `.env`:
```ini
DATABASE_URL=postgresql://medguard_user:SecurePassword123@db.internal:5432/medguard_soc
```
Flask-SQLAlchemy automatically handles connection pooling and dialect mapping with zero application code changes.

---

## 5. Backend Production Configuration

### Step 5.1: Production `.env` Settings
```ini
# Environment
FLASK_ENV=production
DEBUG=False
SECRET_KEY=generate-a-strong-64-character-random-hex-string

# Database
DATABASE_URL=postgresql://medguard_user:SecurePassword123@db.internal:5432/medguard_soc

# Network & CORS
CORS_ORIGINS=https://soc.hospital.internal,https://192.168.10.50
HOST=0.0.0.0
PORT=5000

# Storage
SNAPSHOT_DIR=/var/lib/medguard/snapshots
VIDEO_DIR=/var/lib/medguard/videos
MODEL_DIR=/var/lib/medguard/models

# AI Vision & Device
YOLO_MODEL=yolov8n.pt
YOLO_DEVICE=cuda:0      # Use 'cpu' if no NVIDIA GPU is installed
TARGET_FPS=15
INFERENCE_INTERVAL_FRAMES=2
```

### Step 5.2: Gunicorn Production Execution
Run the Flask application with Gunicorn using Eventlet worker class for asynchronous WebSocket support:
```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 run:app
```
*(Note: Use 1 Gunicorn worker process so that in-memory camera video processors and trackers remain centralized, or manage camera workers via an external Celery/Daemon service).*

---

## 6. Frontend Production Build & Hosting

### Step 6.1: Build Production Assets
```bash
cd frontend
npm install
npm run build
```
The compiled bundle is output to `frontend/dist/`.

### Step 6.2: Sample Nginx Configuration
```nginx
server {
    listen 80;
    server_name soc.hospital.internal;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name soc.hospital.internal;

    ssl_certificate /etc/ssl/certs/medguard.crt;
    ssl_certificate_key /etc/ssl/private/medguard.key;

    # Serve React Static SPA
    root /var/www/medguard/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy REST API
    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy WebSockets
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

---

## 7. Systemd Service Specification (Linux)

Create `/etc/systemd/system/medguard.service`:
```ini
[Unit]
Description=MedGuard AI Healthcare Security Backend
After=network.target postgresql.service

[Service]
User=medguard
Group=medguard
WorkingDirectory=/opt/medguard/backend
Environment="PATH=/opt/medguard/backend/.venv/bin"
EnvironmentFile=/opt/medguard/backend/.env
ExecStart=/opt/medguard/backend/.venv/bin/gunicorn --worker-class eventlet -w 1 --bind 127.0.0.1:5000 run:app
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable medguard
sudo systemctl start medguard
```
