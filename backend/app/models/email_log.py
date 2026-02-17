from app import db
from datetime import datetime

class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipients.id'))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'))
    step_id = db.Column(db.Integer, db.ForeignKey('campaign_steps.id'), nullable=True)
    gmail_message_id = db.Column(db.String(100))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    status = db.Column(db.String(20))  # sent, failed
    error_details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Tracking fields
    tracking_id = db.Column(db.String(36), unique=True, index=True)
    gmail_thread_id = db.Column(db.String(100))
    gmail_account_id = db.Column(db.Integer)
    recipient_email = db.Column(db.String(255))
    opened_at = db.Column(db.DateTime)
    open_count = db.Column(db.Integer, default=0)
    clicked_at = db.Column(db.DateTime)
    click_count = db.Column(db.Integer, default=0)
    replied_at = db.Column(db.DateTime)
    bounced_at = db.Column(db.DateTime)
    bounce_reason = db.Column(db.Text)
    link_map = db.Column(db.Text)  # JSON dict of link_id -> original_url
    is_html = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'recipient_id': self.recipient_id,
            'campaign_id': self.campaign_id,
            'step_id': self.step_id,
            'gmail_message_id': self.gmail_message_id,
            'subject': self.subject,
            'status': self.status,
            'error_details': self.error_details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'tracking_id': self.tracking_id,
            'recipient_email': self.recipient_email,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'open_count': self.open_count or 0,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'click_count': self.click_count or 0,
            'replied_at': self.replied_at.isoformat() if self.replied_at else None,
            'bounced_at': self.bounced_at.isoformat() if self.bounced_at else None,
            'bounce_reason': self.bounce_reason,
        }
