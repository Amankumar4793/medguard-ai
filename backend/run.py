import os
from dotenv import load_dotenv
from app import create_app
from app.extensions import socketio

load_dotenv()

flask_env = os.getenv('FLASK_ENV') or ('production' if os.getenv('RENDER') or os.getenv('PORT') else 'development')
app = create_app(flask_env)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    is_prod = (flask_env == 'production') or bool(os.getenv('RENDER'))
    debug = False if is_prod else app.config.get('DEBUG', False)
    use_reloader = False if is_prod else debug
    print(f"[*] AI Healthcare Security System running on http://{host}:{port} [{flask_env}]")
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=use_reloader, allow_unsafe_werkzeug=True)
