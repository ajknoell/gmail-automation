import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getAuthStatus } from './api/client';
import { useFeatureVisibility } from './hooks/useFeatureVisibility';
import Home from './pages/Home';
import QuickSend from './pages/QuickSend';
import Campaigns from './pages/Campaigns';
import CampaignDetail from './pages/CampaignDetail';
import Templates from './pages/Templates';
import Contacts from './pages/Contacts';
import ContactDetail from './pages/ContactDetail';
import ReplyHub from './pages/ReplyHub';
import Settings from './pages/Settings';
import Listings from './pages/Listings';
import Insights from './pages/Insights';
import MapExplorer from './pages/MapExplorer';
import Discovery from './pages/Discovery';
import DailyBrief from './pages/DailyBrief';
import Triggers from './pages/Triggers';
import Pipeline from './pages/Pipeline';
import Intelligence from './pages/Intelligence';
import IntelligenceSources from './pages/IntelligenceSources';
import BusinessProfile from './pages/BusinessProfile';
import Prospects from './pages/Prospects';
import Agents from './pages/Agents';
import DealTracker from './pages/DealTracker';
import ApolloSearch from './pages/ApolloSearch';
import WorkspaceSelector from './components/WorkspaceSelector';
import MobileLayout from './components/MobileLayout';
import QuickSendPanel from './components/QuickSendPanel';
import { ToastProvider } from './components/Toast';
import './App.css';

function NavLink({ to, children, exact }) {
  const location = useLocation();
  const isActive = exact
    ? location.pathname === to
    : location.pathname === to || location.pathname.startsWith(to + '/');
  return (
    <Link to={to} className={`sidebar-link ${isActive ? 'active' : ''}`}>
      {children}
    </Link>
  );
}

function WorkflowIndicator() {
  const location = useLocation();
  const path = location.pathname;

  const getActiveStep = () => {
    if (path.startsWith('/prospects') || path === '/discovery' || path === '/map-explorer' || path === '/pipeline' || path === '/apollo') return 'find';
    if (path === '/contacts' || path.startsWith('/contacts/')) return 'enrich';
    if (path.startsWith('/campaigns') || path === '/replies' || path === '/templates' || path === '/quick-send') return 'outreach';
    if (path === '/insights' || path === '/' || path === '/brief') return 'track';
    return '';
  };

  const active = getActiveStep();
  const steps = [
    { id: 'find', label: 'Find' },
    { id: 'enrich', label: 'Enrich' },
    { id: 'outreach', label: 'Outreach' },
    { id: 'track', label: 'Track' },
  ];

  return (
    <div className="workflow-indicator">
      {steps.map((step, i) => (
        <div key={step.id} style={{ display: 'contents' }}>
          <div className={`workflow-step ${active === step.id ? 'active' : ''}`}>
            <div className="workflow-dot" />
            <span className="workflow-step-label">{step.label}</span>
          </div>
          {i < steps.length - 1 && <div className="workflow-connector" />}
        </div>
      ))}
    </div>
  );
}

function CollapsibleSection({ label, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="nav-section">
      <div className="nav-section-toggle" onClick={() => setOpen(!open)}>
        <div className="nav-section-label">{label}</div>
        <svg className={`nav-section-chevron ${!open ? 'collapsed' : ''}`} viewBox="0 0 14 14" fill="none">
          <path d="M4 5.5L7 8.5L10 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className={`nav-section-items ${!open ? 'collapsed' : ''}`}>
        {children}
      </div>
    </div>
  );
}

function PageTransition({ children }) {
  const location = useLocation();
  return (
    <div className="page-transition" key={location.key}>
      {children}
    </div>
  );
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isMobile;
}

