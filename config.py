import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ── Security ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'nihd-dev-secret-change-in-production')

    # ── Database ──────────────────────────────────────────────
    # Supports DATABASE_URL env var (for PostgreSQL in production)
    # Falls back to SQLite locally and on platforms with disk mounts
    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url.startswith('postgres://'):          # Heroku legacy
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = _db_url or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'dashboard.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Sessions ──────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # ── File storage ─────────────────────────────────────────
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')

    # ── Port (Railway / Render inject PORT env var) ──────────
    PORT = int(os.environ.get('PORT', 5000))

    # ── Environment ───────────────────────────────────────────
    DEBUG = os.environ.get('FLASK_ENV', 'development') == 'development'

    # Ensure required directories exist
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)
