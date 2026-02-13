import { useState, useEffect, useRef } from 'react';
import { getTemplates, createTemplate, updateTemplate, deleteTemplate, generateTemplate, refineTemplate } from '../api/client';
import RichTextEditor from '../components/RichTextEditor';

function Templates() {
  const [templates, setTemplates] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [showAiModal, setShowAiModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', subject: '', body: '' });
  const [aiForm, setAiForm] = useState({
    purpose: '',
    target_audience: '',
    tone: 'professional but casual',
    key_points: '',
    call_to_action: '',
    length: 'short'
  });
  const [generating, setGenerating] = useState(false);
  const [aiError, setAiError] = useState('');

  // Refinement state
  const [aiPreview, setAiPreview] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [refining, setRefining] = useState(false);
  const [refinementCount, setRefinementCount] = useState(0);

  // Enhance state (for manual create/edit modal)
  const [enhancePrompt, setEnhancePrompt] = useState('');
  const [enhancing, setEnhancing] = useState(false);
  const [showEnhance, setShowEnhance] = useState(false);

  useEffect(() => {
    loadTemplates();
    const handleWsChange = () => loadTemplates();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const loadTemplates = () => {
    getTemplates().then((res) => setTemplates(res.data));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await updateTemplate(editing.id, form);
      } else {
        await createTemplate(form);
      }
      setShowModal(false);
      setEditing(null);
      setForm({ name: '', subject: '', body: '' });
      loadTemplates();
    } catch (error) {
      alert('Failed to save template');
    }
  };

  const handleEdit = (template) => {
    setEditing(template);
    setForm({ name: template.name, subject: template.subject, body: template.body });
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this template?')) return;
    try {
      await deleteTemplate(id);
      loadTemplates();
    } catch (error) {
      alert('Failed to delete template');
    }
  };

  const openNewModal = () => {
    setEditing(null);
    setForm({ name: '', subject: '', body: '' });
    setShowModal(true);
  };

  const openAiModal = () => {
    setAiForm({
      purpose: '',
      target_audience: '',
      tone: 'professional but casual',
      key_points: '',
      call_to_action: '',
      length: 'short'
    });
    setAiError('');
    setAiPreview(null);
    setFeedback('');
    setRefinementCount(0);
    setShowAiModal(true);
  };

  const handleAiGenerate = async (e) => {
    e.preventDefault();
    if (!aiForm.purpose.trim()) {
      setAiError('Please describe the purpose of this template');
      return;
    }

    setGenerating(true);
    setAiError('');

    try {
      const res = await generateTemplate(aiForm);
      setAiPreview({
        name: res.data.name || 'Generated Template',
        subject: res.data.subject || '',
        body: res.data.body || ''
      });
      setRefinementCount(0);
    } catch (error) {
      setAiError(error.response?.data?.error || 'Failed to generate template. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleRefine = async () => {
    if (!feedback.trim()) return;

    setRefining(true);
    setAiError('');

    try {
      const res = await refineTemplate({
        name: aiPreview.name,
        subject: aiPreview.subject,
        body: aiPreview.body,
        feedback: feedback,
        purpose: aiForm.purpose
      });
      setAiPreview({
        name: res.data.name || aiPreview.name,
        subject: res.data.subject || aiPreview.subject,
        body: res.data.body || aiPreview.body
      });
      setFeedback('');
      setRefinementCount((c) => c + 1);
    } catch (error) {
      setAiError(error.response?.data?.error || 'Failed to refine template. Please try again.');
    } finally {
      setRefining(false);
    }
  };

  const handleUseTemplate = async () => {
    if (!aiPreview) return;
    try {
      await createTemplate({
        name: aiPreview.name,
        subject: aiPreview.subject,
        body: aiPreview.body
      });
      setShowAiModal(false);
      setAiPreview(null);
      loadTemplates();
    } catch (error) {
      setAiError('Failed to save template');
    }
  };

  const handleEditBeforeSave = () => {
    setShowAiModal(false);
    setEditing(null);
    setForm({
      name: aiPreview.name,
      subject: aiPreview.subject,
      body: aiPreview.body
    });
    setAiPreview(null);
    setShowModal(true);
  };

  const handleEnhance = async () => {
    if (!form.subject && !form.body) return;

    setEnhancing(true);
    try {
      const res = await refineTemplate({
        name: form.name || 'Template',
        subject: form.subject,
        body: form.body,
        feedback: enhancePrompt || 'Improve this template — make it more compelling, natural, and effective. Keep the same intent and variables.',
      });
      setForm({
        name: res.data.name || form.name,
        subject: res.data.subject || form.subject,
        body: res.data.body || form.body
      });
      setEnhancePrompt('');
      setShowEnhance(false);
    } catch (error) {
      alert('Failed to enhance template: ' + (error.response?.data?.error || error.message));
    } finally {
      setEnhancing(false);
    }
  };

  const isBusy = generating || refining;

  // Track mousedown target to prevent closing modal on drag-release
  const mouseDownTarget = useRef(null);
  const handleOverlayMouseDown = (e) => { mouseDownTarget.current = e.target; };
  const handleOverlayClick = (e, closeFn) => {
    if (e.target === e.currentTarget && mouseDownTarget.current === e.currentTarget) {
      closeFn();
    }
    mouseDownTarget.current = null;
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1>Email Templates</h1>
        <div className="flex gap-2">
          <button className="btn btn-secondary" onClick={openAiModal}>
            ✨ AI Generate
          </button>
          <button className="btn btn-primary" onClick={openNewModal}>
            + New Template
          </button>
        </div>
      </div>

      {templates.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📝</div>
            <p>No templates yet. Create your first template!</p>
            <div className="flex gap-2 justify-center mt-2">
              <button className="btn btn-secondary" onClick={openAiModal}>
                ✨ Generate with AI
              </button>
              <button className="btn btn-primary" onClick={openNewModal}>
                Create Manually
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-2">
          {templates.map((template) => (
            <div key={template.id} className="card">
              <div className="card-header">
                <h3 className="card-title">{template.name}</h3>
                <div className="flex gap-1">
                  <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(template)}>
                    Edit
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(template.id)}>
                    Delete
                  </button>
                </div>
              </div>
              <p className="text-sm mb-2"><strong>Subject:</strong> {template.subject}</p>
              <div
                className="text-sm text-light"
                style={{ maxHeight: '100px', overflow: 'hidden', lineHeight: '1.5' }}
                dangerouslySetInnerHTML={{ __html: template.body }}
              />
              {template.variables && template.variables.length > 0 && (
                <div className="mt-2">
                  <span className="text-sm text-light">Variables: </span>
                  {template.variables.map((v) => (
                    <span key={v} className="badge badge-draft" style={{ marginRight: '0.25rem' }}>
                      {`{{${v}}}`}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* AI Generation Modal */}
      {showAiModal && (
        <div className="modal-overlay" onMouseDown={handleOverlayMouseDown} onClick={(e) => !isBusy && handleOverlayClick(e, () => setShowAiModal(false))}>
          <div className="modal" style={{ maxWidth: aiPreview ? '700px' : '550px' }}>
            <div className="modal-header">
              <h3 className="modal-title">✨ {aiPreview ? 'Review & Refine Template' : 'Generate Template with AI'}</h3>
              <button className="modal-close" onClick={() => !isBusy && setShowAiModal(false)} disabled={isBusy}>×</button>
            </div>

            {!aiPreview ? (
              /* === STEP 1: Generation Form === */
              <form onSubmit={handleAiGenerate} style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1, minHeight: 0 }}>
                <div className="modal-body">
                  {aiError && (
                    <div className="alert alert-error mb-3">{aiError}</div>
                  )}

                  <div className="form-group">
                    <label className="form-label">What's the purpose of this email? *</label>
                    <textarea
                      className="form-textarea"
                      value={aiForm.purpose}
                      onChange={(e) => setAiForm({ ...aiForm, purpose: e.target.value })}
                      placeholder="e.g., Introduce our SaaS product to startup founders, pitch consulting services to small business owners, follow up after a conference..."
                      required
                      style={{ minHeight: '80px' }}
                      disabled={generating}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Target audience</label>
                    <input
                      type="text"
                      className="form-input"
                      value={aiForm.target_audience}
                      onChange={(e) => setAiForm({ ...aiForm, target_audience: e.target.value })}
                      placeholder="e.g., Startup founders, Marketing managers, CTOs at mid-size companies"
                      disabled={generating}
                    />
                  </div>

                  <div className="grid grid-2 gap-3">
                    <div className="form-group">
                      <label className="form-label">Tone</label>
                      <select
                        className="form-select"
                        value={aiForm.tone}
                        onChange={(e) => setAiForm({ ...aiForm, tone: e.target.value })}
                        disabled={generating}
                      >
                        <option value="professional but casual">Professional but casual</option>
                        <option value="very casual and friendly">Very casual and friendly</option>
                        <option value="formal and professional">Formal and professional</option>
                        <option value="direct and to the point">Direct and to the point</option>
                        <option value="warm and personal">Warm and personal</option>
                        <option value="witty and clever">Witty and clever</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Length</label>
                      <select
                        className="form-select"
                        value={aiForm.length}
                        onChange={(e) => setAiForm({ ...aiForm, length: e.target.value })}
                        disabled={generating}
                      >
                        <option value="short">Short (2-3 sentences)</option>
                        <option value="medium">Medium (4-5 sentences)</option>
                        <option value="long">Long (6+ sentences)</option>
                      </select>
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Key points to include</label>
                    <input
                      type="text"
                      className="form-input"
                      value={aiForm.key_points}
                      onChange={(e) => setAiForm({ ...aiForm, key_points: e.target.value })}
                      placeholder="e.g., Save 10 hours/week, free trial available, trusted by 500+ companies"
                      disabled={generating}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Call to action</label>
                    <input
                      type="text"
                      className="form-input"
                      value={aiForm.call_to_action}
                      onChange={(e) => setAiForm({ ...aiForm, call_to_action: e.target.value })}
                      placeholder="e.g., Book a 15-min call, reply to this email, try our free demo"
                      disabled={generating}
                    />
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowAiModal(false)} disabled={generating}>
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={generating}>
                    {generating ? '✨ Generating...' : '✨ Generate Template'}
                  </button>
                </div>
              </form>
            ) : (
              /* === STEP 2: Preview + Refine === */
              <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1, minHeight: 0 }}>
                <div className="modal-body">
                  {aiError && (
                    <div className="alert alert-error mb-3">{aiError}</div>
                  )}

                  {/* Template Preview */}
                  <div style={{
                    background: '#F9FAFB',
                    border: '1px solid var(--border)',
                    borderRadius: '0.5rem',
                    padding: '1.25rem',
                    marginBottom: '1rem'
                  }}>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <span className="text-sm text-light" style={{ fontWeight: 600 }}>Template Name</span>
                      <p style={{ margin: '0.25rem 0 0', fontWeight: 500 }}>{aiPreview.name}</p>
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <span className="text-sm text-light" style={{ fontWeight: 600 }}>Subject</span>
                      <p style={{ margin: '0.25rem 0 0', fontWeight: 500 }}>{aiPreview.subject}</p>
                    </div>
                    <div>
                      <span className="text-sm text-light" style={{ fontWeight: 600 }}>Body</span>
                      <div style={{ margin: '0.25rem 0 0', lineHeight: '1.6' }} dangerouslySetInnerHTML={{ __html: aiPreview.body }} />
                    </div>
                  </div>

                  {refinementCount > 0 && (
                    <p className="text-sm text-light" style={{ marginBottom: '0.5rem' }}>
                      Refined {refinementCount} {refinementCount === 1 ? 'time' : 'times'}
                    </p>
                  )}

                  {/* Feedback Input */}
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">What should change?</label>
                    <textarea
                      className="form-textarea"
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      placeholder='e.g., Make it shorter, add {{website_insights}} variable, softer CTA, more direct tone...'
                      style={{ minHeight: '60px' }}
                      disabled={refining}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey && feedback.trim()) {
                          e.preventDefault();
                          handleRefine();
                        }
                      }}
                    />
                    <button
                      className="btn btn-secondary mt-2"
                      onClick={handleRefine}
                      disabled={refining || !feedback.trim()}
                      style={{ width: '100%' }}
                    >
                      {refining ? '🔄 Refining...' : '🔄 Refine Template'}
                    </button>
                  </div>
                </div>

                <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setAiPreview(null)}
                    disabled={isBusy}
                  >
                    ← Start Over
                  </button>
                  <div className="flex gap-2">
                    <button
                      className="btn btn-secondary"
                      onClick={handleEditBeforeSave}
                      disabled={isBusy}
                    >
                      Edit Manually
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={handleUseTemplate}
                      disabled={isBusy}
                    >
                      ✓ Save Template
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onMouseDown={handleOverlayMouseDown} onClick={(e) => handleOverlayClick(e, () => setShowModal(false))}>
          <div className="modal" style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h3 className="modal-title">{editing ? 'Edit Template' : 'New Template'}</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', flex: 1, minHeight: 0 }}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Template Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g., Cold Outreach"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email Subject</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.subject}
                    onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    placeholder="e.g., Quick question about {{company}}"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email Body</label>
                  <RichTextEditor
                    value={form.body}
                    onChange={(html) => setForm({ ...form, body: html })}
                    placeholder="Hi {{name}}, I noticed that {{company}} is doing great work in..."
                    minHeight="200px"
                  />
                </div>
                <p className="text-sm text-light mb-3">
                  Use {'{{variable}}'} syntax for personalization. Common variables: name, company, email, website_insights
                </p>

                {/* Enhance with AI */}
                {!showEnhance ? (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setShowEnhance(true)}
                    disabled={enhancing || (!form.subject && !form.body)}
                    style={{ width: '100%' }}
                  >
                    ✨ Enhance with AI
                  </button>
                ) : (
                  <div style={{
                    background: '#F9FAFB',
                    border: '1px solid var(--border)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem'
                  }}>
                    <label className="form-label text-sm">How should AI improve this? <span className="text-light">(optional — leave blank for general improvement)</span></label>
                    <textarea
                      className="form-textarea"
                      value={enhancePrompt}
                      onChange={(e) => setEnhancePrompt(e.target.value)}
                      placeholder="e.g., Make it punchier, add urgency, soften the ask, include website_insights variable..."
                      style={{ minHeight: '50px', marginBottom: '0.5rem' }}
                      disabled={enhancing}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleEnhance();
                        }
                      }}
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => { setShowEnhance(false); setEnhancePrompt(''); }}
                        disabled={enhancing}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={handleEnhance}
                        disabled={enhancing || (!form.subject && !form.body)}
                        style={{ flex: 1 }}
                      >
                        {enhancing ? '✨ Enhancing...' : '✨ Enhance'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowModal(false); setShowEnhance(false); }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={enhancing}>
                  {editing ? 'Update' : 'Create'} Template
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Templates;
