"""
Training script for MedGuard AI Isolation Forest Anomaly Detection Model.
Reads synthetic security event dataset, trains StandardScaler and IsolationForest,
evaluates precision/recall/F1, and serializes model artifacts to data/models/.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ml.features import FEATURE_NAMES
from app.ml.anomaly_detector import AnomalyDetector


def train_model():
    project_root = backend_dir.parent
    data_csv = project_root / 'data' / 'ml' / 'synthetic_security_events.csv'
    models_dir = project_root / 'data' / 'models'

    if not data_csv.exists():
        print(f"Error: Dataset not found at {data_csv}")
        print("Please run 'python scripts/generate_ml_dataset.py' first.")
        sys.exit(1)

    print(f"Loading synthetic dataset from: {data_csv}")
    df = pd.read_csv(data_csv)
    print(f"Loaded {len(df)} records with {len(df.columns)} columns.")

    # Validate feature columns presence
    missing_cols = [col for col in FEATURE_NAMES if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing required feature columns: {missing_cols}")
        sys.exit(1)

    X = df[FEATURE_NAMES].values
    y_true = df['is_anomaly'].values if 'is_anomaly' in df.columns else None

    # Calculate actual contamination in dataset
    actual_contamination = float(np.mean(y_true)) if y_true is not None else 0.10
    print(f"Empirical contamination rate: {actual_contamination:.3f}")

    # Instantiate detector with calibrated contamination
    detector = AnomalyDetector(
        contamination=min(0.15, max(0.05, actual_contamination)),
        n_estimators=100,
        random_state=42
    )

    print("Training Isolation Forest Anomaly Detector...")
    metadata = detector.train(X, y_true=y_true, metadata_extra={
        'dataset_source': str(data_csv),
        'trained_samples': len(df),
        'normal_samples': int(np.sum(y_true == 0)) if y_true is not None else len(df),
        'anomaly_samples': int(np.sum(y_true == 1)) if y_true is not None else 0
    })

    # Test sample inference on known cases
    print("\n--- Model Inference Sanity Check ---")
    normal_sample = df[df['is_anomaly'] == 0].iloc[0][FEATURE_NAMES].values
    anomaly_sample = df[df['is_anomaly'] == 1].iloc[0][FEATURE_NAMES].values

    res_norm = detector.predict_one(normal_sample)
    print(f"Normal Case Inference:")
    print(f"  - Is Anomaly: {res_norm['is_anomaly']}")
    print(f"  - ML Threat Score: {res_norm['anomaly_score']} / 100")
    print(f"  - Raw Decision Score: {res_norm['raw_decision_score']}")
    print(f"  - Explanation: {res_norm['indicators']}")

    res_anom = detector.predict_one(anomaly_sample)
    print(f"\nAnomalous Case Inference:")
    print(f"  - Is Anomaly: {res_anom['is_anomaly']}")
    print(f"  - ML Threat Score: {res_anom['anomaly_score']} / 100")
    print(f"  - Raw Decision Score: {res_anom['raw_decision_score']}")
    print(f"  - Explanation: {res_anom['indicators']}")

    # Save artifacts
    print(f"\nSaving model artifacts to: {models_dir}")
    saved = detector.save(models_dir)
    for k, p in saved.items():
        print(f"  [OK] {k}: {p}")

    print("\n=== Model Training Complete and Verified! ===")


if __name__ == '__main__':
    train_model()
