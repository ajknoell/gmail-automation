import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getOpportunityFeed, createSignalOutreach } from '../api/client';

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
      fontSize: '0.75em', padding: '3px 8px', borderRadius: '8px',
      background: bg, color, fontWeight: 600,
    }}>
      {pct}% {label}
    </span>
  );
}

function OpportunityFeed() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterSource, setFilterSource] = useState('');
  const [generatingId, setGeneratingId] = useState(null);

  useEffect(() => { loadFeed(); }, [page, filterSource]);

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
      loadFeed();
    } catch (err) {
      alert('Generation failed: ' + (err.response?.data?.error || err.message));
    }
    setGeneratingId(null);
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Opportunities</h1>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select value={filterSource} onChange={e => { setFilterSource(e.target.value); setPage(1); }}
            className="input" style={{ maxWidth: '180px' }}>
            <option value="">All Sources</option>
            <option value="website">Website</option>
            <option value="job_posting">Job Posting</option>
            <option value="news">News</option>
          </select>
          <span style={{ color: '#6B7280', fontSize: '0.85em' }}>{total} opportunities</span>
        </div>
      </div>

      <p style={{ color: '#6B7280', marginBottom: '20px' }}>
        Contacts ranked by signal strength and relevance to your business profile.
      </p>

      {loading ? (
        <p>Loading...</p>
      ) : opportunities.length === 0 ? (
        <div className="card" style={{ padding: '40px', textAlign: 'center', color: '#6B7280' }}>
          <div style={{ fontSize: '2em', marginBottom: '12px' }}>{'\u{1F4E1}'}</div>
          <p style={{ fontSize: '1.1em', marginBottom: '8px' }}>No opportunities yet</p>
          <p style={{ fontSize: '0.9em' }}>
            Set up your <Link to="/business-profile" style={{ color: '#6366F1' }}>Business Profile</Link> and
            enable <Link to="/signals" style={{ color: '#6366F1' }}>Signal Sources</Link> to start seeing ranked opportunities.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px' }}>
          {opportunities.map(opp => (
            <div key={opp.contact.id} className="card" style={{ padding: '20px' }}>
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                    <Link to={`/contacts/${opp.contact.id}`} style={{
                      fontSize: '1.1em', fontWeight: 600, color: '#111827', textDecoration: 'none',
                    }}>
                      {opp.contact.name || opp.contact.email}
                    </Link>
                    {opp.contact.company && (
                      <span style={{ color: '#6B7280' }}>{opp.contact.company}</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <ScoreBadge score={opp.max_intent_score} label="intent" />
                    <ScoreBadge score={opp.max_relevance_score} label="relevant" />
                    <span style={{
                      fontSize: '0.75em', padding: '3px 8px', borderRadius: '8px',
                      background: '#F3F4F6', color: '#374151',
                    }}>
                      {opp.signal_count} signal{opp.signal_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
                <div style={{
                  fontSize: '1.5em', fontWeight: 700,
                  color: opp.combined_score >= 0.5 ? '#059669' : opp.combined_score >= 0.25 ? '#D97706' : '#6B7280',
                }}>
                  {Math.round(opp.combined_score * 100)}
                </div>
              </div>

              {/* Signals */}
              <div style={{ display: 'grid', gap: '8px' }}>
                {opp.top_signals.map(sig => (
                  <div key={sig.id} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 12px', borderRadius: '8px', background: '#F9FAFB',
                    borderLeft: `3px solid ${SEVERITY_COLORS[sig.severity] || '#6B7280'}`,
                  }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>{SOURCE_ICONS[sig.source_type] || '\u{1F514}'}</span>
                        <span style={{ fontWeight: 500, fontSize: '0.9em' }}>{sig.title || sig.signal_type}</span>
                      </div>
                      {sig.summary && (
                        <div style={{ fontSize: '0.8em', color: '#6B7280', marginTop: '2px' }}>
                          {sig.summary.length > 120 ? sig.summary.slice(0, 120) + '...' : sig.summary}
                        </div>
                      )}
                    </div>
                    {!sig.actioned && (
                      <button className="btn btn-sm btn-primary" onClick={() => handleCreateOutreach(sig.id)}
                        disabled={generatingId === sig.id} style={{ marginLeft: '8px', flexShrink: 0 }}>
                        {generatingId === sig.id ? '...' : 'Outreach'}
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Footer */}
              {opp.latest_signal_at && (
                <div style={{ fontSize: '0.8em', color: '#9CA3AF', marginTop: '8px' }}>
                  Latest signal: {new Date(opp.latest_signal_at).toLocaleDateString()}
                  {opp.contact.business_category && <> &middot; {opp.contact.business_category}</>}
                  {opp.contact.website && (
                    <> &middot; <a href={opp.contact.website.startsWith('http') ? opp.contact.website : `https://${opp.contact.website}`}
                      target="_blank" rel="noopener noreferrer" style={{ color: '#6366F1' }}>Website</a></>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '20px' }}>
          <button className="btn btn-sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>
            Previous
          </button>
          <span style={{ padding: '4px 12px', color: '#6B7280' }}>
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <button className="btn btn-sm" onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 20)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default OpportunityFeed;
