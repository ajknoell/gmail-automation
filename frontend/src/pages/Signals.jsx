import { useState, useEffect } from 'react';
import {
  getSignals, createSignalOutreach, dismissSignal,
  getSignalStats, signalCollectNow,
  getSignalSources, createSignalSource,
} from '../api/client';

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
  let color = '#6B7280';
  if (score >= 0.7) color = '#10B981';
  else if (score >= 0.4) color = '#F59E0B';
  return (
    <span style={{
      fontSize: '0.75em', padding: '2px 8px', borderRadius: '12px',
      background: color, color: 'white', fontWeight: 600,
    }}>
      {pct}% intent
    </span>
  );
}

function Signals() {
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState({});
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [generatingId, setGeneratingId] = useState(null);
  const [outreachPreview, setOutreachPreview] = useState(null);
  const [filterSource, setFilterSource] = useState('');
  const [showSourceSetup, setShowSourceSetup] = useState(false);

  useEffect(() => { loadAll(); }, [filterSource]);

  const loadAll = async () => {
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
  };

  const handleCollectNow = async () => {
    setCollecting(true);
    try {
      await signalCollectNow();
      alert('Signal collection started in background.');
      setTimeout(loadAll, 5000);
    } catch (err) {
      alert('Collection failed: ' + (err.response?.data?.error || err.message));
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
      alert('Generation failed: ' + (err.response?.data?.error || err.message));
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
      alert('Failed to add source: ' + (err.response?.data?.error || err.message));
    }
  };

  const activeSourceTypes = new Set(sources.filter(s => s.is_active).map(s => s.source_type));
  const availableSourceTypes = Object.keys(SOURCE_LABELS).filter(t => !activeSourceTypes.has(t));

  return (
    <div className="page">
      <div className="page-header">
        <h1>Signals</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary" onClick={() => setShowSourceSetup(!showSourceSetup)}>
            Sources ({sources.length})
          </button>
          <button className="btn btn-primary" onClick={handleCollectNow} disabled={collecting}>
            {collecting ? 'Collecting...' : 'Collect Now'}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-row" style={{ display: 'flex', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
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
        <div className="card" style={{ padding: '16px', marginBottom: '16px' }}>
          <h3 style={{ marginBottom: '12px' }}>Signal Sources</h3>
          {sources.length === 0 ? (
            <p style={{ color: '#6B7280', marginBottom: '12px' }}>No signal sources configured yet. Add sources to start collecting signals.</p>
          ) : (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
              {sources.map(s => (
                <span key={s.id} style={{
                  padding: '4px 12px', borderRadius: '16px',
                  background: s.is_active ? '#DBEAFE' : '#F3F4F6',
                  color: s.is_active ? '#1D4ED8' : '#6B7280',
                  fontSize: '0.85em',
                }}>
                  {SOURCE_ICONS[s.source_type] || ''} {s.name}
                  {s.last_checked_at && <span style={{ opacity: 0.6 }}> (checked {new Date(s.last_checked_at).toLocaleDateString()})</span>}
                </span>
              ))}
            </div>
          )}
          {availableSourceTypes.length > 0 && (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
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
      <div style={{ marginBottom: '16px' }}>
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
        <p>Loading...</p>
      ) : signals.length === 0 ? (
        <div className="card" style={{ padding: '32px', textAlign: 'center', color: '#6B7280' }}>
          <p>No active signals detected.</p>
          <p style={{ fontSize: '0.9em' }}>
            {sources.length === 0
              ? 'Add signal sources above to start collecting intent signals from job postings, news, and websites.'
              : 'Signals are detected when contacts show intent through hiring, funding, website changes, and more.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {signals.map(s => (
            <div key={s.id} className="card" style={{
              padding: '16px',
              borderLeft: `4px solid ${SEVERITY_COLORS[s.severity] || '#6B7280'}`,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '1.2em' }}>{SOURCE_ICONS[s.source_type] || '\u{1F514}'}</span>
                    <strong>{s.title || (SOURCE_LABELS[s.source_type] || s.source_type) + ': ' + s.signal_type}</strong>
                    <IntentBadge score={s.intent_score} />
                    {s.relevance_score != null && (
                      <span style={{
                        fontSize: '0.75em', padding: '2px 8px', borderRadius: '12px',
                        background: '#E0E7FF', color: '#4338CA',
                      }}>
                        {Math.round(s.relevance_score * 100)}% relevant
                      </span>
                    )}
                    <span style={{
                      fontSize: '0.75em', padding: '2px 8px', borderRadius: '12px',
                      background: SEVERITY_COLORS[s.severity] || '#6B7280', color: 'white',
                    }}>{s.severity}</span>
                  </div>
                  <div style={{ marginBottom: '4px' }}>
                    <strong>{s.contact_name || s.contact_email}</strong>
                    {s.contact_company && <span style={{ color: '#6B7280' }}> - {s.contact_company}</span>}
                  </div>
                  {s.summary && (
                    <div style={{ fontSize: '0.85em', color: '#374151', marginBottom: '4px' }}>
                      {s.summary}
                    </div>
                  )}
                  <div style={{ fontSize: '0.8em', color: '#9CA3AF' }}>
                    {SOURCE_LABELS[s.source_type] || s.source_type} &middot;{' '}
                    {s.detected_at ? new Date(s.detected_at).toLocaleDateString() : '-'}
                    {s.source_url && (
                      <>
                        {' '}&middot;{' '}
                        <a href={s.source_url} target="_blank" rel="noopener noreferrer" style={{ color: '#6366F1' }}>Source</a>
                      </>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', marginLeft: '12px', flexShrink: 0 }}>
                  {!s.actioned && (
                    <button className="btn btn-primary btn-sm" onClick={() => handleCreateOutreach(s.id)}
                      disabled={generatingId === s.id}>
                      {generatingId === s.id ? 'Generating...' : 'Create Outreach'}
                    </button>
                  )}
                  {s.actioned && s.outreach_subject && (
                    <button className="btn btn-sm" onClick={() => setOutreachPreview(s)}>
                      View Email
                    </button>
                  )}
                  <button className="btn btn-sm" onClick={() => handleDismiss(s.id)}
                    style={{ color: '#6B7280' }}>
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
            <h3>Generated Outreach</h3>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontWeight: 'bold' }}>Subject:</label>
              <p>{outreachPreview.outreach_subject || outreachPreview.subject}</p>
            </div>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontWeight: 'bold' }}>Body:</label>
              <div style={{ whiteSpace: 'pre-wrap', background: '#F9FAFB', padding: '12px', borderRadius: '8px' }}>
                {outreachPreview.outreach_body || outreachPreview.body}
              </div>
            </div>
            <button className="btn btn-secondary" onClick={() => setOutreachPreview(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default Signals;
