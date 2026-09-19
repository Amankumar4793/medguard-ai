import React, { useState } from 'react';

const COLOR_MAP = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#10b981',
  NEW: '#0ea5e9',
  ACKNOWLEDGED: '#f59e0b',
  INVESTIGATING: '#a855f7',
  RESOLVED: '#10b981',
};

export default function DonutChart({
  data = {},
  title = '',
  size = 170,
  strokeWidth = 22,
}) {
  const [hoverKey, setHoverKey] = useState(null);

  // Parse dictionary or array
  const rawEntries = Array.isArray(data)
    ? data
    : Object.entries(data).map(([k, v]) => ({
        label: k,
        value: Number(v) || 0,
        color: COLOR_MAP[k.toUpperCase()] || '#64748b',
      }));

  const entries = rawEntries.map((e) => ({
    label: e.label || e.name || 'Other',
    value: Number(e.value !== undefined ? e.value : e.count) || 0,
    color: e.color || COLOR_MAP[(e.label || e.name || '').toUpperCase()] || '#64748b',
  }));

  const total = entries.reduce((acc, curr) => acc + curr.value, 0);

  if (total === 0) {
    return (
      <div style={{ height: size + 40, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted, #64748b)', fontSize: '0.8rem' }}>
        No categorized records recorded.
      </div>
    );
  }

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Calculate arc slices
  let accumulatedOffset = 0;
  const slices = entries
    .filter((e) => e.value > 0)
    .map((entry) => {
      const sliceLength = (entry.value / total) * circumference;
      const strokeDashoffset = -accumulatedOffset;
      accumulatedOffset += sliceLength;
      const pct = Math.round((entry.value / total) * 100);
      return {
        ...entry,
        sliceLength,
        strokeDashoffset,
        pct,
      };
    });

  const activeEntry = hoverKey ? entries.find((e) => e.label === hoverKey) : null;

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1.25rem', width: '100%', flexWrap: 'wrap' }}>
      {/* Donut SVG */}
      <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255, 255, 255, 0.05)"
            strokeWidth={strokeWidth}
          />
          {/* Slices */}
          {slices.map((slice, i) => (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={slice.color}
              strokeWidth={hoverKey === slice.label ? strokeWidth + 3 : strokeWidth}
              strokeDasharray={`${slice.sliceLength} ${circumference}`}
              strokeDashoffset={slice.strokeDashoffset}
              style={{
                transition: 'stroke-width 0.2s ease, opacity 0.2s ease',
                cursor: 'pointer',
                opacity: hoverKey && hoverKey !== slice.label ? 0.4 : 1,
              }}
              onMouseEnter={() => setHoverKey(slice.label)}
              onMouseLeave={() => setHoverKey(null)}
            />
          ))}
        </svg>

        {/* Center Total Count */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
            pointerEvents: 'none',
          }}
        >
          <span style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f8fafc', lineHeight: 1 }}>
            {activeEntry ? activeEntry.value : total}
          </span>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '3px' }}>
            {activeEntry ? activeEntry.label : 'TOTAL'}
          </span>
        </div>
      </div>

      {/* Legend List */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.45rem', minWidth: '140px' }}>
        {entries.map((entry, idx) => {
          const pct = total > 0 ? Math.round((entry.value / total) * 100) : 0;
          const isHovered = hoverKey === entry.label;

          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '0.78rem',
                padding: '0.2rem 0.4rem',
                borderRadius: '4px',
                backgroundColor: isHovered ? 'rgba(255,255,255,0.05)' : 'transparent',
                cursor: 'pointer',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={() => setHoverKey(entry.label)}
              onMouseLeave={() => setHoverKey(null)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }} />
                <span style={{ color: isHovered ? '#fff' : 'var(--text-secondary, #94a3b8)', fontWeight: isHovered ? 600 : 400 }}>
                  {entry.label}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontWeight: 600, color: '#f8fafc' }}>{entry.value}</span>
                <span style={{ color: 'var(--text-muted, #64748b)', fontSize: '0.72rem', minWidth: '28px', textAlign: 'right' }}>
                  {pct}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
