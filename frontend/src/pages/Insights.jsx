import { useState, useEffect } from 'react';
import { getInsights, triggerAnalysis, getEmailScores } from '../api/client';

const INSIGHT_LABELS = {
  subject_line_patterns: { icon: '✉️', title: 'Subject Line Patterns' },
  opening_patterns:      { icon: '👋', title: 'Opening Patterns' },
  personalization_depth: { icon: '🎯', title: 'Personalization Depth' },
  length_insights:       { icon: '📏', title: 'Email Length' },
  cta_patterns:          { icon: '🔗', title: 'Calls to Action' },
  tone_insights:         { icon: '🎨', title: 'Tone & Voice' },
  avoid_patterns:        { icon: '🚫', title: 'What to Avoid' },
};

const TIER_STYLES = {
  winner: { background: '#D1FAE5', color: '#065F46', label: 'Winner' },
  loser:  { background: '#FEE2E2', color: '#991B1B', label: 'Low' },
  middle: { background: '#E5E7EB', color: '#374151', label: 'Middle' },
};

const CONFIDENCE_STYLES = {
  high:   { background: '#D1FAE5', color: '#065F46' },
  medium: { background: '#FEF3C7', color: '#92400E' },
  low:    { background: '#FEE2E2', color: '#991B1B' },
};

