from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models.settings import SystemConfiguration

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/', methods=['GET'])
def get_settings():
    """Get all system configuration items with sensible defaults."""
    configs = SystemConfiguration.query.all()
    # Structured key-value dict for simple consumption
    settings_dict = {
        'operating_hours': {'start': '08:00', 'end': '20:00'},
        'crowd_threshold_count': 4,
        'loitering_threshold_seconds': 30,
        'alert_cooldown_seconds': 20,
        'detection_confidence_threshold': 0.45,
        'crowd_duration_seconds': 15,
        'repeated_entry_threshold': 3,
        'rule_risk_weight': 0.70,
        'ml_risk_weight': 0.30,
        'ml_feature_window_seconds': 60,
        'ml_inference_interval_seconds': 10
    }
    for c in configs:
        settings_dict[c.key] = c.value

    return jsonify({
        'success': True,
        'settings': settings_dict,
        'details': [c.to_dict() for c in configs]
    }), 200


@settings_bp.route('/', methods=['PUT'])
def update_settings():
    """Update one or multiple system configuration settings with strict input validation."""
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({
            'success': False,
            'error': 'Validation Error',
            'message': 'Request body must be a valid JSON object.'
        }), 400

    # Cross-field validation: weights cannot both sum to 0.0
    if 'rule_risk_weight' in data and 'ml_risk_weight' in data:
        try:
            r_w = float(data['rule_risk_weight'])
            m_w = float(data['ml_risk_weight'])
            if (r_w + m_w) <= 0.0:
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': 'The sum of rule_risk_weight and ml_risk_weight must be greater than 0.0.'
                }), 400
        except (ValueError, TypeError):
            pass

    # Validation rules
    for key, val in data.items():
        if key in ('rule_risk_weight', 'ml_risk_weight'):
            try:
                f_val = float(val)
                if not (0.0 <= f_val <= 1.0):
                    return jsonify({
                        'success': False,
                        'error': 'Validation Error',
                        'message': f"Setting '{key}' must be a numeric weight between 0.0 and 1.0."
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': f"Setting '{key}' must be a numeric value."
                }), 400

        elif key in ('alert_cooldown_seconds', 'loitering_threshold_seconds', 'crowd_duration_seconds'):
            try:
                f_val = float(val)
                if f_val < 1.0:
                    return jsonify({
                        'success': False,
                        'error': 'Validation Error',
                        'message': f"Setting '{key}' must be at least 1 second."
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': f"Setting '{key}' must be a positive numeric value."
                }), 400

        elif key in ('crowd_threshold_count', 'repeated_entry_threshold'):
            try:
                i_val = int(val)
                if i_val < 1:
                    return jsonify({
                        'success': False,
                        'error': 'Validation Error',
                        'message': f"Setting '{key}' must be an integer of at least 1."
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': f"Setting '{key}' must be an integer."
                }), 400

        elif key == 'detection_confidence_threshold':
            try:
                f_val = float(val)
                if not (0.05 <= f_val <= 1.0):
                    return jsonify({
                        'success': False,
                        'error': 'Validation Error',
                        'message': "Detection confidence threshold must be between 0.05 and 1.0."
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': "Detection confidence threshold must be a numeric value."
                }), 400

        elif key in ('ml_feature_window_seconds', 'ml_inference_interval_seconds'):
            try:
                i_val = int(val)
                if i_val < 1:
                    return jsonify({
                        'success': False,
                        'error': 'Validation Error',
                        'message': f"Setting '{key}' must be at least 1."
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': f"Setting '{key}' must be an integer."
                }), 400

        elif key == 'operating_hours':
            if not isinstance(val, dict) or 'start' not in val or 'end' not in val:
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': "Operating hours must be an object with 'start' and 'end' keys (e.g. {'start': '08:00', 'end': '20:00'})."
                }), 400
            for k in ('start', 'end'):
                time_str = str(val[k]).strip()
                parts = time_str.split(':')
                if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                    return jsonify({
                        'success': False,
                        'error': 'Validation Error',
                        'message': f"Invalid operating hours format for '{k}': expected 'HH:MM'."
                    }), 400
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    return jsonify({
                        'success': False,
                        'error': 'Validation Error',
                        'message': f"Invalid time range for '{k}': hour 0-23, minute 0-59."
                    }), 400

    updated_keys = []
    for key, val in data.items():
        config_item = SystemConfiguration.query.filter_by(key=key).first()
        if config_item:
            config_item.value = val
            updated_keys.append(key)
        else:
            new_item = SystemConfiguration(
                key=key,
                value=val,
                category='custom',
                description='Custom configuration key'
            )
            db.session.add(new_item)
            updated_keys.append(key)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Updated settings: {", ".join(updated_keys)}',
        'updated_keys': updated_keys
    }), 200
