import pytest
import sys
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.extensions import db


@pytest.fixture(scope='session')
def app():
    """Create testing application context."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Test HTTP client."""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Clean database session for each test function."""
    with app.app_context():
        # Clear tables before each test
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        yield db.session
        db.session.rollback()