function Insights() {
  const [insights, setInsights] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [summary, setSummary] = useState(null);
  const [emailScores, setEmailScores] = useState([]);
  const [showScores, setShowScores] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = async () => {
    try {
      const res = await getInsights();
      setInsights(res.data.insights);
      setMetadata(res.data.metadata);
      setSummary(res.data.summary);
      setError(null);
    } catch (err) {
      console.error('Failed to load insights:', err);
      setError('Failed to load insights data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const handleWsChange = () => {
      setLoading(true);
      setInsights(null);
      setMetadata(null);
      setEmailScores([]);
      setShowScores(false);
      loadData();
    };
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const res = await triggerAnalysis();
      if (res.data.status === 'insufficient_data') {
        setError(`Need at least ${res.data.minimum} sent emails to analyze. You have ${res.data.count} so far.`);
      } else if (res.data.status === 'error') {
        setError(res.data.message || 'Analysis failed');
      } else {
        setInsights(res.data.insights);
        setMetadata(res.data.metadata);
        if (res.data.summary) setSummary(res.data.summary);
      }
    } catch (err) {
      setError('Failed to run analysis: ' + (err.response?.data?.error || err.message));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleLoadScores = async () => {
    if (showScores) {
      setShowScores(false);
      return;
    }
    try {
      const res = await getEmailScores();
      setEmailScores(res.data);
      setShowScores(true);
    } catch (err) {
      console.error('Failed to load email scores:', err);
    }
  };

  if (loading) {
    return (
      <div>
        <h1 className="mb-4">Email Insights</h1>
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: '#6B7280' }}>
          Loading insights data…
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0 }}>Email Insights</h1>
        <button
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={analyzing}
        >
          {analyzing ? '⏳ Analyzing…' : insights ? '🔄 Re-analyze' : '🧠 Analyze Performance'}
        </button>
      </div>

      {error && (
        <div className="alert alert-error mb-3">{error}</div>
      )}

      {/* ── Performance Summary ────────────────────────────────── */}
      {summary && summary.total_sent > 0 && (
        <div className="grid mb-4" style={{ gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
          <div className="card stat-card">
            <div className="stat-value">{summary.total_sent}</div>
            <div className="stat-label">Emails Sent</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value">{summary.open_rate}%</div>
            <div className="stat-label">Open Rate</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value">{summary.click_rate}%</div>
            <div className="stat-label">Click Rate</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value" style={{ color: summary.reply_rate > 0 ? '#10B981' : undefined }}>
              {summary.reply_rate}%
            </div>
            <div className="stat-label">Reply Rate</div>
          </div>
          <div className="card stat-card">
            <div className="stat-value" style={{ color: summary.positive_reply_rate > 0 ? '#10B981' : undefined }}>
              {summary.positive_reply_rate}%
            </div>
            <div className="stat-label">Positive Replies</div>
          </div>
        </div>
      )}

      {/* ── No Data State ─────────────────────────────────────── */}
      {(!summary || summary.total_sent === 0) && !insights && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📊</div>
          <h3 style={{ marginBottom: '0.5rem' }}>No email data yet</h3>
          <p style={{ color: '#6B7280' }}>
            Start sending emails through campaigns or quick send. Once you have 20+ sent emails,
            the system can analyze what's working and what isn't.
          </p>
        </div>
      )}

      {/* ── Top Recommendation ────────────────────────────────── */}
      {insights?.top_recommendation && (
        <div className="card mb-4" style={{
          background: 'linear-gradient(135deg, #EEF2FF, #E0E7FF)',
          border: '1px solid #C7D2FE',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
            <span style={{ fontSize: '2rem' }}>💡</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: '1.1rem', marginBottom: '0.5rem', color: '#3730A3' }}>
                Top Recommendation
              </div>
              <p style={{ margin: 0, color: '#4338CA', lineHeight: 1.6 }}>
                {insights.top_recommendation}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── AI Insight Cards ──────────────────────────────────── */}
      {insights && (
        <div className="mb-4">
          <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem' }}>What the Data Shows</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
            {Object.entries(INSIGHT_LABELS).map(([key, { icon, title }]) => {
              const text = insights[key];
              if (!text) return null;
              return (
                <div key={key} className="card" style={{ padding: '1.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <span style={{ fontSize: '1.25rem' }}>{icon}</span>
                    <span style={{ fontWeight: 600 }}>{title}</span>
                  </div>
                  <p style={{ margin: 0, color: '#374151', lineHeight: 1.6, fontSize: '0.9rem' }}>
                    {text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Analysis Metadata ─────────────────────────────────── */}
      {metadata && (
        <div className="card mb-4" style={{
          padding: '1rem 1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#F9FAFB',
        }}>
          <div style={{ display: 'flex', gap: '2rem', fontSize: '0.875rem', color: '#6B7280' }}>
            <span>
              📅 Analyzed: {new Date(metadata.analyzed_at).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
              })}
            </span>
            <span>📧 Based on {metadata.email_count} emails</span>
            <span>🏆 {metadata.winner_count} winners · {metadata.loser_count} losers</span>
            {metadata.confidence && (
              <span
                className="badge"
                style={{
                  ...CONFIDENCE_STYLES[metadata.confidence],
                  fontSize: '0.75rem',
                }}
              >
                {metadata.confidence} confidence
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Email Scores Table ────────────────────────────────── */}
      {summary && summary.total_sent > 0 && (
        <div className="card">
          <div
            className="card-header"
            style={{ cursor: 'pointer' }}
            onClick={handleLoadScores}
          >
            <h3 className="card-title">
              {showScores ? '▾' : '▸'} Individual Email Scores
            </h3>
            <span style={{ fontSize: '0.875rem', color: '#6B7280' }}>
              {showScores ? 'Click to collapse' : 'Click to expand'}
            </span>
          </div>

          {showScores && emailScores.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Recipient</th>
                    <th>Score</th>
                    <th>Engagement</th>
                    <th>Tier</th>
                    <th>Sent</th>
                  </tr>
                </thead>
                <tbody>
                  {emailScores.map((email) => {
                    const tier = TIER_STYLES[email.tier] || TIER_STYLES.middle;
                    const engagement = [];
                    if (email.breakdown.opened) engagement.push(`Opened (${email.open_count}x)`);
                    if (email.breakdown.clicked) engagement.push(`Clicked (${email.click_count}x)`);
                    if (email.breakdown.replied) {
                      const s = email.breakdown.sentiment;
                      engagement.push(`Reply${s && s !== 'unknown' ? ` (${s})` : ''}`);
                    }

                    return (
                      <tr key={email.email_log_id}>
                        <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {email.subject || '(no subject)'}
                        </td>
                        <td style={{ fontSize: '0.875rem', color: '#6B7280' }}>
                          {email.recipient_email}
                        </td>
                        <td>
                          <strong>{email.score}</strong>
                        </td>
                        <td style={{ fontSize: '0.875rem' }}>
                          {engagement.length > 0 ? engagement.join(', ') : (
                            <span style={{ color: '#9CA3AF' }}>No engagement</span>
                          )}
                        </td>
                        <td>
                          <span
                            className="badge"
                            style={{ background: tier.background, color: tier.color }}
                          >
                            {tier.label}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.875rem', color: '#6B7280', whiteSpace: 'nowrap' }}>
                          {email.sent_at
                            ? new Date(email.sent_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                            : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {showScores && emailScores.length === 0 && (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#6B7280' }}>
              No scored emails found.
            </div>
          )}
        </div>
      )}

      {/* ── How It Works (always visible) ─────────────────────── */}
      {!insights && summary && summary.total_sent > 0 && (
        <div className="card" style={{ marginTop: '1.5rem', background: '#F9FAFB' }}>
          <h3 style={{ marginBottom: '1rem' }}>How Email Insights Works</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.5rem', textAlign: 'center' }}>
            {[
              { icon: '📊', title: 'Score', desc: 'Every sent email gets a performance score based on opens, clicks, and replies' },
              { icon: '🏆', title: 'Rank', desc: 'Emails are split into winners (top 25%) and losers (bottom 25%)' },
              { icon: '🧠', title: 'Analyze', desc: 'Claude compares winners vs losers to find what patterns drive engagement' },
              { icon: '✨', title: 'Apply', desc: 'Insights are automatically woven into future email generation' },
            ].map((step, i) => (
              <div key={i}>
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{step.icon}</div>
                <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{step.title}</div>
                <div style={{ fontSize: '0.85rem', color: '#6B7280', lineHeight: 1.5 }}>{step.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default Insights;
