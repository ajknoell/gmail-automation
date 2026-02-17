import json

from app import db
from datetime import datetime


class WebsiteAnalysisLog(db.Model):
    """Tracks every website analysis so we can learn which observations drive engagement."""

    __tablename__ = 'website_analysis_logs'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipients.id'), nullable=True)
    email_log_id = db.Column(db.Integer, db.ForeignKey('email_logs.id'), nullable=True)
    url = db.Column(db.String(500), nullable=False)
    company = db.Column(db.String(200))
    raw_text_preview = db.Column(db.Text)  # First ~500 chars of scraped text for pattern analysis
    analysis_result = db.Column(db.Text, nullable=False)  # The 2 observations as plain text
    analysis_json = db.Column(db.Text)  # Structured JSON with issues, severity, recommendation
    max_severity = db.Column(db.String(20))  # 'critical' or 'important'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        parsed_json = None
        if self.analysis_json:
            try:
                parsed_json = json.loads(self.analysis_json)
            except Exception:
                pass
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'recipient_id': self.recipient_id,
            'email_log_id': self.email_log_id,
            'url': self.url,
            'company': self.company,
            'analysis_result': self.analysis_result,
            'analysis_json': parsed_json,
            'max_severity': self.max_severity,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
