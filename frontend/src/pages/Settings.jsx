import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  getAuthStatus,
  getSettings,
  saveSettings,
  getGmailConnectUrl,
  getGmailAccounts,
  disconnectGmailAccount,
  setDefaultGmailAccount,
  getClaySettings,
  saveClaySettings,
  getClayWebhookUrl,
  getAutopilotConfig,
  updateAutopilotConfig,
  getAllFeatures,
  getEnabledFeatures,
  updateFeatureVisibility,
  triggerGmailSync,
  getGmailSyncStatus,
} from '../api/client';
import { useFeatureVisibility } from '../hooks/useFeatureVisibility';

const DEFAULT_WRITING_STYLE = {
  tone: 'Casual but buttoned up. California-friendly - warm and personable but still professional. NOT a New York finance bro vibe. Approachable and real.',
  opening_style: 'Start with a warm opening to lighten the mood and see if there\'s a connection. Grab their attention quickly - founders are busy.',
  value_prop_style: 'Show I understand their business and can connect the dots between our businesses without sounding weird or coming in "too hot." Lead with how I can benefit them.',
  length: 'Short - 2-4 sentences, concise but complete',
  closing_style: 'Close casually. Soft ask, not aggressive. Keep it low-pressure.',
  phrases_to_use: '',
  phrases_to_avoid: '"I hope this finds you well", corporate jargon, anything too salesy or pushy, generic mass-email language',
  additional_notes: 'My emails work because I prove I understand their business. I connect the dots without being "too hot." Owners appreciate my casual yet tailored approach - it never feels like a mass email.'
};

