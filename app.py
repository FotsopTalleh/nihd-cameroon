import eventlet
eventlet.monkey_patch()

from flask import Flask
from config import Config
from extensions import db, login_manager, bcrypt, socketio
from models import User
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to download data.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.api import api_bp
    from routes.download import download_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(download_bp)

    # Register SocketIO events
    from routes.socket_events import register_socket_events
    register_socket_events(socketio)

    # Create DB tables and seed sample data
    with app.app_context():
        db.create_all()
        from utils.seed_data import seed_database
        seed_database()

    # Start background probe scheduler
    _start_probe_scheduler(app)

    return app


def _start_probe_scheduler(app):
    """Start APScheduler to run probe cycle every 30 seconds."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from utils.probe_agent import run_probe_cycle

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            func=run_probe_cycle,
            args=[app, socketio],
            trigger='interval',
            seconds=30,
            id='probe_cycle',
            name='Real-time Probe',
            replace_existing=True,
            max_instances=1,
        )
        scheduler.start()
        logger.info('Probe scheduler started — measuring every 30 seconds')
    except Exception as e:
        logger.error(f'Failed to start probe scheduler: {e}')


if __name__ == '__main__':
    app = create_app()
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', False)
    socketio.run(app, debug=debug, host='0.0.0.0', port=port, use_reloader=False)
