import React from 'react';

export default function StatCard({ label, value, icon: Icon, color = 'cyan', subtitle }) {
  const colorStyles = {
    cyan: { bg: 'rgba(14, 165, 233, 0.15)', text: '#0ea5e9' },
    red: { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444' },
    amber: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b' },
    orange: { bg: 'rgba(249, 115, 22, 0.15)', text: '#f97316' },
    green: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981' },
    teal: { bg: 'rgba(20, 184, 166, 0.15)', text: '#14b8a6' },
    purple: { bg: 'rgba(168, 85, 247, 0.15)', text: '#a855f7' },
    blue: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6' },
  };

  const currentStyle = colorStyles[color] || colorStyles.cyan;

  return (
    <div className="stat-card">
      <div className="stat-card-header">
        <span className="stat-label">{label}</span>
        {Icon && (
          <div
            className="stat-icon"
            style={{ backgroundColor: currentStyle.bg, color: currentStyle.text }}
          >
            <Icon size={18} />
          </div>
        )}
      </div>
      <div className="stat-value">{value ?? '—'}</div>
      {subtitle && <div className="stat-footer">{subtitle}</div>}
    </div>
  );
}
