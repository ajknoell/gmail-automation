import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getCampaigns, createCampaign, deleteCampaign, getTemplates } from '../api/client';

function Campaigns() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: '', template_id: '', delay_seconds: 30 });

  const mouseDownTarget = useRef(null);
  const handleOverlayMouseDown = (e) => { mouseDownTarget.current = e.target; };
  const handleOverlayClick = (e, closeFn) => {
    if (e.target === e.currentTarget && mouseDownTarget.current === e.currentTarget) {
      closeFn();
    }
    mouseDownTarget.current = null;
  };

  useEffect(() => {
    loadData();
    const handleWsChange = () => loadData();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const loadData = () => {
    getCampaigns().then((res) => setCampaigns(res.data));
    getTemplates().then((res) => setTemplates(res.data));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const res = await createCampaign({
        name: form.name,
        template_id: form.template_id || null,
        delay_seconds: parseInt(form.delay_seconds) || 30,
      });
      setShowModal(false);
      navigate(`/campaigns/${res.data.id}`);
    } catch (error) {
      alert('Failed to create campaign');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this campaign?')) return;
    try {
      await deleteCampaign(id);
      loadData();
    } catch (error) {
      alert('Failed to delete campaign');
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      draft: 'badge-draft',
      running: 'badge-running',
      paused: 'badge-paused',
      completed: 'badge-completed',
      cancelled: 'badge-cancelled',
      failed: 'badge-failed',
    };
    return colors[status] || 'badge-draft';
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1>Campaigns</h1>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          + New Campaign
        </button>
      </div>

      {campaigns.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📬</div>
            <p>No campaigns yet. Create your first email campaign!</p>
            <button className="btn btn-primary mt-2" onClick={() => setShowModal(true)}>
              Create Campaign
            </button>
          </div>
        </div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((campaign) => (
                <tr key={campaign.id}>
                  <td>
                    <Link to={`/campaigns/${campaign.id}`} style={{ fontWeight: 500 }}>
                      {campaign.name}
                    </Link>
                  </td>
                  <td>
                    <span className={`badge ${getStatusColor(campaign.status)}`}>
                      {campaign.status}
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="progress-bar" style={{ width: '80px' }}>
                        <div
                          className="progress-fill"
                          style={{
                            width: campaign.total_recipients
                              ? `${(campaign.sent_count / campaign.total_recipients) * 100}%`
                              : '0%',
                          }}
                        />
                      </div>
                      <span className="text-sm text-light">
                        {campaign.sent_count}/{campaign.total_recipients}
                      </span>
                    </div>
                  </td>
                  <td className="text-sm text-light">
                    {new Date(campaign.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="flex gap-1">
                      <Link to={`/campaigns/${campaign.id}`} className="btn btn-secondary btn-sm">
                        View
                      </Link>
                      {campaign.status === 'draft' && (
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(campaign.id)}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="modal-overlay" onMouseDown={handleOverlayMouseDown} onClick={(e) => handleOverlayClick(e, () => setShowModal(false))}>
          <div className="modal">
            <div className="modal-header">
              <h3 className="modal-title">New Campaign</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleCreate}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Campaign Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g., Q1 Outreach"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email Template (Optional)</label>
                  <select
                    className="form-select"
                    value={form.template_id}
                    onChange={(e) => setForm({ ...form, template_id: e.target.value })}
                  >
                    <option value="">Select a template...</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Delay Between Emails (seconds)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={form.delay_seconds}
                    onChange={(e) => setForm({ ...form, delay_seconds: e.target.value })}
                    min="0"
                    max="3600"
                  />
                  <p className="text-sm text-light mt-1">Recommended: 30-60 seconds to avoid rate limits</p>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create Campaign
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Campaigns;
