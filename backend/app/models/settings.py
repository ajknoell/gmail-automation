from app import db
from datetime import datetime
import json

class Settings(db.Model):
    __tablename__ = 'settings'

    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls, key, default=None):
        setting = cls.query.get(key)
        return setting.value if setting else default

    @classmethod
    def set(cls, key, value):
        setting = cls.query.get(key)
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value)
            db.session.add(setting)
        db.session.commit()


class WorkspaceSettings(db.Model):
    __tablename__ = 'workspace_settings'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    key = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'key', name='uq_ws_setting'),
    )

    @classmethod
    def get(cls, workspace_id, key, default=None):
        setting = cls.query.filter_by(workspace_id=workspace_id, key=key).first()
        return setting.value if setting else default

    @classmethod
    def set(cls, workspace_id, key, value):
        setting = cls.query.filter_by(workspace_id=workspace_id, key=key).first()
        if setting:
            setting.value = value
        else:
            setting = cls(workspace_id=workspace_id, key=key, value=value)
            db.session.add(setting)
        db.session.commit()


class OAuthToken(db.Model):
    __tablename__ = 'oauth_tokens'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), default='gmail')
    email_address = db.Column(db.String(255))
    display_name = db.Column(db.String(255))
    is_default = db.Column(db.Boolean, default=False)
    token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.Text)
    client_id = db.Column(db.Text)
    client_secret = db.Column(db.Text)
    scopes = db.Column(db.Text)
    expiry = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_credentials_dict(self):
        return {
            'token': self.token,
            'refresh_token': self.refresh_token,
            'token_uri': self.token_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scopes': json.loads(self.scopes) if self.scopes else [],
            'expiry': self.expiry.isoformat() if self.expiry else None
        }

    @classmethod
    def from_credentials(cls, credentials, provider='gmail', email_address=None, display_name=None):
        return cls(
            provider=provider,
            email_address=email_address,
            display_name=display_name,
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=json.dumps(list(credentials.scopes)) if credentials.scopes else None,
            expiry=credentials.expiry
        )

    @classmethod
    def get_default_gmail(cls):
        """Get the default Gmail account."""
        token = cls.query.filter_by(provider='gmail', is_default=True).first()
        if not token:
            # Fall back to first Gmail account if no default set
            token = cls.query.filter_by(provider='gmail').first()
        return token

    @classmethod
    def get_all_gmail_accounts(cls):
        """Get all connected Gmail accounts."""
        return cls.query.filter_by(provider='gmail').all()

    @classmethod
    def get_by_id(cls, account_id):
        """Get a specific Gmail account by ID."""
        return cls.query.filter_by(id=account_id, provider='gmail').first()

    @property
    def has_calendar_scope(self):
        """Check if this account has Google Calendar read scope."""
        if not self.scopes:
            return False
        try:
            scope_list = json.loads(self.scopes)
            return 'https://www.googleapis.com/auth/calendar.readonly' in scope_list
        except (json.JSONDecodeError, TypeError):
            return False

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'email_address': self.email_address,
            'display_name': self.display_name,
            'is_default': self.is_default,
            'has_calendar_scope': self.has_calendar_scope,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
