from app import db
from datetime import datetime
import json

class Recipient(db.Model):
    __tablename__ = 'recipients'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100))
    company = db.Column(db.String(100))
    custom_fields = db.Column(db.Text)  # JSON object
    notes = db.Column(db.Text)  # Manual research notes for personalization
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed, skipped
    personalized_subject = db.Column(db.String(200))
    personalized_body = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)  # Track when recipient was added to campaign
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_custom_fields(self):
        if self.custom_fields:
            return json.loads(self.custom_fields)
        return {}

    def set_custom_fields(self, fields_dict):
        self.custom_fields = json.dumps(fields_dict)

    def to_dict(self):
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'email': self.email,
            'name': self.name,
            'company': self.company,
            'custom_fields': self.get_custom_fields(),
            'notes': self.notes,
            'status': self.status,
            'personalized_subject': self.personalized_subject,
            'personalized_body': self.personalized_body,
            'approved': self.approved,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message,
            'enrolled_at': self.enrolled_at.isoformat() if self.enrolled_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def get_all_context(self):
        """Get all context for AI personalization including notes."""
        context = self.get_custom_fields()
        if self.notes:
            context['context'] = self.notes
        return context

    def get_website_url(self):
        """Get website URL from custom fields or derive from email domain."""
        from app.services.website_analyzer import WebsiteAnalyzer
        return WebsiteAnalyzer.resolve_url({
            'email': self.email,
            'custom_fields': self.get_custom_fields()
        })
