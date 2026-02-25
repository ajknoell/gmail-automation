"""
Signal — unified event store for detected intent signals across sources.
Tracks website triggers, job postings, funding events, news, and more.
"""
from app import db
from datetime import datetime
import json


class Signal(db.Model):
    __tablename__ = 'signals'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)

    # Signal classification
    source_type = db.Column(db.String(50), nullable=False)  # website, job_posting, funding, news, tech_change
    signal_type = db.Column(db.String(50), nullable=False)  # ssl_expiry, hiring_engineer, series_a, etc.

    # Signal content
    title = db.Column(db.String(500))
    summary = db.Column(db.Text)
    raw_data = db.Column(db.Text)  # JSON
    source_url = db.Column(db.String(500))

    # Scoring
    intent_score = db.Column(db.Float)       # 0.0-1.0, buying signal strength
    relevance_score = db.Column(db.Float)    # 0.0-1.0, match against BusinessProfile
    intent_category = db.Column(db.String(50))  # active_buying, passive_need, growth, pain_point

    # Severity
    severity = db.Column(db.String(20), default='info')  # critical, important, info

    # Lifecycle
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    actioned = db.Column(db.Boolean, default=False)
    dismissed = db.Column(db.Boolean, default=False)

    # Outreach link
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    outreach_subject = db.Column(db.String(200))
    outreach_body = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    contact = db.relationship('Contact', backref=db.backref('signals', lazy='dynamic'))

    def get_raw_data(self):
        if self.raw_data:
            try:
                return json.loads(self.raw_data)
            except Exception:
                return self.raw_data
        return None

    def to_dict(self):
        try:
            contact = self.contact
        except Exception:
            contact = None
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'contact_id': self.contact_id,
            'contact_name': contact.name if contact else None,
            'contact_email': contact.email if contact else None,
            'contact_company': contact.company if contact else None,
            'source_type': self.source_type,
            'signal_type': self.signal_type,
            'title': self.title,
            'summary': self.summary,
            'raw_data': self.get_raw_data(),
            'source_url': self.source_url,
            'intent_score': self.intent_score,
            'relevance_score': self.relevance_score,
            'intent_category': self.intent_category,
            'severity': self.severity,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'actioned': self.actioned,
            'dismissed': self.dismissed,
            'campaign_id': self.campaign_id,
            'outreach_subject': self.outreach_subject,
            'outreach_body': self.outreach_body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
