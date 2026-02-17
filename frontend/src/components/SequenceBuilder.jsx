import { useState } from 'react';
import StepRecipientList from './StepRecipientList';

const STEP_TYPE_LABELS = {
  template: 'Template',
  ai_followup: 'AI Follow-up',
};

const STATUS_COLORS = {
  draft: '#6B7280',
  generating: '#F59E0B',
  ready: '#3B82F6',
  running: '#8B5CF6',
  completed: '#10B981',
  cancelled: '#EF4444',
};

function SequenceBuilder({
  campaignId,
  steps,
  templates,
  campaignStatus,
  onCreateStep,
  onUpdateStep,
  onDeleteStep,
  onGeneratePreview,
  onApproveStep,
  onStartStep,
  onReloadSteps,
}) {
  const [expandedStep, setExpandedStep] = useState(null);
  const [addingAfter, setAddingAfter] = useState(null);
  const [newStepForm, setNewStepForm] = useState({
    step_type: 'ai_followup',
    delay_days: 3,
    ai_prompt: '',
    use_web_research: false,
    web_research_prompt: '',
    auto_send: false,
    template_id: null,
    name: '',
  });
  const [generatingStepId, setGeneratingStepId] = useState(null);

  const handleAddStep = async () => {
    const position = addingAfter != null ? addingAfter + 1 : (steps.length > 0 ? steps[steps.length - 1].position + 1 : 2);
    await onCreateStep({
      ...newStepForm,
      position,
      name: newStepForm.name || `Follow-up #${position - 1}`,
    });
    setAddingAfter(null);
    setNewStepForm({
      step_type: 'ai_followup',
      delay_days: 3,
      ai_prompt: '',
      use_web_research: false,
      web_research_prompt: '',
      auto_send: false,
      template_id: null,
      name: '',
    });
  };

  const handleGenerate = async (stepId) => {
    setGeneratingStepId(stepId);
    await onGeneratePreview(stepId);
    setGeneratingStepId(null);
  };

  // Filter out step 1 (initial outreach) — that's handled by the main campaign UI
  const followUpSteps = steps.filter((s) => s.position > 1);

  const canEdit = !['running'].includes(campaignStatus);

  return (
    <div className="card mb-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="card-title">Follow-up Sequence</h3>
        {canEdit && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setAddingAfter(steps.length > 0 ? steps[steps.length - 1].position : 1)}
          >
            + Add Follow-up Step
          </button>
        )}
      </div>

      {followUpSteps.length === 0 && addingAfter === null && (
        <div style={{ padding: '1.5rem', textAlign: 'center', color: '#6B7280' }}>
          <p>No follow-up steps yet. Add steps to create a multi-email sequence.</p>
          <p style={{ fontSize: '0.8rem', marginTop: '0.5rem' }}>
            Follow-up emails are sent automatically after a delay, in the same Gmail thread.
          </p>
        </div>
      )}

      {/* Step cards as a vertical timeline */}
      <div style={{ position: 'relative' }}>
        {followUpSteps.map((step, idx) => (
          <div key={step.id}>
            {/* Delay indicator */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.5rem 0', color: '#9CA3AF', fontSize: '0.8rem',
            }}>
              <div style={{ width: '2rem', textAlign: 'center' }}>
                <div style={{
                  width: '2px', height: '1rem', background: '#D1D5DB',
                  margin: '0 auto',
                }} />
              </div>
              <span>{step.delay_days} day{step.delay_days !== 1 ? 's' : ''} after previous step</span>
            </div>

            {/* Step card */}
            <div style={{
              border: '1px solid #E5E7EB',
              borderRadius: '0.5rem',
              padding: '1rem',
              background: expandedStep === step.id ? '#F9FAFB' : '#fff',
            }}>
              {/* Step header */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                cursor: 'pointer',
              }}
                onClick={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{
                    background: STATUS_COLORS[step.status] || '#6B7280',
                    color: '#fff', borderRadius: '50%', width: '1.75rem', height: '1.75rem',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.8rem', fontWeight: 600, flexShrink: 0,
                  }}>
                    {step.position}
                  </span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                      {step.name || `Step ${step.position}`}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#6B7280' }}>
                      {STEP_TYPE_LABELS[step.step_type]}
                      {step.use_web_research && ' + Web Research'}
                      {step.auto_send && ' | Auto-send'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  {/* Stats */}
                  {(step.sent_count > 0 || step.skipped_count > 0) && (
                    <div style={{ fontSize: '0.8rem', color: '#6B7280', textAlign: 'right' }}>
                      <span style={{ color: '#10B981' }}>{step.sent_count} sent</span>
                      {step.skipped_count > 0 && (
                        <span style={{ marginLeft: '0.5rem', color: '#F59E0B' }}>{step.skipped_count} skipped</span>
                      )}
                      {step.failed_count > 0 && (
                        <span style={{ marginLeft: '0.5rem', color: '#EF4444' }}>{step.failed_count} failed</span>
                      )}
                    </div>
                  )}

                  <span className={`badge badge-${step.status}`} style={{ fontSize: '0.75rem' }}>
                    {step.status}
                  </span>
                </div>
              </div>

              {/* Expanded step content */}
              {expandedStep === step.id && (
                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #E5E7EB' }}>
                  {/* Configuration */}
                  {canEdit && step.status !== 'completed' && (
                    <div style={{ display: 'grid', gap: '0.75rem', marginBottom: '1rem' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                        <div>
                          <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                            Step Type
                          </label>
                          <select
                            className="form-input"
                            value={step.step_type}
                            onChange={(e) => onUpdateStep(step.id, { step_type: e.target.value })}
                            style={{ width: '100%' }}
                          >
                            <option value="ai_followup">AI Follow-up</option>
                            <option value="template">Template</option>
                          </select>
                        </div>
                        <div>
                          <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                            Delay (days)
                          </label>
                          <input
                            type="number"
                            className="form-input"
                            value={step.delay_days}
                            min={1}
                            onChange={(e) => onUpdateStep(step.id, { delay_days: parseInt(e.target.value) || 1 })}
                            style={{ width: '100%' }}
                          />
                        </div>
                      </div>

                      {step.step_type === 'template' && (
                        <div>
                          <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                            Template
                          </label>
                          <select
                            className="form-input"
                            value={step.template_id || ''}
                            onChange={(e) => onUpdateStep(step.id, { template_id: parseInt(e.target.value) || null })}
                            style={{ width: '100%' }}
                          >
                            <option value="">Select template...</option>
                            {(templates || []).map((t) => (
                              <option key={t.id} value={t.id}>{t.name}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {step.step_type === 'ai_followup' && (
                        <div>
                          <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                            AI Instructions (optional)
                          </label>
                          <textarea
                            className="form-input"
                            rows={2}
                            placeholder="e.g., Mention a recent industry trend, ask about their expansion plans..."
                            defaultValue={step.ai_prompt || ''}
                            onBlur={(e) => onUpdateStep(step.id, { ai_prompt: e.target.value })}
                            style={{ width: '100%' }}
                          />
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={step.use_web_research}
                            onChange={(e) => onUpdateStep(step.id, { use_web_research: e.target.checked })}
                          />
                          <span style={{ fontSize: '0.85rem' }}>Web Research</span>
                        </label>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={step.auto_send}
                            onChange={(e) => onUpdateStep(step.id, { auto_send: e.target.checked })}
                          />
                          <span style={{ fontSize: '0.85rem' }}>Auto-send when due</span>
                        </label>
                      </div>

                      {step.use_web_research && (
                        <div>
                          <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
                            Search Query Template (optional)
                          </label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g., {{company}} {{industry}} recent news trends"
                            defaultValue={step.web_research_prompt || ''}
                            onBlur={(e) => onUpdateStep(step.id, { web_research_prompt: e.target.value })}
                            style={{ width: '100%' }}
                          />
                          <span style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>
                            Use {'{{company}}'}, {'{{industry}}'}, {'{{name}}'} as variables
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                    {step.status === 'draft' && (
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleGenerate(step.id)}
                        disabled={generatingStepId === step.id}
                      >
                        {generatingStepId === step.id ? 'Generating...' : 'Generate Previews'}
                      </button>
                    )}
                    {step.status === 'ready' && !step.auto_send && (
                      <>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onApproveStep(step.id)}
                        >
                          Approve All
                        </button>
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => onStartStep(step.id)}
                        >
                          Send Now
                        </button>
                      </>
                    )}
                    {step.status === 'ready' && step.auto_send && (
                      <span style={{ fontSize: '0.8rem', color: '#6B7280', alignSelf: 'center' }}>
                        Will auto-send when recipients are due
                      </span>
                    )}
                    {canEdit && step.status !== 'completed' && (
                      <button
                        className="btn btn-sm"
                        style={{ background: 'none', color: '#EF4444', border: '1px solid #EF4444', marginLeft: 'auto' }}
                        onClick={() => {
                          if (confirm(`Delete step "${step.name || 'Step ' + step.position}"?`)) {
                            onDeleteStep(step.id);
                          }
                        }}
                      >
                        Delete
                      </button>
                    )}
                  </div>

                  {/* Step recipients list */}
                  <StepRecipientList
                    campaignId={campaignId}
                    stepId={step.id}
                    stepStatus={step.status}
                    onReload={onReloadSteps}
                  />
                </div>
              )}
            </div>

            {/* Add step button between steps */}
            {canEdit && idx < followUpSteps.length - 1 && (
              <div style={{ textAlign: 'center', padding: '0.25rem 0' }}>
                <button
                  className="btn btn-sm"
                  style={{
                    background: 'none', border: '1px dashed #D1D5DB', color: '#9CA3AF',
                    fontSize: '0.75rem', padding: '0.2rem 0.75rem',
                  }}
                  onClick={() => setAddingAfter(step.position)}
                >
                  + Insert step
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* New step form */}
      {addingAfter !== null && (
        <div style={{
          marginTop: '1rem', padding: '1rem', border: '2px dashed #3B82F6',
          borderRadius: '0.5rem', background: '#EFF6FF',
        }}>
          <h4 style={{ marginBottom: '0.75rem', fontWeight: 600 }}>New Follow-up Step</h4>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Type</label>
                <select
                  className="form-input"
                  value={newStepForm.step_type}
                  onChange={(e) => setNewStepForm((f) => ({ ...f, step_type: e.target.value }))}
                  style={{ width: '100%' }}
                >
                  <option value="ai_followup">AI Follow-up</option>
                  <option value="template">Template</option>
                </select>
              </div>
              <div>
                <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Delay (days)</label>
                <input
                  type="number"
                  className="form-input"
                  value={newStepForm.delay_days}
                  min={1}
                  onChange={(e) => setNewStepForm((f) => ({ ...f, delay_days: parseInt(e.target.value) || 1 }))}
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Name (optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Follow-up #1"
                  value={newStepForm.name}
                  onChange={(e) => setNewStepForm((f) => ({ ...f, name: e.target.value }))}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            {newStepForm.step_type === 'ai_followup' && (
              <div>
                <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>AI Instructions</label>
                <textarea
                  className="form-input"
                  rows={2}
                  placeholder="e.g., Mention a recent industry trend..."
                  value={newStepForm.ai_prompt}
                  onChange={(e) => setNewStepForm((f) => ({ ...f, ai_prompt: e.target.value }))}
                  style={{ width: '100%' }}
                />
              </div>
            )}

            <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={newStepForm.use_web_research}
                  onChange={(e) => setNewStepForm((f) => ({ ...f, use_web_research: e.target.checked }))}
                />
                <span style={{ fontSize: '0.85rem' }}>Web Research</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={newStepForm.auto_send}
                  onChange={(e) => setNewStepForm((f) => ({ ...f, auto_send: e.target.checked }))}
                />
                <span style={{ fontSize: '0.85rem' }}>Auto-send when due</span>
              </label>
            </div>

            <div className="flex gap-2">
              <button className="btn btn-primary btn-sm" onClick={handleAddStep}>
                Add Step
              </button>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setAddingAfter(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SequenceBuilder;
