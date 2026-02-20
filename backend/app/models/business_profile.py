"""
Business Profile — defines what the user's business does, who they serve,
and what capabilities they offer. Keystone model for relevance scoring.
"""
from app import db
from datetime import datetime
import json


class BusinessProfile(db.Model):
    __tablename__ = 'business_profiles'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, unique=True)

    # Core identity
    company_name = db.Column(db.String(200))
    domain = db.Column(db.String(255))
    tagline = db.Column(db.String(500))
    description = db.Column(db.Text)

    # Structured capabilities (JSON)
    # [{name, description, keywords, industries_served}]
    capabilities = db.Column(db.Text)

    # Target market (JSON)
    # {industries: [], company_sizes: [], geographies: []}
    target_market = db.Column(db.Text)

    # Relevance keywords (JSON array)
    keywords = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_capabilities(self):
        if self.capabilities:
            try:
                return json.loads(self.capabilities)
            except Exception:
                return []
        return []

    def get_target_market(self):
        if self.target_market:
            try:
                return json.loads(self.target_market)
            except Exception:
                return {}
        return {}

    def get_keywords(self):
        if self.keywords:
            try:
                return json.loads(self.keywords)
            except Exception:
                return []
        return []

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'company_name': self.company_name,
            'domain': self.domain,
            'tagline': self.tagline,
            'description': self.description,
            'capabilities': self.get_capabilities(),
            'target_market': self.get_target_market(),
            'keywords': self.get_keywords(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
