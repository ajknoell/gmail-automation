import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getOpportunityFeed, createSignalOutreach } from '../api/client';
import { useToast } from '../components/Toast';

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

function ScoreBadge({ score, label }) {
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
      {pct}% {label}
    </span>
  );
}

function OpportunityFeed() {
  const showToast = useToast();
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterSource, setFilterSource] = useState('');
  const [generatingId, setGeneratingId] = useState(null);

  useEffect(() => {
    loadFeed();
    const handleWsChange = () => loadFeed();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, [page, filterSource]);

  const loadFeed = async () => {
    setLoading(true);
    try {
      const params = { page, per_page: 20 };
      if (filterSource) params.source_type = filterSource;
      const res = await getOpportunityFeed(params);
      setOpportunities(res.data.opportunities || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error('Opportunity feed load error:', err);
    }
    setLoading(false);
  };

  const handleCreateOutreach = async (signalId) => {
    setGeneratingId(signalId);
    try {
      await createSignalOutreach(signalId);
      try { await loadFeed(); } catch (_) { /* reload failed, non-critical */ }
    } catch (err) {
      showToast('Generation failed: ' + (err.response?.data?.error || err.message), 'error');
    } finally {
      setGeneratingId(null);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Opportunities</h1>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <select value={filterSource} onChange={e => { setFilterSource(e.target.value); setPage(1); }}
            className="input" style={{ maxWidth: '180px' }}>
            <option value="">All Sources</option>
            <option value="website">Website</option>
            <option value="job_posting">Job Posting</option>
            <option value="news">News</option>
          </select>
          <span style={{ color: 'var(--text-light)', fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>
            {total} opportunit{total === 1 ? 'y' : 'ies'}
          </span>
        </div>
      </div>

      <p style={{ color: 'var(--text-light)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
        Contacts ranked by signal strength and relevance to your business profile.
      </p>

      {loading ? (
        <p style={{ color: 'var(--text-light)' }}>Loading...</p>
      ) : opportunities.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1.5rem', color: 'var(--text-light)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem', opacity: 0.5 }}>{'\u{1F4E1}'}</div>
          <p style={{ fontWeight: 500, marginBottom: '0.375rem' }}>No opportunities yet</p>
          <p style={{ fontSize: '0.875rem' }}>
            Set up your <Link to="/business-profile" style={{ color: 'var(--primary)' }}>Business Profile</Link> and
            enable <Link to="/signals" style={{ color: 'var(--primary)' }}>Signal Sources</Link> to start seeing ranked opportunities.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {opportunities.map(opp => (
            <div key={opp.contact.id} className="card">
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', gap: '0.75rem' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem', flexWrap: 'wrap' }}>
                    <Link to={`/contacts/${opp.contact.id}`} style={{
                      fontSize: '1rem', fontWeight: 600, color: 'var(--text)', textDecoration: 'none',
                    }}>
                      {opp.contact.name || opp.contact.email}
                    </Link>
                    {opp.contact.company && (
                      <span style={{ color: 'var(--text-light)', fontSize: '0.875rem' }}>{opp.contact.company}</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
                    <ScoreBadge score={opp.max_intent_score} label="intent" />
                    <ScoreBadge score={opp.max_relevance_score} label="relevant" />
                    <span style={{
                      fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '9999px',
                      background: 'var(--bg)', color: 'var(--text-light)', border: '1px solid var(--border)',
                    }}>
                      {opp.signal_count} signal{opp.signal_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
                <div style={{
                  fontSize: '1.25rem', fontWeight: 700, flexShrink: 0,
                  color: opp.combined_score >= 0.5 ? '#059669' : opp.combined_score >= 0.25 ? '#D97706' : 'var(--text-light)',
                  minWidth: '2.5rem', textAlign: 'right',
                }}>
                  {Math.round(opp.combined_score * 100)}
                </div>
              </div>

              {/* Signals */}
              <div style={{ display: 'grid', gap: '0.375rem' }}>
                {opp.top_signals.map(sig => (
                  <div key={sig.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.5rem 0.75rem', borderRadius: '0.375rem', background: 'var(--bg)',
                    borderLeft: `3px solid ${SEVERITY_COLORS[sig.severity] || '#6B7280'}`,
                    gap: '0.5rem',
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                        <span style={{ fontSize: '0.9em' }}>{SOURCE_ICONS[sig.source_type] || '\u{1F514}'}</span>
                        <span style={{ fontWeight: 500, fontSize: '0.8125rem' }}>{sig.title || sig.signal_type}</span>
                      </div>
                      {sig.summary && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: '0.125rem' }}>
                          {sig.summary.length > 120 ? sig.summary.slice(0, 120) + '...' : sig.summary}
                        </div>
                      )}
                    </div>
                    {!sig.actioned && (
                      <button className="btn btn-sm btn-primary" onClick={() => handleCreateOutreach(sig.id)}
                        disabled={generatingId === sig.id} style={{ flexShrink: 0 }}>
                        {generatingId === sig.id ? '...' : 'Outreach'}
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Footer */}
              {opp.latest_signal_at && (
                <div style={{ fontSize: '0.75rem', color: '#9CA3AF', marginTop: '0.625rem' }}>
                  Latest signal: {new Date(opp.latest_signal_at).toLocaleDateString()}
                  {opp.contact.business_category && <> &middot; {opp.contact.business_category}</>}
                  {opp.contact.website && (
                    <> &middot; <a href={opp.contact.website.startsWith('http') ? opp.contact.website : `https://${opp.contact.website}`}
                      target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)' }}>Website</a></>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1.5rem', alignItems: 'center' }}>
          <button className="btn btn-sm btn-secondary" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>
            Previous
          </button>
          <span style={{ padding: '0.25rem 0.75rem', color: 'var(--text-light)', fontSize: '0.8125rem' }}>
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <button className="btn btn-sm btn-secondary" onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 20)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default OpportunityFeed;
