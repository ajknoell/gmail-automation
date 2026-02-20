import { Link, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { path: '/brief', label: 'Brief', icon: '📋' },
  { path: '/discovery', label: 'Discover', icon: '🔍' },
  { path: '/replies', label: 'Replies', icon: '💬' },
  { path: '/contacts', label: 'Contacts', icon: '👥' },
];

function MobileLayout({ children }) {
  const location = useLocation();

  return (
    <div className="mobile-layout">
      <div className="mobile-content">
        {children}
      </div>
      <nav className="mobile-bottom-nav">
        {NAV_ITEMS.map(item => {
          const isActive = location.pathname === item.path || location.pathname.startsWith(item.path + '/');
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`mobile-nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="mobile-nav-icon">{item.icon}</span>
              <span className="mobile-nav-label">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

export default MobileLayout;
