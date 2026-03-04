"""
Discovery Source — configurable, schedulable data sources for business
target list building. Each source represents a scraping job (state license
DB, Google Maps query, Yelp search, industry directory, etc.).
"""
import json
from datetime import datetime

from app import db


SOURCE_TYPES = ['state_license', 'google_maps', 'yelp', 'industry_dir']
SCHEDULE_OPTIONS = ['manual', 'daily', 'weekly']


class DiscoverySource(db.Model):
    """A configured discovery source for automated business list building."""

    __tablename__ = 'discovery_sources'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey('acquisition_theses.id'), nullable=True)

    name = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)  # state_license, google_maps, yelp, industry_dir
    config = db.Column(db.Text)  # JSON: {state, license_type, location, radius, etc.}

    # Execution tracking
    last_run_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    results_count = db.Column(db.Integer, default=0)
    total_results_count = db.Column(db.Integer, default=0)  # Lifetime total

    # Scheduling
    schedule = db.Column(db.String(20), default='manual')  # manual, daily, weekly
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_config(self) -> dict:
        """Return parsed config dict."""
        if not self.config:
            return {}
        try:
            return json.loads(self.config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config(self, config: dict) -> None:
        """Store config as JSON."""
        self.config = json.dumps(config) if config else None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'thesis_id': self.thesis_id,
            'name': self.name,
            'source_type': self.source_type,
            'config': self.get_config(),
            'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
            'last_error': self.last_error,
            'results_count': self.results_count,
            'total_results_count': self.total_results_count,
            'schedule': self.schedule,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
