import React, { useState, useEffect } from 'react';
import { Clock, ShieldCheck, Menu } from 'lucide-react';
import NotificationCenter from '../NotificationCenter';
import RealtimeIndicator from './RealtimeIndicator';

export default function Navbar({ title = 'Security Operations Center', onToggleMobileMenu }) {
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toTimeString().split(' ')[0] + ' UTC' + (now.getTimezoneOffset() > 0 ? '-' : '+') + Math.abs(now.getTimezoneOffset() / 60));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="top-header">
      <div className="header-left">
        {onToggleMobileMenu && (
          <button
            type="button"
            className="hamburger-btn"
            onClick={onToggleMobileMenu}
            aria-label="Toggle navigation menu"
          >
            <Menu size={20} />
          </button>
        )}
        <h1 className="page-title">{title}</h1>
      </div>
      <div className="header-right">
        <RealtimeIndicator />
        <div className="badge-facility" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: '#0ea5e9' }}>
          <ShieldCheck size={16} />
          <span>Physical Security Active</span>
        </div>
        <div className="system-clock" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <Clock size={13} />
          <span>{timeStr}</span>
        </div>
        <NotificationCenter />
      </div>
    </header>
  );
}

