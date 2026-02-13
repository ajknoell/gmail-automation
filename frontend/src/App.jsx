import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getAuthStatus } from './api/client';
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
import WorkspaceSelector from './components/WorkspaceSelector';
import './App.css';

function NavLink({ to, children }) {
  const location = useLocation();
  const isActive = location.pathname === to || location.pathname.startsWith(to + '/');
  return (
    <Link to={to} className={`nav-link ${isActive ? 'active' : ''}`}>
      {children}
    </Link>
  );
}

function App() {
  const [status, setStatus] = useState({ gmail_connected: false, anthropic_configured: false });

  const refreshStatus = () => {
    getAuthStatus()
      .then((res) => setStatus(res.data))
      .catch(() => {});
  };

  useEffect(() => {
    refreshStatus();
    // Refresh auth status when workspace changes
    const handleWsChange = () => refreshStatus();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  return (
    <Router>
      <div className="app">
        <header className="header">
          <div className="header-content">
            <Link to="/" className="logo">
              <span className="logo-icon">✉️</span>
              Gmail Automation
            </Link>
            <WorkspaceSelector />
            <nav className="nav">
              <NavLink to="/">Dashboard</NavLink>
              <NavLink to="/insights">Insights</NavLink>
              <NavLink to="/replies">Reply Hub</NavLink>
              <NavLink to="/quick-send">Quick Send</NavLink>
              <NavLink to="/campaigns">Campaigns</NavLink>
              <NavLink to="/templates">Templates</NavLink>
              <NavLink to="/contacts">Contacts</NavLink>
              <NavLink to="/listings">Listings</NavLink>
              <NavLink to="/settings">Settings</NavLink>
            </nav>
            <div className="status-indicators">
              <span className={`status-badge ${status.gmail_connected ? 'connected' : 'disconnected'}`}>
                Gmail: {status.gmail_connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </header>

        <main className="main">
          <Routes>
            <Route path="/" element={<Home status={status} />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/quick-send" element={<QuickSend />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaigns/:id" element={<CampaignDetail />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/contacts/:id" element={<ContactDetail />} />
            <Route path="/replies" element={<ReplyHub />} />
            <Route path="/listings" element={<Listings />} />
            <Route path="/settings" element={<Settings onStatusChange={setStatus} />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
