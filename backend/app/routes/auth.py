from flask import Blueprint, redirect, request, session, jsonify, current_app, url_for, g
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app import db
from app.models import OAuthToken, Settings
from app.models.settings import WorkspaceSettings
from urllib.parse import quote
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

def get_gmail_credentials(account_id=None):
    """Get valid Gmail credentials from database.

    Args:
        account_id: Optional account ID. If None, uses the default account.
    """
    if account_id:
        token = OAuthToken.get_by_id(account_id)
    else:
        token = OAuthToken.get_default_gmail()

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
    accounts = OAuthToken.get_all_gmail_accounts()
    anthropic_key = Settings.get('anthropic_api_key')

    return jsonify({
        'gmail_connected': len(accounts) > 0,
        'gmail_accounts_count': len(accounts),
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

        # Get the user's email address from Gmail API
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        email_address = profile.get('emailAddress')

        # Check if this account is already connected
        existing = OAuthToken.query.filter_by(provider='gmail', email_address=email_address).first()
        if existing:
            # Update existing token
            existing.token = credentials.token
            existing.refresh_token = credentials.refresh_token
            existing.token_uri = credentials.token_uri
            existing.client_id = credentials.client_id
            existing.client_secret = credentials.client_secret
            existing.scopes = json.dumps(list(credentials.scopes)) if credentials.scopes else None
            existing.expiry = credentials.expiry
            db.session.commit()
            return redirect('http://localhost:5173/settings?gmail=updated')

        # Check if this is the first account (make it default)
        is_first = OAuthToken.query.filter_by(provider='gmail').count() == 0

        # Save new token
        oauth_token = OAuthToken.from_credentials(
            credentials,
            provider='gmail',
            email_address=email_address,
            display_name=email_address.split('@')[0]
        )
        oauth_token.is_default = is_first
        db.session.add(oauth_token)
        db.session.commit()

        # Redirect to frontend
        return redirect('http://localhost:5173/settings?gmail=connected')
    except Exception as e:
        return redirect(f'http://localhost:5173/settings?gmail=error&message={quote(str(e))}')

@auth_bp.route('/gmail/disconnect', methods=['POST'])
def gmail_disconnect():
    """Remove all Gmail credentials (legacy endpoint)."""
    OAuthToken.query.filter_by(provider='gmail').delete()
    db.session.commit()
    return jsonify({'success': True})


@auth_bp.route('/gmail/accounts')
def gmail_accounts():
    """Get all connected Gmail accounts."""
    accounts = OAuthToken.get_all_gmail_accounts()
    return jsonify({
        'accounts': [account.to_dict() for account in accounts]
    })


@auth_bp.route('/gmail/accounts/<int:account_id>', methods=['DELETE'])
def disconnect_gmail_account(account_id):
    """Disconnect a specific Gmail account."""
    account = OAuthToken.get_by_id(account_id)
    if not account:
        return jsonify({'error': 'Account not found'}), 404

    was_default = account.is_default
    db.session.delete(account)
    db.session.commit()

    # If we deleted the default, set a new default
    if was_default:
        remaining = OAuthToken.query.filter_by(provider='gmail').first()
        if remaining:
            remaining.is_default = True
            db.session.commit()

    return jsonify({'success': True})


@auth_bp.route('/gmail/accounts/<int:account_id>/default', methods=['POST'])
def set_default_gmail_account(account_id):
    """Set a Gmail account as the default."""
    account = OAuthToken.get_by_id(account_id)
    if not account:
        return jsonify({'error': 'Account not found'}), 404

    # Clear existing defaults
    OAuthToken.query.filter_by(provider='gmail').update({'is_default': False})

    # Set new default
    account.is_default = True
    db.session.commit()

    return jsonify({'success': True})

@auth_bp.route('/settings', methods=['GET'])
def get_settings():
    """Get current settings (API keys masked, writing style per-workspace)."""
    anthropic_key = Settings.get('anthropic_api_key', '')
    tavily_key = Settings.get('tavily_api_key', '')
    google_places_key = Settings.get('google_places_api_key', '')
    yelp_key = Settings.get('yelp_api_key', '')
    apollo_key = Settings.get('apollo_api_key', '')
    tracking_base_url = Settings.get('tracking_base_url', '')

    # Writing style: workspace-scoped, fallback to global
    writing_style_raw = WorkspaceSettings.get(g.workspace_id, 'writing_style') if g.workspace_id else None
    if not writing_style_raw:
        writing_style_raw = Settings.get('writing_style', '')

    return jsonify({
        'anthropic_api_key': '***' + anthropic_key[-4:] if anthropic_key and len(anthropic_key) > 4 else '',
        'tavily_api_key': '***' + tavily_key[-4:] if tavily_key and len(tavily_key) > 4 else '',
        'google_places_api_key': '***' + google_places_key[-4:] if google_places_key and len(google_places_key) > 4 else '',
        'yelp_api_key': '***' + yelp_key[-4:] if yelp_key and len(yelp_key) > 4 else '',
        'apollo_api_key': '***' + apollo_key[-4:] if apollo_key and len(apollo_key) > 4 else '',
        'tracking_base_url': tracking_base_url,
        'writing_style': json.loads(writing_style_raw) if writing_style_raw else None
    })

@auth_bp.route('/settings', methods=['POST'])
def save_settings():
    """Save API keys (global) and writing style (per-workspace)."""
    data = request.get_json()

    if 'anthropic_api_key' in data:
        Settings.set('anthropic_api_key', data['anthropic_api_key'])

    if 'tavily_api_key' in data:
        Settings.set('tavily_api_key', data['tavily_api_key'])

    if 'google_places_api_key' in data:
        Settings.set('google_places_api_key', data['google_places_api_key'])

    if 'yelp_api_key' in data:
        Settings.set('yelp_api_key', data['yelp_api_key'])

    if 'apollo_api_key' in data:
        Settings.set('apollo_api_key', data['apollo_api_key'])

    if 'tracking_base_url' in data:
        Settings.set('tracking_base_url', data['tracking_base_url'].rstrip('/') if data['tracking_base_url'] else '')

    if 'writing_style' in data:
        # Save writing style per-workspace
        if g.workspace_id:
            WorkspaceSettings.set(g.workspace_id, 'writing_style', json.dumps(data['writing_style']))
        else:
            Settings.set('writing_style', json.dumps(data['writing_style']))

    return jsonify({'success': True})
