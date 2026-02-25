import { Link, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { path: '/', label: 'Today', icon: 'V', exact: true },
  { path: '/prospects', label: 'Prospects', icon: 'P' },
  { path: '/campaigns', label: 'Campaigns', icon: 'C' },
  { path: '/replies', label: 'Inbox', icon: 'I' },
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
          const isActive = item.exact
            ? location.pathname === item.path
            : location.pathname === item.path || location.pathname.startsWith(item.path + '/');
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
