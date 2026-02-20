import { useState, useEffect } from 'react';
import {
  getTriggers, createTriggerOutreach, dismissTrigger,
  getTriggerStats, triggerCheckNow,
} from '../api/client';

const TRIGGER_LABELS = {
  ssl_expiry: 'SSL Expiring',
  content_change: 'Content Changed',
  review_change: 'Reviews Changed',
  downtime: 'Site Down',
  copyright_outdated: 'Copyright Outdated',
};

const TRIGGER_ICONS = {
  ssl_expiry: '🔒',
  content_change: '📝',
  review_change: '⭐',
  downtime: '🔴',
  copyright_outdated: '📅',
};

const SEVERITY_COLORS = {
  critical: '#EF4444',
  important: '#F59E0B',
  info: '#6B7280',
};

function Triggers() {
  const [triggers, setTriggers] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [generatingId, setGeneratingId] = useState(null);
  const [outreachPreview, setOutreachPreview] = useState(null);
  const [filterType, setFilterType] = useState('');

  useEffect(() => { loadAll(); }, [filterType]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterType) params.type = filterType;
      const [triggersRes, statsRes] = await Promise.all([
        getTriggers(params),
        getTriggerStats(),
      ]);
      setTriggers(triggersRes.data.triggers || []);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Triggers load error:', err);
    }
    setLoading(false);
  };

  const handleCheckNow = async () => {
    setChecking(true);
    try {
      await triggerCheckNow();
      alert('Trigger check started in background.');
      setTimeout(loadAll, 5000);
    } catch (err) {
      alert('Check failed: ' + (err.response?.data?.error || err.message));
    }
    setChecking(false);
  };

  const handleCreateOutreach = async (triggerId) => {
    setGeneratingId(triggerId);
    try {
      const res = await createTriggerOutreach(triggerId);
      setOutreachPreview(res.data);
      loadAll();
    } catch (err) {
      alert('Generation failed: ' + (err.response?.data?.error || err.message));
    }
    setGeneratingId(null);
  };

  const handleDismiss = async (triggerId) => {
    await dismissTrigger(triggerId);
    loadAll();
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Triggers</h1>
        <button className="btn btn-primary" onClick={handleCheckNow} disabled={checking}>
          {checking ? 'Checking...' : 'Check Now'}
        </button>
      </div>

      {/* Stats */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-value">{stats.total || 0}</div>
          <div className="stat-label">Total Active</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.pending || 0}</div>
          <div className="stat-label">Pending Action</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.actioned || 0}</div>
          <div className="stat-label">Actioned</div>
        </div>
      </div>

      {/* Filter */}
      <div style={{ marginBottom: '1rem' }}>
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="input" style={{ maxWidth: '200px' }}>
          <option value="">All Types</option>
          {Object.entries(TRIGGER_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {/* Triggers List */}
      {loading ? (
        <p style={{ color: 'var(--text-light)' }}>Loading...</p>
      ) : triggers.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1.5rem', color: 'var(--text-light)' }}>
          <p style={{ fontWeight: 500, marginBottom: '0.25rem' }}>No active triggers detected.</p>
          <p style={{ fontSize: '0.875rem' }}>
            Triggers are detected when contact websites have changes like SSL expiry, downtime, or outdated content.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.625rem' }}>
          {triggers.map(t => (
            <div key={t.id} className="card" style={{
              padding: '1rem 1.25rem',
              borderLeft: `3px solid ${SEVERITY_COLORS[t.severity] || '#6B7280'}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '1.1em' }}>{TRIGGER_ICONS[t.trigger_type] || '🔔'}</span>
                    <strong style={{ fontSize: '0.9rem' }}>{TRIGGER_LABELS[t.trigger_type] || t.trigger_type}</strong>
                    <span style={{
                      fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '9999px',
                      background: SEVERITY_COLORS[t.severity] || '#6B7280', color: 'white',
                    }}>{t.severity}</span>
                  </div>
                  <div style={{ fontSize: '0.875rem', marginBottom: '0.25rem' }}>
                    <strong>{t.contact_name || t.contact_email}</strong>
                    {t.contact_company && <span style={{ color: 'var(--text-light)' }}> - {t.contact_company}</span>}
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-light)' }}>
                    Detected: {t.detected_at ? new Date(t.detected_at).toLocaleDateString() : '-'}
                  </div>
                  {t.current_value && (
                    <div style={{ fontSize: '0.8125rem', color: '#374151', marginTop: '0.25rem' }}>
                      {typeof t.current_value === 'object' ? JSON.stringify(t.current_value) : t.current_value}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                  {!t.actioned && (
                    <button className="btn btn-primary btn-sm" onClick={() => handleCreateOutreach(t.id)}
                      disabled={generatingId === t.id}>
                      {generatingId === t.id ? 'Generating...' : 'Create Outreach'}
                    </button>
                  )}
                  {t.actioned && t.outreach_subject && (
                    <button className="btn btn-sm btn-secondary" onClick={() => setOutreachPreview(t)}>
                      View Email
                    </button>
                  )}
                  <button className="btn btn-sm" onClick={() => handleDismiss(t.id)}
                    style={{ color: 'var(--text-light)' }}>
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Outreach Preview Modal */}
      {outreachPreview && (
        <div className="modal-overlay" onClick={() => setOutreachPreview(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <div className="modal-title">Generated Outreach</div>
              <button className="modal-close" onClick={() => setOutreachPreview(null)}>&times;</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: '1rem' }}>
                <label className="label">Subject</label>
                <p style={{ fontSize: '0.9rem' }}>{outreachPreview.outreach_subject || outreachPreview.subject}</p>
              </div>
              <div>
                <label className="label">Body</label>
                <div style={{
                  whiteSpace: 'pre-wrap', background: 'var(--bg)', padding: '0.75rem',
                  borderRadius: '0.5rem', fontSize: '0.875rem', lineHeight: 1.6,
                  border: '1px solid var(--border)',
                }}>
                  {outreachPreview.outreach_body || outreachPreview.body}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setOutreachPreview(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Triggers;
