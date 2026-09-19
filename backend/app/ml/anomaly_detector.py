import os
import json
import joblib
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from app.ml.features import FEATURE_NAMES, get_feature_names
from app.utils import setup_logger

logger = setup_logger('anomaly_detector')


class AnomalyDetector:
    """
    Unsupervised Anomaly Detection engine for MedGuard AI.
    Wraps scikit-learn's Isolation Forest with StandardScaler preprocessing.
    Transforms raw decision function scores to calibrated 0-100 continuous threat scores
    and generates explainable feature deviation indicators grounded in baseline statistics.
    """

    def __init__(self, contamination=0.10, n_estimators=100, random_state=42):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.feature_names = get_feature_names()

        self.model = None
        self.scaler = None
        self.baseline_statistics = {}
        self.metadata = {}
        self.is_ready = False

    def train(self, X, y_true=None, metadata_extra=None):
        """
        Fits StandardScaler and IsolationForest on input feature matrix X.
        Computes baseline statistics for explainable deviation analysis.

        Args:
            X (np.ndarray or list): Feature matrix of shape (n_samples, 19).
            y_true (np.ndarray, optional): Ground truth labels (0=normal, 1=anomaly) for test metrics.
            metadata_extra (dict, optional): Additional training metadata to store.

        Returns:
            dict: Evaluation and training summary.
        """
        X_arr = np.asarray(X, dtype=np.float64)
        n_samples, n_features = X_arr.shape

        if n_features != len(self.feature_names):
            raise ValueError(f"Expected {len(self.feature_names)} features, got {n_features}")

        logger.info(f"Fitting StandardScaler on {n_samples} training samples...")
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X_arr)

        logger.info(f"Training IsolationForest (n_estimators={self.n_estimators}, contamination={self.contamination})...")
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1
        )
        self.model.fit(X_scaled)

        # Compute baseline statistical distributions for explainability
        stats = {}
        for idx, feat_name in enumerate(self.feature_names):
            vals = X_arr[:, idx]
            stats[feat_name] = {
                'mean': float(round(np.mean(vals), 4)),
                'std': float(round(np.std(vals), 4)),
                'median': float(round(np.median(vals), 4)),
                'min': float(round(np.min(vals), 4)),
                'max': float(round(np.max(vals), 4)),
                'p25': float(round(np.percentile(vals, 25), 4)),
                'p75': float(round(np.percentile(vals, 75), 4)),
                'p95': float(round(np.percentile(vals, 95), 4))
            }
        self.baseline_statistics = stats

        # Evaluate performance on training data if ground truth is available
        metrics = {}
        if y_true is not None:
            raw_preds = self.model.predict(X_scaled)  # +1 = normal, -1 = anomaly
            pred_anomalies = (raw_preds == -1).astype(int)
            y_arr = np.asarray(y_true, dtype=int)

            tp = int(np.sum((pred_anomalies == 1) & (y_arr == 1)))
            fp = int(np.sum((pred_anomalies == 1) & (y_arr == 0)))
            tn = int(np.sum((pred_anomalies == 0) & (y_arr == 0)))
            fn = int(np.sum((pred_anomalies == 0) & (y_arr == 1)))

            precision = round(tp / max(1, (tp + fp)), 4)
            recall = round(tp / max(1, (tp + fn)), 4)
            f1 = round(2 * (precision * recall) / max(1e-6, (precision + recall)), 4)
            accuracy = round((tp + tn) / max(1, len(y_arr)), 4)

            metrics = {
                'samples_evaluated': len(y_arr),
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'accuracy': accuracy,
                'confusion_matrix': {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn}
            }
            logger.info(f"Model Training Metrics: Precision={precision:.3f}, Recall={recall:.3f}, F1={f1:.3f}")

        self.metadata = {
            'model_type': 'IsolationForest',
            'algorithm': 'Unsupervised Isolation Forest with StandardScaler',
            'version': '1.0.0',
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'feature_count': n_features,
            'feature_names': self.feature_names,
            'hyperparameters': {
                'n_estimators': self.n_estimators,
                'contamination': self.contamination,
                'random_state': self.random_state
            },
            'sample_count': n_samples,
            'evaluation_metrics': metrics
        }
        if metadata_extra:
            self.metadata.update(metadata_extra)

        self.is_ready = True
        return self.metadata

    def predict_one(self, feature_vector):
        """
        Runs anomaly detection on a single 19-dimensional feature vector.

        Args:
            feature_vector (list or np.ndarray): 19-dimensional numerical array.

        Returns:
            dict: {
                'is_anomaly': bool,
                'anomaly_score': float (0.0 to 100.0),
                'raw_decision_score': float,
                'indicators': list[str] (explainable top drivers)
            }
        """
        if not self.is_ready or self.model is None or self.scaler is None:
            return {
                'is_anomaly': False,
                'anomaly_score': 0.0,
                'raw_decision_score': 0.0,
                'indicators': ['ML model unavailable - default neutral score']
            }

        arr = np.asarray(feature_vector, dtype=np.float64).reshape(1, -1)
        scaled = self.scaler.transform(arr)

        # Raw decision score: positive = normal, negative = anomalous
        raw_score = float(self.model.decision_function(scaled)[0])
        pred_label = int(self.model.predict(scaled)[0])  # +1 = normal, -1 = anomaly
        is_anomaly = (pred_label == -1)

        # Calibrate raw decision function score (-0.35 to +0.20 typical range) to 0.0 - 100.0
        # Score calibration:
        # raw >= 0.15 -> score ~ 0
        # raw == 0.00 -> score ~ 37.5
        # raw == -0.10 -> score ~ 62.5
        # raw <= -0.25 -> score -> 100
        calibrated = (0.15 - raw_score) / 0.40 * 100.0
        anomaly_score = float(round(max(0.0, min(100.0, calibrated)), 1))

        # Generate explainable indicators based on standardized deviation from baseline
        indicators = self._explain_deviations(feature_vector, is_anomaly)

        return {
            'is_anomaly': is_anomaly,
            'anomaly_score': anomaly_score,
            'raw_decision_score': round(raw_score, 4),
            'indicators': indicators
        }

    def _explain_deviations(self, feature_vector, is_anomaly):
        """
        Compares sample feature values against normal baseline distributions
        and generates human-readable explanations for significant deviations.
        """
        deviations = []
        vec = list(feature_vector)

        for idx, feat_name in enumerate(self.feature_names):
            val = vec[idx]
            base = self.baseline_statistics.get(feat_name)
            if not base:
                continue

            mean = base['mean']
            std = max(base['std'], 1e-4)
            z_score = (val - mean) / std

            deviations.append({
                'feature': feat_name,
                'value': val,
                'mean': mean,
                'std': std,
                'z_score': z_score
            })

        # Filter and explain features that deviate meaningfully
        explanations = []

        # Feature-specific contextual templates
        for dev in sorted(deviations, key=lambda d: abs(d['z_score']), reverse=True):
            feat = dev['feature']
            val = dev['value']
            mean = dev['mean']
            z = dev['z_score']

            if feat == 'time_in_restricted_zone' and val >= 15.0 and z > 1.0:
                explanations.append(f"Elevated restricted zone dwell time ({val:.1f}s vs avg {mean:.1f}s)")
            elif feat == 'after_hours_activity' and val >= 0.5:
                explanations.append("Off-hours presence detected outside standard facility schedule")
            elif feat == 'loitering_events' and val >= 1.0:
                explanations.append(f"Stationary loitering violation observed ({int(val)} lingering track)")
            elif feat == 'crowd_level' and val >= 3.0 and z > 1.2:
                explanations.append(f"High occupant concentration in surveillance zone ({int(val)} persons)")
            elif feat == 'restricted_zone_entries' and val >= 2.0 and z > 1.2:
                explanations.append(f"Unusually high restricted zone ingress rate ({int(val)} entries)")
            elif feat == 'repeated_entries' and val >= 2.0 and z > 1.2:
                explanations.append(f"Repeated ingress attempts detected ({int(val)} visits in window)")
            elif feat == 'movement_speed' and val < 10.0 and z < -1.2:
                explanations.append(f"Abnormally sluggish/stationary movement pattern ({val:.1f} px/s vs avg {mean:.1f})")
            elif feat == 'event_frequency' and val >= 2.0 and z > 1.2:
                explanations.append(f"Multiple co-occurring security violations ({int(val)} events)")
            elif feat == 'unique_tracks' and val >= 6.0 and z > 1.5:
                explanations.append(f"High pedestrian volume density ({int(val)} active tracks)")

            if len(explanations) >= 3:
                break

        if not explanations:
            if is_anomaly:
                explanations.append("Compound multivariate deviation from normal hospital operational baseline")
            else:
                explanations.append("Surveillance metrics align with standard operational baseline")

        return explanations

    def save(self, models_dir):
        """
        Serializes the trained Isolation Forest model, scaler, metadata,
        and baseline statistics to the specified directory.
        """
        out_dir = Path(models_dir)
        os.makedirs(out_dir, exist_ok=True)

        model_path = out_dir / 'isolation_forest.joblib'
        scaler_path = out_dir / 'scaler.joblib'
        meta_path = out_dir / 'model_metadata.json'
        stats_path = out_dir / 'baseline_statistics.json'

        joblib.dump(self.model, str(model_path))
        joblib.dump(self.scaler, str(scaler_path))

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2)

        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(self.baseline_statistics, f, indent=2)

        logger.info(f"Saved AnomalyDetector artifacts to {out_dir}")
        return {
            'model_path': str(model_path),
            'scaler_path': str(scaler_path),
            'metadata_path': str(meta_path),
            'statistics_path': str(stats_path)
        }

    def load(self, models_dir):
        """
        Deserializes trained Isolation Forest artifacts from disk.
        Returns True if successful, False otherwise.
        """
        try:
            in_dir = Path(models_dir)
            model_path = in_dir / 'isolation_forest.joblib'
            scaler_path = in_dir / 'scaler.joblib'
            meta_path = in_dir / 'model_metadata.json'
            stats_path = in_dir / 'baseline_statistics.json'

            if not model_path.exists() or not scaler_path.exists():
                logger.warning(f"Model artifacts missing in {models_dir}. ML detection unavailable.")
                self.is_ready = False
                return False

            self.model = joblib.load(str(model_path))
            self.scaler = joblib.load(str(scaler_path))

            if meta_path.exists():
                with open(meta_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)

            if stats_path.exists():
                with open(stats_path, 'r', encoding='utf-8') as f:
                    self.baseline_statistics = json.load(f)

            self.is_ready = True
            logger.info(f"Loaded AnomalyDetector successfully from {in_dir}.")
            return True
        except Exception as e:
            logger.error(f"Failed to load AnomalyDetector artifacts: {e}")
            self.is_ready = False
            return False
