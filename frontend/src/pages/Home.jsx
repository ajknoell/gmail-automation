import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getCampaigns, getTemplates } from '../api/client';

function Home({ status }) {
  const [campaigns, setCampaigns] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [stats, setStats] = useState({ sent: 0, campaigns: 0, templates: 0 });

  useEffect(() => {
    Promise.all([getCampaigns(), getTemplates()])
      .then(([campaignsRes, templatesRes]) => {
        const campaignData = campaignsRes.data;
        const templateData = templatesRes.data;
        setCampaigns(campaignData.slice(0, 5));
        setTemplates(templateData);

        const totalSent = campaignData.reduce((sum, c) => sum + (c.sent_count || 0), 0);
        setStats({
          sent: totalSent,
          campaigns: campaignData.length,
          templates: templateData.length,
        });
      })
      .catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="mb-4">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-4 mb-4">
        <div className="card stat-card">
          <div className="stat-value">{stats.sent}</div>
          <div className="stat-label">Emails Sent</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{stats.campaigns}</div>
          <div className="stat-label">Campaigns</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value">{stats.templates}</div>
          <div className="stat-label">Templates</div>
        </div>
        <div className="card stat-card">
          <div className="stat-value" style={{ color: status.gmail_connected ? '#10B981' : '#EF4444' }}>
            {status.gmail_connected ? '✓' : '✗'}
          </div>
          <div className="stat-label">Gmail Status</div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Quick Actions</h3>
        <div className="flex gap-2">
          <Link to="/campaigns" className="btn btn-primary">+ New Campaign</Link>
          <Link to="/templates" className="btn btn-secondary">+ New Template</Link>
          {!status.gmail_connected && (
            <Link to="/settings" className="btn btn-danger">Connect Gmail</Link>
          )}
        </div>
      </div>

      {/* Recent Campaigns */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recent Campaigns</h3>
          <Link to="/campaigns" className="btn btn-secondary btn-sm">View All</Link>
        </div>

        {campaigns.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📧</div>
            <p>No campaigns yet. Create your first campaign to get started!</p>
          </div>
        ) : (
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
              {campaigns.map((campaign) => (
                <tr key={campaign.id}>
                  <td>
                    <Link to={`/campaigns/${campaign.id}`}>{campaign.name}</Link>
                  </td>
                  <td>
                    <span className={`badge badge-${campaign.status}`}>{campaign.status}</span>
                  </td>
                  <td>
                    {campaign.sent_count}/{campaign.total_recipients}
                  </td>
                  <td className="text-sm text-light">
                    {new Date(campaign.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default Home;
