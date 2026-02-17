from app import db
from datetime import datetime


class StepRecipient(db.Model):
    __tablename__ = 'step_recipients'

    id = db.Column(db.Integer, primary_key=True)
    step_id = db.Column(db.Integer, db.ForeignKey('campaign_steps.id', ondelete='CASCADE'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipients.id', ondelete='CASCADE'), nullable=False, index=True)

    # Generated content for this step
    personalized_subject = db.Column(db.String(200))
    personalized_body = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=False)

    # Web research results cached for this step+recipient
    web_research_results = db.Column(db.Text)  # JSON string

    # Status: pending, generating, ready, approved, sent, failed, skipped
    status = db.Column(db.String(20), default='pending')
    skip_reason = db.Column(db.String(100))
    error_message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)

    # Reference to the email log entry after sending
    email_log_id = db.Column(db.Integer, db.ForeignKey('email_logs.id'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('step_id', 'recipient_id', name='uq_step_recipient'),
    )

    # Relationships
    recipient = db.relationship('Recipient', backref=db.backref('step_entries', lazy='dynamic'))
    email_log = db.relationship('EmailLog', foreign_keys=[email_log_id])

    def to_dict(self):
        return {
            'id': self.id,
            'step_id': self.step_id,
            'recipient_id': self.recipient_id,
            'recipient_email': self.recipient.email if self.recipient else None,
            'recipient_name': self.recipient.name if self.recipient else None,
            'recipient_company': self.recipient.company if self.recipient else None,
            'personalized_subject': self.personalized_subject,
            'personalized_body': self.personalized_body,
            'approved': self.approved,
            'web_research_results': self.web_research_results,
            'status': self.status,
            'skip_reason': self.skip_reason,
            'error_message': self.error_message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'email_log_id': self.email_log_id,
        }
