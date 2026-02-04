from app import db
from datetime import datetime

class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipients.id'))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'))
    gmail_message_id = db.Column(db.String(100))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    status = db.Column(db.String(20))  # sent, failed
    error_details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'recipient_id': self.recipient_id,
            'campaign_id': self.campaign_id,
            'gmail_message_id': self.gmail_message_id,
            'subject': self.subject,
            'status': self.status,
            'error_details': self.error_details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
