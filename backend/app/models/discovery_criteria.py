"""
Discovery Criteria — workspace-level rules that define what kinds of
businesses to discover automatically via Google Maps scraping.
"""
from app import db
from datetime import datetime
import json


class DiscoveryCriteria(db.Model):
    __tablename__ = 'discovery_criteria'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    name = db.Column(db.String(200))  # e.g. "NJ Plumbers", "NYC Restaurants"

    # Search parameters
    search_queries = db.Column(db.Text)     # JSON list: ["plumber", "plumbing company"]
    zip_codes = db.Column(db.Text)          # JSON list: ["07302", "07304"]
    radius_miles = db.Column(db.Integer, default=10)

    # Filtering
    min_rating = db.Column(db.Float, default=0.0)
    max_results_per_query = db.Column(db.Integer, default=20)
    exclude_chains = db.Column(db.Boolean, default=False)

    # Scheduling
    is_active = db.Column(db.Boolean, default=True)
    last_scanned_at = db.Column(db.DateTime)
    scan_interval_hours = db.Column(db.Integer, default=168)  # weekly

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_search_queries(self):
        if self.search_queries:
            try:
                return json.loads(self.search_queries)
            except Exception:
                pass
        return []

    def set_search_queries(self, queries):
        self.search_queries = json.dumps(queries) if queries else None

    def get_zip_codes(self):
        if self.zip_codes:
            try:
                return json.loads(self.zip_codes)
            except Exception:
                pass
        return []

    def set_zip_codes(self, codes):
        self.zip_codes = json.dumps(codes) if codes else None

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'name': self.name,
            'search_queries': self.get_search_queries(),
            'zip_codes': self.get_zip_codes(),
            'radius_miles': self.radius_miles,
            'min_rating': self.min_rating,
            'max_results_per_query': self.max_results_per_query,
            'exclude_chains': self.exclude_chains,
            'is_active': self.is_active,
            'last_scanned_at': self.last_scanned_at.isoformat() if self.last_scanned_at else None,
            'scan_interval_hours': self.scan_interval_hours,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
