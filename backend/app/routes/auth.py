from flask import Blueprint, redirect, request, session, jsonify, current_app, url_for
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from app import db
from app.models import OAuthToken, Settings
import os
import json

auth_bp = Blueprint('auth', __name__)

def get_oauth_flow():
    """Create OAuth flow for web redirect."""
    flow = Flow.from_client_secrets_file(
        current_app.config['GOOGLE_CLIENT_SECRETS_FILE'],
        scopes=current_app.config['GOOGLE_SCOPES'],
        redirect_uri=current_app.config['GOOGLE_REDIRECT_URI']
    )
    return flow

def get_gmail_credentials():
    """Get valid Gmail credentials from database."""
    token = OAuthToken.query.filter_by(provider='gmail').first()
    if not token:
        return None

    creds = Credentials(
        token=token.token,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        client_id=token.client_id,
        client_secret=token.client_secret,
        scopes=json.loads(token.scopes) if token.scopes else None
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Update token in database
        token.token = creds.token
        token.expiry = creds.expiry
        db.session.commit()

    return creds

@auth_bp.route('/status')
def status():
    """Check Gmail connection status."""
    token = OAuthToken.query.filter_by(provider='gmail').first()
    anthropic_key = Settings.get('anthropic_api_key')

    return jsonify({
        'gmail_connected': token is not None,
        'anthropic_configured': anthropic_key is not None and len(anthropic_key) > 0
    })

@auth_bp.route('/gmail/connect')
def gmail_connect():
    """Initiate Gmail OAuth flow."""
    flow = get_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['oauth_state'] = state
    return redirect(authorization_url)

@auth_bp.route('/gmail/callback')
def gmail_callback():
    """Handle OAuth callback from Google."""
    flow = get_oauth_flow()

    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        # Delete existing tokens
        OAuthToken.query.filter_by(provider='gmail').delete()

        # Save new token
        oauth_token = OAuthToken.from_credentials(credentials, provider='gmail')
        db.session.add(oauth_token)
        db.session.commit()

        # Redirect to frontend
        return redirect('http://localhost:5173/settings?gmail=connected')
    except Exception as e:
        return redirect(f'http://localhost:5173/settings?gmail=error&message={str(e)}')

@auth_bp.route('/gmail/disconnect', methods=['POST'])
def gmail_disconnect():
    """Remove Gmail credentials."""
    OAuthToken.query.filter_by(provider='gmail').delete()
    db.session.commit()
    return jsonify({'success': True})

@auth_bp.route('/settings', methods=['GET'])
def get_settings():
    """Get current settings (API keys masked)."""
    anthropic_key = Settings.get('anthropic_api_key', '')
    return jsonify({
        'anthropic_api_key': '***' + anthropic_key[-4:] if anthropic_key and len(anthropic_key) > 4 else ''
    })

@auth_bp.route('/settings', methods=['POST'])
def save_settings():
    """Save API keys."""
    data = request.get_json()

    if 'anthropic_api_key' in data:
        Settings.set('anthropic_api_key', data['anthropic_api_key'])

    return jsonify({'success': True})
