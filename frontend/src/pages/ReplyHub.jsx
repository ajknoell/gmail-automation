import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  getReplies,
  getReplyStats,
  classifyReply,
  generateReplyResponse,
  sendReplyResponse,
  getCalendarStatus,
  getGmailAccounts,
  getGmailConnectUrl,
  getFollowUps,
  generateFollowUp,
  setReplyFollowUp,
  sendQuickEmail,
  updateContact,
  triggerReplyCheck,
  dismissReply,
  getAutopilotStats,
} from '../api/client';

const SENTIMENT_COLORS = {
  positive: { bg: '#D1FAE5', text: '#065F46', label: 'Positive' },
  negative: { bg: '#FEE2E2', text: '#991B1B', label: 'Negative' },
  neutral: { bg: '#F3F4F6', text: '#374151', label: 'Neutral' },
};

function ReplyHub() {
  // Data
  const [replies, setReplies] = useState([]);
  const [outstandingReplies, setOutstandingReplies] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [stats, setStats] = useState({});
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [calendarStatus, setCalendarStatus] = useState({});
  const [accounts, setAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState('');

  // Reply interaction
  const [selectedReply, setSelectedReply] = useState(null);
  const [generatedResponse, setGeneratedResponse] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [expandedReplies, setExpandedReplies] = useState({});

  // Follow-up interaction
  const [generatingFollowUp, setGeneratingFollowUp] = useState(null);
  const [followUpDrafts, setFollowUpDrafts] = useState({});
  const [sendingFollowUp, setSendingFollowUp] = useState(null);

  // Autopilot
  const [flaggedReplies, setFlaggedReplies] = useState([]);
  const [autopilotStats, setAutopilotStats] = useState({});

  // Check now
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState(null);

  // Set follow-up modal
  const [followUpForm, setFollowUpForm] = useState(null); // { replyId, date, note }

  // Section collapse
  const [followUpsOpen, setFollowUpsOpen] = useState(true);
  const [outstandingOpen, setOutstandingOpen] = useState(true);
  const [allRepliesOpen, setAllRepliesOpen] = useState(true);

  useEffect(() => {
    loadData();
    const handleWsChange = () => loadData();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, [filter]);

  const loadData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter === 'auto_responded') {
        params.auto_responded = 'true';
      } else if (filter === 'flagged') {
        params.flagged = 'true';
      } else if (filter === 'needs_response') {
        params.responded = 'false';
      } else if (filter !== 'all') {
        params.sentiment = filter;
      }

      const [repliesRes, statsRes, calRes, acctRes, fuRes, outstandingRes, flaggedRes, apStatsRes] = await Promise.all([
        getReplies(params),
        getReplyStats(),
        getCalendarStatus(),
        getGmailAccounts(),
        getFollowUps(),
        getReplies({ responded: 'false' }),
        getReplies({ flagged: 'true' }),
        getAutopilotStats().catch(() => ({ data: {} })),
      ]);

      setReplies(repliesRes.data.replies || []);
      setStats(statsRes.data || {});
      setCalendarStatus(calRes.data || {});
      setAccounts(acctRes.data || []);
      setFollowUps(fuRes.data || []);
      setOutstandingReplies(outstandingRes.data.replies || []);
      setFlaggedReplies(flaggedRes.data.replies || []);
      setAutopilotStats(apStatsRes.data || {});
    } catch (err) {
      console.error('Failed to load replies:', err);
    }
    setLoading(false);
  };

  const handleCheckNow = async () => {
    setChecking(true);
    setCheckResult(null);
    try {
      const res = await triggerReplyCheck();
      const data = res.data || {};
      const newCount = data.replies_found || 0;
      const autoResp = data.auto_responded || 0;
      const parts = [];
      if (newCount > 0) parts.push(`Found ${newCount} new repl${newCount === 1 ? 'y' : 'ies'}`);
      if (autoResp > 0) parts.push(`${autoResp} marked as responded (sent via Gmail)`);
      setCheckResult(parts.length > 0 ? parts.join('. ') + '!' : 'No new replies');
      if (newCount > 0 || autoResp > 0) loadData();
      setTimeout(() => setCheckResult(null), 4000);
    } catch (err) {
      console.error('Reply check failed:', err);
      setCheckResult('Check failed');
      setTimeout(() => setCheckResult(null), 4000);
    }
    setChecking(false);
  };

  // --- Reply actions ---

  const handleClassify = async (replyId) => {
    try {
      await classifyReply(replyId);
      loadData();
    } catch (err) {
      console.error('Classification failed:', err);
    }
  };

  const handleGenerateResponse = async (item, type) => {
    setSelectedReply(item);
    setGeneratedResponse(null);
    setGenerating(true);
    try {
      const res = await generateReplyResponse(item.reply.id, {
        type,
        account_id: selectedAccount || item.original_email?.gmail_account_id,
      });
      setGeneratedResponse(res.data);
    } catch (err) {
      console.error('Generation failed:', err);
      alert('Failed to generate response. Check that your Anthropic API key is configured.');
    }
    setGenerating(false);
  };

  const handleSendResponse = async () => {
    if (!selectedReply || !generatedResponse) return;
    setSending(true);
    try {
      await sendReplyResponse(selectedReply.reply.id, {
        subject: generatedResponse.subject,
        body: generatedResponse.body,
        account_id: selectedAccount || selectedReply.original_email?.gmail_account_id,
      });
      setSelectedReply(null);
      setGeneratedResponse(null);
      loadData();
    } catch (err) {
      console.error('Send failed:', err);
      alert('Failed to send response.');
    }
    setSending(false);
  };

  const toggleExpand = (id) => {
    setExpandedReplies((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // --- Follow-up actions ---

  const handleGenerateFollowUp = async (contactId, fu) => {
    setGeneratingFollowUp(contactId);
    try {
      const res = await generateFollowUp(contactId);
      setFollowUpDrafts((prev) => ({
        ...prev,
        [contactId]: {
          subject: res.data.subject,
          body: res.data.body,
          gmail_thread_id: res.data.gmail_thread_id,
          gmail_account_id: res.data.gmail_account_id,
          original_email_id: res.data.original_email_id,
        },
      }));
    } catch (err) {
      console.error('Follow-up generation failed:', err);
      alert('Failed to generate follow-up. Check your Anthropic API key.');
    }
    setGeneratingFollowUp(null);
  };

  const handleSendFollowUp = async (contactId, fu) => {
    const draft = followUpDrafts[contactId];
    if (!draft) return;
    setSendingFollowUp(contactId);
    try {
      await sendQuickEmail({
        to: fu.email,
        subject: draft.subject,
        body: draft.body,
        account_id: draft.gmail_account_id,
      });
      // Clear follow-up date after sending
      await updateContact(fu.id, { follow_up_date: null, follow_up_note: null });
      setFollowUpDrafts((prev) => {
        const copy = { ...prev };
        delete copy[contactId];
        return copy;
      });
      loadData();
    } catch (err) {
      console.error('Send follow-up failed:', err);
      alert('Failed to send follow-up email.');
    }
    setSendingFollowUp(null);
  };

  const handleClearFollowUp = async (contactId) => {
    try {
      await updateContact(contactId, { follow_up_date: null, follow_up_note: null });
      loadData();
    } catch {}
  };

  // --- Set follow-up from reply ---

  const handleDismiss = async (replyId) => {
    try {
      await dismissReply(replyId);
      await loadData();
    } catch (err) {
      alert('Failed to dismiss reply: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleSetFollowUp = async () => {
    if (!followUpForm) return;
    try {
      await setReplyFollowUp(followUpForm.replyId, {
        date: followUpForm.date,
        note: followUpForm.note,
      });
      setFollowUpForm(null);
      loadData();
    } catch (err) {
      console.error('Set follow-up failed:', err);
      alert('Failed to set follow-up.');
    }
  };

  // --- Stat cards ---

  const statCards = [
    { key: 'total', label: 'Total Replies', value: stats.total, color: '#E8603C' },
    { key: 'positive', label: 'Positive', value: stats.positive, color: '#10B981' },
    { key: 'negative', label: 'Negative', value: stats.negative, color: '#EF4444' },
    { key: 'neutral', label: 'Neutral', value: stats.neutral, color: '#6B7280' },
    { key: 'needs_response', label: 'Needs Response', value: stats.needs_response, color: '#F59E0B' },
    { key: 'follow_ups', label: 'Follow-Ups Due', value: stats.follow_ups_due, color: '#E8603C' },
  ];

  // --- Helper: format follow-up date ---

  const formatFollowUpDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diff = Math.floor((d - today) / (1000 * 60 * 60 * 24));
    if (diff < 0) return `${Math.abs(diff)}d overdue`;
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Tomorrow';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getDateColor = (fu) => {
    if (fu.is_overdue) return '#EF4444';
    if (fu.is_today) return '#F59E0B';
    return '#6B7280';
  };

  // --- Reply Card (shared between outstanding + all replies) ---

  const renderReplyCard = (item) => {
    const reply = item.reply;
    const email = item.original_email;
    const contact = item.contact;
    const sentiment = SENTIMENT_COLORS[reply.sentiment] || SENTIMENT_COLORS.neutral;
    const isExpanded = expandedReplies[reply.id];
    const isSelected = selectedReply?.reply?.id === reply.id;

    return (
      <div key={reply.id}>
        <div
          className="card"
          style={{
            border: isSelected ? '2px solid #E8603C' : '1px solid #E5E7EB',
            transition: 'border 0.2s',
          }}
        >
          {/* Header Row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <strong style={{ fontSize: '16px' }}>
                  {contact ? (
                    <Link to={`/contacts/${contact.id}`}>{contact.name || reply.from_email}</Link>
                  ) : (
                    reply.from_name || reply.from_email
                  )}
                </strong>
                {reply.sentiment && (
                  <span
                    style={{
                      padding: '2px 10px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor: sentiment.bg,
                      color: sentiment.text,
                    }}
                  >
                    {sentiment.label}
                  </span>
                )}
                {reply.auto_responded && (
                  <span
                    style={{
                      padding: '2px 10px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor: '#FEEAE3',
                      color: '#D4532F',
                    }}
                  >
                    Auto-Responded ({reply.auto_response_type || 'auto'})
                  </span>
                )}
                {reply.flagged_for_review && (
                  <span
                    style={{
                      padding: '2px 10px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor: '#FEF3C7',
                      color: '#92400E',
                    }}
                  >
                    Flagged: {reply.flag_reason || 'Review needed'}
                  </span>
                )}
                {reply.sentiment_subcategory && (
                  <span
                    style={{
                      padding: '2px 10px',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontWeight: 500,
                      backgroundColor: '#F3F4F6',
                      color: '#6B7280',
                    }}
                  >
                    {reply.sentiment_subcategory}
                  </span>
                )}
                {reply.response_sent_at && !reply.auto_responded && (
                  <span
                    style={{
                      padding: '2px 10px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor: '#DBEAFE',
                      color: '#1E40AF',
                    }}
                  >
                    ✓ Responded
                  </span>
                )}
              </div>
              <div className="text-sm text-light" style={{ marginTop: '2px' }}>
                {reply.from_email}
                {contact?.company && ` · ${contact.company}`}
              </div>
            </div>
            <div className="text-sm text-light" style={{ textAlign: 'right' }}>
              {reply.received_at && new Date(reply.received_at).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
              })}
            </div>
          </div>

          {/* Original Subject */}
          <div className="text-sm text-light" style={{ marginBottom: '6px' }}>
            Re: {email?.subject || 'Unknown'}
          </div>

          {/* Reply Content */}
          <div
            style={{
              padding: '10px 14px',
              backgroundColor: '#F9FAFB',
              borderRadius: '8px',
              marginBottom: '12px',
              cursor: 'pointer',
              fontSize: '14px',
              lineHeight: '1.5',
            }}
            onClick={() => toggleExpand(reply.id)}
          >
            {isExpanded ? (
              <div style={{ whiteSpace: 'pre-wrap' }}>{reply.body_text || reply.snippet}</div>
            ) : (
              <div>
                {(reply.body_text || reply.snippet || '').slice(0, 150)}
                {(reply.body_text || reply.snippet || '').length > 150 && '...'}
              </div>
            )}
          </div>

          {/* Sentiment reason */}
          {reply.sentiment_reason && (
            <div className="text-sm text-light" style={{ marginBottom: '10px', fontStyle: 'italic' }}>
              AI: {reply.sentiment_reason}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            {!reply.sentiment && (
              <button className="btn btn-secondary btn-sm" onClick={() => handleClassify(reply.id)}>
                Classify
              </button>
            )}

            {reply.sentiment === 'negative' && !reply.response_sent_at && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => handleGenerateResponse(item, 'rebuttal')}
                disabled={generating && isSelected}
              >
                {generating && isSelected ? 'Generating...' : 'Generate Rebuttal'}
              </button>
            )}

            {reply.sentiment === 'positive' && !reply.response_sent_at && (
              <button
                className="btn btn-primary btn-sm"
                style={{ backgroundColor: '#059669' }}
                onClick={() => handleGenerateResponse(item, 'meeting_followup')}
                disabled={generating && isSelected}
              >
                {generating && isSelected ? 'Generating...' : 'Schedule & Follow Up'}
              </button>
            )}

            {reply.sentiment === 'neutral' && !reply.response_sent_at && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleGenerateResponse(item, 'rebuttal')}
                disabled={generating && isSelected}
              >
                {generating && isSelected ? 'Generating...' : 'Generate Response'}
              </button>
            )}

            {/* Pass / Responded / Set Follow-Up buttons */}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
              {!reply.response_sent_at && (
                <>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleDismiss(reply.id)}
                    title="Mark as handled without responding"
                  >
                    Pass
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleDismiss(reply.id)}
                    title="I already replied to this in Gmail"
                    style={{ color: '#059669' }}
                  >
                    ✓ Replied in Gmail
                  </button>
                </>
              )}
              <button
                className="btn btn-secondary btn-sm"
                onClick={() =>
                  setFollowUpForm({
                    replyId: reply.id,
                    date: '',
                    note: '',
                  })
                }
              >
                Set Follow-Up
              </button>
            </div>

            {reply.response_sent_at && (
              <span className="text-sm text-light">
                Responded {new Date(reply.response_sent_at).toLocaleDateString()}
              </span>
            )}
          </div>

          {/* Inline follow-up form */}
          {followUpForm?.replyId === reply.id && (
            <div
              style={{
                marginTop: '12px',
                padding: '12px',
                backgroundColor: '#FFF5F1',
                borderRadius: '8px',
                display: 'flex',
                gap: '8px',
                alignItems: 'flex-end',
                flexWrap: 'wrap',
              }}
            >
              <div>
                <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                  Follow-up date
                </label>
                <input
                  type="date"
                  className="input"
                  value={followUpForm.date}
                  onChange={(e) => setFollowUpForm((f) => ({ ...f, date: e.target.value }))}
                  style={{ fontSize: '13px' }}
                />
              </div>
              <div style={{ flex: 1, minWidth: '150px' }}>
                <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                  Note (optional)
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. Check back on quote"
                  value={followUpForm.note}
                  onChange={(e) => setFollowUpForm((f) => ({ ...f, note: e.target.value }))}
                  style={{ fontSize: '13px' }}
                />
              </div>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleSetFollowUp}
                disabled={!followUpForm.date}
              >
                Save
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setFollowUpForm(null)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        {/* Response Panel is rendered outside ReplyCard */}
      </div>
    );
  };

  // --- Response Panel (rendered separately to avoid remounting on state change) ---
  const renderResponsePanel = (item) => {
    if (!item || !generatedResponse) return null;
    const isSelected = selectedReply?.reply?.id === item.reply.id;
    if (!isSelected) return null;

    return (
          <div
            style={{
              marginTop: '4px',
              border: '1px solid #FEEAE3',
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            {/* Panel header */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '10px 16px',
                backgroundColor: '#FFF5F1',
                borderBottom: '1px solid #FEEAE3',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600, color: '#D4532F' }}>
                  {generatedResponse.type === 'meeting_followup' ? 'Meeting Follow-Up' : 'Response Draft'}
                </span>
                {generatedResponse.type === 'meeting_followup' && !calendarStatus.has_calendar && (
                  <a
                    href={getGmailConnectUrl()}
                    style={{
                      fontSize: '12px',
                      color: '#92400E',
                      backgroundColor: '#FEF3C7',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      textDecoration: 'none',
                    }}
                  >
                    Connect calendar for real availability
                  </a>
                )}
              </div>
              <button
                onClick={() => { setSelectedReply(null); setGeneratedResponse(null); }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#6B7280',
                  cursor: 'pointer',
                  fontSize: '18px',
                  lineHeight: 1,
                  padding: '0 4px',
                }}
              >
                ×
              </button>
            </div>

            <div style={{ padding: '16px', backgroundColor: '#FAFBFF' }}>
              {/* Available slots */}
              {generatedResponse.available_slots?.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '12px' }}>
                  {generatedResponse.available_slots.map((slot, i) => (
                    <span
                      key={i}
                      style={{
                        padding: '3px 9px',
                        backgroundColor: '#FFF5F1',
                        borderRadius: '6px',
                        fontSize: '12px',
                        color: '#D4532F',
                        border: '1px solid #FEEAE3',
                      }}
                    >
                      {slot.display}
                    </span>
                  ))}
                </div>
              )}

              {/* Subject */}
              <input
                type="text"
                value={generatedResponse.subject || ''}
                onChange={(e) => setGeneratedResponse((prev) => ({ ...prev, subject: e.target.value }))}
                style={{
                  display: 'block',
                  width: '100%',
                  boxSizing: 'border-box',
                  marginBottom: '10px',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  fontWeight: 500,
                  color: '#374151',
                  border: '1px solid #D1D5DB',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  backgroundColor: '#fff',
                  outline: 'none',
                }}
                placeholder="Subject"
              />

              {/* Body */}
              <textarea
                rows={10}
                value={generatedResponse.body || ''}
                onChange={(e) => setGeneratedResponse((prev) => ({ ...prev, body: e.target.value }))}
                style={{
                  display: 'block',
                  width: '100%',
                  boxSizing: 'border-box',
                  resize: 'vertical',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  lineHeight: '1.6',
                  color: '#374151',
                  border: '1px solid #D1D5DB',
                  borderRadius: '8px',
                  padding: '12px 14px',
                  backgroundColor: '#fff',
                  marginBottom: '14px',
                  outline: 'none',
                }}
                placeholder="Email body"
              />

              {/* Footer: account + actions */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleSendResponse}
                    disabled={sending}
                    style={{ borderRadius: '8px', padding: '6px 16px' }}
                  >
                    {sending ? 'Sending...' : 'Send Reply'}
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleGenerateResponse(selectedReply, generatedResponse.type || 'rebuttal')}
                    disabled={generating}
                    style={{ borderRadius: '8px', padding: '6px 12px' }}
                  >
                    Regenerate
                  </button>
                </div>
                {accounts.length > 1 && (
                  <select
                    className="input"
                    value={selectedAccount}
                    onChange={(e) => setSelectedAccount(e.target.value)}
                    style={{ width: 'auto', fontSize: '12px', padding: '4px 8px', borderRadius: '6px', color: '#6B7280' }}
                  >
                    <option value="">Default account</option>
                    {accounts.map((acct) => (
                      <option key={acct.id} value={acct.id}>
                        {acct.email_address} {acct.is_default ? '(default)' : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </div>
          </div>
    );
  };

  // --- Filters for All Replies section ---

  const filters = [
    { key: 'all', label: 'All', count: stats.total },
    { key: 'positive', label: 'Positive', count: stats.positive },
    { key: 'negative', label: 'Negative', count: stats.negative },
    { key: 'neutral', label: 'Neutral', count: stats.neutral },
    { key: 'auto_responded', label: 'Auto-Responded', count: autopilotStats.total_auto_responded || 0 },
    { key: 'flagged', label: 'Flagged', count: autopilotStats.total_flagged || 0 },
  ];

  if (loading) {
    return (
      <div>
        <h1 className="mb-4">Reply Hub</h1>
        <div className="card" style={{ textAlign: 'center', padding: '40px' }}>Loading...</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h1 style={{ margin: 0 }}>Reply Hub</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {checkResult && (
            <span style={{ fontSize: '13px', color: checkResult.includes('Found') ? '#10B981' : '#6B7280' }}>
              {checkResult}
            </span>
          )}
          <button
            className="btn btn-secondary"
            onClick={handleCheckNow}
            disabled={checking}
            style={{ fontSize: '14px' }}
          >
            {checking ? 'Checking...' : 'Check Now'}
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-4 mb-4" style={{ gridTemplateColumns: 'repeat(6, 1fr)' }}>
        {statCards.map((s) => (
          <div key={s.key} className="card stat-card">
            <div className="stat-value" style={{ color: (s.value || 0) > 0 ? s.color : undefined }}>
              {s.value || 0}
            </div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {/* ===== SECTION 1: Follow-Up To-Dos ===== */}
      <div style={{ marginBottom: '24px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '12px',
            cursor: 'pointer',
          }}
          onClick={() => setFollowUpsOpen(!followUpsOpen)}
        >
          <span style={{ fontSize: '12px', color: '#6B7280' }}>{followUpsOpen ? '▼' : '▶'}</span>
          <h2 style={{ margin: 0, fontSize: '18px' }}>Follow-Up To-Dos</h2>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: '10px',
              fontSize: '12px',
              fontWeight: 600,
              backgroundColor: followUps.length > 0 ? '#FFF1EC' : '#F3F4F6',
              color: followUps.length > 0 ? '#D4532F' : '#6B7280',
            }}
          >
            {followUps.length}
          </span>
          <span className="text-sm text-light" style={{ marginLeft: '4px' }}>
            Prospects who haven't replied yet
          </span>
        </div>

        {followUpsOpen && (
          followUps.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <p className="text-light">No follow-ups scheduled. Set a follow-up date on any contact or reply to track them here.</p>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {followUps.map((fu) => {
                const draft = followUpDrafts[fu.id];
                const isGenerating = generatingFollowUp === fu.id;
                const isSending = sendingFollowUp === fu.id;

                return (
                  <div key={fu.id} className="card" style={{ border: fu.is_overdue ? '1px solid #FECACA' : fu.is_today ? '1px solid #FDE68A' : '1px solid #E5E7EB' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <Link to={`/contacts/${fu.id}`} style={{ fontWeight: 600, fontSize: '15px' }}>
                            {fu.name || fu.email}
                          </Link>
                          {fu.company && <span className="text-sm text-light">· {fu.company}</span>}
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '10px',
                              fontSize: '11px',
                              fontWeight: 600,
                              color: getDateColor(fu),
                              backgroundColor: fu.is_overdue ? '#FEE2E2' : fu.is_today ? '#FEF3C7' : '#F3F4F6',
                            }}
                          >
                            {formatFollowUpDate(fu.follow_up_date)}
                          </span>
                        </div>
                        <div className="text-sm text-light">{fu.email}</div>
                        {fu.follow_up_note && (
                          <div className="text-sm" style={{ marginTop: '4px', color: '#4B5563', fontStyle: 'italic' }}>
                            Note: {fu.follow_up_note}
                          </div>
                        )}
                        {fu.last_email && (
                          <div className="text-sm text-light" style={{ marginTop: '4px' }}>
                            Last email: "{fu.last_email.subject}" — {fu.last_email.created_at && new Date(fu.last_email.created_at).toLocaleDateString()}
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        {!draft && (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleGenerateFollowUp(fu.id, fu)}
                            disabled={isGenerating}
                          >
                            {isGenerating ? 'Generating...' : 'Generate Follow-Up'}
                          </button>
                        )}
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleClearFollowUp(fu.id)}
                          title="Clear follow-up"
                          style={{ padding: '4px 8px' }}
                        >
                          Clear
                        </button>
                      </div>
                    </div>

                    {/* Generated follow-up draft */}
                    {draft && (
                      <div
                        style={{
                          marginTop: '12px',
                          padding: '14px',
                          backgroundColor: '#FFF5F1',
                          borderRadius: '8px',
                        }}
                      >
                        <h4 style={{ marginBottom: '10px', color: '#D4532F', fontSize: '14px' }}>Follow-Up Draft</h4>
                        <div style={{ marginBottom: '8px' }}>
                          <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>Subject</label>
                          <input
                            type="text"
                            className="input"
                            value={draft.subject}
                            onChange={(e) =>
                              setFollowUpDrafts((prev) => ({
                                ...prev,
                                [fu.id]: { ...prev[fu.id], subject: e.target.value },
                              }))
                            }
                          />
                        </div>
                        <div style={{ marginBottom: '10px' }}>
                          <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>Body</label>
                          <textarea
                            className="input"
                            rows={5}
                            value={draft.body}
                            onChange={(e) =>
                              setFollowUpDrafts((prev) => ({
                                ...prev,
                                [fu.id]: { ...prev[fu.id], body: e.target.value },
                              }))
                            }
                            style={{ resize: 'vertical' }}
                          />
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleSendFollowUp(fu.id, fu)}
                            disabled={isSending}
                          >
                            {isSending ? 'Sending...' : 'Send Follow-Up'}
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleGenerateFollowUp(fu.id, fu)}
                            disabled={isGenerating}
                          >
                            Regenerate
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() =>
                              setFollowUpDrafts((prev) => {
                                const copy = { ...prev };
                                delete copy[fu.id];
                                return copy;
                              })
                            }
                          >
                            Discard
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )
        )}
      </div>

      {/* ===== SECTION: Flagged for Review ===== */}
      {flaggedReplies.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Flagged for Review</h2>
            <span
              style={{
                padding: '2px 8px',
                borderRadius: '10px',
                fontSize: '12px',
                fontWeight: 600,
                backgroundColor: '#FEF3C7',
                color: '#92400E',
              }}
            >
              {flaggedReplies.length}
            </span>
            <span className="text-sm text-light" style={{ marginLeft: '4px' }}>
              Autopilot flagged these for human review (contains sensitive keywords)
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {flaggedReplies.map((item) => (
              <div key={item.reply.id}>
                {renderReplyCard(item)}
                {renderResponsePanel(item)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Autopilot Stats */}
      {(autopilotStats.total_auto_responded > 0) && (
        <div className="card mb-4" style={{ background: '#FFF5F1', border: '1px solid #FEEAE3' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, color: '#D4532F', fontSize: '0.875rem' }}>Autopilot Summary:</span>
            <span style={{ fontSize: '0.875rem' }}>{autopilotStats.total_auto_responded || 0} auto-responded</span>
            <span style={{ fontSize: '0.875rem' }}>{autopilotStats.total_flagged || 0} flagged for review</span>
            {autopilotStats.by_type && Object.entries(autopilotStats.by_type).map(([type, count]) => (
              <span key={type} style={{ fontSize: '0.8rem', color: '#6B7280' }}>{type}: {count}</span>
            ))}
          </div>
        </div>
      )}

      {/* ===== SECTION 2: Outstanding Replies ===== */}
      <div style={{ marginBottom: '24px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '12px',
            cursor: 'pointer',
          }}
          onClick={() => setOutstandingOpen(!outstandingOpen)}
        >
          <span style={{ fontSize: '12px', color: '#6B7280' }}>{outstandingOpen ? '▼' : '▶'}</span>
          <h2 style={{ margin: 0, fontSize: '18px' }}>Outstanding Replies</h2>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: '10px',
              fontSize: '12px',
              fontWeight: 600,
              backgroundColor: outstandingReplies.length > 0 ? '#FEF3C7' : '#F3F4F6',
              color: outstandingReplies.length > 0 ? '#92400E' : '#6B7280',
            }}
          >
            {outstandingReplies.length}
          </span>
          <span className="text-sm text-light" style={{ marginLeft: '4px' }}>
            People who replied but you haven't responded yet
          </span>
        </div>

        {outstandingOpen && (
          outstandingReplies.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <p className="text-light">All caught up! No outstanding replies.</p>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {outstandingReplies.map((item) => (
                <div key={item.reply.id}>
                  {renderReplyCard(item)}
                  {renderResponsePanel(item)}
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* ===== SECTION 3: All Replies ===== */}
      <div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '12px',
            cursor: 'pointer',
          }}
          onClick={() => setAllRepliesOpen(!allRepliesOpen)}
        >
          <span style={{ fontSize: '12px', color: '#6B7280' }}>{allRepliesOpen ? '▼' : '▶'}</span>
          <h2 style={{ margin: 0, fontSize: '18px' }}>All Replies</h2>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: '10px',
              fontSize: '12px',
              fontWeight: 600,
              backgroundColor: '#F3F4F6',
              color: '#6B7280',
            }}
          >
            {stats.total || 0}
          </span>
        </div>

        {allRepliesOpen && (
          <>
            {/* Filter tabs */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              {filters.map((f) => (
                <button
                  key={f.key}
                  className={`btn btn-sm ${filter === f.key ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label} ({f.count || 0})
                </button>
              ))}
            </div>

            {replies.length === 0 ? (
              <div className="card">
                <div className="empty-state">
                  <p>No replies yet. Replies will appear here as they come in.</p>
                  <p className="text-sm text-light" style={{ marginTop: '8px' }}>
                    Replies are checked automatically every 5 minutes.
                  </p>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {replies.map((item) => (
                  <div key={item.reply.id}>
                    {renderReplyCard(item)}
                    {renderResponsePanel(item)}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default ReplyHub;
