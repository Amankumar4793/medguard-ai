import os
import time
import threading
from pathlib import Path
from datetime import datetime, timezone
from flask import current_app
from app.ml.anomaly_detector import AnomalyDetector
from app.ml.features import FEATURE_NAMES
from app.services.security_engine import calculate_risk_level
from app.utils import setup_logger

logger = setup_logger('ml_service')


class MLService:
    """
    Singleton Service managing Machine Learning Anomaly Detection and Risk Fusion.
    Provides thread-safe model lifecycle management, periodic inference caching per camera,
    graceful degradation fallback, and explainable risk fusion calculations.
    """

    DEFAULT_RULE_WEIGHT = 0.70
    DEFAULT_ML_WEIGHT = 0.30

    def __init__(self, models_dir=None):
        self._lock = threading.Lock()
        self.models_dir = models_dir or self._resolve_default_models_dir()
        self.detector = AnomalyDetector()
        self.status = 'UNINITIALIZED'
        self.last_load_error = None

        # Camera inference cache: camera_id -> (timestamp, result_dict)
        self._inference_cache = {}

        # Attempt initial load
        self.load_model()

    def _resolve_default_models_dir(self):
        """Resolves models directory relative to backend or project root."""
        base_dir = Path(__file__).resolve().parent.parent.parent
        candidate = base_dir.parent / 'data' / 'models'
        if candidate.exists():
            return str(candidate)
        candidate2 = base_dir / 'data' / 'models'
        return str(candidate2)

    def load_model(self, models_dir=None):
        """
        Loads the trained Isolation Forest and scaler from disk.
        Gracefully marks status as UNAVAILABLE if files are missing or corrupt.
        """
        with self._lock:
            target_dir = models_dir or self._resolve_default_models_dir()
            self.models_dir = target_dir

            try:
                success = self.detector.load(target_dir)
                if success:
                    self.status = 'READY'
                    self.last_load_error = None
                    logger.info(f"MLService model loaded successfully from {target_dir}. Status: READY")
                    return True
                else:
                    self.status = 'UNAVAILABLE'
                    self.last_load_error = "Model artifacts missing or incomplete."
                    logger.warning("MLService: Model artifacts not found. Graceful fallback active.")
                    return False
            except Exception as e:
                self.status = 'UNAVAILABLE'
                self.last_load_error = str(e)
                logger.error(f"MLService failed to load model: {e}. Graceful fallback active.")
                return False

    def get_status(self):
        """Returns comprehensive health, configuration, and metadata for the ML subsystem."""
        with self._lock:
            meta = self.detector.metadata or {}
            eval_metrics = meta.get('evaluation_metrics', {})
            return {
                'status': self.status,
                'is_ready': (self.status == 'READY'),
                'model_type': meta.get('model_type', 'IsolationForest'),
                'algorithm': meta.get('algorithm', 'Unsupervised Isolation Forest with StandardScaler'),
                'version': meta.get('version', '1.0.0'),
                'trained_at': meta.get('trained_at'),
                'feature_count': len(FEATURE_NAMES),
                'feature_names': list(FEATURE_NAMES),
                'hyperparameters': meta.get('hyperparameters', {}),
                'sample_count': meta.get('sample_count', 0),
                'evaluation_metrics': eval_metrics,
                'models_directory': self.models_dir,
                'last_error': self.last_load_error
            }

    def analyze_camera(self, camera_id, feature_vector, cache_ttl=5.0):
        """
        Evaluates a 19-dimensional feature vector for a camera.
        Employs short-lived caching to avoid redundant inferences on identical frames.

        Returns:
            dict: {
                'camera_id': int,
                'is_anomaly': bool,
                'anomaly_score': float, # 0-100
                'raw_score': float,
                'indicators': list[str],
                'features': dict,
                'model_status': str,
                'timestamp': str
            }
        """
        now = time.time()

        with self._lock:
            # Check cache
            cached = self._inference_cache.get(camera_id)
            if cached and (now - cached['time']) < cache_ttl:
                return cached['data']

        # Format features dict
        feat_dict = {}
        if isinstance(feature_vector, dict):
            feat_list = [float(feature_vector.get(k, 0.0)) for k in FEATURE_NAMES]
            feat_dict = dict(feature_vector)
        else:
            feat_list = [float(v) for v in (feature_vector or [0.0] * len(FEATURE_NAMES))]
            feat_dict = {k: v for k, v in zip(FEATURE_NAMES, feat_list)}

        # Perform inference
        if self.status != 'READY':
            res = {
                'camera_id': camera_id,
                'is_anomaly': False,
                'anomaly_score': 0.0,
                'raw_score': 0.0,
                'indicators': ['ML anomaly detection unavailable (model offline)'],
                'features': feat_dict,
                'model_status': self.status,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        else:
            try:
                pred = self.detector.predict_one(feat_list)
                res = {
                    'camera_id': camera_id,
                    'is_anomaly': pred['is_anomaly'],
                    'anomaly_score': pred['anomaly_score'],
                    'raw_score': pred['raw_decision_score'],
                    'indicators': pred['indicators'],
                    'features': feat_dict,
                    'model_status': 'READY',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                logger.warning(f"ML inference prediction error for camera #{camera_id}: {e}. Fallback active.")
                res = {
                    'camera_id': camera_id,
                    'is_anomaly': False,
                    'anomaly_score': 0.0,
                    'raw_score': 0.0,
                    'indicators': [f'ML inference degraded: {str(e)}'],
                    'features': feat_dict,
                    'model_status': 'DEGRADED',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

        # Update cache
        with self._lock:
            self._inference_cache[camera_id] = {
                'time': now,
                'data': res
            }

        return res

    def fuse_risk(self, rule_risk, ml_risk, rule_weight=None, ml_weight=None):
        """
        Combines deterministic rule risk with continuous ML anomaly risk score.

        Formula:
            final_risk = round(w_rule * rule_risk + w_ml * ml_risk, 1)

        If ML is unavailable or ml_risk is None, gracefully returns pure rule risk.

        Returns:
            tuple: (final_risk_score: float, risk_level: str)
        """
        r_risk = max(0.0, min(100.0, float(rule_risk)))

        # Graceful degradation if ML model is offline
        if self.status != 'READY' or ml_risk is None:
            return round(r_risk, 1), calculate_risk_level(r_risk)

        m_risk = max(0.0, min(100.0, float(ml_risk)))

        w_rule = float(rule_weight if rule_weight is not None else self.DEFAULT_RULE_WEIGHT)
        w_ml = float(ml_weight if ml_weight is not None else self.DEFAULT_ML_WEIGHT)

        # Normalize weights so they sum to 1.0
        total_w = w_rule + w_ml
        if total_w > 0:
            norm_w_rule = w_rule / total_w
            norm_w_ml = w_ml / total_w
        else:
            norm_w_rule = 0.70
            norm_w_ml = 0.30

        fused = (norm_w_rule * r_risk) + (norm_w_ml * m_risk)
        final_score = float(round(max(0.0, min(100.0, fused)), 1))
        risk_level = calculate_risk_level(final_score)

        return final_score, risk_level


# Global MLService Singleton
ml_service = MLService()
