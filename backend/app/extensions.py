from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO

# Initialize unattached extensions (Application Factory pattern)
db = SQLAlchemy()
cors = CORS()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
