import { useState, useEffect } from 'react';
import StepRecipientList from './StepRecipientList';

const STEP_TYPE_LABELS = {
  template: 'Template',
  ai_followup: 'AI Follow-up',
};

const STATUS_COLORS = {
  draft: '#6B7280',
  generating: '#F59E0B',
  ready: '#3B82F6',
  running: '#E8603C',
  completed: '#10B981',
  cancelled: '#EF4444',
};

// --- Delay helpers ---

function parseDelay(minutes) {
  if (minutes === 0) return { value: 0, unit: 'minutes' };
  if (minutes % 1440 === 0) return { value: minutes / 1440, unit: 'days' };
  if (minutes % 60 === 0) return { value: minutes / 60, unit: 'hours' };
  return { value: minutes, unit: 'minutes' };
}

function toMinutes(value, unit) {
  switch (unit) {
    case 'days': return value * 1440;
    case 'hours': return value * 60;
    case 'minutes': return value;
    default: return value * 1440;
  }
}

function formatDelay(minutes) {
  if (minutes === 0 || minutes == null) return 'Immediately';
  if (minutes >= 1440 && minutes % 1440 === 0) {
    const d = minutes / 1440;
    return `${d} day${d !== 1 ? 's' : ''}`;
  }
  if (minutes >= 60 && minutes % 60 === 0) {
    const h = minutes / 60;
    return `${h} hour${h !== 1 ? 's' : ''}`;
  }
  return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
}

// --- Delay Input Component ---

function DelayInput({ delayMinutes, onChange, style }) {
  const parsed = parseDelay(delayMinutes ?? 4320);
  const [value, setValue] = useState(parsed.value);
  const [unit, setUnit] = useState(parsed.unit);

  useEffect(() => {
    const p = parseDelay(delayMinutes ?? 4320);
    setValue(p.value);
    setUnit(p.unit);
  }, [delayMinutes]);

  const handleChange = (newVal, newUnit) => {
    setValue(newVal);
    setUnit(newUnit);
    onChange(toMinutes(newVal, newUnit));
  };

  return (
    <div style={{ display: 'flex', gap: '0.5rem', ...style }}>
      <input
        type="number"
        className="form-input"
        value={value}
        min={0}
        onChange={(e) => handleChange(parseInt(e.target.value) || 0, unit)}
        style={{ width: '5rem' }}
      />
      <select
        className="form-input"
        value={unit}
        onChange={(e) => handleChange(value, e.target.value)}
        style={{ width: '7rem' }}
      >
        <option value="minutes">Minutes</option>
        <option value="hours">Hours</option>
        <option value="days">Days</option>
      </select>
    </div>
  );
}

// --- Step Config (shared between regular steps and variant cards) ---

function StepConfig({ step, canEdit, templates, onUpdateStep }) {
  if (!canEdit || step.status === 'completed') return null;

  return (
    <div style={{ display: 'grid', gap: '0.75rem' }}>
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
        {!step.variant_group && (
          <div>
            <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>
              Delay after previous step
            </label>
            <DelayInput
              delayMinutes={step.delay_minutes ?? step.effective_delay_minutes ?? (step.delay_days || 3) * 1440}
              onChange={(mins) => onUpdateStep(step.id, { delay_minutes: mins })}
            />
          </div>
        )}
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
  );
}

// --- Step Actions ---

