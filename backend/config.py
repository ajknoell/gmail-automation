import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google OAuth
    GOOGLE_CLIENT_SECRETS_FILE = os.path.join(basedir, 'credentials.json')
    GOOGLE_SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/calendar.readonly',
    ]
    GOOGLE_REDIRECT_URI = 'http://localhost:5001/auth/gmail/callback'

    # Anthropic
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(basedir, 'data', 'uploads')

    # Tracking
    TRACKING_BASE_URL = os.environ.get('TRACKING_BASE_URL', 'http://localhost:5001')
    REPLY_CHECK_INTERVAL = 300  # seconds between reply checks

    # CORS
    CORS_ORIGINS = ['http://localhost:5174']  # Vite dev server