function App() {
  const [status, setStatus] = useState({ gmail_connected: false, anthropic_configured: false });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [quickSendOpen, setQuickSendOpen] = useState(false);
  const [quickSendPrefill, setQuickSendPrefill] = useState(null);
  const isMobile = useIsMobile();
  const { isFeatureEnabled } = useFeatureVisibility();

  const refreshStatus = () => {
    getAuthStatus()
      .then((res) => setStatus(res.data))
      .catch(() => {});
  };

  useEffect(() => {
    refreshStatus();
    const handleWsChange = () => refreshStatus();
    // Allow opening quick send from anywhere via custom event
    const handleQuickSend = (e) => {
      setQuickSendPrefill(e.detail || null);
      setQuickSendOpen(true);
    };
    window.addEventListener('workspace-changed', handleWsChange);
    window.addEventListener('open-quick-send', handleQuickSend);
    return () => {
      window.removeEventListener('workspace-changed', handleWsChange);
      window.removeEventListener('open-quick-send', handleQuickSend);
    };
  }, []);

  const routeElements = (
    <Routes>
      <Route path="/" element={<Home status={status} />} />
      <Route path="/brief" element={<Navigate to="/" replace />} />
      <Route path="/insights" element={<Insights />} />
      <Route path="/prospects" element={<Prospects />} />
      <Route path="/prospects/:tab" element={<Prospects />} />
      <Route path="/discovery" element={<Discovery />} />
      <Route path="/quick-send" element={<QuickSend />} />
      <Route path="/campaigns" element={<Campaigns />} />
      <Route path="/campaigns/:id" element={<CampaignDetail />} />
      <Route path="/templates" element={<Templates />} />
      <Route path="/contacts" element={<Contacts />} />
      <Route path="/contacts/:id" element={<ContactDetail />} />
      <Route path="/replies" element={<ReplyHub />} />
      <Route path="/map-explorer" element={<MapExplorer />} />
      <Route path="/pipeline" element={<Pipeline />} />
      <Route path="/listings" element={<Listings />} />
      <Route path="/deals" element={<DealTracker />} />
      <Route path="/intelligence" element={<Intelligence />} />
      <Route path="/intelligence/triggers" element={<Triggers />} />
      <Route path="/intelligence/sources" element={<IntelligenceSources />} />
      <Route path="/triggers" element={<Navigate to="/intelligence/triggers" replace />} />
      <Route path="/signals" element={<Navigate to="/intelligence" replace />} />
      <Route path="/opportunities" element={<Navigate to="/intelligence" replace />} />
      <Route path="/apollo" element={<ApolloSearch />} />
      <Route path="/business-profile" element={<BusinessProfile />} />
      <Route path="/agents" element={<Agents />} />
      <Route path="/settings" element={<Settings onStatusChange={setStatus} />} />
    </Routes>
  );

  if (isMobile) {
    return (
      <ToastProvider>
        <Router>
          <MobileLayout>
            <main className="main main-mobile">
              <PageTransition>
                {routeElements}
              </PageTransition>
            </main>
          </MobileLayout>
          <QuickSendPanel open={quickSendOpen} onClose={() => setQuickSendOpen(false)} prefill={quickSendPrefill} />
          {/* Mobile FAB */}
          <div className="fab-container">
            <button
              className={`fab-button ${quickSendOpen ? 'open' : ''}`}
              onClick={() => setQuickSendOpen(!quickSendOpen)}
              aria-label="Quick Send"
            >
              <svg width="22" height="22" viewBox="0 0 16 16" fill="none">
                <path d="M14 2L7 9M14 2L10 14L7 9M14 2L2 6L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </Router>
      </ToastProvider>
    );
  }

  return (
    <ToastProvider>
    <Router>
      <div className="app">
        <header className="header">
          <div className="header-content">
            <button
              className="sidebar-toggle"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              aria-label="Toggle sidebar"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M2 4h14M2 9h14M2 14h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
            <Link to="/" className="logo">
              Veloro
            </Link>
            <div className="header-right">
              <WorkspaceSelector />
              <span className={`status-badge ${status.gmail_connected ? 'connected' : 'disconnected'}`}>
                {status.gmail_connected ? 'Gmail Connected' : 'Gmail Disconnected'}
              </span>
            </div>
          </div>
        </header>

        <div className="app-body">
          <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
            <nav className="sidebar-nav">
              {/* Workflow Progress Indicator */}
              <WorkflowIndicator />

              {/* COMMAND CENTER */}
              <div className="nav-section">
                <div className="nav-section-label">Command Center</div>
                <NavLink to="/" exact>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 8L8 2L14 8V14H10V10H6V14H2V8Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                  <span>Today</span>
                </NavLink>
              </div>

              {/* FIND */}
              <div className="nav-section">
                <div className="nav-section-label">Find</div>
                <NavLink to="/prospects">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6.5 11C9 11 11 9 11 6.5S9 2 6.5 2 2 4 2 6.5 4 11 6.5 11ZM11 11L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  <span>Prospects</span>
                </NavLink>
                {isFeatureEnabled('contacts') && (
                  <NavLink to="/contacts">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 7C9.66 7 11 5.66 11 4S9.66 1 8 1 5 2.34 5 4 6.34 7 8 7ZM2 15V13C2 11.34 5 10 8 10S14 11.34 14 13V15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                    <span>Contacts</span>
                  </NavLink>
                )}
                {isFeatureEnabled('listings') && (
                  <NavLink to="/listings">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 2H7V7H2V2ZM9 2H14V7H9V2ZM2 9H7V14H2V9ZM9 9H14V14H9V9Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Listings</span>
                  </NavLink>
                )}
                <NavLink to="/deals">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 4H14M2 4V12C2 13.1 2.9 14 4 14H12C13.1 14 14 13.1 14 12V4M2 4L4 2H12L14 4M6 7H10M6 10H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  <span>Deals</span>
                </NavLink>
                <NavLink to="/apollo">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1L2 15M8 1L14 15M4.5 10H11.5M8 1V4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  <span>Apollo</span>
                </NavLink>
              </div>

              {/* OUTREACH */}
              <div className="nav-section">
                <div className="nav-section-label">Outreach</div>
                {isFeatureEnabled('campaigns') && (
                  <NavLink to="/campaigns">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 3H14V13H2V3ZM2 3L8 8.5L14 3" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Campaigns</span>
                  </NavLink>
                )}
                {isFeatureEnabled('replies') && (
                  <NavLink to="/replies">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 7L2 4L14 2L12 14L8 9M6 7L8 9M6 7V11" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Inbox</span>
                  </NavLink>
                )}
                {isFeatureEnabled('templates') && (
                  <NavLink to="/templates">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 2H12C13 2 14 3 14 4V12C14 13 13 14 12 14H4C3 14 2 13 2 12V4C2 3 3 2 4 2ZM2 6H14" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Templates</span>
                  </NavLink>
                )}
              </div>

              {/* INTELLIGENCE */}
              <CollapsibleSection label="Intelligence" defaultOpen={true}>
                <NavLink to="/intelligence">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1V3M8 13V15M1 8H3M13 8H15M3.05 3.05L4.46 4.46M11.54 11.54L12.95 12.95M12.95 3.05L11.54 4.46M4.46 11.54L3.05 12.95M8 5C6.34 5 5 6.34 5 8S6.34 11 8 11 11 9.66 11 8 9.66 5 8 5Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  <span>Radar</span>
                </NavLink>
                <NavLink to="/intelligence/sources">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 12C4 10 4 6 2 4M6 10.5C7 9.5 7 6.5 6 5.5M10 9C10.5 8.5 10.5 7.5 10 7M14 8C14 8 14 8 14 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  <span>Sources</span>
                </NavLink>
                <NavLink to="/intelligence/triggers">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M9 1L3 9H8L7 15L13 7H8L9 1Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                  <span>Triggers</span>
                </NavLink>
              </CollapsibleSection>
            </nav>

            <div className="sidebar-footer">
              <NavLink to="/insights">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 14V8M6 14V4M10 14V6M14 14V2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                <span>Insights</span>
              </NavLink>
              <NavLink to="/settings">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 10C9.1 10 10 9.1 10 8S9.1 6 8 6 6 6.9 6 8 6.9 10 8 10ZM13.5 8C13.5 8.34 13.47 8.66 13.42 8.98L15 10.19L14.1 11.81L12.25 11.14C11.77 11.54 11.21 11.84 10.6 12.02L10.2 14H7.8L7.4 12.02C6.79 11.84 6.23 11.54 5.75 11.14L3.9 11.81L3 10.19L4.58 8.98C4.53 8.66 4.5 8.34 4.5 8S4.53 7.34 4.58 7.02L3 5.81L3.9 4.19L5.75 4.86C6.23 4.46 6.79 4.16 7.4 3.98L7.8 2H10.2L10.6 3.98C11.21 4.16 11.77 4.46 12.25 4.86L14.1 4.19L15 5.81L13.42 7.02C13.47 7.34 13.5 7.66 13.5 8Z" stroke="currentColor" strokeWidth="1.3"/></svg>
                <span>Settings</span>
              </NavLink>
            </div>
          </aside>

          <main className="main">
            <PageTransition>
              {routeElements}
            </PageTransition>
          </main>
        </div>
      </div>

      {/* Floating Quick Send Button */}
      <div className="fab-container">
        <button
          className={`fab-button ${quickSendOpen ? 'open' : ''}`}
          onClick={() => setQuickSendOpen(!quickSendOpen)}
          aria-label="Quick Send"
        >
          <svg width="22" height="22" viewBox="0 0 16 16" fill="none">
            <path d="M14 2L7 9M14 2L10 14L7 9M14 2L2 6L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      {/* Quick Send Slide-in Panel */}
      <QuickSendPanel open={quickSendOpen} onClose={() => setQuickSendOpen(false)} prefill={quickSendPrefill} />
    </Router>
    </ToastProvider>
  );
}

export default App;
