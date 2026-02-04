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


class OAuthToken(db.Model):
    __tablename__ = 'oauth_tokens'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), default='gmail')
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
    def from_credentials(cls, credentials, provider='gmail'):
        return cls(
            provider=provider,
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=json.dumps(list(credentials.scopes)) if credentials.scopes else None,
            expiry=credentials.expiry
        )
