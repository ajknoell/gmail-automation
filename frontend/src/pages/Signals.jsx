import { useState, useEffect, useCallback } from 'react';
import {
  getSignals, createSignalOutreach, dismissSignal,
  getSignalStats, signalCollectNow,
  getSignalSources, createSignalSource,
} from '../api/client';
import { useToast } from '../components/Toast';

const SOURCE_LABELS = {
  website: 'Website',
  job_posting: 'Job Posting',
  news: 'News',
  funding: 'Funding',
  tech_change: 'Tech Stack',
};

const SOURCE_ICONS = {
  website: '\u{1F310}',
  job_posting: '\u{1F4BC}',
  news: '\u{1F4F0}',
  funding: '\u{1F4B0}',
  tech_change: '\u{1F527}',
};

const SEVERITY_COLORS = {
  critical: '#EF4444',
  important: '#F59E0B',
  info: '#6B7280',
};

function IntentBadge({ score }) {
  if (score == null) return null;
  const pct = Math.round(score * 100);
  let bg = '#F3F4F6';
  let color = '#374151';
  if (score >= 0.7) { bg = '#D1FAE5'; color = '#065F46'; }
  else if (score >= 0.4) { bg = '#FEF3C7'; color = '#92400E'; }
  return (
    <span style={{
      fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '9999px',
      background: bg, color, fontWeight: 600,
    }}>
      {pct}% intent
    </span>
  );
}

