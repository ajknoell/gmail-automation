from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

db = SQLAlchemy()

def create_app(config_class=None):
    app = Flask(__name__)

    if config_class is None:
        from config import Config
        config_class = Config

    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['http://localhost:5173']))

    # Ensure upload folder exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'data/uploads'), exist_ok=True)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.templates import templates_bp
    from app.routes.campaigns import campaigns_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(templates_bp, url_prefix='/api/templates')
    app.register_blueprint(campaigns_bp, url_prefix='/api/campaigns')

    # Create database tables
    with app.app_context():
        db.create_all()

    return app
