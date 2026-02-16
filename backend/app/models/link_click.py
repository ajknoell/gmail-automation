from app import db
from datetime import datetime


class LinkClick(db.Model):
    __tablename__ = 'link_clicks'

    id = db.Column(db.Integer, primary_key=True)
    email_log_id = db.Column(db.Integer, db.ForeignKey('email_logs.id'))
    tracking_id = db.Column(db.String(36), index=True)
    link_id = db.Column(db.String(36))
    original_url = db.Column(db.Text)
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_agent = db.Column(db.Text)
