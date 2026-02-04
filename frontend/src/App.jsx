import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getAuthStatus } from './api/client';
import Home from './pages/Home';
import Campaigns from './pages/Campaigns';
import CampaignDetail from './pages/CampaignDetail';
import Templates from './pages/Templates';
import Settings from './pages/Settings';
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

  useEffect(() => {
    getAuthStatus()
      .then((res) => setStatus(res.data))
      .catch(() => {});
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
            <nav className="nav">
              <NavLink to="/">Dashboard</NavLink>
              <NavLink to="/campaigns">Campaigns</NavLink>
              <NavLink to="/templates">Templates</NavLink>
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
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaigns/:id" element={<CampaignDetail />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/settings" element={<Settings onStatusChange={setStatus} />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
