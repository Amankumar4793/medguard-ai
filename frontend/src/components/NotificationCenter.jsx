import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Volume2, VolumeX, ShieldAlert, AlertTriangle, ExternalLink, Check } from 'lucide-react';
import { AlertService } from '../services/api';
import { getSocket } from '../services/socket';
import { isAudioMuted, setAudioMuted } from '../utils/audio';

export default function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [soundMuted, setSoundMuted] = useState(isAudioMuted());
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  const fetchActiveAlerts = async () => {
    try {
      const res = await AlertService.getAlerts({ status: 'NEW', limit: 8 });
      if (res.success) {
        setAlerts(res.alerts);
        setUnreadCount(res.total || res.alerts.length);
      }
    } catch (err) {
      console.debug('Could not fetch active alerts for notification center:', err);
    }
  };

  useEffect(() => {
    fetchActiveAlerts();

    const socket = getSocket();
    const handleNewAlert = (newAlert) => {
      if (!newAlert || typeof newAlert !== 'object' || !newAlert.id) return;
      setAlerts((prev) => [newAlert, ...prev.filter((a) => a.id !== newAlert.id).slice(0, 7)]);
      setUnreadCount((c) => c + 1);
    };

    const handleUpdatedAlert = (updatedAlert) => {
      if (!updatedAlert || typeof updatedAlert !== 'object' || !updatedAlert.id) return;
      if (updatedAlert.status !== 'NEW') {
        setAlerts((prev) => prev.filter((a) => a.id !== updatedAlert.id));
        setUnreadCount((c) => Math.max(0, c - 1));
      }
    };

    socket.on('alert_new', handleNewAlert);
    socket.on('alert_updated', handleUpdatedAlert);

    return () => {
      socket.off('alert_new', handleNewAlert);
      socket.off('alert_updated', handleUpdatedAlert);
    };
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleSound = () => {
    const nextState = !soundMuted;
    setSoundMuted(nextState);
    setAudioMuted(nextState);
  };

  const handleAlertClick = (alertId) => {
    setIsOpen(false);
    navigate('/alerts');
  };

  return (
    <div style={{ position: 'relative' }} ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: 'none',
          border: 'none',
          color: unreadCount > 0 ? '#f8fafc' : '#94a3b8',
          cursor: 'pointer',
          padding: '0.4rem',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          transition: 'all 0.2s ease',
        }}
        title="Security Notifications"
      >
        <Bell size={19} color={unreadCount > 0 ? '#f59e0b' : '#94a3b8'} />
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '1px',
              right: '1px',
              backgroundColor: '#ef4444',
              color: '#fff',
              fontSize: '0.65rem',
              fontWeight: 700,
              borderRadius: '999px',
              padding: '0.1rem 0.35rem',
              minWidth: '16px',
              textAlign: 'center',
              boxShadow: '0 0 8px rgba(239, 68, 68, 0.7)',
            }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Notification Dropdown Popover */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '360px',
            backgroundColor: 'var(--bg-card, #0f172a)',
            border: '1px solid var(--border-color, #1e293b)',
            borderRadius: '8px',
            boxShadow: '0 15px 35px rgba(0,0,0,0.6)',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          {/* Dropdown Header */}
          <div
            style={{
              padding: '0.75rem 1rem',
              borderBottom: '1px solid var(--border-color, #1e293b)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'rgba(255,255,255,0.02)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#fff' }}>
                Incident Notifications
              </span>
              {unreadCount > 0 && (
                <span
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    color: '#ef4444',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '0.1rem 0.4rem',
                    borderRadius: '4px',
                  }}
                >
                  {unreadCount} NEW
                </span>
              )}
            </div>

            {/* Audio Toggle Button */}
            <button
              onClick={toggleSound}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: soundMuted ? '#64748b' : '#10b981',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
                fontSize: '0.72rem',
                padding: '0.2rem 0.4rem',
                borderRadius: '4px',
              }}
              title={soundMuted ? 'Unmute alert sounds' : 'Mute alert sounds'}
            >
              {soundMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
              <span>{soundMuted ? 'Muted' : 'Audio On'}</span>
            </button>
          </div>

          {/* Alert List */}
          <div style={{ maxHeight: '340px', overflowY: 'auto' }}>
            {alerts.length === 0 ? (
              <div
                style={{
                  padding: '2rem',
                  textAlign: 'center',
                  color: 'var(--text-muted, #64748b)',
                  fontSize: '0.8rem',
                }}
              >
                No unacknowledged security alerts. Facility perimeter secure.
              </div>
            ) : (
              alerts.map((alt) => {
                const isCrit = alt.severity === 'CRITICAL';
                const isHigh = alt.severity === 'HIGH';
                const badgeColor = isCrit ? '#ef4444' : isHigh ? '#f97316' : '#eab308';

                return (
                  <div
                    key={alt.id}
                    onClick={() => handleAlertClick(alt.id)}
                    style={{
                      padding: '0.75rem 1rem',
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                      display: 'flex',
                      gap: '0.75rem',
                      alignItems: 'flex-start',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.03)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <div style={{ marginTop: '2px' }}>
                      {isCrit ? (
                        <ShieldAlert size={16} color="#ef4444" />
                      ) : (
                        <AlertTriangle size={16} color={badgeColor} />
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: badgeColor }}>
                          {alt.severity}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                          {alt.created_at ? new Date(alt.created_at).toLocaleTimeString() : ''}
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: '0.8rem',
                          fontWeight: 500,
                          color: '#f1f5f9',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {alt.title || alt.description}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '0.15rem' }}>
                        {alt.camera_name || `Camera #${alt.camera_id || ''}`} • {alt.camera_location || 'Zone'}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Dropdown Footer */}
          <div
            style={{
              padding: '0.6rem 1rem',
              borderTop: '1px solid var(--border-color, #1e293b)',
              textAlign: 'center',
              backgroundColor: 'rgba(255,255,255,0.02)',
            }}
          >
            <button
              onClick={() => {
                setIsOpen(false);
                navigate('/alerts');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent-cyan, #0ea5e9)',
                cursor: 'pointer',
                fontSize: '0.78rem',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
              }}
            >
              <span>Open Incident Command Queue</span>
              <ExternalLink size={12} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
