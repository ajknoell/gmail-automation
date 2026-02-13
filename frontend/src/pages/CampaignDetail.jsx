import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getCampaign,
  getRecipients,
  uploadRecipients,
  generatePreview,
  approveRecipients,
  startCampaign,
  pauseCampaign,
  resumeCampaign,
  cancelCampaign,
  exportCampaign,
  getCampaignProgressUrl,
} from '../api/client';

function CampaignDetail() {
  const { id } = useParams();
  const [campaign, setCampaign] = useState(null);
  const [recipients, setRecipients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const fileInputRef = useRef();
  const eventSourceRef = useRef();

  useEffect(() => {
    loadData();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [id]);

  useEffect(() => {
    if (campaign?.status === 'running') {
      startProgressStream();
    }
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [campaign?.status]);

  const loadData = async () => {
    try {
      const [campaignRes, recipientsRes] = await Promise.all([
        getCampaign(id),
        getRecipients(id),
      ]);
      setCampaign(campaignRes.data);
      setRecipients(recipientsRes.data);
    } catch (error) {
      alert('Failed to load campaign');
    }
    setLoading(false);
  };

  const startProgressStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    const es = new EventSource(getCampaignProgressUrl(id));
    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setCampaign((prev) => ({
        ...prev,
        sent_count: data.sent,
        failed_count: data.failed,
        status: data.status,
      }));
      if (data.status === 'completed' || data.status === 'cancelled') {
        es.close();
        loadData();
      }
    };
    es.onerror = () => {
      es.close();
    };
    eventSourceRef.current = es;
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    try {
      await uploadRecipients(id, file);
      loadData();
    } catch (error) {
      alert('Failed to upload file: ' + (error.response?.data?.error || error.message));
    }
    setUploading(false);
    fileInputRef.current.value = '';
  };

  const handleGeneratePreview = async (batchSize) => {
    setGenerating(true);
    try {
      const res = await generatePreview(id, batchSize);
      const { generated, remaining } = res.data;
      if (remaining > 0) {
        const continueGenerating = confirm(
          `Generated ${generated} emails. ${remaining} recipients remaining.\n\nGenerate the next batch?`
        );
        if (continueGenerating) {
          await loadData();
          handleGeneratePreview(batchSize);
          return;
        }
      }
      loadData();
    } catch (error) {
      alert('Failed to generate previews: ' + (error.response?.data?.error || error.message));
    }
    setGenerating(false);
  };

  const handleApproveAll = async () => {
    try {
      await approveRecipients(id, []);
      loadData();
    } catch (error) {
      alert('Failed to approve recipients');
    }
  };

  const handleStart = async () => {
    try {
      await startCampaign(id);
      loadData();
    } catch (error) {
      alert('Failed to start campaign: ' + (error.response?.data?.error || error.message));
    }
  };

  const handlePause = async () => {
    try {
      await pauseCampaign(id);
      loadData();
    } catch (error) {
      alert('Failed to pause campaign');
    }
  };

  const handleResume = async () => {
    try {
      await resumeCampaign(id);
      loadData();
    } catch (error) {
      alert('Failed to resume campaign');
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel this campaign?')) return;
    try {
      await cancelCampaign(id);
      loadData();
    } catch (error) {
      alert('Failed to cancel campaign');
    }
  };

  if (loading) {
    return <div className="card">Loading...</div>;
  }

  if (!campaign) {
    return <div className="card">Campaign not found</div>;
  }

  const pendingCount = recipients.filter((r) => r.status === 'pending').length;
  const approvedCount = recipients.filter((r) => r.approved).length;
  const hasPersonalized = recipients.some((r) => r.personalized_body);

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <Link to="/campaigns" className="text-sm text-light">← Back to Campaigns</Link>
          <h1>{campaign.name}</h1>
        </div>
        <span className={`badge badge-${campaign.status}`} style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>
          {campaign.status}
        </span>
      </div>

      {/* Progress Card */}
      <div className="card mb-4">
        <div className="grid grid-4">
          <div className="stat-card">
            <div className="stat-value">{campaign.total_recipients}</div>
            <div className="stat-label">Total Recipients</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#10B981' }}>{campaign.sent_count}</div>
            <div className="stat-label">Sent</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ color: '#EF4444' }}>{campaign.failed_count}</div>
            <div className="stat-label">Failed</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{pendingCount}</div>
            <div className="stat-label">Pending</div>
          </div>
        </div>

        {campaign.total_recipients > 0 && (
          <div className="mt-2">
            <div className="progress-bar" style={{ height: '1rem' }}>
              <div
                className="progress-fill"
                style={{
                  width: `${((campaign.sent_count + campaign.failed_count) / campaign.total_recipients) * 100}%`,
                  background: campaign.failed_count > 0 ? 'linear-gradient(to right, #10B981, #EF4444)' : '#10B981',
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Actions</h3>
        <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
          {campaign.status === 'draft' && (
            <>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".csv,.xlsx,.xls"
                style={{ display: 'none' }}
              />
              <button
                className="btn btn-secondary"
                onClick={() => fileInputRef.current.click()}
                disabled={uploading}
              >
                {uploading ? 'Uploading...' : '📁 Upload Recipients'}
              </button>

              {recipients.length > 0 && (
                <>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleGeneratePreview(50)}
                    disabled={generating}
                  >
                    {generating ? 'Generating...' : '🤖 Generate AI Previews'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleGeneratePreview(0)}
                    disabled={generating}
                    title="Generate personalized emails for all recipients at once"
                  >
                    {generating ? 'Generating...' : '🤖 Generate All'}
                  </button>
                  <button className="btn btn-secondary" onClick={handleApproveAll}>
                    ✓ Approve All
                  </button>
                  <button
                    className="btn btn-success"
                    onClick={handleStart}
                    disabled={approvedCount === 0}
                  >
                    ▶ Start Campaign
                  </button>
                </>
              )}
            </>
          )}

          {campaign.status === 'running' && (
            <>
              <button className="btn btn-warning" onClick={handlePause}>⏸ Pause</button>
              <button className="btn btn-danger" onClick={handleCancel}>✕ Cancel</button>
            </>
          )}

          {campaign.status === 'paused' && (
            <>
              <button className="btn btn-success" onClick={handleResume}>▶ Resume</button>
              <button className="btn btn-danger" onClick={handleCancel}>✕ Cancel</button>
            </>
          )}

          {(campaign.status === 'completed' || campaign.status === 'cancelled') && (
            <a href={exportCampaign(id)} className="btn btn-secondary" download>
              📥 Export Results
            </a>
          )}
        </div>
      </div>

      {/* Recipients Table */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recipients ({recipients.length})</h3>
        </div>

        {recipients.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <p>No recipients yet. Upload a CSV or Excel file to add recipients.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Approved</th>
                  <th>Preview</th>
                </tr>
              </thead>
              <tbody>
                {recipients.map((recipient) => (
                  <tr key={recipient.id}>
                    <td>{recipient.email}</td>
                    <td>{recipient.name || '-'}</td>
                    <td>{recipient.company || '-'}</td>
                    <td>
                      <span className={`badge badge-${recipient.status}`}>{recipient.status}</span>
                    </td>
                    <td>
                      {recipient.approved ? (
                        <span style={{ color: '#10B981' }}>✓</span>
                      ) : (
                        <span style={{ color: '#9CA3AF' }}>-</span>
                      )}
                    </td>
                    <td>
                      {recipient.personalized_body ? (
                        <details>
                          <summary className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
                            View
                          </summary>
                          <div style={{ padding: '1rem', background: '#F9FAFB', marginTop: '0.5rem', borderRadius: '0.5rem' }}>
                            <p><strong>Subject:</strong> {recipient.personalized_subject}</p>
                            <hr style={{ margin: '0.5rem 0', border: 'none', borderTop: '1px solid #E5E7EB' }} />
                            <p style={{ whiteSpace: 'pre-wrap' }}>{recipient.personalized_body}</p>
                          </div>
                        </details>
                      ) : (
                        <span className="text-light">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default CampaignDetail;
