import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getCampaign,
  getRecipients,
  getCampaigns,
  clearRecipients,
  deleteRecipient,
  moveRecipients,
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
  getSteps,
  createStep,
  updateStep,
  deleteStep,
  generateStepPreview,
  approveStepRecipients,
  startStep,
  getTemplates,
} from '../api/client';
import AttachmentPicker from '../components/AttachmentPicker';
import RichTextEditor from '../components/RichTextEditor';
import SequenceBuilder from '../components/SequenceBuilder';
import ColdCallModal from '../components/ColdCallModal';
import AddContactToRunningCampaignModal from '../components/AddContactToRunningCampaignModal';

function MoveModal({ campaigns, selectedCount, onMove, onClose, isMoving }) {
  const [targetMode, setTargetMode] = useState('existing');
  const [selectedTargetId, setSelectedTargetId] = useState('');
  const [newName, setNewName] = useState('');

  const canSubmit = targetMode === 'existing'
    ? selectedTargetId !== ''
    : newName.trim() !== '';

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '2rem',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: '#fff', borderRadius: '0.75rem', width: '100%', maxWidth: '500px',
        boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
      }}>
        <div style={{
          padding: '1rem 1.5rem', borderBottom: '1px solid #E5E7EB',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <h3 style={{ margin: 0 }}>Move {selectedCount} Recipient{selectedCount !== 1 ? 's' : ''}</h3>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', fontSize: '1.5rem',
              color: '#9CA3AF', cursor: 'pointer', lineHeight: 1,
            }}
          >&times;</button>
        </div>

        <div style={{ padding: '1.5rem' }}>
          <p style={{ fontSize: '0.875rem', color: '#6B7280', marginBottom: '1rem' }}>
            Personalized content will be cleared when recipients are moved. Only pending recipients will be moved.
          </p>

          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
              <input
                type="radio"
                name="targetMode"
                checked={targetMode === 'existing'}
                onChange={() => setTargetMode('existing')}
              />
              Existing campaign
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
              <input
                type="radio"
                name="targetMode"
                checked={targetMode === 'new'}
                onChange={() => setTargetMode('new')}
              />
              New campaign
            </label>
          </div>

          {targetMode === 'existing' ? (
            <select
              className="form-input"
              value={selectedTargetId}
              onChange={(e) => setSelectedTargetId(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">Select a campaign...</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.status} — {c.total_recipients} recipients)
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              className="form-input"
              placeholder="New campaign name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              style={{ width: '100%' }}
              autoFocus
            />
          )}
        </div>

        <div style={{
          padding: '1rem 1.5rem', borderTop: '1px solid #E5E7EB',
          display: 'flex', justifyContent: 'flex-end', gap: '0.5rem',
        }}>
          <button className="btn btn-secondary" onClick={onClose} disabled={isMoving}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit || isMoving}
            onClick={() => onMove(
              targetMode === 'existing' ? parseInt(selectedTargetId) : null,
              targetMode === 'new' ? newName.trim() : null
            )}
          >
            {isMoving ? 'Moving...' : 'Move Recipients'}
          </button>
        </div>
      </div>
    </div>
  );
}

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
  const [previewRecipientId, setPreviewRecipientId] = useState(null);
  const [selectedRecipientIds, setSelectedRecipientIds] = useState(new Set());
  const [showMoveModal, setShowMoveModal] = useState(false);
  const [movingRecipients, setMovingRecipients] = useState(false);
  const [campaignsList, setCampaignsList] = useState([]);
  const [steps, setSteps] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [coldCallRecipientId, setColdCallRecipientId] = useState(null);
  const [showAddContactModal, setShowAddContactModal] = useState(false);
  const fileInputRef = useRef();
  const eventSourceRef = useRef();

  useEffect(() => {
    loadData();
    getGmailAccounts().then((res) => {
      setGmailAccounts(res.data.accounts || []);
    });
    getTemplates().then((res) => {
      setTemplates(res.data);
    }).catch(() => {});
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
    if (campaign?.status === 'running' || campaign?.status === 'sequence_active') {
      startProgressStream();
    }
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [campaign?.status]);

  // Keyboard shortcuts for email preview modal
  useEffect(() => {
    if (!previewRecipientId) return;
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        setPreviewRecipientId(null);
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const previewRecipients = recipients.filter((r) => r.personalized_body);
        const idx = previewRecipients.findIndex((r) => r.id === previewRecipientId);
        if (e.key === 'ArrowLeft' && idx > 0) {
          setPreviewRecipientId(previewRecipients[idx - 1].id);
        } else if (e.key === 'ArrowRight' && idx < previewRecipients.length - 1) {
          setPreviewRecipientId(previewRecipients[idx + 1].id);
        }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [previewRecipientId, recipients]);

  const loadData = async () => {
    try {
      const [campaignRes, recipientsRes] = await Promise.all([
        getCampaign(id),
        getRecipients(id),
      ]);
      setCampaign(campaignRes.data);
      setAttachments(campaignRes.data.attachments || []);
      setSteps(campaignRes.data.steps || []);
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
      const { added, updated, invalid_skipped } = res.data;

      let msg = `Added ${added} recipient${added !== 1 ? 's' : ''}.`;
      if (updated > 0) {
        msg += `\nUpdated ${updated} existing recipient${updated !== 1 ? 's' : ''}.`;
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
      const { generated, failed, remaining, message, spam_warnings } = res.data;
      if (message) {
        alert(message);
      } else if (remaining > 0) {
        const mode = batchSize > 0 ? 'batch preview' : 'generation';
        let statusMsg = `Generated ${generated} emails (${mode})`;
        if (failed > 0) statusMsg += ` (${failed} fell back to template)`;
        if (spam_warnings > 0) statusMsg += `\n\nSpam warning: ${spam_warnings} email(s) may trigger spam filters. Check the status dots for details.`;
        statusMsg += `\n\n${remaining} recipients remaining.\n\nGenerate the next batch?`;
        const continueGenerating = confirm(statusMsg);
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

      // Auto-advance: move to next unsent preview or close the modal
      if (previewRecipientId === recipientId) {
        const unsent = recipients.filter(
          (r) => r.personalized_body && r.status !== 'sent' && r.id !== recipientId
        );
        if (unsent.length > 0) {
          // Find next one after current position, or wrap to first
          const curIdx = recipients.findIndex((r) => r.id === recipientId);
          const nextUnsent = unsent.find((r) => recipients.indexOf(r) > curIdx) || unsent[0];
          setPreviewRecipientId(nextUnsent.id);
        } else {
          setPreviewRecipientId(null);
        }
      }
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

  const handleToggleRecipient = (recipientId) => {
    setSelectedRecipientIds((prev) => {
      const next = new Set(prev);
      if (next.has(recipientId)) {
        next.delete(recipientId);
      } else {
        next.add(recipientId);
      }
      return next;
    });
  };

  const handleToggleAll = () => {
    const pendingIds = recipients.filter((r) => r.status === 'pending').map((r) => r.id);
    if (pendingIds.length > 0 && pendingIds.every((rid) => selectedRecipientIds.has(rid))) {
      setSelectedRecipientIds(new Set());
    } else {
      setSelectedRecipientIds(new Set(pendingIds));
    }
  };

  const handleOpenMoveModal = async () => {
    try {
      const res = await getCampaigns();
      setCampaignsList(res.data.filter((c) => c.id !== parseInt(id)));
    } catch {
      alert('Failed to load campaigns');
      return;
    }
    setShowMoveModal(true);
  };

  const handleMoveRecipients = async (targetCampaignId, newCampaignName) => {
    setMovingRecipients(true);
    try {
      const res = await moveRecipients(
        id,
        Array.from(selectedRecipientIds),
        targetCampaignId,
        newCampaignName
      );
      const { moved, skipped_sent, skipped_duplicate, target_campaign_name } = res.data;
      let msg = `Moved ${moved} recipient(s) to "${target_campaign_name}".`;
      if (skipped_sent > 0) msg += `\n${skipped_sent} skipped (already sent).`;
      if (skipped_duplicate > 0) msg += `\n${skipped_duplicate} skipped (already in target).`;
      alert(msg);
      setSelectedRecipientIds(new Set());
      setShowMoveModal(false);
      loadData();
    } catch (error) {
      alert('Failed to move recipients: ' + (error.response?.data?.error || error.message));
    }
    setMovingRecipients(false);
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
      const data = error.response?.data;
      if (data?.ungenerated_count) {
        const proceed = confirm(
          `${data.ungenerated_count} of ${data.total_approved} recipients do not have generated emails. ` +
          `These recipients will be skipped.\n\nDo you want to proceed anyway?`
        );
        if (proceed) {
          try {
            await startCampaign(id, { force: true });
            loadData();
          } catch (e) {
            alert('Failed to start campaign: ' + (e.response?.data?.error || e.message));
          }
        }
      } else {
        alert('Failed to start campaign: ' + (data?.error || error.message));
      }
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

  // Step management handlers
  const handleCreateStep = async (stepData) => {
    try {
      await createStep(id, stepData);
      loadData();
    } catch (error) {
      alert('Failed to create step: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleUpdateStep = async (stepId, data) => {
    try {
      await updateStep(id, stepId, data);
      loadData();
    } catch (error) {
      alert('Failed to update step: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleDeleteStep = async (stepId) => {
    try {
      await deleteStep(id, stepId);
      loadData();
    } catch (error) {
      alert('Failed to delete step: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleGenerateStepPreview = async (stepId) => {
    try {
      const res = await generateStepPreview(id, stepId);
      const { generated, failed, remaining } = res.data;
      let msg = `Generated ${generated} follow-up emails.`;
      if (failed > 0) msg += ` ${failed} failed.`;
      if (remaining > 0) msg += ` ${remaining} remaining.`;
      alert(msg);
      loadData();
    } catch (error) {
      alert('Failed to generate step previews: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleApproveStep = async (stepId) => {
    try {
      await approveStepRecipients(id, stepId);
      loadData();
    } catch (error) {
      alert('Failed to approve step recipients');
    }
  };

  const handleStartStep = async (stepId) => {
    try {
      await startStep(id, stepId);
      loadData();
    } catch (error) {
      alert('Failed to start step: ' + (error.response?.data?.error || error.message));
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
  const generatedCount = recipients.filter((r) => r.personalized_body).length;
  const ungeneratedCount = recipients.length - generatedCount;
  const hasSentEmails = campaign.sent_count > 0;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <div>
          <Link to="/campaigns" className="text-sm text-light">&larr; Back to Campaigns</Link>
          <h1>{campaign.name}</h1>
        </div>
        <span className={`badge badge-${campaign.status === 'sequence_active' ? 'running' : campaign.status}`} style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>
          {campaign.status === 'sequence_active' ? 'Sequence Active' : campaign.status}
        </span>
      </div>

      {/* Auto-Send Settings */}
      {campaign.status === 'draft' && (
        <div className="card mb-4">
          <h3 className="card-title mb-2">Confidence Auto-Send</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={!!campaign.auto_send_enabled}
                onChange={(e) => updateCampaign(id, { auto_send_enabled: e.target.checked }).then(loadData)}
              />
              <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>Auto-approve emails above confidence threshold</span>
            </label>
            {campaign.auto_send_enabled && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="range"
                  min="0.5"
                  max="0.95"
                  step="0.05"
                  value={campaign.auto_send_threshold || 0.8}
                  onChange={(e) => updateCampaign(id, { auto_send_threshold: parseFloat(e.target.value) }).then(loadData)}
                  style={{ width: '120px' }}
                />
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#4F46E5', minWidth: '40px' }}>
                  {((campaign.auto_send_threshold || 0.8) * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>
          {campaign.auto_send_enabled && (
            <p className="text-sm text-light" style={{ marginTop: '0.5rem' }}>
              Emails scoring above {((campaign.auto_send_threshold || 0.8) * 100).toFixed(0)}% confidence will be auto-approved during generation.
            </p>
          )}
        </div>
      )}

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
                  {selectedRecipientIds.size > 0 && (
                    <button
                      className="btn btn-secondary"
                      onClick={handleOpenMoveModal}
                      style={{ padding: '0.4rem 0.75rem' }}
                    >
                      Move Selected ({selectedRecipientIds.size})
                    </button>
                  )}
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleGeneratePreview(10)}
                    disabled={generating || ungeneratedCount === 0}
                    title="Generate a batch of up to 10 previews to review before generating the rest"
                  >
                    {generating ? 'Generating...' : ungeneratedCount > 0 ? `Preview Batch (10)` : 'All Previews Generated'}
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={() => handleGeneratePreview(0)}
                    disabled={generating || ungeneratedCount === 0}
                    title="Generate personalized emails for all recipients at once"
                  >
                    {generating ? 'Generating...' : ungeneratedCount > 0 ? `Generate All (${ungeneratedCount})` : 'All Generated'}
                  </button>
                  {generatedCount > 0 && (
                    <span style={{ fontSize: '0.85rem', color: '#6B7280', alignSelf: 'center' }}>
                      {generatedCount}/{recipients.length} generated
                    </span>
                  )}
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

          {campaign.status === 'draft' && (
            <div style={{ width: '100%', marginTop: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: !!campaign.competitor_search_query ? '0.5rem' : 0 }}>
                <label style={{ position: 'relative', display: 'inline-block', width: '36px', height: '20px', flexShrink: 0 }}>
                  <input
                    type="checkbox"
                    checked={!!campaign.competitor_search_query}
                    onChange={(e) => {
                      if (e.target.checked) {
                        updateCampaign(id, { competitor_search_query: '{{industry}} in {{city}} {{state}}' }).then(loadData);
                      } else {
                        updateCampaign(id, { competitor_search_query: null }).then(loadData);
                      }
                    }}
                    style={{ opacity: 0, width: 0, height: 0 }}
                  />
                  <span style={{
                    position: 'absolute', cursor: 'pointer', inset: 0, borderRadius: '10px',
                    backgroundColor: campaign.competitor_search_query ? '#10B981' : '#D1D5DB',
                    transition: 'background-color 0.2s',
                  }}>
                    <span style={{
                      position: 'absolute', height: '16px', width: '16px', left: campaign.competitor_search_query ? '18px' : '2px',
                      bottom: '2px', backgroundColor: 'white', borderRadius: '50%',
                      transition: 'left 0.2s',
                    }} />
                  </span>
                </label>
                <span style={{ fontSize: '0.85rem', color: '#374151', fontWeight: 500 }}>Competitor Discovery</span>
              </div>
              {!!campaign.competitor_search_query && (
                <div>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. {{industry}} in {{city}} {{state}}"
                    defaultValue={campaign.competitor_search_query || ''}
                    key={campaign.competitor_search_query}
                    onBlur={(e) => {
                      const val = e.target.value.trim();
                      if (!val) {
                        updateCampaign(id, { competitor_search_query: null }).then(loadData);
                      } else if (val !== campaign.competitor_search_query) {
                        updateCampaign(id, { competitor_search_query: val }).then(loadData);
                      }
                    }}
                    style={{ width: '100%', marginBottom: '0.25rem' }}
                  />
                  <span style={{ fontSize: '0.7rem', color: '#9CA3AF' }}>
                    Searches the web and pulls the top businesses that show up, excluding the target company. Use {'{{competitor1}}'}, {'{{competitor2}}'}, or {'{{competitors}}'} in your template. Supports any CSV variable like {'{{city}}'}, {'{{state}}'}, {'{{industry}}'}.
                  </span>
                </div>
              )}
            </div>
          )}

          {campaign.status === 'running' && (
            <>
              <button className="btn btn-primary" onClick={() => setShowAddContactModal(true)}>Add Contacts</button>
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

          {campaign.status === 'sequence_active' && (
            <>
              <span style={{ fontSize: '0.85rem', color: '#6B7280', alignSelf: 'center' }}>
                Follow-up sequence is running. Steps will send automatically based on their delay settings.
              </span>
              <button className="btn btn-primary" onClick={() => setShowAddContactModal(true)}>Add Contacts</button>
              <button className="btn btn-danger" onClick={handleCancel}>Cancel Sequence</button>
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

      {/* Follow-up Sequence Builder */}
      {recipients.length > 0 && (
        <SequenceBuilder
          campaignId={id}
          steps={steps}
          templates={templates}
          campaignStatus={campaign.status}
          onCreateStep={handleCreateStep}
          onUpdateStep={handleUpdateStep}
          onDeleteStep={handleDeleteStep}
          onGeneratePreview={handleGenerateStepPreview}
          onApproveStep={handleApproveStep}
          onStartStep={handleStartStep}
          onReloadSteps={loadData}
        />
      )}

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
                  {campaign.status === 'draft' && (
                    <th style={{ width: '40px' }}>
                      <input
                        type="checkbox"
                        checked={
                          recipients.filter((r) => r.status === 'pending').length > 0 &&
                          recipients.filter((r) => r.status === 'pending').every((r) => selectedRecipientIds.has(r.id))
                        }
                        onChange={handleToggleAll}
                      />
                    </th>
                  )}
                  <th>Email</th>
                  <th>Name</th>
                  <th>Company</th>
                  <th>Notes</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th>Approved</th>
                  {hasSentEmails && <th>Opened</th>}
                  {hasSentEmails && <th>Clicked</th>}
                  {hasSentEmails && <th>Replied</th>}
                  {hasSentEmails && <th>Bounced</th>}
                  <th>Preview</th>
                  <th>Send</th>
                  <th>Call</th>
                  {campaign.status === 'draft' && <th></th>}
                </tr>
              </thead>
              <tbody>
                {recipients.map((recipient) => (
                  <tr key={recipient.id}>
                    {campaign.status === 'draft' && (
                      <td>
                        {recipient.status === 'pending' ? (
                          <input
                            type="checkbox"
                            checked={selectedRecipientIds.has(recipient.id)}
                            onChange={() => handleToggleRecipient(recipient.id)}
                          />
                        ) : (
                          <span style={{ color: '#D1D5DB' }} title="Already sent — cannot move">—</span>
                        )}
                      </td>
                    )}
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
                      {recipient.confidence_score != null ? (
                        <span
                          title={recipient.confidence_breakdown ? Object.entries(recipient.confidence_breakdown).map(([k,v]) => `${k}: ${(v*100).toFixed(0)}%`).join('\n') : ''}
                          style={{
                            padding: '0.15rem 0.5rem',
                            borderRadius: '9999px',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            cursor: 'help',
                            background: recipient.confidence_score >= 0.8 ? '#D1FAE5' : recipient.confidence_score >= 0.5 ? '#FEF3C7' : '#FEE2E2',
                            color: recipient.confidence_score >= 0.8 ? '#065F46' : recipient.confidence_score >= 0.5 ? '#92400E' : '#991B1B',
                          }}
                        >
                          {(recipient.confidence_score * 100).toFixed(0)}%
                        </span>
                      ) : (
                        <span style={{ color: '#9CA3AF' }}>-</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge badge-${recipient.status}`}>{recipient.status}</span>
                      {recipient.website_severity && (
                        <span
                          title={`Website issue severity: ${recipient.website_severity}`}
                          style={{
                            display: 'inline-block',
                            marginLeft: '0.35rem',
                            padding: '0.1rem 0.4rem',
                            fontSize: '0.65rem',
                            fontWeight: 600,
                            borderRadius: '0.25rem',
                            textTransform: 'uppercase',
                            background: recipient.website_severity === 'critical' ? '#FEE2E2' : '#FEF3C7',
                            color: recipient.website_severity === 'critical' ? '#DC2626' : '#D97706',
                            cursor: 'help',
                          }}
                        >
                          {recipient.website_severity}
                        </span>
                      )}
                      {recipient.content_warnings && recipient.content_warnings.length > 0 && (
                        <span
                          title={`Content warning:\n${recipient.content_warnings.join('\n')}`}
                          style={{
                            display: 'inline-block',
                            marginLeft: '0.35rem',
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            background: '#F59E0B',
                            cursor: 'help',
                          }}
                        />
                      )}
                      {recipient.spam_check && recipient.spam_check.level !== 'low' && (
                        <span
                          title={`Spam risk: ${recipient.spam_check.level} (${recipient.spam_check.score}/100)\n${recipient.spam_check.reasons.join('\n')}`}
                          style={{
                            display: 'inline-block',
                            marginLeft: '0.35rem',
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            background: recipient.spam_check.level === 'high' ? '#EF4444' : '#F59E0B',
                            cursor: 'help',
                          }}
                        />
                      )}
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
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setPreviewRecipientId(recipient.id)}
                        >
                          View
                        </button>
                      ) : (
                        <span className="text-light">-</span>
                      )}
                    </td>
                    <td>
                      {recipient.status === 'sent' ? (
                        <span style={{ color: '#10B981' }}>Sent</span>
                      ) : (
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => handleSendIndividual(recipient.id)}
                          disabled={sendingIds.has(recipient.id) || !recipient.personalized_body}
                          title={!recipient.personalized_body ? 'Generate AI preview first' : ''}
                        >
                          {sendingIds.has(recipient.id) ? 'Sending...' : 'Send'}
                        </button>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setColdCallRecipientId(recipient.id)}
                        style={{ padding: '0.2rem 0.5rem', fontSize: '0.85rem' }}
                        title="Log cold call"
                      >
                        &#128222;
                      </button>
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

      {/* Email Preview Modal */}
      {previewRecipientId && (() => {
        const recipientIndex = recipients.findIndex((r) => r.id === previewRecipientId);
        const recipient = recipients[recipientIndex];
        if (!recipient) return null;
        const previewRecipients = recipients.filter((r) => r.personalized_body);
        const previewIndex = previewRecipients.findIndex((r) => r.id === previewRecipientId);
        const hasPrev = previewIndex > 0;
        const hasNext = previewIndex < previewRecipients.length - 1;
        return (
          <div
            style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              zIndex: 1000, padding: '2rem',
            }}
            onClick={(e) => { if (e.target === e.currentTarget) setPreviewRecipientId(null); }}
          >
            <div style={{
              background: '#fff', borderRadius: '0.75rem', width: '100%', maxWidth: '700px',
              maxHeight: '90vh', display: 'flex', flexDirection: 'column',
              boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
            }}>
              {/* Header */}
              <div style={{
                padding: '1rem 1.5rem', borderBottom: '1px solid #E5E7EB',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                flexShrink: 0,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ fontSize: '0.875rem', color: '#6B7280' }}>
                    {previewIndex + 1} of {previewRecipients.length}
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!hasPrev}
                    onClick={() => setPreviewRecipientId(previewRecipients[previewIndex - 1].id)}
                    style={{ padding: '0.2rem 0.6rem' }}
                  >
                    Prev
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={!hasNext}
                    onClick={() => setPreviewRecipientId(previewRecipients[previewIndex + 1].id)}
                    style={{ padding: '0.2rem 0.6rem' }}
                  >
                    Next
                  </button>
                </div>
                <button
                  onClick={() => setPreviewRecipientId(null)}
                  style={{
                    background: 'none', border: 'none', fontSize: '1.5rem',
                    color: '#9CA3AF', cursor: 'pointer', lineHeight: 1,
                  }}
                >
                  &times;
                </button>
              </div>

              {/* Email content */}
              <div style={{ overflow: 'auto', padding: '1.5rem', flex: 1 }}>
                {/* To / recipient info */}
                <div style={{
                  padding: '0.75rem 1rem', background: '#F9FAFB', borderRadius: '0.5rem',
                  marginBottom: '1rem', fontSize: '0.875rem',
                }}>
                  <div><strong>To:</strong> {recipient.name ? `${recipient.name} <${recipient.email}>` : recipient.email}</div>
                  {recipient.company && <div><strong>Company:</strong> {recipient.company}</div>}
                  <div style={{ marginTop: '0.25rem' }}>
                    <span className={`badge badge-${recipient.status}`} style={{ fontSize: '0.75rem' }}>{recipient.status}</span>
                    {recipient.website_severity && (
                      <span style={{
                        marginLeft: '0.35rem',
                        padding: '0.1rem 0.4rem',
                        fontSize: '0.65rem',
                        fontWeight: 600,
                        borderRadius: '0.25rem',
                        textTransform: 'uppercase',
                        background: recipient.website_severity === 'critical' ? '#FEE2E2' : '#FEF3C7',
                        color: recipient.website_severity === 'critical' ? '#DC2626' : '#D97706',
                      }}>
                        {recipient.website_severity}
                      </span>
                    )}
                    {recipient.approved && <span style={{ color: '#10B981', marginLeft: '0.5rem', fontSize: '0.75rem' }}>Approved</span>}
                    {recipient.confidence_score != null && (
                      <span
                        title={recipient.confidence_breakdown ? Object.entries(recipient.confidence_breakdown).map(([k,v]) => `${k}: ${(v*100).toFixed(0)}%`).join('\n') : ''}
                        style={{
                          marginLeft: '0.5rem',
                          padding: '0.1rem 0.5rem',
                          borderRadius: '9999px',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          cursor: 'help',
                          background: recipient.confidence_score >= 0.8 ? '#D1FAE5' : recipient.confidence_score >= 0.5 ? '#FEF3C7' : '#FEE2E2',
                          color: recipient.confidence_score >= 0.8 ? '#065F46' : recipient.confidence_score >= 0.5 ? '#92400E' : '#991B1B',
                        }}
                      >
                        Confidence: {(recipient.confidence_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>

                {/* Content warnings (e.g. missing website insights) */}
                {recipient.content_warnings && recipient.content_warnings.length > 0 && (
                  <div style={{
                    padding: '0.75rem 1rem',
                    background: '#FFFBEB',
                    border: '1px solid #FDE68A',
                    borderRadius: '0.5rem',
                    marginBottom: '1rem',
                    fontSize: '0.85rem',
                  }}>
                    <div style={{ fontWeight: 600, color: '#D97706', marginBottom: '0.25rem' }}>
                      Content Warning
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#6B7280' }}>
                      {recipient.content_warnings.map((warning, i) => (
                        <li key={i}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Spam warning */}
                {recipient.spam_check && recipient.spam_check.level !== 'low' && (
                  <div style={{
                    padding: '0.75rem 1rem',
                    background: recipient.spam_check.level === 'high' ? '#FEF2F2' : '#FFFBEB',
                    border: `1px solid ${recipient.spam_check.level === 'high' ? '#FECACA' : '#FDE68A'}`,
                    borderRadius: '0.5rem',
                    marginBottom: '1rem',
                    fontSize: '0.85rem',
                  }}>
                    <div style={{ fontWeight: 600, color: recipient.spam_check.level === 'high' ? '#DC2626' : '#D97706', marginBottom: '0.25rem' }}>
                      Spam Risk: {recipient.spam_check.level.toUpperCase()} (score: {recipient.spam_check.score}/100)
                    </div>
                    {recipient.spam_check.reasons.length > 0 && (
                      <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#6B7280' }}>
                        {recipient.spam_check.reasons.map((reason, i) => (
                          <li key={i}>{reason}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {/* Subject */}
                {campaign.status === 'draft' ? (
                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', color: '#374151' }}>Subject</label>
                    <input
                      type="text"
                      key={recipient.id + '-subject'}
                      defaultValue={recipient.personalized_subject}
                      style={{ width: '100%', padding: '0.5rem 0.75rem', fontSize: '0.95rem', border: '1px solid #D1D5DB', borderRadius: '0.375rem' }}
                      onBlur={(e) => handleUpdatePersonalizedContent(recipient.id, 'personalized_subject', e.target.value)}
                    />
                  </div>
                ) : (
                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem', fontSize: '0.875rem', color: '#374151' }}>Subject</label>
                    <div style={{ fontSize: '0.95rem' }}>{recipient.personalized_subject}</div>
                  </div>
                )}

                <hr style={{ margin: '0 0 1rem 0', border: 'none', borderTop: '1px solid #E5E7EB' }} />

                {/* Body */}
                {campaign.status === 'draft' ? (
                  <RichTextEditor
                    key={recipient.id + '-body'}
                    value={recipient.personalized_body}
                    onChange={(html) => handleUpdatePersonalizedContent(recipient.id, 'personalized_body', html)}
                    minHeight="250px"
                  />
                ) : (
                  <div style={{ lineHeight: '1.7', fontSize: '0.95rem' }} dangerouslySetInnerHTML={{ __html: recipient.personalized_body }} />
                )}
              </div>

              {/* Footer actions */}
              {campaign.status === 'draft' && (
                <div style={{
                  padding: '1rem 1.5rem', borderTop: '1px solid #E5E7EB',
                  display: 'flex', gap: '0.5rem', flexShrink: 0,
                }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleRegeneratePreview(recipient.id)}
                    disabled={regeneratingId === recipient.id}
                  >
                    {regeneratingId === recipient.id ? 'Regenerating...' : 'Regenerate'}
                  </button>
                  {!recipient.approved ? (
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleApproveRecipient(recipient.id, true)}
                    >
                      Approve
                    </button>
                  ) : (
                    <span style={{ color: '#10B981', alignSelf: 'center', fontSize: '0.875rem' }}>Approved</span>
                  )}
                  {recipient.personalized_body && recipient.status !== 'sent' && (
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleSendIndividual(recipient.id)}
                      disabled={sendingIds.has(recipient.id)}
                      style={{ marginLeft: 'auto' }}
                    >
                      {sendingIds.has(recipient.id) ? 'Sending...' : 'Send'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {showMoveModal && (
        <MoveModal
          campaigns={campaignsList}
          selectedCount={selectedRecipientIds.size}
          onMove={handleMoveRecipients}
          onClose={() => setShowMoveModal(false)}
          isMoving={movingRecipients}
        />
      )}
      {coldCallRecipientId && (
        <ColdCallModal
          recipientId={coldCallRecipientId}
          campaignId={parseInt(id)}
          onClose={() => setColdCallRecipientId(null)}
          onSaved={() => setColdCallRecipientId(null)}
        />
      )}
      {showAddContactModal && (
        <AddContactToRunningCampaignModal
          campaignId={parseInt(id)}
          onClose={() => setShowAddContactModal(false)}
          onSuccess={() => {
            loadData();
          }}
        />
      )}
    </div>
  );
}

export default CampaignDetail;
