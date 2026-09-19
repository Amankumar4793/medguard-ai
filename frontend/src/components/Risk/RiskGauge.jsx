import React from 'react';

export default function RiskGauge({ score = 0, size = 120, showLabel = true, label = 'Threat Risk' }) {
  const clampedScore = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));

  // Color thresholds
  let color = '#10b981'; // LOW
  let level = 'LOW';
  if (clampedScore >= 85) {
    color = '#ef4444'; // CRITICAL
    level = 'CRITICAL';
  } else if (clampedScore >= 65) {
    color = '#f97316'; // HIGH
    level = 'HIGH';
  } else if (clampedScore >= 40) {
    color = '#f59e0b'; // MEDIUM
    level = 'MEDIUM';
  }

  // SVG parameters
  const strokeWidth = size * 0.1;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  // Use a 240-degree arc gauge
  const arcLength = circumference * (240 / 360);
  const strokeDashoffset = arcLength - (clampedScore / 100) * arcLength;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'relative', width: size, height: size, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(150deg)' }}>
          {/* Background Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
          />
          {/* Filled Value Arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.6s ease, stroke 0.4s ease' }}
          />
        </svg>

        {/* Center Score Readout */}
        <div
          style={{
            position: 'absolute',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
          }}
        >
          <span style={{ fontSize: size * 0.28, fontWeight: 800, color: '#f8fafc', lineHeight: 1 }}>
            {clampedScore}
          </span>
          <span style={{ fontSize: size * 0.11, fontWeight: 700, color: color, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '2px' }}>
            {level}
          </span>
        </div>
      </div>

      {showLabel && (
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #94a3b8)', marginTop: '0.2rem' }}>
          {label}
        </span>
      )}
    </div>
  );
}