function Settings({ onStatusChange }) {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState({ gmail_connected: false, anthropic_configured: false });
  const [settings, setSettings] = useState({ anthropic_api_key: '', tavily_api_key: '', google_places_api_key: '', yelp_api_key: '', firecrawl_api_key: '', tracking_base_url: '', writing_style: null });
  const [gmailAccounts, setGmailAccounts] = useState([]);
  const [apiKey, setApiKey] = useState('');
  const [tavilyKey, setTavilyKey] = useState('');
  const [googlePlacesKey, setGooglePlacesKey] = useState('');
  const [yelpKey, setYelpKey] = useState('');
  const [firecrawlKey, setFirecrawlKey] = useState('');
  const [trackingUrl, setTrackingUrl] = useState('');
  const [writingStyle, setWritingStyle] = useState(DEFAULT_WRITING_STYLE);
  const [saving, setSaving] = useState(false);
  const [savingStyle, setSavingStyle] = useState(false);
  const [message, setMessage] = useState('');
  const [claySettings, setClaySettings] = useState({
    clay_webhook_secret: '',
    clay_export_webhook_url: '',
    clay_export_enabled: false
  });
  const [clayWebhookUrl, setClayWebhookUrl] = useState('');
  const [savingClay, setSavingClay] = useState(false);
  const [autopilotConfig, setAutopilotConfig] = useState({
    enabled: false,
    auto_respond_positive: false,
    auto_respond_negative: false,
    auto_respond_neutral: false,
    auto_schedule_enabled: false,
    human_review_keywords: 'price, cost, contract, legal, urgent, budget, invoice, payment, proposal, quote',
  });
  const [savingAutopilot, setSavingAutopilot] = useState(false);
  const [allFeatures, setAllFeatures] = useState({});
  const [featureVisibility, setFeatureVisibility] = useState({});
  const { reloadFeatures } = useFeatureVisibility();
  const [gmailSyncStatus, setGmailSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const loadGmailAccounts = async () => {
    try {
      const res = await getGmailAccounts();
      setGmailAccounts(res.data.accounts || []);
    } catch (error) {
      console.error('Failed to load Gmail accounts:', error);
    }
  };

  useEffect(() => {
    // Check for OAuth callback messages
    const gmailStatus = searchParams.get('gmail');
    if (gmailStatus === 'connected') {
      setMessage('Gmail account connected successfully!');
    } else if (gmailStatus === 'updated') {
      setMessage('Gmail account updated successfully!');
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
      if (res.data.writing_style) {
        setWritingStyle({ ...DEFAULT_WRITING_STYLE, ...res.data.writing_style });
      }
      if (res.data.tracking_base_url) {
        setTrackingUrl(res.data.tracking_base_url);
      }
    });
    loadGmailAccounts();

    // Load Clay settings
    getClaySettings().then((res) => setClaySettings(res.data)).catch(() => {});
    getClayWebhookUrl().then((res) => setClayWebhookUrl(res.data.webhook_url)).catch(() => {});

    // Load Gmail sync status
    getGmailSyncStatus().then((res) => setGmailSyncStatus(res.data)).catch(() => {});

    // Load autopilot config
    getAutopilotConfig().then((res) => {
      if (res.data && typeof res.data === 'object') {
        setAutopilotConfig(prev => ({ ...prev, ...res.data }));
      }
    }).catch(() => {});

    // Load feature visibility
    const loadFeatureVisibility = async () => {
      try {
        const allFeaturesRes = await getAllFeatures();
        setAllFeatures(allFeaturesRes.data || {});
        const enabledRes = await getEnabledFeatures();
        const enabled = enabledRes.data.enabled_features || [];
        const visibility = {};
        Object.keys(allFeaturesRes.data || {}).forEach(feature => {
          visibility[feature] = enabled.includes(feature);
        });
        setFeatureVisibility(visibility);
      } catch (error) {
        console.error('Failed to load feature visibility:', error);
      }
    };
    loadFeatureVisibility();

    // Reload writing style and features when workspace changes
    const handleWsChange = () => {
      getSettings().then((res) => {
        setSettings(res.data);
        if (res.data.writing_style) {
          setWritingStyle({ ...DEFAULT_WRITING_STYLE, ...res.data.writing_style });
        } else {
          setWritingStyle(DEFAULT_WRITING_STYLE);
        }
      });
      loadFeatureVisibility();
    };
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, [searchParams, onStatusChange]);

  const handleSaveWritingStyle = async () => {
    setSavingStyle(true);
    try {
      await saveSettings({ writing_style: writingStyle });
      setMessage('Writing style saved successfully!');
      const settingsRes = await getSettings();
      setSettings(settingsRes.data);
    } catch (error) {
      setMessage('Failed to save writing style');
    }
    setSavingStyle(false);
  };

  const updateStyleField = (field, value) => {
    setWritingStyle(prev => ({ ...prev, [field]: value }));
  };

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

  const handleSaveTavilyKey = async () => {
    if (!tavilyKey.trim()) return;
    setSaving(true);
    try {
      await saveSettings({ tavily_api_key: tavilyKey });
      setMessage('Tavily API key saved successfully!');
      setTavilyKey('');
      const settingsRes = await getSettings();
      setSettings(settingsRes.data);
    } catch (error) {
      setMessage('Failed to save Tavily API key');
    }
    setSaving(false);
  };

  const handleSaveGooglePlacesKey = async () => {
    if (!googlePlacesKey.trim()) return;
    setSaving(true);
    try {
      await saveSettings({ google_places_api_key: googlePlacesKey });
      setMessage('Google Places API key saved successfully!');
      setGooglePlacesKey('');
      const settingsRes = await getSettings();
      setSettings(settingsRes.data);
    } catch (error) {
      setMessage('Failed to save Google Places API key');
    }
    setSaving(false);
  };

  const handleSaveYelpKey = async () => {
    if (!yelpKey.trim()) return;
    setSaving(true);
    try {
      await saveSettings({ yelp_api_key: yelpKey });
      setMessage('Yelp API key saved! Yelp results will now appear in Map Explorer searches.');
      setYelpKey('');
      const settingsRes = await getSettings();
      setSettings(settingsRes.data);
    } catch (error) {
      setMessage('Failed to save Yelp API key');
    }
    setSaving(false);
  };

  const handleSaveFirecrawlKey = async () => {
    if (!firecrawlKey.trim()) return;
    setSaving(true);
    try {
      await saveSettings({ firecrawl_api_key: firecrawlKey });
      setMessage('Firecrawl API key saved! AI agents can now crawl websites for deep research.');
      setFirecrawlKey('');
      const settingsRes = await getSettings();
      setSettings(settingsRes.data);
    } catch (error) {
      setMessage('Failed to save Firecrawl API key');
    }
    setSaving(false);
  };

  const handleSaveTrackingUrl = async () => {
    setSaving(true);
    try {
      await saveSettings({ tracking_base_url: trackingUrl.trim() });
      setMessage(trackingUrl.trim() ? 'Tracking URL saved! Open & click tracking is now active.' : 'Tracking URL cleared. Open & click tracking is disabled.');
      const settingsRes = await getSettings();
      setSettings(settingsRes.data);
    } catch (error) {
      setMessage('Failed to save tracking URL');
    }
    setSaving(false);
  };

  const handleSaveClaySettings = async () => {
    setSavingClay(true);
    try {
      await saveClaySettings(claySettings);
      setMessage('Clay settings saved successfully!');
    } catch (error) {
      setMessage('Failed to save Clay settings');
    }
    setSavingClay(false);
  };

  const handleSaveAutopilot = async () => {
    setSavingAutopilot(true);
    try {
      await updateAutopilotConfig(autopilotConfig);
      setMessage('Reply Autopilot settings saved successfully!');
    } catch (error) {
      setMessage('Failed to save autopilot settings');
    }
    setSavingAutopilot(false);
  };

  const handleDisconnectGmailAccount = async (accountId, email) => {
    if (!confirm(`Are you sure you want to disconnect ${email}?`)) return;
    try {
      await disconnectGmailAccount(accountId);
      await loadGmailAccounts();
      const statusRes = await getAuthStatus();
      setStatus(statusRes.data);
      onStatusChange(statusRes.data);
      setMessage(`${email} disconnected`);
    } catch (error) {
      setMessage('Failed to disconnect Gmail account');
    }
  };

  const handleSetDefaultAccount = async (accountId) => {
    try {
      await setDefaultGmailAccount(accountId);
      await loadGmailAccounts();
      setMessage('Default account updated');
    } catch (error) {
      setMessage('Failed to set default account');
    }
  };

  const handleGmailSync = async () => {
    setSyncing(true);
    try {
      const res = await triggerGmailSync();
      const data = res.data;
      setMessage(`Gmail sync complete successfully! Synced ${data.synced_sent} sent and ${data.synced_received} received emails.`);
      // Refresh status
      const statusRes = await getGmailSyncStatus();
      setGmailSyncStatus(statusRes.data);
    } catch (error) {
      setMessage('Gmail sync failed: ' + (error.response?.data?.error || error.message));
    }
    setSyncing(false);
  };

  const handleToggleFeatureVisibility = async (featureName) => {
    try {
      const newEnabled = !featureVisibility[featureName];
      await updateFeatureVisibility(featureName, newEnabled);
      setFeatureVisibility(prev => ({ ...prev, [featureName]: newEnabled }));
      await reloadFeatures();
      // Dispatch workspace-changed to update nav in other components
      window.dispatchEvent(new CustomEvent('workspace-changed'));
      setMessage(`${allFeatures[featureName]?.display_name || featureName} ${newEnabled ? 'enabled' : 'disabled'}`);
    } catch (error) {
      setMessage(`Failed to toggle ${featureName} visibility`);
      console.error('Feature visibility toggle error:', error);
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

      {/* Gmail Accounts */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Gmail Accounts <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Connect multiple Gmail accounts to send emails from different addresses.
        </p>

        {gmailAccounts.length > 0 ? (
          <div style={{ marginBottom: '1rem' }}>
            {gmailAccounts.map((account) => (
              <div
                key={account.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.75rem',
                  background: account.is_default ? '#E0F2FE' : '#F9FAFB',
                  borderRadius: '0.5rem',
                  marginBottom: '0.5rem'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontWeight: 500 }}>{account.email_address}</span>
                  {account.is_default && (
                    <span className="badge badge-completed" style={{ fontSize: '0.7rem' }}>
                      Default
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {!account.is_default && (
                    <button
                      className="btn btn-sm"
                      style={{ background: '#E5E7EB', color: '#374151' }}
                      onClick={() => handleSetDefaultAccount(account.id)}
                    >
                      Set Default
                    </button>
                  )}
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => handleDisconnectGmailAccount(account.id, account.email_address)}
                  >
                    Disconnect
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-light mb-2">No Gmail accounts connected.</p>
        )}

        <a href={getGmailConnectUrl()} className="btn btn-primary">
          {gmailAccounts.length > 0 ? 'Connect Another Account' : 'Connect Gmail Account'}
        </a>
      </div>

      {/* Gmail Sync */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Gmail Email Sync <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Automatically records emails sent and received directly in Gmail with your contacts.
          Runs every 10 minutes in the background, or sync manually below.
        </p>

        {gmailSyncStatus && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '0.75rem',
            marginBottom: '1rem',
            padding: '0.75rem',
            background: '#F9FAFB',
            borderRadius: '0.5rem',
          }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#9CA3AF', textTransform: 'uppercase' }}>Last Sync</div>
              <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>
                {gmailSyncStatus.last_sync
                  ? new Date(gmailSyncStatus.last_sync).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
                  : 'Never'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#9CA3AF', textTransform: 'uppercase' }}>Sent Recorded</div>
              <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>{gmailSyncStatus.total_synced_sent || 0}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#9CA3AF', textTransform: 'uppercase' }}>Received Recorded</div>
              <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>{gmailSyncStatus.total_synced_received || 0}</div>
            </div>
          </div>
        )}

        <button
          className="btn btn-primary"
          onClick={handleGmailSync}
          disabled={syncing || gmailAccounts.length === 0}
        >
          {syncing ? 'Syncing...' : 'Sync Now'}
        </button>
        {gmailAccounts.length === 0 && (
          <span className="text-sm text-light" style={{ marginLeft: '0.75rem' }}>
            Connect a Gmail account first
          </span>
        )}
      </div>

      {/* Anthropic API Key */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Anthropic API Key <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Enter your Anthropic API key for AI-powered email personalization. Shared across all workspaces.
        </p>

        {settings.anthropic_api_key && (
          <p className="mb-2">
            Current key: <code>{settings.anthropic_api_key.slice(0, 12)}...{settings.anthropic_api_key.slice(-4)}</code>
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

      {/* Tavily API Key (Web Research) */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Tavily API Key (Web Research) <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Optional. Used for web research in follow-up sequences — searches for recent news and trends about recipients' companies to add value to follow-up emails.
          Get a key at <a href="https://tavily.com" target="_blank" rel="noopener noreferrer">tavily.com</a>.
        </p>

        {settings.tavily_api_key && (
          <p className="mb-2">
            Current key: <code>{settings.tavily_api_key.slice(0, 8)}...{settings.tavily_api_key.slice(-4)}</code>
          </p>
        )}

        <div className="flex gap-2">
          <input
            type="password"
            className="form-input"
            placeholder="tvly-..."
            value={tavilyKey}
            onChange={(e) => setTavilyKey(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={handleSaveTavilyKey}
            disabled={saving || !tavilyKey.trim()}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Google Places API Key (Competitor Discovery) */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Google Places API Key (Competitor Discovery) <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Used for competitor discovery — finds the same local businesses that show up in Google Maps.
          Get a key at <a href="https://console.cloud.google.com/apis/library/places-backend.googleapis.com" target="_blank" rel="noopener noreferrer">Google Cloud Console</a> (enable "Places API").
        </p>

        {settings.google_places_api_key && (
          <p className="mb-2">
            Current key: <code>{settings.google_places_api_key.slice(0, 8)}...{settings.google_places_api_key.slice(-4)}</code>
          </p>
        )}

        <div className="flex gap-2">
          <input
            type="password"
            className="form-input"
            placeholder="AIza..."
            value={googlePlacesKey}
            onChange={(e) => setGooglePlacesKey(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={handleSaveGooglePlacesKey}
            disabled={saving || !googlePlacesKey.trim()}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Yelp Fusion API Key */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Yelp Fusion API Key (Extra Business Coverage) <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Adds ~20-30% more businesses to Map Explorer searches, especially restaurants, home services, and beauty.
          Get a free API key at <a href="https://www.yelp.com/developers/v3/manage_app" target="_blank" rel="noopener noreferrer">Yelp Developers</a> (5,000 calls/day free).
        </p>

        {settings.yelp_api_key && (
          <p className="mb-2">
            Current key: <code>{settings.yelp_api_key.slice(0, 8)}...{settings.yelp_api_key.slice(-4)}</code>
          </p>
        )}

        <div className="flex gap-2">
          <input
            type="password"
            className="form-input"
            placeholder="Yelp API key..."
            value={yelpKey}
            onChange={(e) => setYelpKey(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={handleSaveYelpKey}
            disabled={saving || !yelpKey.trim()}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Firecrawl API Key (AI Agents) */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Firecrawl API Key (AI Agents) <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Powers AI agents for deep prospect research, lead discovery, and competitive intelligence.
          Get a key at <a href="https://firecrawl.dev" target="_blank" rel="noopener noreferrer">firecrawl.dev</a>.
        </p>

        {settings.firecrawl_api_key && (
          <p className="mb-2">
            Current key: <code>{settings.firecrawl_api_key.slice(0, 8)}...{settings.firecrawl_api_key.slice(-4)}</code>
          </p>
        )}

        <div className="flex gap-2">
          <input
            type="password"
            className="form-input"
            placeholder="fc-..."
            value={firecrawlKey}
            onChange={(e) => setFirecrawlKey(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={handleSaveFirecrawlKey}
            disabled={saving || !firecrawlKey.trim()}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Tracking URL */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Email Tracking URL <span style={{ fontSize: '12px', background: '#F0FDF4', color: '#166534', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Shared</span></h3>
        <p className="text-sm text-light mb-2">
          Public URL for open &amp; click tracking. Without this, only reply and bounce detection works.
          Run <code>cloudflared tunnel --url http://localhost:5001</code> and paste the URL here.
        </p>

        {settings.tracking_base_url ? (
          <p className="mb-2" style={{ color: '#10B981', fontSize: '0.85rem' }}>
            Active: <code>{settings.tracking_base_url}</code>
          </p>
        ) : (
          <p className="mb-2" style={{ color: '#9CA3AF', fontSize: '0.85rem' }}>
            Not configured — open &amp; click tracking is disabled
          </p>
        )}

        <div className="flex gap-2">
          <input
            type="text"
            className="form-input"
            placeholder="https://your-tunnel-url.trycloudflare.com"
            value={trackingUrl}
            onChange={(e) => setTrackingUrl(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={handleSaveTrackingUrl}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Writing Style Profile */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">✍️ Your Writing Style <span style={{ fontSize: '12px', background: '#FFF5F1', color: '#D4532F', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Per Workspace</span></h3>
        <p className="text-sm text-light mb-4">
          Train the AI to write emails exactly like you. This style is saved per workspace — each business can have its own voice.
        </p>

        <div style={{ display: 'grid', gap: '1rem' }}>
          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              Tone & Vibe
            </label>
            <textarea
              className="form-input"
              rows={2}
              placeholder="e.g., Casual but buttoned up. California-friendly, professional but not corporate. Warm and personable, never stiff."
              value={writingStyle.tone}
              onChange={(e) => updateStyleField('tone', e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              How You Open Emails
            </label>
            <textarea
              className="form-input"
              rows={2}
              placeholder="e.g., Start with a warm opening to lighten the mood. Show I've done my homework on their business. Grab attention quickly."
              value={writingStyle.opening_style}
              onChange={(e) => updateStyleField('opening_style', e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              How You Present Value
            </label>
            <textarea
              className="form-input"
              rows={2}
              placeholder="e.g., Connect the dots between our businesses without being too salesy. Show I understand their business. Lead with how I can benefit them."
              value={writingStyle.value_prop_style}
              onChange={(e) => updateStyleField('value_prop_style', e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              Email Length
            </label>
            <select
              className="form-input"
              value={writingStyle.length}
              onChange={(e) => updateStyleField('length', e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">Select length preference...</option>
              <option value="Very short - 1-2 sentences, punchy">Very short (1-2 sentences)</option>
              <option value="Short - 2-4 sentences, concise but complete">Short (2-4 sentences)</option>
              <option value="Medium - 1-2 short paragraphs">Medium (1-2 paragraphs)</option>
              <option value="Longer - detailed but not overwhelming">Longer (detailed)</option>
            </select>
          </div>

          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              How You Close / CTA
            </label>
            <textarea
              className="form-input"
              rows={2}
              placeholder="e.g., Close casually. Soft ask, not aggressive. Something like 'Would love to chat if interested' rather than 'Let's book a call this week.'"
              value={writingStyle.closing_style}
              onChange={(e) => updateStyleField('closing_style', e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              Phrases or Patterns You Like
            </label>
            <textarea
              className="form-input"
              rows={2}
              placeholder="e.g., 'Came across your work...', 'Thought this might resonate...', signing off with just my first name"
              value={writingStyle.phrases_to_use}
              onChange={(e) => updateStyleField('phrases_to_use', e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              Phrases to Avoid
            </label>
            <textarea
              className="form-input"
              rows={2}
              placeholder="e.g., 'I hope this finds you well', 'Just following up', 'Circling back', corporate jargon, pushy language"
              value={writingStyle.phrases_to_avoid}
              onChange={(e) => updateStyleField('phrases_to_avoid', e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
              What Makes Your Emails Work
            </label>
            <textarea
              className="form-input"
              rows={3}
              placeholder="e.g., I prove I understand their business. I connect the dots without coming in 'too hot.' Owners appreciate my casual yet tailored approach. I never sound like a mass email."
              value={writingStyle.additional_notes}
              onChange={(e) => updateStyleField('additional_notes', e.target.value)}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <button
              className="btn btn-primary"
              onClick={handleSaveWritingStyle}
              disabled={savingStyle}
            >
              {savingStyle ? 'Saving...' : 'Save Writing Style'}
            </button>
            {settings.writing_style && (
              <span className="text-sm text-light" style={{ marginLeft: '1rem' }}>
                ✓ Style profile saved
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Reply Autopilot */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Reply Autopilot <span style={{ fontSize: '12px', background: '#FFF5F1', color: '#D4532F', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Per Workspace</span></h3>
        <p className="text-sm text-light mb-4">
          Configure AI to automatically handle routine replies. Sensitive replies (containing keywords like pricing, contracts) are always flagged for human review.
        </p>

        <div style={{ display: 'grid', gap: '1rem' }}>
          {/* Master toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={autopilotConfig.enabled}
              onChange={(e) => setAutopilotConfig(prev => ({ ...prev, enabled: e.target.checked }))}
            />
            <div>
              <span style={{ fontWeight: 600 }}>Enable Reply Autopilot</span>
              <p className="text-sm text-light" style={{ margin: 0 }}>When enabled, AI will automatically process and respond to incoming replies</p>
            </div>
          </label>

          {autopilotConfig.enabled && (
            <>
              {/* Per-sentiment toggles */}
              <div style={{ padding: '1rem', background: '#F9FAFB', borderRadius: '0.5rem' }}>
                <h4 style={{ marginBottom: '0.75rem', fontSize: '0.9rem' }}>Auto-respond by sentiment</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={autopilotConfig.auto_respond_positive}
                      onChange={(e) => setAutopilotConfig(prev => ({ ...prev, auto_respond_positive: e.target.checked }))}
                    />
                    <span style={{ color: '#065F46', fontWeight: 500 }}>Positive replies</span>
                    <span className="text-sm text-light">- Auto-send meeting follow-up with calendar availability</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={autopilotConfig.auto_respond_negative}
                      onChange={(e) => setAutopilotConfig(prev => ({ ...prev, auto_respond_negative: e.target.checked }))}
                    />
                    <span style={{ color: '#991B1B', fontWeight: 500 }}>Negative replies</span>
                    <span className="text-sm text-light">- Auto-send graceful close / rebuttal</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={autopilotConfig.auto_respond_neutral}
                      onChange={(e) => setAutopilotConfig(prev => ({ ...prev, auto_respond_neutral: e.target.checked }))}
                    />
                    <span style={{ color: '#374151', fontWeight: 500 }}>Neutral replies</span>
                    <span className="text-sm text-light">- Auto-send acknowledgment</span>
                  </label>
                </div>
              </div>

              {/* Calendar integration */}
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={autopilotConfig.auto_schedule_enabled}
                  onChange={(e) => setAutopilotConfig(prev => ({ ...prev, auto_schedule_enabled: e.target.checked }))}
                />
                <span style={{ fontWeight: 500 }}>Include real calendar availability</span>
                <span className="text-sm text-light">in positive reply responses</span>
              </label>

              {/* Keywords */}
              <div>
                <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
                  Human Review Keywords
                </label>
                <p className="text-sm text-light" style={{ marginBottom: '0.5rem' }}>
                  Replies containing any of these words will be flagged for human review instead of auto-responding. Comma-separated.
                </p>
                <textarea
                  className="form-input"
                  rows={2}
                  value={autopilotConfig.human_review_keywords}
                  onChange={(e) => setAutopilotConfig(prev => ({ ...prev, human_review_keywords: e.target.value }))}
                  style={{ width: '100%' }}
                />
              </div>
            </>
          )}

          <div>
            <button
              className="btn btn-primary"
              onClick={handleSaveAutopilot}
              disabled={savingAutopilot}
            >
              {savingAutopilot ? 'Saving...' : 'Save Autopilot Settings'}
            </button>
          </div>
        </div>
      </div>

      {/* Feature Visibility */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Feature Visibility <span style={{ fontSize: '12px', background: '#FFF5F1', color: '#D4532F', padding: '2px 8px', borderRadius: '12px', fontWeight: 500, marginLeft: '8px' }}>Per Workspace</span></h3>
        <p className="text-sm text-light mb-4">
          Control which features are visible in this workspace. Hidden features preserve their data — you can re-enable them anytime.
        </p>

        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Object.entries(allFeatures).map(([featureName, metadata]) => (
            <label key={featureName} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', padding: '0.5rem', borderRadius: '0.5rem', background: '#F9FAFB' }}>
              <input
                type="checkbox"
                checked={featureVisibility[featureName] || false}
                onChange={() => handleToggleFeatureVisibility(featureName)}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ fontWeight: 500 }}>{metadata.display_name}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Clay Integration */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Clay Integration</h3>
        <p className="text-sm text-light mb-4">
          Connect with Clay to import enriched contacts and export tracking data.
        </p>

        {/* Inbound Webhook URL */}
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
            Inbound Webhook URL (for Clay to send contacts)
          </label>
          <p className="text-sm text-light mb-1">
            Add this URL as an HTTP action in Clay to push enriched contacts into campaigns.
          </p>
          <div className="flex gap-2" style={{ alignItems: 'center' }}>
            <code
              style={{
                flex: 1,
                padding: '0.5rem 0.75rem',
                background: '#F3F4F6',
                borderRadius: '0.375rem',
                fontSize: '0.85rem',
                wordBreak: 'break-all'
              }}
            >
              {clayWebhookUrl || 'Loading...'}
            </code>
            <button
              className="btn btn-sm"
              style={{ background: '#E5E7EB', color: '#374151', whiteSpace: 'nowrap' }}
              onClick={() => {
                navigator.clipboard.writeText(clayWebhookUrl);
                setMessage('Webhook URL copied!');
              }}
            >
              Copy
            </button>
          </div>
        </div>

        {/* Webhook Secret */}
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
            Webhook Secret (optional)
          </label>
          <p className="text-sm text-light mb-1">
            If set, incoming webhooks must include a valid X-Clay-Signature header.
          </p>
          <input
            type="text"
            className="form-input"
            placeholder="Enter a secret key..."
            value={claySettings.clay_webhook_secret}
            onChange={(e) => setClaySettings(prev => ({ ...prev, clay_webhook_secret: e.target.value }))}
            style={{ width: '100%' }}
          />
        </div>

        {/* Outbound Export */}
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>
            Export Webhook URL (push tracking data to Clay)
          </label>
          <p className="text-sm text-light mb-1">
            When enabled, opens/clicks/replies are sent to this URL in real-time. You can also manually export full campaign results.
          </p>
          <input
            type="url"
            className="form-input"
            placeholder="https://api.clay.com/v1/webhooks/..."
            value={claySettings.clay_export_webhook_url}
            onChange={(e) => setClaySettings(prev => ({ ...prev, clay_export_webhook_url: e.target.value }))}
            style={{ width: '100%', marginBottom: '0.5rem' }}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={claySettings.clay_export_enabled}
              onChange={(e) => setClaySettings(prev => ({ ...prev, clay_export_enabled: e.target.checked }))}
            />
            <span className="text-sm">Enable real-time tracking export to Clay</span>
          </label>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleSaveClaySettings}
          disabled={savingClay}
        >
          {savingClay ? 'Saving...' : 'Save Clay Settings'}
        </button>
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
