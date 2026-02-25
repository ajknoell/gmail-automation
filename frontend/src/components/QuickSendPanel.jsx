import { useState, useEffect, useMemo } from 'react';
import { generateQuickEmail, sendQuickEmail, getGmailAccounts, getTemplates } from '../api/client';
import { useToast } from './Toast';

const AUTO_VARIABLES = new Set(['name', 'email', 'company', 'website_insights']);

function QuickSendPanel({ open, onClose, prefill }) {
  const showToast = useToast();
  const [recipient, setRecipient] = useState({ name: '', email: '', company: '', website: '', notes: '' });
  const [context, setContext] = useState('');
  const [customFields, setCustomFields] = useState({});
  const [generatedEmail, setGeneratedEmail] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [gmailAccounts, setGmailAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');

  useEffect(() => {
    if (!open) return;
    getGmailAccounts().then(res => {
      const accounts = res.data.accounts || [];
      setGmailAccounts(accounts);
      const def = accounts.find(a => a.is_default);
      if (def) setSelectedAccountId(def.id.toString());
      else if (accounts.length > 0) setSelectedAccountId(accounts[0].id.toString());
    }).catch(() => {});
    getTemplates().then(res => setTemplates(res.data || [])).catch(() => {});
  }, [open]);

  useEffect(() => {
    if (prefill && open) {
      setRecipient(prev => ({
        ...prev,
        name: prefill.name || prev.name,
        email: prefill.email || prev.email,
        company: prefill.company || prev.company,
        website: prefill.website || prev.website,
      }));
    }
  }, [prefill, open]);

  const selectedTemplate = templates.find(t => t.id === parseInt(selectedTemplateId));

  const templateCustomVars = useMemo(() => {
    if (!selectedTemplate) return [];
    const allText = (selectedTemplate.subject || '') + ' ' + (selectedTemplate.body || '');
    const matches = allText.match(/\{\{\s*(\w+)\s*\}\}/g) || [];
    const varNames = [...new Set(matches.map(m => m.replace(/[{}]/g, '').trim()))];
    return varNames.filter(v => !AUTO_VARIABLES.has(v));
  }, [selectedTemplate]);

  useEffect(() => {
    const newFields = {};
    templateCustomVars.forEach(v => { newFields[v] = customFields[v] || ''; });
    setCustomFields(newFields);
  }, [selectedTemplateId, templateCustomVars.join(',')]);

  const handleGenerate = async () => {
    if (!recipient.email) { showToast('Email address is required', 'error'); return; }
    setGenerating(true);
    try {
      const payload = { recipient, context };
      if (selectedTemplateId) {
        payload.template_id = parseInt(selectedTemplateId);
        if (Object.keys(customFields).length > 0) payload.custom_fields = customFields;
      }
      const res = await generateQuickEmail(payload);
      setGeneratedEmail(res.data);
    } catch (err) {
      showToast('Failed to generate: ' + (err.response?.data?.error || err.message), 'error');
    }
    setGenerating(false);
  };

  const handleSend = async () => {
    if (!generatedEmail) return;
    setSending(true);
    try {
      const res = await sendQuickEmail({
        to: recipient.email,
        subject: generatedEmail.subject,
        body: generatedEmail.body,
        account_id: selectedAccountId ? parseInt(selectedAccountId) : undefined,
        recipient_name: recipient.name,
        recipient_company: recipient.company,
        recipient_website: recipient.website,
      });
      showToast(`Email sent${res.data.sent_from ? ` from ${res.data.sent_from}` : ''}!`, 'success');
      resetForm();
      onClose();
    } catch (err) {
      showToast('Failed to send: ' + (err.response?.data?.error || err.message), 'error');
    }
    setSending(false);
  };

  const resetForm = () => {
    setRecipient({ name: '', email: '', company: '', website: '', notes: '' });
    setContext('');
    setCustomFields({});
    setGeneratedEmail(null);
    setSelectedTemplateId('');
  };

  const formatVarLabel = (v) => v.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <>
      <div className={`slide-panel-overlay ${open ? 'open' : ''}`} onClick={onClose} />
      <div className={`slide-panel ${open ? 'open' : ''}`}>
        <div className="slide-panel-header">
          <span className="slide-panel-title">Quick Send</span>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="slide-panel-body">
          {!generatedEmail ? (
            <>
              <div className="form-group">
                <label className="form-label">Email *</label>
                <input type="email" className="form-input" value={recipient.email}
                  onChange={e => setRecipient({ ...recipient, email: e.target.value })}
                  placeholder="founder@company.com" />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="form-group">
                  <label className="form-label">Name</label>
                  <input type="text" className="form-input" value={recipient.name}
                    onChange={e => setRecipient({ ...recipient, name: e.target.value })}
                    placeholder="John Smith" />
                </div>
                <div className="form-group">
                  <label className="form-label">Company</label>
                  <input type="text" className="form-input" value={recipient.company}
                    onChange={e => setRecipient({ ...recipient, company: e.target.value })}
                    placeholder="Acme Corp" />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Website</label>
                <input type="text" className="form-input" value={recipient.website}
                  onChange={e => setRecipient({ ...recipient, website: e.target.value })}
                  placeholder="acmecorp.com" />
              </div>

              <div className="form-group">
                <label className="form-label">Template</label>
                <select className="form-input" value={selectedTemplateId}
                  onChange={e => setSelectedTemplateId(e.target.value)}>
                  <option value="">Freeform AI</option>
                  {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>

              {templateCustomVars.length > 0 && templateCustomVars.map(v => (
                <div className="form-group" key={v}>
                  <label className="form-label" style={{ fontSize: '0.8125rem' }}>{formatVarLabel(v)}</label>
                  <input type="text" className="form-input" value={customFields[v] || ''}
                    onChange={e => setCustomFields(prev => ({ ...prev, [v]: e.target.value }))}
                    placeholder={`Enter ${formatVarLabel(v).toLowerCase()}`} />
                </div>
              ))}

              <div className="form-group">
                <label className="form-label">Notes / Context</label>
                <textarea className="form-textarea" value={context || recipient.notes}
                  onChange={e => { setContext(e.target.value); setRecipient({ ...recipient, notes: e.target.value }); }}
                  placeholder="Any context for personalization..."
                  style={{ minHeight: '80px' }} />
              </div>

              <button className="btn btn-primary" onClick={handleGenerate}
                disabled={generating || !recipient.email} style={{ width: '100%' }}>
                {generating ? 'Generating...' : 'Generate Email'}
              </button>
            </>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">Subject</label>
                <input type="text" className="form-input" value={generatedEmail.subject}
                  onChange={e => setGeneratedEmail({ ...generatedEmail, subject: e.target.value })} />
              </div>

              <div className="form-group">
                <label className="form-label">Body</label>
                <textarea className="form-textarea" value={generatedEmail.body.replace(/<[^>]+>/g, '')}
                  onChange={e => setGeneratedEmail({ ...generatedEmail, body: e.target.value })}
                  style={{ minHeight: '200px' }} />
              </div>

              {gmailAccounts.length > 1 && (
                <div className="form-group">
                  <label className="form-label">Send From</label>
                  <select className="form-input" value={selectedAccountId}
                    onChange={e => setSelectedAccountId(e.target.value)}>
                    {gmailAccounts.map(a => (
                      <option key={a.id} value={String(a.id)}>
                        {a.email_address} {a.is_default ? '(Default)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}
        </div>

        {generatedEmail && (
          <div className="slide-panel-footer">
            <div className="flex gap-1">
              <button className="btn btn-success" onClick={handleSend}
                disabled={sending || gmailAccounts.length === 0} style={{ flex: 1 }}>
                {sending ? 'Sending...' : 'Send'}
              </button>
              <button className="btn btn-secondary" onClick={handleGenerate} disabled={generating}>
                Redo
              </button>
              <button className="btn btn-secondary" onClick={() => setGeneratedEmail(null)}>
                Edit Info
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default QuickSendPanel;
