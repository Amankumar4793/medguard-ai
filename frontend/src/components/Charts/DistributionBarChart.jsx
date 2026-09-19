import React from 'react';

export default function DistributionBarChart({
  items = [],
  maxItems = 6,
  emptyMessage = 'No category records found.',
}) {
  if (!items || items.length === 0) {
    return (
      <div style={{ padding: '2rem 1rem', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '0.8rem' }}>
        {emptyMessage}
      </div>
    );
  }

  const displayItems = items.slice(0, maxItems);
  const maxCount = Math.max(...displayItems.map((d) => d.count || 0), 1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', width: '100%' }}>
      {displayItems.map((item, idx) => {
        const pct = Math.round(((item.count || 0) / maxCount) * 100);
        const avgRisk = item.avg_risk !== undefined ? Math.round(item.avg_risk) : null;

        let riskColor = '#10b981';
        if (avgRisk !== null) {
          if (avgRisk >= 85) riskColor = '#ef4444';
          else if (avgRisk >= 65) riskColor = '#f97316';
          else if (avgRisk >= 40) riskColor = '#f59e0b';
        }

        return (
          <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
              <span style={{ fontWeight: 500, color: '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%' }}>
                {item.label || item.type || item.name}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                {avgRisk !== null && (
                  <span style={{ fontSize: '0.7rem', color: riskColor, fontWeight: 600 }}>
                    Avg Risk: {avgRisk}
                  </span>
                )}
                <span style={{ fontWeight: 700, color: '#f8fafc', fontFamily: 'var(--font-mono, monospace)', minWidth: '24px', textAlign: 'right' }}>
                  {item.count}
                </span>
              </div>
            </div>

            {/* Progress Track */}
            <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255, 255, 255, 0.06)', borderRadius: '3px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${pct}%`,
                  height: '100%',
                  backgroundColor: 'var(--accent-cyan, #0ea5e9)',
                  borderRadius: '3px',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
