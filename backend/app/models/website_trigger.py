"""
Website Trigger — records changes detected on contact websites that
create outreach opportunities (SSL expiry, content changes, review shifts, etc.)
"""
from app import db
from datetime import datetime
import json


class WebsiteTrigger(db.Model):
    __tablename__ = 'website_triggers'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False, index=True)

    # Trigger type: ssl_expiry, content_change, review_change, downtime, copyright_outdated
    trigger_type = db.Column(db.String(50), nullable=False)

    # What changed
    previous_value = db.Column(db.Text)  # JSON
    current_value = db.Column(db.Text)   # JSON
    severity = db.Column(db.String(20), default='info')  # critical, important, info

    # Status
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    actioned = db.Column(db.Boolean, default=False)
    dismissed = db.Column(db.Boolean, default=False)

    # Outreach link
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    outreach_subject = db.Column(db.String(200))
    outreach_body = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    contact = db.relationship('Contact', backref=db.backref('triggers', lazy='dynamic'))

    def get_previous_value(self):
        if self.previous_value:
            try:
                return json.loads(self.previous_value)
            except Exception:
                return self.previous_value
        return None

    def get_current_value(self):
        if self.current_value:
            try:
                return json.loads(self.current_value)
            except Exception:
                return self.current_value
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'contact_id': self.contact_id,
            'contact_name': self.contact.name if self.contact else None,
            'contact_email': self.contact.email if self.contact else None,
            'contact_company': self.contact.company if self.contact else None,
            'trigger_type': self.trigger_type,
            'previous_value': self.get_previous_value(),
            'current_value': self.get_current_value(),
            'severity': self.severity,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'actioned': self.actioned,
            'dismissed': self.dismissed,
            'campaign_id': self.campaign_id,
            'outreach_subject': self.outreach_subject,
            'outreach_body': self.outreach_body,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