function StepActions({ step, canEdit, generatingStepId, onGenerate, onApproveStep, onStartStep, onDeleteStep }) {
  return (
    <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
      {step.status === 'draft' && (
        <button
          className="btn btn-primary btn-sm"
          onClick={() => onGenerate(step.id)}
          disabled={generatingStepId === step.id}
        >
          {generatingStepId === step.id ? 'Generating...' : 'Generate Previews'}
        </button>
      )}
      {step.status === 'ready' && !step.auto_send && (
        <>
          <button className="btn btn-secondary btn-sm" onClick={() => onApproveStep(step.id)}>
            Approve All
          </button>
          <button className="btn btn-success btn-sm" onClick={() => onStartStep(step.id)}>
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
  );
}

// --- A/B Test Card ---

function ABTestCard({
  variants, campaignId, canEdit, templates, expandedStep, setExpandedStep,
  generatingStepId, onGenerate, onUpdateStep, onDeleteStep, onApproveStep,
  onStartStep, onReloadSteps,
}) {
  const variantGroup = variants[0]?.variant_group;

  return (
    <div style={{
      border: '2px solid #8B5CF6', borderRadius: '0.5rem', padding: '1rem',
    }}>
      {/* A/B test header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <span style={{
          background: '#8B5CF6', color: '#fff', padding: '0.15rem 0.5rem',
          borderRadius: '0.25rem', fontSize: '0.75rem', fontWeight: 600,
        }}>
          A/B TEST
        </span>
        <span style={{ fontSize: '0.8rem', color: '#6B7280' }}>
          {variants.map(v => `${v.variant_label}: ${v.variant_pct}%`).join(' / ')}
        </span>
        <span style={{ fontSize: '0.8rem', color: '#6B7280', marginLeft: 'auto' }}>
          Position {variants[0].position}
        </span>
      </div>

      {/* Variant cards side by side */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${variants.length}, 1fr)`,
        gap: '0.75rem',
      }}>
        {variants.map((step) => {
          const isExpanded = expandedStep === step.id;
          return (
            <div key={step.id} style={{
              border: '1px solid #E5E7EB', borderRadius: '0.5rem', padding: '0.75rem',
              background: isExpanded ? '#F9FAFB' : '#fff',
            }}>
              {/* Variant header */}
              <div
                style={{ cursor: 'pointer', marginBottom: '0.5rem' }}
                onClick={() => setExpandedStep(isExpanded ? null : step.id)}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{
                      background: '#8B5CF6', color: '#fff', borderRadius: '0.25rem',
                      width: '1.5rem', height: '1.5rem', display: 'flex', alignItems: 'center',
                      justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700,
                    }}>
                      {step.variant_label}
                    </span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                        {step.name || `Variant ${step.variant_label}`}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                        {STEP_TYPE_LABELS[step.step_type]} | {step.variant_pct}%
                        {step.auto_send && ' | Auto-send'}
                      </div>
                    </div>
                  </div>
                  <span className={`badge badge-${step.status}`} style={{ fontSize: '0.7rem' }}>
                    {step.status}
                  </span>
                </div>

                {/* Stats */}
                {(step.sent_count > 0 || step.skipped_count > 0) && (
                  <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.25rem' }}>
                    <span style={{ color: '#10B981' }}>{step.sent_count} sent</span>
                    {step.skipped_count > 0 && (
                      <span style={{ marginLeft: '0.5rem', color: '#F59E0B' }}>{step.skipped_count} skipped</span>
                    )}
                  </div>
                )}
              </div>

              {/* Expanded content */}
              {isExpanded && (
                <div style={{ paddingTop: '0.5rem', borderTop: '1px solid #E5E7EB' }}>
                  <StepConfig
                    step={step}
                    canEdit={canEdit}
                    templates={templates}
                    onUpdateStep={onUpdateStep}
                  />
                  <div style={{ marginTop: '0.75rem' }}>
                    <StepActions
                      step={step}
                      canEdit={canEdit}
                      generatingStepId={generatingStepId}
                      onGenerate={onGenerate}
                      onApproveStep={onApproveStep}
                      onStartStep={onStartStep}
                      onDeleteStep={onDeleteStep}
                    />
                  </div>
                  <StepRecipientList
                    campaignId={campaignId}
                    stepId={step.id}
                    stepStatus={step.status}
                    onReload={onReloadSteps}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- A/B Test Creation Form ---

function ABTestForm({ position, templates, onCreateABTest, onCancel }) {
  const [delayMinutes, setDelayMinutes] = useState(4320);
  const [variants, setVariants] = useState([
    { label: 'A', pct: 50, step_type: 'ai_followup', ai_prompt: '', template_id: null, name: '' },
    { label: 'B', pct: 50, step_type: 'ai_followup', ai_prompt: '', template_id: null, name: '' },
  ]);

  const updateVariant = (idx, updates) => {
    setVariants(vs => vs.map((v, i) => i === idx ? { ...v, ...updates } : v));
  };

  const addVariant = () => {
    if (variants.length >= 4) return;
    const labels = ['A', 'B', 'C', 'D'];
    const newLabel = labels[variants.length];
    const newPct = Math.floor(100 / (variants.length + 1));
    const adjusted = variants.map(v => ({ ...v, pct: newPct }));
    adjusted.push({ label: newLabel, pct: 100 - newPct * variants.length, step_type: 'ai_followup', ai_prompt: '', template_id: null, name: '' });
    setVariants(adjusted);
  };

  const handleSplitPreset = (splits) => {
    setVariants(vs => vs.map((v, i) => ({ ...v, pct: splits[i] || 0 })));
  };

  const totalPct = variants.reduce((s, v) => s + (v.pct || 0), 0);

  const handleCreate = () => {
    if (totalPct !== 100) {
      alert('Variant percentages must sum to 100%');
      return;
    }
    onCreateABTest({
      position,
      delay_minutes: delayMinutes,
      variants: variants.map(v => ({
        label: v.label,
        pct: v.pct,
        step_type: v.step_type,
        ai_prompt: v.ai_prompt || undefined,
        template_id: v.template_id || undefined,
        name: v.name || `Variant ${v.label}`,
      })),
    });
  };

  return (
    <div style={{
      marginTop: '1rem', padding: '1rem', border: '2px dashed #8B5CF6',
      borderRadius: '0.5rem', background: '#F5F3FF',
    }}>
      <h4 style={{ marginBottom: '0.75rem', fontWeight: 600, color: '#7C3AED' }}>New A/B Test</h4>

      <div style={{ display: 'flex', gap: '1rem', alignItems: 'end', marginBottom: '1rem' }}>
        <div>
          <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Delay</label>
          <DelayInput delayMinutes={delayMinutes} onChange={setDelayMinutes} />
        </div>
        <div>
          <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Split</label>
          <div style={{ display: 'flex', gap: '0.25rem' }}>
            {variants.length === 2 && (
              <>
                <button className="btn btn-sm" style={{ fontSize: '0.7rem' }} onClick={() => handleSplitPreset([50, 50])}>50/50</button>
                <button className="btn btn-sm" style={{ fontSize: '0.7rem' }} onClick={() => handleSplitPreset([70, 30])}>70/30</button>
                <button className="btn btn-sm" style={{ fontSize: '0.7rem' }} onClick={() => handleSplitPreset([80, 20])}>80/20</button>
              </>
            )}
          </div>
        </div>
        {variants.length < 4 && (
          <button className="btn btn-sm btn-secondary" onClick={addVariant}>
            + Variant
          </button>
        )}
      </div>

      {/* Variant configs */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${variants.length}, 1fr)`, gap: '0.75rem', marginBottom: '1rem' }}>
        {variants.map((v, idx) => (
          <div key={v.label} style={{
            border: '1px solid #DDD6FE', borderRadius: '0.5rem', padding: '0.75rem', background: '#fff',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <span style={{
                background: '#8B5CF6', color: '#fff', borderRadius: '0.25rem',
                width: '1.5rem', height: '1.5rem', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700,
              }}>
                {v.label}
              </span>
              <input
                type="number"
                className="form-input"
                value={v.pct}
                min={1} max={99}
                onChange={(e) => updateVariant(idx, { pct: parseInt(e.target.value) || 0 })}
                style={{ width: '3.5rem', textAlign: 'center' }}
              />
              <span style={{ fontSize: '0.8rem', color: '#6B7280' }}>%</span>
            </div>

            <div style={{ marginBottom: '0.5rem' }}>
              <input
                type="text"
                className="form-input"
                placeholder={`Variant ${v.label} name`}
                value={v.name}
                onChange={(e) => updateVariant(idx, { name: e.target.value })}
                style={{ width: '100%', fontSize: '0.85rem' }}
              />
            </div>

            <select
              className="form-input"
              value={v.step_type}
              onChange={(e) => updateVariant(idx, { step_type: e.target.value })}
              style={{ width: '100%', marginBottom: '0.5rem' }}
            >
              <option value="ai_followup">AI Follow-up</option>
              <option value="template">Template</option>
            </select>

            {v.step_type === 'ai_followup' && (
              <textarea
                className="form-input"
                rows={2}
                placeholder="AI instructions..."
                value={v.ai_prompt}
                onChange={(e) => updateVariant(idx, { ai_prompt: e.target.value })}
                style={{ width: '100%', fontSize: '0.8rem' }}
              />
            )}

            {v.step_type === 'template' && (
              <select
                className="form-input"
                value={v.template_id || ''}
                onChange={(e) => updateVariant(idx, { template_id: parseInt(e.target.value) || null })}
                style={{ width: '100%' }}
              >
                <option value="">Select template...</option>
                {(templates || []).map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            )}
          </div>
        ))}
      </div>

      {totalPct !== 100 && (
        <div style={{ color: '#EF4444', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
          Percentages must sum to 100% (currently {totalPct}%)
        </div>
      )}

      <div className="flex gap-2">
        <button className="btn btn-primary btn-sm" onClick={handleCreate} disabled={totalPct !== 100}>
          Create A/B Test
        </button>
        <button className="btn btn-secondary btn-sm" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}


// === Main Component ===

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
  onCreateABTest,
}) {
  const [expandedStep, setExpandedStep] = useState(null);
  const [addingAfter, setAddingAfter] = useState(null);
  const [addingABAfter, setAddingABAfter] = useState(null);
  const [newStepForm, setNewStepForm] = useState({
    step_type: 'ai_followup',
    delay_minutes: 4320,
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
      delay_minutes: 4320,
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

  const handleCreateABTest = async (data) => {
    if (onCreateABTest) {
      await onCreateABTest(data);
    }
    setAddingABAfter(null);
  };

  // Filter out step 1 (initial outreach)
  const followUpSteps = steps.filter((s) => s.position > 1);

  // Group steps by position to detect A/B tests
  const groupedByPosition = {};
  followUpSteps.forEach((step) => {
    if (!groupedByPosition[step.position]) {
      groupedByPosition[step.position] = [];
    }
    groupedByPosition[step.position].push(step);
  });
  const positions = Object.keys(groupedByPosition).sort((a, b) => a - b);

  const canEdit = !['running'].includes(campaignStatus);

  return (
    <div className="card mb-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="card-title">Follow-up Sequence</h3>
        {canEdit && (
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setAddingABAfter(null);
                setAddingAfter(steps.length > 0 ? steps[steps.length - 1].position : 1);
              }}
            >
              + Add Follow-up Step
            </button>
            {onCreateABTest && (
              <button
                className="btn btn-sm"
                style={{ background: '#8B5CF6', color: '#fff', border: 'none' }}
                onClick={() => {
                  setAddingAfter(null);
                  setAddingABAfter(steps.length > 0 ? steps[steps.length - 1].position : 1);
                }}
              >
                + Split A/B Test
              </button>
            )}
          </div>
        )}
      </div>

      {followUpSteps.length === 0 && addingAfter === null && addingABAfter === null && (
        <div style={{ padding: '1.5rem', textAlign: 'center', color: '#6B7280' }}>
          <p>No follow-up steps yet. Add steps to create a multi-email sequence.</p>
          <p style={{ fontSize: '0.8rem', marginTop: '0.5rem' }}>
            Follow-up emails are sent automatically after a delay, in the same Gmail thread.
          </p>
        </div>
      )}

      {/* Step cards as a vertical timeline */}
      <div style={{ position: 'relative' }}>
        {positions.map((pos, idx) => {
          const stepsAtPosition = groupedByPosition[pos];
          const isABTest = stepsAtPosition.length > 1;
          const firstStep = stepsAtPosition[0];
          const delayMins = firstStep.delay_minutes ?? firstStep.effective_delay_minutes ?? (firstStep.delay_days || 3) * 1440;

          return (
            <div key={pos}>
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
                <span>
                  {delayMins === 0
                    ? 'Immediately after previous step'
                    : `${formatDelay(delayMins)} after previous step`
                  }
                </span>
              </div>

              {isABTest ? (
                <ABTestCard
                  variants={stepsAtPosition}
                  campaignId={campaignId}
                  canEdit={canEdit}
                  templates={templates}
                  expandedStep={expandedStep}
                  setExpandedStep={setExpandedStep}
                  generatingStepId={generatingStepId}
                  onGenerate={handleGenerate}
                  onUpdateStep={onUpdateStep}
                  onDeleteStep={onDeleteStep}
                  onApproveStep={onApproveStep}
                  onStartStep={onStartStep}
                  onReloadSteps={onReloadSteps}
                />
              ) : (
                /* Regular single step card */
                <div style={{
                  border: '1px solid #E5E7EB',
                  borderRadius: '0.5rem',
                  padding: '1rem',
                  background: expandedStep === firstStep.id ? '#F9FAFB' : '#fff',
                }}>
                  {/* Step header */}
                  <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    cursor: 'pointer',
                  }}
                    onClick={() => setExpandedStep(expandedStep === firstStep.id ? null : firstStep.id)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <span style={{
                        background: STATUS_COLORS[firstStep.status] || '#6B7280',
                        color: '#fff', borderRadius: '50%', width: '1.75rem', height: '1.75rem',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.8rem', fontWeight: 600, flexShrink: 0,
                      }}>
                        {firstStep.position}
                      </span>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                          {firstStep.name || `Step ${firstStep.position}`}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#6B7280' }}>
                          {STEP_TYPE_LABELS[firstStep.step_type]}
                          {firstStep.use_web_research && ' + Web Research'}
                          {firstStep.auto_send && ' | Auto-send'}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      {(firstStep.sent_count > 0 || firstStep.skipped_count > 0) && (
                        <div style={{ fontSize: '0.8rem', color: '#6B7280', textAlign: 'right' }}>
                          <span style={{ color: '#10B981' }}>{firstStep.sent_count} sent</span>
                          {firstStep.skipped_count > 0 && (
                            <span style={{ marginLeft: '0.5rem', color: '#F59E0B' }}>{firstStep.skipped_count} skipped</span>
                          )}
                          {firstStep.failed_count > 0 && (
                            <span style={{ marginLeft: '0.5rem', color: '#EF4444' }}>{firstStep.failed_count} failed</span>
                          )}
                        </div>
                      )}
                      <span className={`badge badge-${firstStep.status}`} style={{ fontSize: '0.75rem' }}>
                        {firstStep.status}
                      </span>
                    </div>
                  </div>

                  {/* Expanded step content */}
                  {expandedStep === firstStep.id && (
                    <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #E5E7EB' }}>
                      <StepConfig
                        step={firstStep}
                        canEdit={canEdit}
                        templates={templates}
                        onUpdateStep={onUpdateStep}
                      />
                      <div style={{ marginTop: '0.75rem' }}>
                        <StepActions
                          step={firstStep}
                          canEdit={canEdit}
                          generatingStepId={generatingStepId}
                          onGenerate={handleGenerate}
                          onApproveStep={onApproveStep}
                          onStartStep={onStartStep}
                          onDeleteStep={onDeleteStep}
                        />
                      </div>
                      <StepRecipientList
                        campaignId={campaignId}
                        stepId={firstStep.id}
                        stepStatus={firstStep.status}
                        onReload={onReloadSteps}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Insert step / A/B test buttons between positions */}
              {canEdit && idx < positions.length - 1 && (
                <div style={{ textAlign: 'center', padding: '0.25rem 0', display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                  <button
                    className="btn btn-sm"
                    style={{
                      background: 'none', border: '1px dashed #D1D5DB', color: '#9CA3AF',
                      fontSize: '0.75rem', padding: '0.2rem 0.75rem',
                    }}
                    onClick={() => { setAddingABAfter(null); setAddingAfter(parseInt(pos)); }}
                  >
                    + Insert step
                  </button>
                  {onCreateABTest && (
                    <button
                      className="btn btn-sm"
                      style={{
                        background: 'none', border: '1px dashed #8B5CF6', color: '#8B5CF6',
                        fontSize: '0.75rem', padding: '0.2rem 0.75rem',
                      }}
                      onClick={() => { setAddingAfter(null); setAddingABAfter(parseInt(pos)); }}
                    >
                      + Insert A/B test
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}
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
                <label style={{ fontWeight: 500, fontSize: '0.85rem', display: 'block', marginBottom: '0.25rem' }}>Delay after previous step</label>
                <DelayInput
                  delayMinutes={newStepForm.delay_minutes}
                  onChange={(mins) => setNewStepForm((f) => ({ ...f, delay_minutes: mins }))}
                />
                <span style={{ fontSize: '0.75rem', color: '#9CA3AF', marginTop: '0.25rem', display: 'block' }}>Time to wait before sending this follow-up</span>
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

      {/* A/B test creation form */}
      {addingABAfter !== null && onCreateABTest && (
        <ABTestForm
          position={addingABAfter + 1}
          templates={templates}
          onCreateABTest={handleCreateABTest}
          onCancel={() => setAddingABAfter(null)}
        />
      )}
    </div>
  );
}

export default SequenceBuilder;
