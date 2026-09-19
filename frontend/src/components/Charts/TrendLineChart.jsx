import React, { useState } from 'react';

export default function TrendLineChart({
  data = [],
  metric = 'events', // 'events' or 'risk'
  height = 240,
  title = 'Surveillance Activity Over Time',
}) {
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!data || data.length === 0) {
    return (
      <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted, #64748b)', fontSize: '0.82rem' }}>
        Insufficient historical data for this period.
      </div>
    );
  }

  const svgWidth = 600;
  const svgHeight = height;
  const padding = { top: 25, right: 25, bottom: 40, left: 45 };
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  // Determine Y-axis max
  let maxY = 10;
  if (metric === 'events') {
    const maxVal = Math.max(...data.map((d) => d.events || 0), 1);
    maxY = Math.ceil(maxVal * 1.25);
  } else {
    // Risk score is 0 - 100
    maxY = 100;
  }

  // Map data to SVG coordinates
  const points = data.map((d, i) => {
    const x = padding.left + (i / Math.max(data.length - 1, 1)) * chartWidth;
    let val = 0;
    if (metric === 'events') {
      val = d.events || 0;
    } else {
      val = d.avg_risk ?? d.avg_final_risk ?? 0;
    }
    const y = padding.top + chartHeight - (val / maxY) * chartHeight;
    return { x, y, val, item: d };
  });

  // Polyline points string
  const polylinePoints = points.map((p) => `${p.x},${p.y}`).join(' ');

  // Area polygon points string
  const areaPoints = `${points[0]?.x || 0},${padding.top + chartHeight} ${polylinePoints} ${
    points[points.length - 1]?.x || 0
  },${padding.top + chartHeight}`;

  const primaryColor = metric === 'events' ? '#0ea5e9' : '#a855f7';
  const fillColor = metric === 'events' ? 'rgba(14, 165, 233, 0.15)' : 'rgba(168, 85, 247, 0.15)';

  // Y-axis grid ticks (4 ticks)
  const yTicks = [0, 0.33, 0.66, 1.0].map((ratio) => {
    const y = padding.top + chartHeight - ratio * chartHeight;
    const value = Math.round(ratio * maxY);
    return { y, value };
  });

  const activePoint = hoverIndex !== null ? points[hoverIndex] : null;

  return (
    <div style={{ width: '100%', position: 'relative' }}>
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {/* Y Gridlines and Labels */}
        {yTicks.map((t, idx) => (
          <g key={idx}>
            <line
              x1={padding.left}
              y1={t.y}
              x2={padding.left + chartWidth}
              y2={t.y}
              stroke="rgba(255, 255, 255, 0.06)"
              strokeDasharray={idx === 0 ? 'none' : '3 3'}
            />
            <text
              x={padding.left - 8}
              y={t.y + 4}
              fill="#64748b"
              fontSize="10"
              fontFamily="var(--font-mono, monospace)"
              textAnchor="end"
            >
              {t.value}
            </text>
          </g>
        ))}

        {/* X Axis Labels (sample 6 ticks) */}
        {points.map((p, i) => {
          const step = Math.max(1, Math.floor(data.length / 6));
          if (i % step === 0 || i === data.length - 1) {
            return (
              <text
                key={i}
                x={p.x}
                y={padding.top + chartHeight + 18}
                fill="#64748b"
                fontSize="10"
                fontFamily="var(--font-mono, monospace)"
                textAnchor="middle"
              >
                {p.item.label}
              </text>
            );
          }
          return null;
        })}

        {/* Area fill */}
        <polygon points={areaPoints} fill={fillColor} />

        {/* Main Line */}
        <polyline
          fill="none"
          stroke={primaryColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={polylinePoints}
        />

        {/* Secondary comparison line for Risk metric (Rule Risk vs ML Risk) */}
        {metric === 'risk' && (
          <>
            <polyline
              fill="none"
              stroke="#0ea5e9"
              strokeWidth="1.5"
              strokeDasharray="4 3"
              points={data
                .map((d, i) => {
                  const x = padding.left + (i / Math.max(data.length - 1, 1)) * chartWidth;
                  const y = padding.top + chartHeight - ((d.avg_rule_risk || 0) / maxY) * chartHeight;
                  return `${x},${y}`;
                })
                .join(' ')}
            />
            <polyline
              fill="none"
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="2 2"
              points={data
                .map((d, i) => {
                  const x = padding.left + (i / Math.max(data.length - 1, 1)) * chartWidth;
                  const y = padding.top + chartHeight - ((d.avg_ml_risk || 0) / maxY) * chartHeight;
                  return `${x},${y}`;
                })
                .join(' ')}
            />
          </>
        )}

        {/* Interactive Hover Guides & Data Points */}
        {points.map((p, i) => (
          <g key={i}>
            {/* Invisible wide capture area for easy hovering */}
            <rect
              x={p.x - chartWidth / (data.length * 2)}
              y={padding.top}
              width={chartWidth / data.length}
              height={chartHeight}
              fill="transparent"
              onMouseEnter={() => setHoverIndex(i)}
            />
            {hoverIndex === i && (
              <>
                <line
                  x1={p.x}
                  y1={padding.top}
                  x2={p.x}
                  y2={padding.top + chartHeight}
                  stroke="rgba(255, 255, 255, 0.2)"
                  strokeDasharray="2 2"
                />
                <circle cx={p.x} cy={p.y} r="5" fill={primaryColor} stroke="#fff" strokeWidth="2" />
              </>
            )}
          </g>
        ))}
      </svg>

      {/* Floating Tooltip Box */}
      {activePoint && (
        <div
          style={{
            position: 'absolute',
            top: '8px',
            right: '12px',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid #334155',
            borderRadius: '6px',
            padding: '0.45rem 0.75rem',
            fontSize: '0.74rem',
            color: '#f8fafc',
            boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
            pointerEvents: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--accent-cyan, #0ea5e9)' }}>
            Time: {activePoint.item.label}
          </div>
          {metric === 'events' ? (
            <div>
              Security Events: <strong>{activePoint.item.events || 0}</strong>
            </div>
          ) : (
            <>
              <div>Threat Score: <strong>{Math.round(activePoint.item.avg_risk ?? activePoint.item.avg_final_risk ?? 0)} / 100</strong></div>
              <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>
                Incident Alerts: {activePoint.item.alerts || 0}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
