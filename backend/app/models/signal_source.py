"""
Signal Source — configuration for signal collection plugins.
Each source maps to a registered SignalCollector.
"""
from app import db
from datetime import datetime
import json


class SignalSource(db.Model):
    __tablename__ = 'signal_sources'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)

    source_type = db.Column(db.String(50), nullable=False)  # Maps to collector registry
    name = db.Column(db.String(200))

    # Source-specific configuration (JSON)
    config = db.Column(db.Text)

    # Scheduling
    is_active = db.Column(db.Boolean, default=True)
    check_interval_hours = db.Column(db.Integer, default=24)
    last_checked_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_config(self):
        if self.config:
            try:
                return json.loads(self.config)
            except Exception:
                return {}
        return {}

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'source_type': self.source_type,
            'name': self.name,
            'config': self.get_config(),
            'is_active': self.is_active,
            'check_interval_hours': self.check_interval_hours,
            'last_checked_at': self.last_checked_at.isoformat() if self.last_checked_at else None,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
