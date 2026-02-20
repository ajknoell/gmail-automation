import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDailyBrief } from '../api/client';

function DailyBrief() {
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadBrief();
  }, []);

  const loadBrief = async () => {
    setLoading(true);
    try {
      const res = await getDailyBrief();
      setBrief(res.data);
    } catch (err) {
      console.error('Brief load error:', err);
    }
    setLoading(false);
  };

  if (loading) return <div className="page"><p>Loading brief...</p></div>;
  if (!brief) return <div className="page"><p>Could not load daily brief.</p></div>;

  const needs = brief.needs_attention || {};

  return (
    <div className="page">
      <div className="page-header">
        <h1>Daily Brief</h1>
        <span style={{ color: '#6B7280' }}>{new Date(brief.date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</span>
      </div>

      {/* Needs Attention */}
      {(needs.replies_pending > 0 || needs.flagged > 0 || needs.follow_ups_due > 0) && (
        <div className="card" style={{ padding: '16px', marginBottom: '20px', borderLeft: '4px solid #F59E0B' }}>
          <h3 style={{ margin: '0 0 12px 0' }}>Needs Your Attention</h3>
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            {needs.replies_pending > 0 && (
              <Link to="/replies" className="attention-item" style={{ padding: '8px 16px', background: '#FEF3C7', borderRadius: '8px', textDecoration: 'none', color: '#92400E' }}>
                {needs.replies_pending} replies pending
              </Link>
            )}
            {needs.flagged > 0 && (
              <Link to="/replies" className="attention-item" style={{ padding: '8px 16px', background: '#FEE2E2', borderRadius: '8px', textDecoration: 'none', color: '#991B1B' }}>
                {needs.flagged} flagged for review
              </Link>
            )}
            {needs.follow_ups_due > 0 && (
              <Link to="/contacts" className="attention-item" style={{ padding: '8px 16px', background: '#DBEAFE', borderRadius: '8px', textDecoration: 'none', color: '#1E40AF' }}>
                {needs.follow_ups_due} follow-ups due
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="stats-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px', marginBottom: '20px' }}>
        <div className="stat-card">
          <div className="stat-value">{brief.new_prospects?.count || 0}</div>
          <div className="stat-label">New Prospects</div>
          <div style={{ fontSize: '0.8em', color: '#6B7280' }}>{brief.new_prospects?.total || 0} total</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{brief.replies?.total || 0}</div>
          <div className="stat-label">Replies</div>
          <div style={{ fontSize: '0.8em' }}>
            <span style={{ color: '#10B981' }}>{brief.replies?.positive || 0}+</span>{' '}
            <span style={{ color: '#EF4444' }}>{brief.replies?.negative || 0}-</span>{' '}
            <span style={{ color: '#6B7280' }}>{brief.replies?.neutral || 0}~</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{brief.auto_responses || 0}</div>
          <div className="stat-label">Auto-Responses</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{brief.email_stats?.sent || 0}</div>
          <div className="stat-label">Emails Sent</div>
          <div style={{ fontSize: '0.8em', color: '#6B7280' }}>
            {brief.email_stats?.opens || 0} opens, {brief.email_stats?.clicks || 0} clicks
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{brief.active_campaigns || 0}</div>
          <div className="stat-label">Active Campaigns</div>
        </div>
      </div>

      {/* Pipeline Snapshot */}
      <div className="card" style={{ padding: '16px', marginBottom: '20px' }}>
        <h3>Pipeline</h3>
        <div style={{ display: 'flex', gap: '4px', height: '32px', borderRadius: '8px', overflow: 'hidden' }}>
          {Object.entries(brief.pipeline || {}).map(([status, count]) => {
            const colors = {
              discovered: '#A855F7', new: '#6B7280', contacted: '#3B82F6',
              replied: '#8B5CF6', interested: '#F59E0B', client: '#10B981', lost: '#EF4444',
            };
            const total = Object.values(brief.pipeline || {}).reduce((a, b) => a + b, 0) || 1;
            return (
              <div key={status} style={{
                flex: count / total, background: colors[status] || '#9CA3AF',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'white', fontSize: '0.75em', minWidth: count > 0 ? '30px' : '0',
              }} title={`${status}: ${count}`}>
                {count > 0 ? count : ''}
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: '16px', marginTop: '8px', flexWrap: 'wrap', fontSize: '0.85em' }}>
          {Object.entries(brief.pipeline || {}).map(([status, count]) => (
            <span key={status}><strong>{count}</strong> {status}</span>
          ))}
        </div>
      </div>

      {/* Follow-ups Due */}
      {brief.follow_ups?.contacts?.length > 0 && (
        <div className="card" style={{ padding: '16px', marginBottom: '20px' }}>
          <h3>Follow-ups Due</h3>
          {brief.follow_ups.contacts.map(c => (
            <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #e5e7eb' }}>
              <div>
                <strong>{c.name || c.email}</strong>
                {c.company && <span style={{ marginLeft: '8px', color: '#6B7280' }}>{c.company}</span>}
                {c.follow_up_note && <div style={{ fontSize: '0.85em', color: '#6B7280' }}>{c.follow_up_note}</div>}
              </div>
              <Link to={`/contacts/${c.id}`} className="btn btn-sm">View</Link>
            </div>
          ))}
        </div>
      )}

      {/* Quick Links */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
        <Link to="/discovery" className="btn btn-secondary" style={{ textAlign: 'center', padding: '16px' }}>
          Discovery
        </Link>
        <Link to="/replies" className="btn btn-secondary" style={{ textAlign: 'center', padding: '16px' }}>
          Reply Hub
        </Link>
        <Link to="/campaigns" className="btn btn-secondary" style={{ textAlign: 'center', padding: '16px' }}>
          Campaigns
        </Link>
        <Link to="/contacts" className="btn btn-secondary" style={{ textAlign: 'center', padding: '16px' }}>
          Contacts
        </Link>
      </div>
    </div>
  );
}

export default DailyBrief;
