import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  ShieldAlert, 
  LayoutDashboard, 
  Cctv, 
  Camera, 
  BellRing, 
  Activity, 
  BarChart3, 
  Settings,
  Hospital,
  X
} from 'lucide-react';

export default function Sidebar({ alertCount = 0, mobileOpen = false, onClose }) {
  const navItems = [
    { name: 'SOC Overview', path: '/', icon: LayoutDashboard },
    { name: 'Live Monitoring', path: '/monitoring', icon: Cctv },
    { name: 'Cameras', path: '/cameras', icon: Camera },
    { name: 'Active Alerts', path: '/alerts', icon: BellRing, badge: alertCount },
    { name: 'Security Events', path: '/events', icon: Activity },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <div className="sidebar-header" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div className="sidebar-logo">
            <ShieldAlert size={20} />
          </div>
          <div>
            <div className="sidebar-title">MedGuard AI</div>
            <div className="sidebar-subtitle">Healthcare SOC</div>
          </div>
        </div>
        {onClose && (
          <button
            type="button"
            className="sidebar-close-btn"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              end={item.path === '/'}
              onClick={onClose}
            >
              <Icon size={18} />
              <span>{item.name}</span>
              {item.badge > 0 && <span className="nav-badge">{item.badge}</span>}
            </NavLink>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="facility-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <Hospital size={16} color="#0ea5e9" />
            <span className="facility-name">St. Jude Medical Center</span>
          </div>
          <div className="facility-status">
            <span className="pulse-dot"></span>
            <span>AI Surveillance Active</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
