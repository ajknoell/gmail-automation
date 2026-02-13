import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getAuthStatus, getSettings, saveSettings, disconnectGmail, getGmailConnectUrl } from '../api/client';

function Settings({ onStatusChange }) {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState({ gmail_connected: false, anthropic_configured: false });
  const [settings, setSettings] = useState({ anthropic_api_key: '' });
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    // Check for OAuth callback messages
    const gmailStatus = searchParams.get('gmail');
    if (gmailStatus === 'connected') {
      setMessage('Gmail connected successfully!');
    } else if (gmailStatus === 'error') {
      setMessage('Failed to connect Gmail: ' + (searchParams.get('message') || 'Unknown error'));
    }

    // Load current status and settings
    getAuthStatus().then((res) => {
      setStatus(res.data);
      onStatusChange(res.data);
    });
    getSettings().then((res) => {
      setSettings(res.data);
    });
  }, [searchParams, onStatusChange]);

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) return;
    setSaving(true);
    try {
      await saveSettings({ anthropic_api_key: apiKey });
      setMessage('API key saved successfully!');
      setApiKey('');
      const statusRes = await getAuthStatus();
      setStatus(statusRes.data);
      onStatusChange(statusRes.data);
      const settingsRes = await getSettings();
      setSettings(settingsRes.data);
    } catch (error) {
      setMessage('Failed to save API key');
    }
    setSaving(false);
  };

  const handleDisconnectGmail = async () => {
    if (!confirm('Are you sure you want to disconnect Gmail?')) return;
    try {
      await disconnectGmail();
      const statusRes = await getAuthStatus();
      setStatus(statusRes.data);
      onStatusChange(statusRes.data);
      setMessage('Gmail disconnected');
    } catch (error) {
      setMessage('Failed to disconnect Gmail');
    }
  };

  return (
    <div>
      <h1 className="mb-4">Settings</h1>

      {message && (
        <div className="card mb-4" style={{ background: message.includes('success') ? '#D1FAE5' : '#FEE2E2' }}>
          <p>{message}</p>
        </div>
      )}

      {/* Gmail Connection */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Gmail Connection</h3>
        <p className="text-sm text-light mb-2">
          Connect your Gmail account to send emails through the Gmail API.
        </p>

        {status.gmail_connected ? (
          <div className="flex items-center gap-2">
            <span className="badge badge-completed">Connected</span>
            <button className="btn btn-danger btn-sm" onClick={handleDisconnectGmail}>
              Disconnect
            </button>
          </div>
        ) : (
          <a href={getGmailConnectUrl()} className="btn btn-primary">
            Connect Gmail Account
          </a>
        )}
      </div>

      {/* Anthropic API Key */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Anthropic API Key</h3>
        <p className="text-sm text-light mb-2">
          Enter your Anthropic API key for AI-powered email personalization.
        </p>

        {settings.anthropic_api_key && (
          <p className="mb-2">
            Current key: <code>{settings.anthropic_api_key}</code>
          </p>
        )}

        <div className="flex gap-2">
          <input
            type="password"
            className="form-input"
            placeholder="sk-ant-..."
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={handleSaveApiKey}
            disabled={saving || !apiKey.trim()}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Setup Instructions */}
      <div className="card">
        <h3 className="card-title mb-2">Setup Instructions</h3>

        <div className="mb-4">
          <h4 className="mb-1">1. Gmail API Setup</h4>
          <ol className="text-sm" style={{ paddingLeft: '1.5rem' }}>
            <li>Go to Google Cloud Console</li>
            <li>Create a new project or select existing</li>
            <li>Enable Gmail API</li>
            <li>Create OAuth 2.0 credentials (Web application type)</li>
            <li>Add <code>http://localhost:5001/auth/gmail/callback</code> as redirect URI</li>
            <li>Download credentials.json to backend folder</li>
            <li>Add your email as a test user in OAuth consent screen</li>
          </ol>
        </div>

        <div>
          <h4 className="mb-1">2. Anthropic API Key</h4>
          <ol className="text-sm" style={{ paddingLeft: '1.5rem' }}>
            <li>Go to console.anthropic.com</li>
            <li>Create an API key</li>
            <li>Paste the key above</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

export default Settings;
