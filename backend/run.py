import os
from dotenv import load_dotenv
from app import create_app
from app.extensions import socketio

load_dotenv()

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    print(f"[*] AI Healthcare Security System running on http://127.0.0.1:{port}")
    socketio.run(app, host=host, port=port, debug=app.config.get('DEBUG', False), allow_unsafe_werkzeug=True)