function Signals() {
  const showToast = useToast();
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState({});
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [generatingId, setGeneratingId] = useState(null);
  const [outreachPreview, setOutreachPreview] = useState(null);
  const [filterSource, setFilterSource] = useState('');
  const [showSourceSetup, setShowSourceSetup] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterSource) params.source_type = filterSource;
      const [signalsRes, statsRes, sourcesRes] = await Promise.all([
        getSignals(params),
        getSignalStats(),
        getSignalSources(),
      ]);
      setSignals(signalsRes.data.signals || []);
      setStats(statsRes.data);
      setSources(sourcesRes.data.sources || []);
    } catch (err) {
      console.error('Signals load error:', err);
    }
    setLoading(false);
  }, [filterSource]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleCollectNow = async () => {
    setCollecting(true);
    try {
      await signalCollectNow();
      showToast('Signal collection started in background', 'info');
      setTimeout(loadAll, 5000);
    } catch (err) {
      showToast('Collection failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setCollecting(false);
  };

  const handleCreateOutreach = async (signalId) => {
    setGeneratingId(signalId);
    try {
      const res = await createSignalOutreach(signalId);
      setOutreachPreview(res.data);
      loadAll();
    } catch (err) {
      showToast('Generation failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setGeneratingId(null);
  };

  const handleDismiss = async (signalId) => {
    await dismissSignal(signalId);
    loadAll();
  };

  const handleAddSource = async (sourceType) => {
    try {
      await createSignalSource({ source_type: sourceType });
      loadAll();
    } catch (err) {
      showToast('Failed to add source: ' + (err.response?.data?.error || err.message), 'error');
    }
  };

  const activeSourceTypes = new Set(sources.filter(s => s.is_active).map(s => s.source_type));
  const availableSourceTypes = Object.keys(SOURCE_LABELS).filter(t => !activeSourceTypes.has(t));

  return (
    <div className="page">
      <div className="page-header">
        <h1>Signals</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={() => setShowSourceSetup(!showSourceSetup)}>
            Sources ({sources.length})
          </button>
          <button className="btn btn-primary" onClick={handleCollectNow} disabled={collecting}>
            {collecting ? 'Collecting...' : 'Collect Now'}
          </button>
        </div>
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
        <div className="stat-card">
          <div className="stat-value">{stats.avg_intent_score ? Math.round(stats.avg_intent_score * 100) + '%' : '-'}</div>
          <div className="stat-label">Avg Intent</div>
        </div>
        {stats.by_source && Object.entries(stats.by_source).map(([source, count]) => (
          <div className="stat-card" key={source}>
            <div className="stat-value">{count}</div>
            <div className="stat-label">{SOURCE_ICONS[source] || ''} {SOURCE_LABELS[source] || source}</div>
          </div>
        ))}
      </div>

      {/* Source Setup */}
      {showSourceSetup && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <div className="card-section-title">Signal Sources</div>
          {sources.length === 0 ? (
            <p style={{ color: 'var(--text-light)', fontSize: '0.875rem', marginBottom: '0.75rem' }}>
              No signal sources configured yet. Add sources to start collecting signals.
            </p>
          ) : (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
              {sources.map(s => (
                <span key={s.id} style={{
                  padding: '0.25rem 0.75rem', borderRadius: '9999px',
                  background: s.is_active ? 'rgba(79, 70, 229, 0.08)' : 'var(--bg)',
                  color: s.is_active ? 'var(--primary)' : 'var(--text-light)',
                  fontSize: '0.8125rem', border: '1px solid var(--border)',
                }}>
                  {SOURCE_ICONS[s.source_type] || ''} {s.name}
                  {s.last_checked_at && <span style={{ opacity: 0.6 }}> (checked {new Date(s.last_checked_at).toLocaleDateString()})</span>}
                </span>
              ))}
            </div>
          )}
          {availableSourceTypes.length > 0 && (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {availableSourceTypes.map(t => (
                <button key={t} className="btn btn-sm btn-secondary" onClick={() => handleAddSource(t)}>
                  + {SOURCE_LABELS[t]}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Filter */}
      <div style={{ marginBottom: '1rem' }}>
        <select value={filterSource} onChange={e => setFilterSource(e.target.value)}
          className="input" style={{ maxWidth: '200px' }}>
          <option value="">All Sources</option>
          {Object.entries(SOURCE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {/* Signals List */}
      {loading ? (
        <p style={{ color: 'var(--text-light)' }}>Loading...</p>
      ) : signals.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1.5rem', color: 'var(--text-light)' }}>
          <p style={{ fontWeight: 500, marginBottom: '0.25rem' }}>No active signals detected.</p>
          <p style={{ fontSize: '0.875rem' }}>
            {sources.length === 0
              ? 'Add signal sources above to start collecting intent signals from job postings, news, and websites.'
              : 'Signals are detected when contacts show intent through hiring, funding, website changes, and more.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.625rem' }}>
          {signals.map(s => (
            <div key={s.id} className="card" style={{
              padding: '1rem 1.25rem',
              borderLeft: `3px solid ${SEVERITY_COLORS[s.severity] || '#6B7280'}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '1.1em' }}>{SOURCE_ICONS[s.source_type] || '\u{1F514}'}</span>
                    <strong style={{ fontSize: '0.9rem' }}>{s.title || (SOURCE_LABELS[s.source_type] || s.source_type) + ': ' + s.signal_type}</strong>
                    <IntentBadge score={s.intent_score} />
                    {s.relevance_score != null && (
                      <span style={{
                        fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '9999px',
                        background: 'rgba(79, 70, 229, 0.08)', color: 'var(--primary)',
                      }}>
                        {Math.round(s.relevance_score * 100)}% relevant
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '0.875rem', marginBottom: '0.25rem' }}>
                    <strong>{s.contact_name || s.contact_email}</strong>
                    {s.contact_company && <span style={{ color: 'var(--text-light)' }}> - {s.contact_company}</span>}
                  </div>
                  {s.summary && (
                    <div style={{ fontSize: '0.8125rem', color: '#374151', marginBottom: '0.25rem', lineHeight: 1.4 }}>
                      {s.summary}
                    </div>
                  )}
                  <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>
                    {SOURCE_LABELS[s.source_type] || s.source_type} &middot;{' '}
                    {s.detected_at ? new Date(s.detected_at).toLocaleDateString() : '-'}
                    {s.source_url && (
                      <>
                        {' '}&middot;{' '}
                        <a href={s.source_url} target="_blank" rel="noopener noreferrer"
                          style={{ color: 'var(--primary)' }}>Source</a>
                      </>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                  {!s.actioned && (
                    <button className="btn btn-primary btn-sm" onClick={() => handleCreateOutreach(s.id)}
                      disabled={generatingId === s.id}>
                      {generatingId === s.id ? 'Generating...' : 'Create Outreach'}
                    </button>
                  )}
                  {s.actioned && s.outreach_subject && (
                    <button className="btn btn-sm btn-secondary" onClick={() => setOutreachPreview(s)}>
                      View Email
                    </button>
                  )}
                  <button className="btn btn-sm" onClick={() => handleDismiss(s.id)}
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

export default Signals;
