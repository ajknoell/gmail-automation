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
    GOOGLE_SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    GOOGLE_REDIRECT_URI = 'http://localhost:5001/auth/gmail/callback'

    # Anthropic
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(basedir, 'data', 'uploads')

    # CORS
    CORS_ORIGINS = ['http://localhost:5173']  # Vite dev server
