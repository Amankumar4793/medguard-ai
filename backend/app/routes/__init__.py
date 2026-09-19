from app.routes.health import health_bp
from app.routes.cameras import cameras_bp
from app.routes.events import events_bp
from app.routes.alerts import alerts_bp
from app.routes.statistics import statistics_bp
from app.routes.monitoring import monitoring_bp
from app.routes.settings import settings_bp
from app.routes.ml import ml_bp


def register_routes(app):
    """Register all API route blueprints to the Flask application."""
    app.register_blueprint(health_bp, url_prefix='/api')
    app.register_blueprint(cameras_bp, url_prefix='/api/cameras')
    app.register_blueprint(events_bp, url_prefix='/api/events')
    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')
    app.register_blueprint(statistics_bp, url_prefix='/api/statistics')
    app.register_blueprint(monitoring_bp, url_prefix='/api/monitoring')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')
    app.register_blueprint(ml_bp, url_prefix='/api/ml')
