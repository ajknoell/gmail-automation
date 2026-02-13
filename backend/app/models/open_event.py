from app import db
from datetime import datetime


class OpenEvent(db.Model):
    __tablename__ = 'open_events'

    id = db.Column(db.Integer, primary_key=True)
    email_log_id = db.Column(db.Integer, db.ForeignKey('email_logs.id'))
    tracking_id = db.Column(db.String(36), index=True)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_agent = db.Column(db.Text)
