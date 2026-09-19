"""
Benchmark Performance & Empirical Diagnostic Script
MedGuard AI - AI-Based Security System in Healthcare
Measures YOLO inference latency, ML anomaly detection latency,
API response times, and system resource utilization.
"""

import os
import sys
import time
import numpy as np
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.detection import get_detector
from app.services.ml_service import ml_service
from app.ml.features import FEATURE_NAMES


def benchmark_yolo(num_frames=30):
    """Measures raw Ultralytics YOLO inference latency on standard 640x480 frame."""
    print(f"\n[1/4] Benchmarking YOLO Object Detector ({num_frames} frames)...")
    detector = get_detector({'YOLO_DEVICE': 'cpu'})
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Warmup
    detector.detect(test_frame)

    latencies = []
    for _ in range(num_frames):
        start = time.perf_counter()
        detector.detect(test_frame)
        latencies.append((time.perf_counter() - start) * 1000.0)

    avg_ms = float(np.mean(latencies))
    p95_ms = float(np.percentile(latencies, 95))
    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0

    print(f"  - Average YOLO Latency: {avg_ms:.2f} ms")
    print(f"  - 95th Percentile:      {p95_ms:.2f} ms")
    print(f"  - Effective Throughput: {fps:.1f} FPS")
    return {
        'model': detector.model_name,
        'device': detector.device,
        'avg_latency_ms': round(avg_ms, 2),
        'p95_latency_ms': round(p95_ms, 2),
        'throughput_fps': round(fps, 1)
    }


def benchmark_ml(num_inferences=100):
    """Measures ML Feature Extraction & Isolation Forest inference latency."""
    print(f"\n[2/4] Benchmarking ML Anomaly Detection Engine ({num_inferences} iterations)...")
    synthetic_vector = [0.15 * (i % 7) for i in range(len(FEATURE_NAMES))]

    latencies = []
    for i in range(num_inferences):
        start = time.perf_counter()
        # Direct detector prediction to measure raw ML algorithmic latency
        ml_service.detector.predict_one(synthetic_vector)
        latencies.append((time.perf_counter() - start) * 1000.0)

    avg_ms = float(np.mean(latencies))
    p95_ms = float(np.percentile(latencies, 95))
    calls_per_sec = 1000.0 / avg_ms if avg_ms > 0 else 0.0

    print(f"  - Average ML Latency:   {avg_ms:.4f} ms")
    print(f"  - 95th Percentile:      {p95_ms:.4f} ms")
    print(f"  - Prediction Capacity:  {calls_per_sec:.1f} inferences/sec")
    return {
        'avg_latency_ms': round(avg_ms, 4),
        'p95_latency_ms': round(p95_ms, 4),
        'inferences_per_sec': round(calls_per_sec, 1)
    }


def benchmark_api_endpoints(num_requests=25):
    """Measures REST API response times for core surveillance endpoints."""
    print(f"\n[3/4] Benchmarking Core REST API Endpoints ({num_requests} requests each)...")
    app = create_app('testing')
    from app.extensions import db
    with app.app_context():
        db.create_all()
    client = app.test_client()

    endpoints = [
        ('/api/health', 'GET /api/health'),
        ('/api/statistics/dashboard', 'GET /api/statistics/dashboard'),
        ('/api/alerts/', 'GET /api/alerts/'),
        ('/api/events/', 'GET /api/events/'),
        ('/api/settings/', 'GET /api/settings/')
    ]

    api_results = {}
    for url, label in endpoints:
        durations = []
        for _ in range(num_requests):
            t0 = time.perf_counter()
            res = client.get(url)
            durations.append((time.perf_counter() - t0) * 1000.0)
            assert res.status_code == 200, f"Endpoint {url} failed with status {res.status_code}"

        avg_lat = float(np.mean(durations))
        p95_lat = float(np.percentile(durations, 95))
        api_results[label] = {
            'avg_ms': round(avg_lat, 2),
            'p95_ms': round(p95_lat, 2)
        }
        print(f"  - {label:<32}: avg = {avg_lat:.2f} ms | p95 = {p95_lat:.2f} ms")

    return api_results


def benchmark_system_resources():
    """Captures memory and CPU metrics for the Python process."""
    print("\n[4/4] Capturing System Resource Utilization...")
    import psutil
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / (1024 * 1024)
    cpu_pct = process.cpu_percent(interval=0.5)

    print(f"  - Process Memory (RSS): {ram_mb:.1f} MB")
    print(f"  - Process CPU Load:     {cpu_pct:.1f}%")
    return {
        'memory_rss_mb': round(ram_mb, 1),
        'cpu_load_percent': round(cpu_pct, 1)
    }


def main():
    print("=" * 65)
    print("MEDGUARD AI - SYSTEM PERFORMANCE & DIAGNOSTIC BENCHMARK")
    print("=" * 65)

    yolo_stats = benchmark_yolo(num_frames=20)
    ml_stats = benchmark_ml(num_inferences=50)
    api_stats = benchmark_api_endpoints(num_requests=20)
    res_stats = benchmark_system_resources()

    print("\n" + "=" * 65)
    print("BENCHMARK SUMMARY")
    print("=" * 65)
    print(f"YOLO Inference Throughput:   {yolo_stats['throughput_fps']} FPS (avg: {yolo_stats['avg_latency_ms']} ms)")
    print(f"ML Anomaly Inference:        {ml_stats['inferences_per_sec']} inf/s (avg: {ml_stats['avg_latency_ms']} ms)")
    print(f"Dashboard API Latency:       {api_stats['GET /api/statistics/dashboard']['avg_ms']} ms")
    print(f"Process Memory (RSS):        {res_stats['memory_rss_mb']} MB")
    print("=" * 65)


if __name__ == '__main__':
    main()
