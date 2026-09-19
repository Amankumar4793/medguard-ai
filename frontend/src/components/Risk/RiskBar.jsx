import React from 'react';

export default function RiskBar({ score = 0, width = '100%', showValue = true }) {
  const s = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));

  let color = '#10b981';
  if (s >= 85) color = '#ef4444';
  else if (s >= 65) color = '#f97316';
  else if (s >= 40) color = '#f59e0b';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width }}>
      <div style={{ flex: 1, height: '6px', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
        <div
          style={{
            width: `${s}%`,
            height: '100%',
            backgroundColor: color,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
      {showValue && (
        <span style={{ fontSize: '0.75rem', fontWeight: 700, color, fontFamily: 'var(--font-mono, monospace)', minWidth: '24px', textAlign: 'right' }}>
          {s}
        </span>
      )}
    </div>
  );
}
