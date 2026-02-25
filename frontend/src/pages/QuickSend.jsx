import { useState, useEffect, useMemo } from 'react';
import { generateQuickEmail, sendQuickEmail, getGmailAccounts, getQuickSendHistory, getTemplates } from '../api/client';
import AttachmentPicker from '../components/AttachmentPicker';
import RichTextEditor from '../components/RichTextEditor';

// Variables that are auto-filled (don't need manual input)
const AUTO_VARIABLES = new Set(['name', 'email', 'company', 'website_insights']);

function QuickSend() {
  const [recipient, setRecipient] = useState({
    name: '',
    email: '',
    company: '',
    website: '',
    notes: '',
  });
  const [context, setContext] = useState('');
  const [customFields, setCustomFields] = useState({});
  const [generatedEmail, setGeneratedEmail] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [sentFrom, setSentFrom] = useState('');
  const [error, setError] = useState('');
  const [gmailAccounts, setGmailAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [history, setHistory] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [attachments, setAttachments] = useState([]);

  const loadHistory = () => {
    getQuickSendHistory().then((res) => setHistory(res.data || [])).catch(() => {});
  };

  const loadAll = () => {
    getGmailAccounts().then((res) => {
      const accounts = res.data.accounts || [];
      setGmailAccounts(accounts);
      const defaultAccount = accounts.find(a => a.is_default);
      if (defaultAccount) {
        setSelectedAccountId(defaultAccount.id.toString());
      } else if (accounts.length > 0) {
        setSelectedAccountId(accounts[0].id.toString());
      }
    });
    getTemplates().then((res) => setTemplates(res.data || [])).catch(() => {});
    loadHistory();
  };

  useEffect(() => {
    loadAll();
    const handleWsChange = () => { loadHistory(); getTemplates().then((res) => setTemplates(res.data || [])).catch(() => {}); };
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const selectedTemplate = templates.find(t => t.id === parseInt(selectedTemplateId));

  // Extract variables from template that need manual input
  const templateCustomVars = useMemo(() => {
    if (!selectedTemplate) return [];

    // Parse variables from subject + body using regex (catches ones not in the variables array too)
    const allText = (selectedTemplate.subject || '') + ' ' + (selectedTemplate.body || '');
    const matches = allText.match(/\{\{\s*(\w+)\s*\}\}/g) || [];
    const varNames = [...new Set(matches.map(m => m.replace(/[{}]/g, '').trim()))];

    // Filter out auto-filled ones
    return varNames.filter(v => !AUTO_VARIABLES.has(v));
  }, [selectedTemplate]);

  // Reset custom fields when template changes
  useEffect(() => {
    const newFields = {};
    templateCustomVars.forEach(v => {
      newFields[v] = customFields[v] || '';
    });
    setCustomFields(newFields);
  }, [selectedTemplateId, templateCustomVars.join(',')]);

  const handleGenerate = async () => {
    if (!recipient.email) {
      setError('Email address is required');
      return;
    }
    setError('');
    setGenerating(true);
    setSent(false);

    try {
      const payload = {
        recipient,
        context,
      };
      if (selectedTemplateId) {
        payload.template_id = parseInt(selectedTemplateId);
        // Send custom field values for template variable substitution
        if (Object.keys(customFields).length > 0) {
          payload.custom_fields = customFields;
        }
      }
      const res = await generateQuickEmail(payload);
      setGeneratedEmail(res.data);
      // Show website status info if relevant
      if (res.data.website_status && res.data.website_status !== 'success' && hasWebsiteInsights) {
        const msgs = {
          no_url: 'Could not determine a website URL from the email address. Website insights were AI-generated based on available context instead.',
          fetch_failed: "Could not fetch the recipient's website. Website insights were AI-generated based on available context instead.",
          error: 'Website analysis encountered an error. Website insights were AI-generated instead.',
        };
        setError(msgs[res.data.website_status] || '');
      }
    } catch (err) {
      setError('Failed to generate email: ' + (err.response?.data?.error || err.message));
    }
    setGenerating(false);
  };

  const handleSend = async () => {
    if (!generatedEmail) return;
    setSending(true);
    setError('');

    try {
      const res = await sendQuickEmail({
        to: recipient.email,
        subject: generatedEmail.subject,
        body: generatedEmail.body,
        account_id: selectedAccountId ? parseInt(selectedAccountId) : undefined,
        recipient_name: recipient.name,
        recipient_company: recipient.company,
        recipient_website: recipient.website,
        attachments: attachments.length > 0 ? attachments : undefined,
      });
      setSent(true);
      setSentFrom(res.data.sent_from || '');
      setRecipient({ name: '', email: '', company: '', website: '', notes: '' });
      setContext('');
      setCustomFields({});
      setGeneratedEmail(null);
      setSelectedTemplateId('');
      setAttachments([]);
      loadHistory();
    } catch (err) {
      setError('Failed to send email: ' + (err.response?.data?.error || err.message));
    }
    setSending(false);
  };

  const handleRegenerate = () => {
    handleGenerate();
  };

  const formatVarLabel = (varName) => {
    return varName
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };

  const hasWebsiteInsights = selectedTemplate &&
    ((selectedTemplate.subject || '') + ' ' + (selectedTemplate.body || '')).includes('{{website_insights}}');

  return (
    <div>
      <h1 className="mb-4">Quick Send</h1>
      <p className="text-light mb-4">Generate and send a personalized one-off email</p>

      {error && (
        <div className="card mb-4" style={{ background: '#FEE2E2', color: '#991B1B' }}>
          {error}
        </div>
      )}

      {sent && (
        <div className="card mb-4" style={{ background: '#D1FAE5', color: '#065F46' }}>
          Email sent successfully{sentFrom ? ` from ${sentFrom}` : ''}!
        </div>
      )}

      <div className="grid grid-2">
        {/* Left: Recipient Info */}
        <div className="card">
          <h3 className="card-title mb-2">Recipient</h3>

          <div className="form-group">
            <label className="form-label">Email *</label>
            <input
              type="email"
              className="form-input"
              value={recipient.email}
              onChange={(e) => setRecipient({ ...recipient, email: e.target.value })}
              placeholder="founder@company.com"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              type="text"
              className="form-input"
              value={recipient.name}
              onChange={(e) => setRecipient({ ...recipient, name: e.target.value })}
              placeholder="John Smith"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Company</label>
            <input
              type="text"
              className="form-input"
              value={recipient.company}
              onChange={(e) => setRecipient({ ...recipient, company: e.target.value })}
              placeholder="Acme Corp"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Website</label>
            <input
              type="text"
              className="form-input"
              value={recipient.website}
              onChange={(e) => setRecipient({ ...recipient, website: e.target.value })}
              placeholder="acmecorp.com"
            />
            <span className="text-sm text-light" style={{ marginTop: '0.25rem', display: 'block' }}>
              {"Used to analyze their site for {{website_insights}}. Falls back to email domain if empty."}
            </span>
          </div>

          <div className="form-group">
            <label className="form-label">Research Notes</label>
            <textarea
              className="form-textarea"
              value={recipient.notes}
              onChange={(e) => setRecipient({ ...recipient, notes: e.target.value })}
              placeholder="Recent funding, product launches, mutual connections, anything relevant..."
              style={{ minHeight: '100px' }}
            />
          </div>

          {/* Template Selector */}
          <div className="form-group">
            <label className="form-label">Template</label>
            <select
              className="form-input"
              value={selectedTemplateId}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
            >
              <option value="">No template (freeform AI)</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            {selectedTemplate && (
              <div
                style={{
                  marginTop: '0.5rem',
                  padding: '0.75rem',
                  background: '#F0F9FF',
                  borderRadius: '0.375rem',
                  border: '1px solid #BAE6FD',
                  fontSize: '0.8rem'
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '0.25rem', color: '#0369A1' }}>
                  Subject: {selectedTemplate.subject}
                </div>
                <div
                  style={{ color: '#475569', maxHeight: '80px', overflow: 'hidden' }}
                  dangerouslySetInnerHTML={{ __html: selectedTemplate.body }}
                />
                {hasWebsiteInsights && (
                  <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#0369A1' }}>
                    Website insights will be auto-generated from the recipient's email domain
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Dynamic custom field inputs for template variables */}
          {templateCustomVars.length > 0 && (
            <div
              style={{
                padding: '0.75rem',
                background: '#FFFBEB',
                borderRadius: '0.375rem',
                border: '1px solid #FDE68A',
                marginBottom: '1rem'
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem', color: '#92400E' }}>
                Template Variables
              </div>
              {templateCustomVars.map((varName) => (
                <div className="form-group" key={varName} style={{ marginBottom: '0.5rem' }}>
                  <label className="form-label" style={{ fontSize: '0.8rem' }}>
                    {formatVarLabel(varName)} <code style={{ fontSize: '0.7rem', color: '#92400E' }}>{`{{${varName}}}`}</code>
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    value={customFields[varName] || ''}
                    onChange={(e) => setCustomFields(prev => ({ ...prev, [varName]: e.target.value }))}
                    placeholder={`Enter ${formatVarLabel(varName).toLowerCase()}...`}
                  />
                </div>
              ))}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">
              {selectedTemplateId ? 'Additional Context / Instructions' : 'Context / Purpose'}
            </label>
            <textarea
              className="form-textarea"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder={
                selectedTemplateId
                  ? 'Any extra instructions for personalizing this template, e.g., mention their recent Series A...'
                  : "What's the purpose of this email? e.g., Interested in acquiring their business, partnership opportunity, etc."
              }
              style={{ minHeight: '80px' }}
            />
          </div>

          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating || !recipient.email}
            style={{ width: '100%' }}
          >
            {generating
              ? 'Generating...'
              : selectedTemplateId
                ? 'Generate from Template'
                : 'Generate Email'
            }
          </button>
        </div>

        {/* Right: Generated Email */}
        <div className="card">
          <h3 className="card-title mb-2">Generated Email</h3>

          {!generatedEmail ? (
            <div className="empty-state">
              <div className="empty-state-icon">✉️</div>
              <p>
                {selectedTemplateId
                  ? 'Fill in recipient details and click Generate from Template'
                  : 'Fill in recipient details and click Generate'
                }
              </p>
            </div>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">Subject</label>
                <input
                  type="text"
                  className="form-input"
                  value={generatedEmail.subject}
                  onChange={(e) => setGeneratedEmail({ ...generatedEmail, subject: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Body</label>
                <RichTextEditor
                  value={generatedEmail.body}
                  onChange={(html) => setGeneratedEmail({ ...generatedEmail, body: html })}
                  minHeight="250px"
                />
              </div>

              <div className="form-group">
                <AttachmentPicker attachments={attachments} onChange={setAttachments} />
              </div>

              {gmailAccounts.length > 1 && (
                <div className="form-group">
                  <label className="form-label">Send From</label>
                  <select
                    className="form-input"
                    value={selectedAccountId}
                    onChange={(e) => setSelectedAccountId(e.target.value)}
                  >
                    {gmailAccounts.map((account) => (
                      <option key={account.id} value={String(account.id)}>
                        {account.email_address} {account.is_default ? '(Default)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex gap-2">
                <button
                  className="btn btn-success"
                  onClick={handleSend}
                  disabled={sending || gmailAccounts.length === 0}
                  style={{ flex: 1 }}
                >
                  {sending ? 'Sending...' : 'Send Email'}
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={handleRegenerate}
                  disabled={generating}
                >
                  Regenerate
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Recent Emails History */}
      {history.length > 0 && (
        <div className="card mt-4">
          <h3 className="card-title mb-2">Recent Emails</h3>
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>To</th>
                  <th>Subject</th>
                  <th>Sent</th>
                  <th>Opened</th>
                  <th>Clicked</th>
                  <th>Replied</th>
                </tr>
              </thead>
              <tbody>
                {history.map((log) => (
                  <tr key={log.id}>
                    <td>{log.recipient_email}</td>
                    <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {log.subject}
                    </td>
                    <td style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                      {log.created_at ? new Date(log.created_at).toLocaleDateString() : '-'}
                    </td>
                    <td>
                      {log.opened_at ? (
                        <span title={new Date(log.opened_at).toLocaleString()} style={{ color: '#3B82F6', fontWeight: 500 }}>
                          ✓ ({log.open_count})
                        </span>
                      ) : (
                        <span style={{ color: '#9CA3AF' }}>-</span>
                      )}
                    </td>
                    <td>
                      {log.clicked_at ? (
                        <span title={new Date(log.clicked_at).toLocaleString()} style={{ color: '#E8603C', fontWeight: 500 }}>
                          ✓ ({log.click_count})
                        </span>
                      ) : (
                        <span style={{ color: '#9CA3AF' }}>-</span>
                      )}
                    </td>
                    <td>
                      {log.replied_at ? (
                        <span title={new Date(log.replied_at).toLocaleString()} style={{ color: '#10B981', fontWeight: 500 }}>
                          ✓
                        </span>
                      ) : (
                        <span style={{ color: '#9CA3AF' }}>-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default QuickSend;
