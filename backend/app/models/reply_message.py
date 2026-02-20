from app import db
from datetime import datetime


class ReplyMessage(db.Model):
    __tablename__ = 'reply_messages'

    id = db.Column(db.Integer, primary_key=True)
    email_log_id = db.Column(db.Integer, db.ForeignKey('email_logs.id'), nullable=False, index=True)
    gmail_message_id = db.Column(db.String(100), unique=True, index=True)
    from_email = db.Column(db.String(255))
    from_name = db.Column(db.String(255))
    body_text = db.Column(db.Text)
    snippet = db.Column(db.Text)
    received_at = db.Column(db.DateTime)

    # AI classification
    sentiment = db.Column(db.String(20))  # positive, negative, neutral
    sentiment_reason = db.Column(db.Text)

    # Generated response (cached)
    ai_response_subject = db.Column(db.String(200))
    ai_response_body = db.Column(db.Text)

    # Sentiment subcategory
    sentiment_subcategory = db.Column(db.String(50))  # interested, meeting_request, not_interested, ooo, etc.

    # Autopilot fields
    auto_responded = db.Column(db.Boolean, default=False)
    auto_response_type = db.Column(db.String(50))  # meeting_followup, graceful_close, acknowledge
    flagged_for_review = db.Column(db.Boolean, default=False)
    flag_reason = db.Column(db.String(200))

    # Response tracking
    response_sent_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    email_log = db.relationship('EmailLog', backref=db.backref('reply_messages', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'email_log_id': self.email_log_id,
            'gmail_message_id': self.gmail_message_id,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'body_text': self.body_text,
            'snippet': self.snippet,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'sentiment': self.sentiment,
            'sentiment_reason': self.sentiment_reason,
            'ai_response_subject': self.ai_response_subject,
            'ai_response_body': self.ai_response_body,
            'sentiment_subcategory': self.sentiment_subcategory,
            'auto_responded': self.auto_responded or False,
            'auto_response_type': self.auto_response_type,
            'flagged_for_review': self.flagged_for_review or False,
            'flag_reason': self.flag_reason,
            'response_sent_at': self.response_sent_at.isoformat() if self.response_sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
