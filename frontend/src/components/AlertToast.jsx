import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSocket } from '../services/socket';
import { playAlertChime } from '../utils/audio';
import { AlertTriangle, ShieldAlert, X, ArrowRight, Camera } from 'lucide-react';

export default function AlertToast({ onSelectAlert }) {
  const [toasts, setToasts] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    const socket = getSocket();

    const handleNewAlert = (alertData) => {
      // Play audio chime for new security alert
      playAlertChime(alertData.severity);

      const toastId = Date.now() + Math.random();
      const newToast = {
        id: toastId,
        alert: alertData,
      };

      setToasts((prev) => [newToast, ...prev.slice(0, 4)]); // max 5 concurrent toasts

      // Auto dismiss after 8 seconds
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== toastId));
      }, 8000);
    };

    socket.on('alert_new', handleNewAlert);
    return () => {
      socket.off('alert_new', handleNewAlert);
    };
  }, []);

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handleTriage = (alert) => {
    if (onSelectAlert) {
      onSelectAlert(alert);
    } else {
      navigate('/alerts');
    }
  };

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '1.5rem',
        right: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        zIndex: 9999,
        maxWidth: '420px',
        width: '100%',
        pointerEvents: 'none',
      }}
    >
      {toasts.map(({ id, alert }) => {
        const isCritical = alert.severity === 'CRITICAL';
        const isHigh = alert.severity === 'HIGH';
        const borderColor = isCritical ? '#ef4444' : isHigh ? '#f97316' : '#eab308';
        const glowColor = isCritical
          ? 'rgba(239, 68, 68, 0.35)'
          : isHigh
          ? 'rgba(249, 115, 22, 0.3)'
          : 'rgba(234, 179, 8, 0.25)';

        return (
          <div
            key={id}
            style={{
              pointerEvents: 'auto',
              backgroundColor: '#0f172a',
              border: `1px solid ${borderColor}`,
              boxShadow: `0 10px 25px -5px rgba(0, 0, 0, 0.8), 0 0 15px ${glowColor}`,
              borderRadius: '8px',
              padding: '1rem',
              color: '#fff',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.6rem',
              animation: 'slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {isCritical ? (
                  <ShieldAlert size={18} color="#ef4444" style={{ animation: 'pulse 1.5s infinite' }} />
                ) : (
                  <AlertTriangle size={18} color={borderColor} />
                )}
                <span
                  style={{
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    color: borderColor,
                    letterSpacing: '0.05em',
                  }}
                >
                  {alert.severity} SECURITY ALERT
                </span>
              </div>
              <button
                onClick={() => removeToast(id)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '2px',
                  lineHeight: 0,
                }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
              {alert.title || alert.description}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8' }}>
              <span>{alert.camera_name || `Camera #${alert.camera_id || ''}`}</span>
              <span>{alert.camera_location || 'Hospital Zone'}</span>
            </div>

            {/* Thumbnail preview if snapshot captured */}
            {alert.snapshot_path && (
              <div
                style={{
                  borderRadius: '4px',
                  overflow: 'hidden',
                  maxHeight: '110px',
                  backgroundColor: '#000',
                  border: '1px solid #334155',
                  display: 'flex',
                  justifyContent: 'center',
                }}
              >
                <img
                  src={alert.snapshot_path}
                  alt="Incident Snapshot"
                  style={{ width: '100%', objectFit: 'cover' }}
                />
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.2rem' }}>
              <button
                onClick={() => {
                  removeToast(id);
                  handleTriage(alert);
                }}
                className="btn btn-primary"
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.75rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  backgroundColor: borderColor,
                }}
              >
                <span>Triage Incident</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
