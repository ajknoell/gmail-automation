import { useState, useEffect, useCallback } from 'react';
import {
  getAgentTasks, getAgentStats, startLeadDiscovery,
  startCompetitiveIntel, cancelAgentTask
} from '../api/client';
import { useToast } from '../components/Toast';

const AGENT_TYPE_LABELS = {
  prospect_research: 'Prospect Research',
  lead_discovery: 'Lead Discovery',
  competitive_intel: 'Competitive Intel',
};

const STATUS_STYLES = {
  pending: { bg: '#F3F4F6', color: '#6B7280' },
  running: { bg: '#FEF3C7', color: '#D97706' },
  completed: { bg: '#D1FAE5', color: '#059669' },
  failed: { bg: '#FEE2E2', color: '#DC2626' },
  cancelled: { bg: '#F3F4F6', color: '#9CA3AF' },
};

function Agents() {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ agent_type: '', status: '' });
  const [expandedTask, setExpandedTask] = useState(null);
  const [showDiscovery, setShowDiscovery] = useState(false);
  const [showCompetitive, setShowCompetitive] = useState(false);
  const [discoveryForm, setDiscoveryForm] = useState({ industry: '', location: '', criteria: '' });
  const [competitiveForm, setCompetitiveForm] = useState({ competitor_url: '', competitor_name: '' });
  const [submitting, setSubmitting] = useState(false);
  const showToast = useToast();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter.agent_type) params.agent_type = filter.agent_type;
      if (filter.status) params.status = filter.status;

      const [tasksRes, statsRes] = await Promise.all([
        getAgentTasks(params),
        getAgentStats(),
      ]);
      setTasks(tasksRes.data.tasks || []);
      setStats(statsRes.data || {});
    } catch (error) {
      console.error('Failed to load agent data:', error);
    }
    setLoading(false);
  }, [filter]);

  useEffect(() => { loadData(); }, [loadData]);

  // Auto-refresh running tasks
  useEffect(() => {
    const hasRunning = tasks.some(t => t.status === 'running' || t.status === 'pending');
    if (!hasRunning) return;
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [tasks, loadData]);

  const handleDiscovery = async () => {
    if (!discoveryForm.industry.trim()) return;
    setSubmitting(true);
    try {
      await startLeadDiscovery(discoveryForm);
      showToast('Lead discovery agent started');
      setShowDiscovery(false);
      setDiscoveryForm({ industry: '', location: '', criteria: '' });
      loadData();
    } catch (error) {
      showToast('Failed to start discovery agent');
    }
    setSubmitting(false);
  };

  const handleCompetitive = async () => {
    if (!competitiveForm.competitor_url.trim()) return;
    setSubmitting(true);
    try {
      await startCompetitiveIntel(competitiveForm);
      showToast('Competitive intel agent started');
      setShowCompetitive(false);
      setCompetitiveForm({ competitor_url: '', competitor_name: '' });
      loadData();
    } catch (error) {
      showToast('Failed to start competitive intel agent');
    }
    setSubmitting(false);
  };

  const handleCancel = async (taskId) => {
    try {
      await cancelAgentTask(taskId);
      showToast('Task cancelled');
      loadData();
    } catch (error) {
      showToast('Failed to cancel task');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1>AI Agents</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-primary" onClick={() => setShowDiscovery(true)}>
            Discover Leads
          </button>
          <button className="btn" style={{ background: '#7C3AED', color: 'white' }} onClick={() => setShowCompetitive(true)}>
            Competitive Intel
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <div className="card" style={{ textAlign: 'center', padding: '1rem' }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{stats.completed || 0}</div>
          <div className="text-sm text-light">Completed</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '1rem' }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#D97706' }}>{stats.running || 0}</div>
          <div className="text-sm text-light">Running</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '1rem' }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{stats.total_firecrawl_pages || 0}</div>
          <div className="text-sm text-light">Pages Crawled</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '1rem' }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{((stats.total_input_tokens || 0) + (stats.total_output_tokens || 0)).toLocaleString()}</div>
          <div className="text-sm text-light">Total Tokens</div>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
        <select className="form-input" value={filter.agent_type} onChange={e => setFilter(f => ({ ...f, agent_type: e.target.value }))} style={{ width: 'auto' }}>
          <option value="">All Types</option>
          <option value="prospect_research">Prospect Research</option>
          <option value="lead_discovery">Lead Discovery</option>
          <option value="competitive_intel">Competitive Intel</option>
        </select>
        <select className="form-input" value={filter.status} onChange={e => setFilter(f => ({ ...f, status: e.target.value }))} style={{ width: 'auto' }}>
          <option value="">All Statuses</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Task List */}
      {loading ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>Loading...</div>
      ) : tasks.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <p className="text-light">No agent tasks yet. Start by running a research or discovery agent.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {tasks.map(task => {
            const statusStyle = STATUS_STYLES[task.status] || STATUS_STYLES.pending;
            const isExpanded = expandedTask === task.id;

            return (
              <div key={task.id} className="card" style={{ padding: '0.75rem 1rem' }}>
                <div
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                  onClick={() => setExpandedTask(isExpanded ? null : task.id)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span style={{ background: statusStyle.bg, color: statusStyle.color, padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600 }}>
                      {task.status}
                    </span>
                    <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{task.agent_type_label}</span>
                    {task.result_summary && (
                      <span className="text-sm text-light" style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {task.result_summary}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="text-sm text-light">
                      {task.created_at ? new Date(task.created_at).toLocaleDateString() : ''}
                    </span>
                    {(task.status === 'running' || task.status === 'pending') && (
                      <button className="btn btn-sm" style={{ background: '#FEE2E2', color: '#DC2626' }} onClick={(e) => { e.stopPropagation(); handleCancel(task.id); }}>
                        Cancel
                      </button>
                    )}
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ transform: isExpanded ? 'rotate(180deg)' : '', transition: '0.2s' }}>
                      <path d="M4 5.5L7 8.5L10 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                </div>

                {isExpanded && (
                  <div style={{ marginTop: '1rem', borderTop: '1px solid #E5E7EB', paddingTop: '1rem' }}>
                    {/* Config */}
                    {task.config && Object.keys(task.config).length > 0 && (
                      <div style={{ marginBottom: '1rem' }}>
                        <h4 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Configuration</h4>
                        <pre style={{ background: '#F9FAFB', padding: '0.75rem', borderRadius: '0.5rem', fontSize: '0.8rem', overflow: 'auto', maxHeight: '150px' }}>
                          {JSON.stringify(task.config, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* Result */}
                    {task.result && Object.keys(task.result).length > 0 && (
                      <div style={{ marginBottom: '1rem' }}>
                        <h4 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Result</h4>
                        {task.agent_type === 'prospect_research' && task.result.company_overview ? (
                          <div style={{ background: '#F9FAFB', padding: '1rem', borderRadius: '0.5rem' }}>
                            <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>{task.result.company_overview}</p>
                            {task.result.industry && <p className="text-sm"><strong>Industry:</strong> {task.result.industry}</p>}
                            {task.result.key_people?.length > 0 && (
                              <p className="text-sm"><strong>Key People:</strong> {task.result.key_people.map(p => `${p.name} (${p.title})`).join(', ')}</p>
                            )}
                            {task.result.products_services?.length > 0 && (
                              <p className="text-sm"><strong>Products/Services:</strong> {task.result.products_services.join(', ')}</p>
                            )}
                            {task.result.talking_points?.length > 0 && (
                              <div style={{ marginTop: '0.5rem' }}>
                                <strong className="text-sm">Talking Points:</strong>
                                <ul style={{ margin: '0.25rem 0', paddingLeft: '1.25rem' }}>
                                  {task.result.talking_points.map((tp, i) => <li key={i} className="text-sm">{tp}</li>)}
                                </ul>
                              </div>
                            )}
                          </div>
                        ) : (
                          <pre style={{ background: '#F9FAFB', padding: '0.75rem', borderRadius: '0.5rem', fontSize: '0.8rem', overflow: 'auto', maxHeight: '300px' }}>
                            {JSON.stringify(task.result, null, 2)}
                          </pre>
                        )}
                      </div>
                    )}

                    {/* Error */}
                    {task.error_message && (
                      <div style={{ background: '#FEE2E2', padding: '0.75rem', borderRadius: '0.5rem', marginBottom: '1rem' }}>
                        <p className="text-sm" style={{ color: '#DC2626' }}>{task.error_message}</p>
                      </div>
                    )}

                    {/* Cost */}
                    <div style={{ display: 'flex', gap: '1.5rem' }}>
                      <span className="text-sm text-light">Tokens: {(task.input_tokens + task.output_tokens).toLocaleString()}</span>
                      <span className="text-sm text-light">Pages scraped: {task.firecrawl_pages_scraped}</span>
                      <span className="text-sm text-light">Iterations: {task.execution_log?.length || 0}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Discovery Modal */}
      {showDiscovery && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="card" style={{ width: '480px', maxWidth: '90vw' }}>
            <h3 className="card-title mb-4">Lead Discovery Agent</h3>
            <p className="text-sm text-light mb-4">
              AI agent will search web directories and listings to find businesses matching your criteria.
            </p>
            <div style={{ display: 'grid', gap: '1rem' }}>
              <div>
                <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Industry *</label>
                <input className="form-input" placeholder="e.g., HVAC, Plumbing, Landscaping" value={discoveryForm.industry} onChange={e => setDiscoveryForm(f => ({ ...f, industry: e.target.value }))} style={{ width: '100%' }} />
              </div>
              <div>
                <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Location</label>
                <input className="form-input" placeholder="e.g., San Diego, CA" value={discoveryForm.location} onChange={e => setDiscoveryForm(f => ({ ...f, location: e.target.value }))} style={{ width: '100%' }} />
              </div>
              <div>
                <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Additional Criteria</label>
                <input className="form-input" placeholder="e.g., 5-50 employees, family-owned" value={discoveryForm.criteria} onChange={e => setDiscoveryForm(f => ({ ...f, criteria: e.target.value }))} style={{ width: '100%' }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.5rem' }}>
              <button className="btn" onClick={() => setShowDiscovery(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleDiscovery} disabled={submitting || !discoveryForm.industry.trim()}>
                {submitting ? 'Starting...' : 'Start Discovery'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Competitive Intel Modal */}
      {showCompetitive && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="card" style={{ width: '480px', maxWidth: '90vw' }}>
            <h3 className="card-title mb-4">Competitive Intelligence Agent</h3>
            <p className="text-sm text-light mb-4">
              AI agent will research a competitor&apos;s website for pricing, features, positioning, and recent activity.
            </p>
            <div style={{ display: 'grid', gap: '1rem' }}>
              <div>
                <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Competitor Website *</label>
                <input className="form-input" placeholder="e.g., competitor.com" value={competitiveForm.competitor_url} onChange={e => setCompetitiveForm(f => ({ ...f, competitor_url: e.target.value }))} style={{ width: '100%' }} />
              </div>
              <div>
                <label style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Competitor Name</label>
                <input className="form-input" placeholder="e.g., Acme Corp" value={competitiveForm.competitor_name} onChange={e => setCompetitiveForm(f => ({ ...f, competitor_name: e.target.value }))} style={{ width: '100%' }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.5rem' }}>
              <button className="btn" onClick={() => setShowCompetitive(false)}>Cancel</button>
              <button className="btn" style={{ background: '#7C3AED', color: 'white' }} onClick={handleCompetitive} disabled={submitting || !competitiveForm.competitor_url.trim()}>
                {submitting ? 'Starting...' : 'Start Research'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Agents;
