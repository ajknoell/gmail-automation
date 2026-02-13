import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getCampaign,
  getRecipients,
  clearRecipients,
  deleteRecipient,
  uploadRecipients,
  generatePreview,
  approveRecipients,
  updateRecipient,
  updateCampaign,
  regenerateRecipientPreview,
  startCampaign,
  pauseCampaign,
  resumeCampaign,
  cancelCampaign,
  exportCampaign,
  getCampaignProgressUrl,
  getSampleCsvUrl,
  getGmailAccounts,
  getCampaignTracking,
  triggerReplyCheck,
  exportToClay,
  sendIndividual,
} from '../api/client';
import AttachmentPicker from '../components/AttachmentPicker';
import RichTextEditor from '../components/RichTextEditor';

function CampaignDetail() {
  const { id } = useParams();
  const [campaign, setCampaign] = useState(null);
  const [recipients, setRecipients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [sendingIds, setSendingIds] = useState(new Set());
  const [editingRecipient, setEditingRecipient] = useState(null);
  const [regeneratingId, setRegeneratingId] = useState(null);
  const [gmailAccounts, setGmailAccounts] = useState([]);
  const [tracking, setTracking] = useState(null);
  const [checkingReplies, setCheckingReplies] = useState(false);
  const [exportingClay, setExportingClay] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef();
  const eventSourceRef = useRef();

  useEffect(() => {
    loadData();
    getGmailAccounts().then((res) => {
      setGmailAccounts(res.data.accounts || []);
    });
    const handleWsChange = () => loadData();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => {
      window.removeEventListener('workspace-changed', handleWsChange);
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
      setAttachments(campaignRes.data.attachments || []);
      setRecipients(recipientsRes.data);

      // Load tracking stats if emails have been sent
      if (campaignRes.data.sent_count > 0) {
        getCampaignTracking(id).then((res) => setTracking(res.data)).catch(() => {});
      }
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
      const res = await uploadRecipients(id, file);
      const { added, duplicates_skipped, duplicate_emails, invalid_skipped } = res.data;

      let msg = `Added ${added} recipient${added !== 1 ? 's' : ''}.`;
      if (duplicates_skipped > 0) {
        msg += `\n\n${duplicates_skipped} duplicate${duplicates_skipped !== 1 ? 's' : ''} skipped`;
        if (duplicate_emails && duplicate_emails.length > 0) {
          msg += `:\n${duplicate_emails.join(', ')}`;
          if (duplicates_skipped > duplicate_emails.length) {
            msg += ` and ${duplicates_skipped - duplicate_emails.length} more`;
          }
        }
      }
      if (invalid_skipped > 0) {
        msg += `\n${invalid_skipped} row${invalid_skipped !== 1 ? 's' : ''} skipped (invalid/missing email).`;
      }

      alert(msg);
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

  const handleSendIndividual = async (recipientId) => {
    setSendingIds((prev) => new Set(prev).add(recipientId));
    try {
      await sendIndividual(id, recipientId);
      loadData();
    } catch (error) {
      alert('Failed to send: ' + (error.response?.data?.error || error.message));
    }
    setSendingIds((prev) => {
      const next = new Set(prev);
      next.delete(recipientId);
      return next;
    });
  };

  const handleApproveAll = async () => {
    try {
      await approveRecipients(id, []);
      loadData();
    } catch (error) {
      alert('Failed to approve recipients');
    }
  };

  const handleSaveNotes = async (recipientId, notes) => {
    try {
      await updateRecipient(id, recipientId, { notes });
      setRecipients((prev) =>
        prev.map((r) => (r.id === recipientId ? { ...r, notes } : r))
      );
    } catch (error) {
      alert('Failed to save notes');
    }
  };

  const handleRegeneratePreview = async (recipientId) => {
    setRegeneratingId(recipientId);
    try {
      const res = await regenerateRecipientPreview(id, recipientId);
      setRecipients((prev) =>
        prev.map((r) => (r.id === recipientId ? res.data : r))
      );
    } catch (error) {
      alert('Failed to regenerate preview: ' + (error.response?.data?.error || error.message));
    }
    setRegeneratingId(null);
  };

  const handleDeleteRecipient = async (recipientId, email) => {
    if (!confirm(`Remove ${email} from this campaign?`)) return;
    try {
      await deleteRecipient(id, recipientId);
      loadData();
    } catch (error) {
      alert('Failed to remove recipient');
    }
  };

  const handleClearRecipients = async () => {
    if (!confirm('Remove all recipients from this campaign?')) return;
    try {
      await clearRecipients(id);
      loadData();
    } catch (error) {
      alert('Failed to clear recipients');
    }
  };

  const handleAttachmentsChange = async (newAttachments) => {
    setAttachments(newAttachments);
    try {
      await updateCampaign(id, { attachments: newAttachments });
    } catch (error) {
      console.error('Failed to save attachments:', error);
    }
  };

  const handleChangeGmailAccount = async (accountId) => {
    try {
      await updateCampaign(id, { gmail_account_id: accountId ? parseInt(accountId) : null });
      loadData();
    } catch (error) {
      alert('Failed to update sending account');
    }
  };

  const handleUpdatePersonalizedContent = async (recipientId, field, value) => {
    try {
      await updateRecipient(id, recipientId, { [field]: value });
      setRecipients((prev) =>
        prev.map((r) => (r.id === recipientId ? { ...r, [field]: value } : r))
      );
    } catch (error) {
      alert('Failed to update content');
    }
  };

  const handleApproveRecipient = async (recipientId, approved) => {
    try {
      await updateRecipient(id, recipientId, { approved });
      setRecipients((prev) =>
        prev.map((r) => (r.id === recipientId ? { ...r, approved } : r))
      );
    } catch (error) {
      alert('Failed to update approval');
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

  const handleCheckReplies = async () => {
    setCheckingReplies(true);
    try {
      const res = await triggerReplyCheck();
      loadData();
      let msg = `Checked ${res.data.checked} emails, found ${res.data.replies_found} new replies`;
      if (res.data.bounces_found > 0) {
        msg += ` and ${res.data.bounces_found} bounced`;
      }
      alert(msg);
    } catch (error) {
      alert('Failed to check replies');
    }
    setCheckingReplies(false);
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
  const hasSentEmails = campaign.sent_count > 0;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <Link to="/campaigns" className="text-sm text-light">&larr; Back to Campaigns</Link>
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

        {/* Sending Account Selection */}
        {gmailAccounts.length > 0 && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #E5E7EB' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <label style={{ fontWeight: 500, fontSize: '0.875rem' }}>Send From:</label>
              {campaign.status === 'draft' ? (
                <select
                  className="form-input"
                  value={campaign.gmail_account_id || ''}
                  onChange={(e) => handleChangeGmailAccount(e.target.value)}
                  style={{ flex: 1, maxWidth: '300px' }}
                >
                  <option value="">Default account</option>
                  {gmailAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.email_address} {account.is_default ? '(Default)' : ''}
                    </option>
                  ))}
                </select>
              ) : (
                <span style={{ fontSize: '0.875rem' }}>
                  {campaign.gmail_account_email || gmailAccounts.find(a => a.is_default)?.email_address || 'Default account'}
                </span>
              )}
            </div>
          </div>
        )}

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

      {/* Tracking Stats Card */}
      {hasSentEmails && tracking && (
        <div className="card mb-4">
          <div className="flex justify-between items-center mb-2">
            <h3 className="card-title">Email Tracking</h3>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleCheckReplies}
              disabled={checkingReplies}
            >
              {checkingReplies ? 'Checking...' : 'Check Replies'}
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem' }}>
            <div className="stat-card">
              <div className="stat-value" style={{ color: '#3B82F6' }}>{tracking.total_opened}</div>
              <div className="stat-label">Opened ({Math.round(tracking.open_rate * 100)}%)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: '#8B5CF6' }}>{tracking.total_clicked}</div>
              <div className="stat-label">Clicked ({Math.round(tracking.click_rate * 100)}%)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: '#10B981' }}>{tracking.total_replied}</div>
              <div className="stat-label">Replied ({Math.round(tracking.reply_rate * 100)}%)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: '#EF4444' }}>{tracking.total_bounced || 0}</div>
              <div className="stat-label">Bounced ({Math.round((tracking.bounce_rate || 0) * 100)}%)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{tracking.total_sent}</div>
              <div className="stat-label">Total Tracked</div>
            </div>
          </div>
        </div>
      )}

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
                {uploading ? 'Uploading...' : 'Upload Recipients'}
              </button>

              {recipients.length > 0 && (
                <>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={handleClearRecipients}
                    style={{ padding: '0.4rem 0.75rem' }}
                  >
                    Clear Recipients
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleGeneratePreview(50)}
                    disabled={generating}
                  >
                    {generating ? 'Generating...' : 'Generate AI Previews'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleGeneratePreview(0)}
                    disabled={generating}
                    title="Generate personalized emails for all recipients at once"
                  >
                    {generating ? 'Generating...' : 'Generate All'}
                  </button>
                  <button className="btn btn-secondary" onClick={handleApproveAll}>
                    Approve All
                  </button>
                  <button
                    className="btn btn-success"
                    onClick={handleStart}
                    disabled={approvedCount === 0}
                  >
                    Start Campaign
                  </button>
                </>
              )}
            </>
          )}

          {campaign.status === 'draft' && (
            <div style={{ width: '100%', marginTop: '0.5rem' }}>
              <AttachmentPicker attachments={attachments} onChange={handleAttachmentsChange} />
            </div>
          )}

          {campaign.status === 'running' && (
            <>
              <button className="btn btn-warning" onClick={handlePause}>Pause</button>
              <button className="btn btn-danger" onClick={handleCancel}>Cancel</button>
            </>
          )}

          {campaign.status === 'paused' && (
            <>
              <button className="btn btn-success" onClick={handleResume}>Resume</button>
              <button className="btn btn-danger" onClick={handleCancel}>Cancel</button>
            </>
          )}

          {(campaign.status === 'completed' || campaign.status === 'cancelled') && (
            <>
              <a href={exportCampaign(id)} className="btn btn-secondary" download>
                Export CSV
              </a>
              <button
                className="btn btn-secondary"
                onClick={async () => {
                  setExportingClay(true);
                  try {
                    const res = await exportToClay(id);
                    alert(`Exported ${res.data.exported} results to Clay`);
                  } catch (error) {
                    const msg = error.response?.data?.error || error.message;
                    alert('Clay export failed: ' + msg);
                  }
                  setExportingClay(false);
                }}
                disabled={exportingClay}
              >
                {exportingClay ? 'Exporting...' : 'Export to Clay'}
              </button>
            </>
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
            <div style={{ marginTop: '1rem', textAlign: 'left', maxWidth: '500px', margin: '1rem auto' }}>
              <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>Recommended CSV fields for founder outreach:</p>
              <ul style={{ fontSize: '0.875rem', color: '#6B7280', lineHeight: '1.6' }}>
                <li><strong>email, name, company</strong> - Required basics</li>
                <li><strong>title</strong> - Their role (CEO, Founder, etc.)</li>
                <li><strong>industry</strong> - SaaS, FinTech, Healthcare, etc.</li>
                <li><strong>funding_stage</strong> - Seed, Series A, etc.</li>
                <li><strong>recent_news</strong> - Press mentions, launches, funding</li>
                <li><strong>pain_points</strong> - Known challenges they face</li>
                <li><strong>referral</strong> - Mutual connection or how you found them</li>
                <li><strong>context</strong> - Personal research notes for max personalization</li>
              </ul>
              <a
                href={getSampleCsvUrl()}
                download
                className="btn btn-secondary"
                style={{ marginTop: '1rem', display: 'inline-block' }}
              >
                Download Sample CSV Template
              </a>
            </div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Company</th>
                  <th>Notes</th>
                  <th>Status</th>
                  <th>Approved</th>
                  {hasSentEmails && <th>Opened</th>}
                  {hasSentEmails && <th>Clicked</th>}
                  {hasSentEmails && <th>Replied</th>}
                  {hasSentEmails && <th>Bounced</th>}
                  <th>Preview</th>
                  <th>Send</th>
                  {campaign.status === 'draft' && <th></th>}
                </tr>
              </thead>
              <tbody>
                {recipients.map((recipient) => (
                  <tr key={recipient.id}>
                    <td>{recipient.email}</td>
                    <td>{recipient.name || '-'}</td>
                    <td>{recipient.company || '-'}</td>
                    <td style={{ maxWidth: '200px' }}>
                      {editingRecipient === recipient.id ? (
                        <div>
                          <textarea
                            defaultValue={recipient.notes || ''}
                            rows={3}
                            style={{ width: '100%', fontSize: '0.875rem', padding: '0.5rem' }}
                            placeholder="Add research notes..."
                            onBlur={(e) => {
                              handleSaveNotes(recipient.id, e.target.value);
                              setEditingRecipient(null);
                            }}
                            autoFocus
                          />
                          <small className="text-light">Click outside to save</small>
                        </div>
                      ) : (
                        <div
                          onClick={() => campaign.status === 'draft' && setEditingRecipient(recipient.id)}
                          style={{
                            cursor: campaign.status === 'draft' ? 'pointer' : 'default',
                            padding: '0.25rem',
                            borderRadius: '0.25rem',
                            background: recipient.notes ? '#F0FDF4' : 'transparent',
                            minHeight: '2rem',
                          }}
                          title={campaign.status === 'draft' ? 'Click to edit notes' : ''}
                        >
                          {recipient.notes ? (
                            <span style={{ fontSize: '0.75rem' }}>{recipient.notes.substring(0, 50)}{recipient.notes.length > 50 ? '...' : ''}</span>
                          ) : (
                            <span className="text-light" style={{ fontSize: '0.75rem' }}>
                              {campaign.status === 'draft' ? '+ Add notes' : '-'}
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className={`badge badge-${recipient.status}`}>{recipient.status}</span>
                    </td>
                    <td>
                      {campaign.status === 'draft' && recipient.personalized_body ? (
                        <button
                          className={`btn btn-sm ${recipient.approved ? 'btn-success' : 'btn-secondary'}`}
                          onClick={() => handleApproveRecipient(recipient.id, !recipient.approved)}
                          style={{ padding: '0.25rem 0.5rem' }}
                        >
                          {recipient.approved ? '✓' : 'Approve'}
                        </button>
                      ) : recipient.approved ? (
                        <span style={{ color: '#10B981' }}>✓</span>
                      ) : (
                        <span style={{ color: '#9CA3AF' }}>-</span>
                      )}
                    </td>
                    {hasSentEmails && (
                      <td>
                        {recipient.tracking?.opened_at ? (
                          <span title={new Date(recipient.tracking.opened_at).toLocaleString()} style={{ color: '#3B82F6', fontWeight: 500 }}>
                            ✓ ({recipient.tracking.open_count})
                          </span>
                        ) : recipient.status === 'sent' ? (
                          <span style={{ color: '#9CA3AF' }}>-</span>
                        ) : null}
                      </td>
                    )}
                    {hasSentEmails && (
                      <td>
                        {recipient.tracking?.clicked_at ? (
                          <span title={new Date(recipient.tracking.clicked_at).toLocaleString()} style={{ color: '#8B5CF6', fontWeight: 500 }}>
                            ✓ ({recipient.tracking.click_count})
                          </span>
                        ) : recipient.status === 'sent' ? (
                          <span style={{ color: '#9CA3AF' }}>-</span>
                        ) : null}
                      </td>
                    )}
                    {hasSentEmails && (
                      <td>
                        {recipient.tracking?.replied_at ? (
                          <span title={new Date(recipient.tracking.replied_at).toLocaleString()} style={{ color: '#10B981', fontWeight: 500 }}>
                            ✓
                          </span>
                        ) : recipient.status === 'sent' ? (
                          <span style={{ color: '#9CA3AF' }}>-</span>
                        ) : null}
                      </td>
                    )}
                    {hasSentEmails && (
                      <td>
                        {recipient.tracking?.bounced_at ? (
                          <span
                            title={`${new Date(recipient.tracking.bounced_at).toLocaleString()}${recipient.tracking.bounce_reason ? '\n' + recipient.tracking.bounce_reason : ''}`}
                            style={{ color: '#EF4444', fontWeight: 500, cursor: 'help' }}
                          >
                            ✕
                          </span>
                        ) : recipient.status === 'sent' ? (
                          <span style={{ color: '#9CA3AF' }}>-</span>
                        ) : null}
                      </td>
                    )}
                    <td>
                      {recipient.personalized_body ? (
                        <details>
                          <summary className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
                            View
                          </summary>
                          <div style={{ padding: '1rem', background: '#F9FAFB', marginTop: '0.5rem', borderRadius: '0.5rem', minWidth: '400px' }}>
                            {campaign.status === 'draft' ? (
                              <>
                                <div style={{ marginBottom: '0.5rem' }}>
                                  <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>Subject:</label>
                                  <input
                                    type="text"
                                    defaultValue={recipient.personalized_subject}
                                    style={{ width: '100%', padding: '0.5rem', fontSize: '0.875rem' }}
                                    onBlur={(e) => handleUpdatePersonalizedContent(recipient.id, 'personalized_subject', e.target.value)}
                                  />
                                </div>
                                <div style={{ marginBottom: '0.5rem' }}>
                                  <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.25rem' }}>Body:</label>
                                  <RichTextEditor
                                    value={recipient.personalized_body}
                                    onChange={(html) => handleUpdatePersonalizedContent(recipient.id, 'personalized_body', html)}
                                    minHeight="150px"
                                    compact
                                  />
                                </div>
                                <div className="flex gap-2" style={{ marginTop: '0.5rem' }}>
                                  <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={() => handleRegeneratePreview(recipient.id)}
                                    disabled={regeneratingId === recipient.id}
                                  >
                                    {regeneratingId === recipient.id ? 'Regenerating...' : 'Regenerate'}
                                  </button>
                                  {!recipient.approved && (
                                    <button
                                      className="btn btn-success btn-sm"
                                      onClick={() => handleApproveRecipient(recipient.id, true)}
                                    >
                                      Approve
                                    </button>
                                  )}
                                </div>
                              </>
                            ) : (
                              <>
                                <p><strong>Subject:</strong> {recipient.personalized_subject}</p>
                                <hr style={{ margin: '0.5rem 0', border: 'none', borderTop: '1px solid #E5E7EB' }} />
                                <div style={{ lineHeight: '1.6' }} dangerouslySetInnerHTML={{ __html: recipient.personalized_body }} />
                              </>
                            )}
                          </div>
                        </details>
                      ) : (
                        <span className="text-light">-</span>
                      )}
                    </td>
                    <td>
                      {recipient.status === 'sent' ? (
                        <span style={{ color: '#10B981' }}>Sent</span>
                      ) : recipient.personalized_body ? (
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => handleSendIndividual(recipient.id)}
                          disabled={sendingIds.has(recipient.id)}
                        >
                          {sendingIds.has(recipient.id) ? 'Sending...' : 'Send'}
                        </button>
                      ) : (
                        <span className="text-light">-</span>
                      )}
                    </td>
                    {campaign.status === 'draft' && (
                      <td>
                        <button
                          className="btn btn-sm"
                          onClick={() => handleDeleteRecipient(recipient.id, recipient.email)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#9CA3AF',
                            cursor: 'pointer',
                            fontSize: '1.1rem',
                            padding: '0.2rem 0.5rem',
                          }}
                          title="Remove recipient"
                          onMouseOver={(e) => e.target.style.color = '#EF4444'}
                          onMouseOut={(e) => e.target.style.color = '#9CA3AF'}
                        >
                          ✕
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Custom Fields Info */}
      {recipients.length > 0 && recipients[0].custom_fields && Object.keys(recipients[0].custom_fields).length > 0 && (
        <div className="card mt-4">
          <h3 className="card-title">Available Custom Fields</h3>
          <p className="text-light" style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>
            These fields from your CSV are available for AI personalization:
          </p>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            {Object.keys(recipients[0].custom_fields).map((field) => (
              <span key={field} className="badge" style={{ background: '#E5E7EB', color: '#374151' }}>
                {field}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default CampaignDetail;
