import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
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
import Signals from './pages/Signals';
import BusinessProfile from './pages/BusinessProfile';
import OpportunityFeed from './pages/OpportunityFeed';
import WorkspaceSelector from './components/WorkspaceSelector';
import MobileLayout from './components/MobileLayout';
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
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const routeElements = (
    <Routes>
      <Route path="/" element={<Home status={status} />} />
      <Route path="/brief" element={<DailyBrief />} />
      <Route path="/insights" element={<Insights />} />
      <Route path="/discovery" element={<Discovery />} />
      <Route path="/quick-send" element={<QuickSend />} />
      <Route path="/campaigns" element={<Campaigns />} />
      <Route path="/campaigns/:id" element={<CampaignDetail />} />
      <Route path="/templates" element={<Templates />} />
      <Route path="/contacts" element={<Contacts />} />
      <Route path="/contacts/:id" element={<ContactDetail />} />
      <Route path="/replies" element={<ReplyHub />} />
      <Route path="/map-explorer" element={<MapExplorer />} />
      <Route path="/listings" element={<Listings />} />
      <Route path="/triggers" element={<Triggers />} />
      <Route path="/signals" element={<Signals />} />
      <Route path="/business-profile" element={<BusinessProfile />} />
      <Route path="/opportunities" element={<OpportunityFeed />} />
      <Route path="/settings" element={<Settings onStatusChange={setStatus} />} />
    </Routes>
  );

  if (isMobile) {
    return (
      <Router>
        <MobileLayout>
          <main className="main main-mobile">
            {routeElements}
          </main>
        </MobileLayout>
      </Router>
    );
  }

  return (
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
              <span className="logo-icon">⚡</span>
              Veloro
            </Link>
            <div className="header-right">
              <WorkspaceSelector />
              <span className={`status-badge ${status.gmail_connected ? 'connected' : 'disconnected'}`}>
                Gmail: {status.gmail_connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </header>

        <div className="app-body">
          <aside className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
            <nav className="sidebar-nav">
              <div className="nav-section">
                <div className="nav-section-label">Overview</div>
                <NavLink to="/" exact>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 8L8 2L14 8V14H10V10H6V14H2V8Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                  <span>Dashboard</span>
                </NavLink>
                <NavLink to="/opportunities">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1V3M8 13V15M1 8H3M13 8H15M3.05 3.05L4.46 4.46M11.54 11.54L12.95 12.95M12.95 3.05L11.54 4.46M4.46 11.54L3.05 12.95" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.5"/></svg>
                  <span>Opportunities</span>
                </NavLink>
                <NavLink to="/brief">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 2H13V14H3V2ZM5 5H11M5 8H11M5 11H9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  <span>Daily Brief</span>
                </NavLink>
                {isFeatureEnabled('insights') && (
                  <NavLink to="/insights">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 14V8M6 14V4M10 14V6M14 14V2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                    <span>Insights</span>
                  </NavLink>
                )}
              </div>

              <div className="nav-section">
                <div className="nav-section-label">Outreach</div>
                {isFeatureEnabled('quick_send') && (
                  <NavLink to="/quick-send">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M14 2L7 9M14 2L10 14L7 9M14 2L2 6L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Quick Send</span>
                  </NavLink>
                )}
                {isFeatureEnabled('replies') && (
                  <NavLink to="/replies">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6 7L2 4L14 2L12 14L8 9M6 7L8 9M6 7V11" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Reply Hub</span>
                  </NavLink>
                )}
                {isFeatureEnabled('campaigns') && (
                  <NavLink to="/campaigns">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 3H14V13H2V3ZM2 3L8 8.5L14 3" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Campaigns</span>
                  </NavLink>
                )}
                {isFeatureEnabled('templates') && (
                  <NavLink to="/templates">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 2H12C13 2 14 3 14 4V12C14 13 13 14 12 14H4C3 14 2 13 2 12V4C2 3 3 2 4 2ZM2 6H14" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Templates</span>
                  </NavLink>
                )}
              </div>

              <div className="nav-section">
                <div className="nav-section-label">Data</div>
                {isFeatureEnabled('contacts') && (
                  <NavLink to="/contacts">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 7C9.66 7 11 5.66 11 4S9.66 1 8 1 5 2.34 5 4 6.34 7 8 7ZM2 15V13C2 11.34 5 10 8 10S14 11.34 14 13V15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                    <span>Contacts</span>
                  </NavLink>
                )}
                <NavLink to="/discovery">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M6.5 11C9 11 11 9 11 6.5S9 2 6.5 2 2 4 2 6.5 4 11 6.5 11ZM11 11L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  <span>Discovery</span>
                </NavLink>
                <NavLink to="/map-explorer">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 1C5.24 1 3 3.24 3 6C3 9.5 8 15 8 15S13 9.5 13 6C13 3.24 10.76 1 8 1ZM8 7.5C7.17 7.5 6.5 6.83 6.5 6S7.17 4.5 8 4.5 9.5 5.17 9.5 6 8.83 7.5 8 7.5Z" stroke="currentColor" strokeWidth="1.5"/></svg>
                  <span>Map Explorer</span>
                </NavLink>
                {isFeatureEnabled('listings') && (
                  <NavLink to="/listings">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 2H7V7H2V2ZM9 2H14V7H9V2ZM2 9H7V14H2V9ZM9 9H14V14H9V9Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                    <span>Listings</span>
                  </NavLink>
                )}
                <NavLink to="/triggers">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M9 1L3 9H8L7 15L13 7H8L9 1Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                  <span>Triggers</span>
                </NavLink>
                <NavLink to="/signals">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 12C4 10 4 6 2 4M6 10.5C7 9.5 7 6.5 6 5.5M10 9C10.5 8.5 10.5 7.5 10 7M14 8C14 8 14 8 14 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  <span>Signals</span>
                </NavLink>
              </div>
            </nav>

            <div className="sidebar-footer">
              <NavLink to="/business-profile">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 14V3C2 2.45 2.45 2 3 2H13C13.55 2 14 2.45 14 3V14L8 11L2 14Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                <span>Business Profile</span>
              </NavLink>
              <NavLink to="/settings">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 10C9.1 10 10 9.1 10 8S9.1 6 8 6 6 6.9 6 8 6.9 10 8 10ZM13.5 8C13.5 8.34 13.47 8.66 13.42 8.98L15 10.19L14.1 11.81L12.25 11.14C11.77 11.54 11.21 11.84 10.6 12.02L10.2 14H7.8L7.4 12.02C6.79 11.84 6.23 11.54 5.75 11.14L3.9 11.81L3 10.19L4.58 8.98C4.53 8.66 4.5 8.34 4.5 8S4.53 7.34 4.58 7.02L3 5.81L3.9 4.19L5.75 4.86C6.23 4.46 6.79 4.16 7.4 3.98L7.8 2H10.2L10.6 3.98C11.21 4.16 11.77 4.46 12.25 4.86L14.1 4.19L15 5.81L13.42 7.02C13.47 7.34 13.5 7.66 13.5 8Z" stroke="currentColor" strokeWidth="1.3"/></svg>
                <span>Settings</span>
              </NavLink>
            </div>
          </aside>

          <main className="main">
            {routeElements}
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;
