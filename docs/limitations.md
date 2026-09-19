# System Boundaries, Assumptions & Limitations: MedGuard AI

## 1. Project Purpose & Engineering Prototype Status

**MedGuard AI** is an advanced engineering prototype developed as an intelligent Physical Security Monitoring System for healthcare environments. 

> [!CAUTION]
> **Operational Disclaimer**:
> This system is designed as an **operator-assistive decision support tool**. It is **not** a fully autonomous security guard or a certified life-safety emergency dispatch system. Security personnel must always verify alerts before taking physical enforcement action.

---

## 2. Hardware & Infrastructure Verification Limitations

### 2.1 RTSP Physical Hardware Status (`PARTIALLY VERIFIED`)
- **Implemented Architecture**: The `VideoProcessor` component fully supports RTSP camera stream URLs (`rtsp://user:pass@ip:port/stream`) utilizing OpenCV's underlying FFmpeg transport.
- **Limitation**: During system development and automated testing, a physical commercial IP camera (e.g. Axis, Hikvision) was not available in the local network environment. The RTSP code path is implemented and syntactically verified, but end-to-end hardware validation on an active CCTV network was not executed.

### 2.2 Continuous Soak Testing (`NOT TESTED`)
- **Current Verification**: Multi-camera concurrency and state isolation were verified over 15-second to 5-minute active stress sessions, and memory pruning was verified via unit tests (`test_cooldown_bounded_memory_pruning`).
- **Limitation**: A continuous 72-hour soak test under uninterrupted live multi-camera load was not performed due to development workstation constraints.

### 2.3 Physical Intrusion Drills (`NOT TESTED`)
- **Current Verification**: Spatial containment, loitering, after-hours intrusion, and crowd buildup were verified using recorded MP4 surveillance footage, synthetic test frames, and real-time physical webcam interaction.
- **Limitation**: Real-world penetration testing and staged physical intrusion drills within an active, operational hospital building were not conducted.

### 2.4 Compute Hardware Dependency & Performance Variance
- **Measured Baseline**: Benchmarks (25.8 FPS YOLO, 74.4 inferences/sec ML, 4.44 ms dashboard API latency) were recorded on an Intel Core i7-13700H CPU with 16 GB RAM running Windows 11.
- **Limitation**: Performance will vary significantly depending on the host machine's processor architecture, available CPU cores, clock speed, thermal throttling, and whether a dedicated NVIDIA CUDA GPU is available.

### 2.5 Cloud vs. Edge Network Topology
- **Limitation**: If the backend is hosted on a public cloud provider (AWS, GCP), it cannot directly access private IP cameras or USB webcams on a local hospital LAN without establishing an encrypted site-to-site VPN tunnel or WebRTC forwarder.

---

## 3. Machine Learning & Modeling Limitations

### 3.1 Synthetic Baseline Training Dataset
- **Implemented Architecture**: The unsupervised Isolation Forest anomaly detection model was trained on a 2,200-sample 19-dimensional surveillance dataset generated via `backend/scripts/generate_ml_dataset.py`. The synthetic data simulates normal hospital facility traffic (day shifts, shift changes, maintenance) alongside statistical anomalies (after-hours intrusion, loitering, rapid crowd surges).
- **Limitation**: While mathematically sound and calibrated with `StandardScaler`, the synthetic dataset does not encapsulate the full environmental variance of every physical hospital. In an enterprise production deployment, the model should be fine-tuned or retrained on 14–30 days of site-specific historical telemetry.

### 3.2 Camera Perspective & Ground-Contact Geometry
- **Assumption**: The ground-contact point-in-polygon algorithm assumes cameras are mounted at a typical surveillance angle ($30^\circ$ to $60^\circ$ pitch) with an unobstructed view of the floor plane.
- **Limitation**: Extremely high top-down (nadir) ceiling mounts or near-horizontal floor-level angles distort bounding box ratios and can cause slight inaccuracies in bottom-center contact point calculations.

### 3.3 Visual Obstruction & Severe Occlusion
- **Limitation**: Severe optical obstructions—such as intense camera glare, heavy smoke, pitch-black lighting, or extreme crowd density where individuals are completely hidden—will degrade YOLOv8n object detection confidences. The system relies on optical visibility.

---

## 4. Ethical & Non-Biometric Scope Boundaries

MedGuard AI strictly enforces the following ethical boundaries by design:
- **No Facial Recognition**: The system cannot identify, recognize, or match human faces against any database.
- **No Biometric Tracking**: No fingerprints, iris patterns, gait signatures, or unique anatomical metrics are captured or computed.
- **No Clinical Diagnosis**: The system cannot detect medical emergencies, patient falls, heart attacks, or vital signs.
- **Ephemeral Session Tokens**: Track IDs are volatile integer counters that reset on stream restart and cannot track individuals across different days or external facilities.
