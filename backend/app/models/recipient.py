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
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed, skipped
    personalized_subject = db.Column(db.String(200))
    personalized_body = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)

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
            'status': self.status,
            'personalized_subject': self.personalized_subject,
            'personalized_body': self.personalized_body,
            'approved': self.approved,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message
        }
