import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  getCampaigns, getReplyStats, getInsights,
  getDailyBrief, getPipelineStats,
} from '../api/client';

function Home({ status }) {
  const [campaigns, setCampaigns] = useState([]);
  const [replyStats, setReplyStats] = useState({ needs_response: 0, total: 0 });
  const [insightsSummary, setInsightsSummary] = useState(null);
  const [brief, setBrief] = useState(null);
  const [pipelineStats, setPipelineStats] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
    const handleWsChange = () => loadData();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [campaignsRes, replyRes, insightsRes, briefRes, pipelineRes] = await Promise.all([
        getCampaigns(),
        getReplyStats(),
        getInsights().catch(() => ({ data: {} })),
        getDailyBrief().catch(() => ({ data: null })),
        getPipelineStats().catch(() => ({ data: {} })),
      ]);
      setCampaigns(campaignsRes.data || []);
      setReplyStats(replyRes.data || {});
      setInsightsSummary(insightsRes.data?.summary || null);
      setBrief(briefRes.data);
      setPipelineStats(pipelineRes.data || {});
    } catch (err) {
      console.error('Dashboard load error:', err);
    }
    setLoading(false);
  };

  const needs = brief?.needs_attention || {};
  const activeCampaigns = campaigns.filter(c => c.status === 'running' || c.status === 'paused');
  const totalSent = campaigns.reduce((sum, c) => sum + (c.sent_count || 0), 0);
  const approvedLeads = (pipelineStats.by_status?.approved || 0) + (pipelineStats.by_status?.in_campaign || 0);
  const newLeads = pipelineStats.by_status?.new || 0;
  const enrichedLeads = (pipelineStats.by_status?.enriched || 0) + (pipelineStats.by_status?.qualified || 0);

  const hasActions = (needs.replies_pending > 0) || (needs.flagged > 0) ||
    (needs.follow_ups_due > 0) || (enrichedLeads > 0) || (approvedLeads > 0);

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const buildSummary = () => {
    const parts = [];
    if (needs.replies_pending > 0) parts.push(`${needs.replies_pending} replies waiting`);
    if (activeCampaigns.length > 0) {
      const topCampaign = activeCampaigns[0];
      const pct = topCampaign.total_recipients > 0
        ? Math.round((topCampaign.sent_count / topCampaign.total_recipients) * 100) : 0;
      parts.push(`${topCampaign.name} is ${pct}% complete`);
    }
    if (brief?.new_prospects?.count > 0) parts.push(`${brief.new_prospects.count} new prospects found`);
    if (approvedLeads > 0) parts.push(`${approvedLeads} leads ready for outreach`);
    if (parts.length === 0) {
      if (pipelineStats.total > 0) return `You have ${pipelineStats.total} leads in your pipeline. Keep building!`;
      return 'Welcome to Veloro. Start by finding prospects or creating a campaign.';
    }
    return parts.join(', ') + '.';
  };

  if (loading) {
    return (
      <div>
        <div className="ai-summary">
          <span className="ai-summary-icon">V</span>
          <div style={{ flex: 1 }}>
            <div className="skeleton skeleton-text" style={{ width: '60%' }} />
            <div className="skeleton skeleton-text-sm" style={{ width: '40%' }} />
          </div>
        </div>
        <div className="action-cards">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="action-card" style={{ minWidth: 200 }}>
              <div className="skeleton" style={{ width: 40, height: 40, borderRadius: '50%' }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton skeleton-text" />
                <div className="skeleton skeleton-text-sm" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* AI Status Summary */}
      <div className="ai-summary">
        <span className="ai-summary-icon">V</span>
        <div>
          <strong>{greeting()}</strong> &mdash; {buildSummary()}
        </div>
      </div>

      {/* Action Cards */}
      {hasActions && (
        <div className="action-cards">
          {needs.replies_pending > 0 && (
            <Link to="/replies" className="action-card" style={{ '--action-color': '#F59E0B' }}>
              <span className="action-card-count">{needs.replies_pending}</span>
              <div>
                <div className="action-card-label">Replies Waiting</div>
                <div className="action-card-sub">Respond to keep momentum</div>
              </div>
            </Link>
          )}
          {needs.flagged > 0 && (
            <Link to="/replies?filter=flagged" className="action-card" style={{ '--action-color': '#EF4444' }}>
              <span className="action-card-count">{needs.flagged}</span>
              <div>
                <div className="action-card-label">Flagged for Review</div>
                <div className="action-card-sub">Needs your attention</div>
              </div>
            </Link>
          )}
          {needs.follow_ups_due > 0 && (
            <Link to="/contacts" className="action-card" style={{ '--action-color': '#3B82F6' }}>
              <span className="action-card-count">{needs.follow_ups_due}</span>
              <div>
                <div className="action-card-label">Follow-ups Due</div>
                <div className="action-card-sub">Don't let leads go cold</div>
              </div>
            </Link>
          )}
          {enrichedLeads > 0 && (
            <Link to="/prospects/review" className="action-card" style={{ '--action-color': '#E8603C' }}>
              <span className="action-card-count">{enrichedLeads}</span>
              <div>
                <div className="action-card-label">Leads to Review</div>
                <div className="action-card-sub">Enriched and ready</div>
              </div>
            </Link>
          )}
          {approvedLeads > 0 && (
            <Link to="/prospects/ready" className="action-card" style={{ '--action-color': '#10B981' }}>
              <span className="action-card-count">{approvedLeads}</span>
              <div>
                <div className="action-card-label">Ready for Outreach</div>
                <div className="action-card-sub">Add to a campaign</div>
              </div>
            </Link>
          )}
        </div>
      )}

      {/* Quick Start - show when no campaigns yet */}
      {campaigns.length === 0 && (
        <div className="card mb-4" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>V</div>
          <h2 style={{ marginBottom: '0.5rem' }}>Get Started with Veloro</h2>
          <p className="text-light" style={{ marginBottom: '1.5rem', maxWidth: 440, margin: '0 auto 1.5rem' }}>
            Find the best businesses in your area, get the data to reach them, and send personalized outreach that wins.
          </p>
          <div className="flex gap-2 justify-center">
            <Link to="/prospects" className="btn btn-primary">Find Prospects</Link>
            {!status.gmail_connected && (
              <Link to="/settings" className="btn btn-secondary">Connect Gmail</Link>
            )}
          </div>
        </div>
      )}

      {/* Two-column: Active Campaigns + Key Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: activeCampaigns.length > 0 ? '1fr 1fr' : '1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Active Campaigns */}
        {activeCampaigns.length > 0 && (
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">Active Campaigns</h3>
              <Link to="/campaigns" className="btn btn-secondary btn-sm">View All</Link>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {activeCampaigns.slice(0, 3).map(campaign => {
                const pct = campaign.total_recipients > 0
                  ? Math.round((campaign.sent_count / campaign.total_recipients) * 100) : 0;
                return (
                  <Link key={campaign.id} to={`/campaigns/${campaign.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    <div className="campaign-card">
                      <div className="campaign-card-name">{campaign.name}</div>
                      <div className="campaign-card-stats">
                        <span className="campaign-card-stat">
                          <strong>{campaign.sent_count}</strong> / {campaign.total_recipients} sent
                        </span>
                        <span className="campaign-card-stat">
                          <span className={`badge badge-${campaign.status}`}>{campaign.status}</span>
                        </span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {/* Key Metrics */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Performance</h3>
            <Link to="/insights" className="btn btn-secondary btn-sm">Details</Link>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--primary)' }}>
                {totalSent}
              </div>
              <div className="text-sm text-light">Emails Sent</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: insightsSummary?.reply_rate > 0 ? 'var(--success)' : 'var(--text)' }}>
                {insightsSummary?.reply_rate != null ? `${insightsSummary.reply_rate}%` : '--'}
              </div>
              <div className="text-sm text-light">Reply Rate</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text)' }}>
                {pipelineStats.total || 0}
              </div>
              <div className="text-sm text-light">Pipeline Leads</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--warning)' }}>
                {replyStats.total || 0}
              </div>
              <div className="text-sm text-light">Total Replies</div>
            </div>
          </div>

          {/* AI Recommendation */}
          {insightsSummary?.top_recommendation && (
            <div style={{
              marginTop: '1rem', padding: '0.75rem 1rem',
              background: 'rgba(232, 96, 60, 0.04)', borderRadius: '0.5rem',
              fontSize: '0.8125rem', lineHeight: 1.5
            }}>
              <strong style={{ color: 'var(--primary)' }}>AI Tip:</strong>{' '}
              {insightsSummary.top_recommendation}
            </div>
          )}
        </div>
      </div>

      {/* Recent Campaigns Table */}
      {campaigns.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">All Campaigns</h3>
            <Link to="/campaigns" className="btn btn-secondary btn-sm">Manage</Link>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.slice(0, 5).map(campaign => (
                <tr key={campaign.id}>
                  <td>
                    <Link to={`/campaigns/${campaign.id}`}>{campaign.name}</Link>
                  </td>
                  <td>
                    <span className={`badge badge-${campaign.status}`}>{campaign.status}</span>
                  </td>
                  <td>{campaign.sent_count}/{campaign.total_recipients}</td>
                  <td className="text-sm text-light">
                    {new Date(campaign.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default Home;
