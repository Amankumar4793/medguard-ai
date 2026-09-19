import React from 'react';
import { Sliders, Brain, ShieldAlert } from 'lucide-react';

export default function RiskBreakdown({
  ruleRisk = 0,
  mlRisk = 0,
  finalRisk = null,
  ruleWeight = 0.70,
  mlWeight = 0.30,
  indicators = [],
  showFormula = true,
}) {
  const rScore = Math.round(Number(ruleRisk) || 0);
  const mScore = Math.round(Number(mlRisk) || 0);
  const fScore =
    finalRisk !== null
      ? Math.round(Number(finalRisk))
      : Math.round(rScore * ruleWeight + mScore * mlWeight);

  const rPct = Math.round(ruleWeight * 100);
  const mPct = Math.round(mlWeight * 100);

  const getRiskColor = (s) => {
    if (s >= 85) return '#ef4444';
    if (s >= 65) return '#f97316';
    if (s >= 40) return '#f59e0b';
    return '#10b981';
  };

  const finalColor = getRiskColor(fScore);

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-secondary, #111827)',
        padding: '1rem',
        borderRadius: 'var(--radius-md, 10px)',
        border: '1px solid var(--border-color, #1f2d45)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.85rem',
      }}
    >
      {/* Header with Final Score */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.84rem', fontWeight: 600, color: '#f8fafc' }}>
          <Sliders size={16} color="var(--accent-cyan, #0ea5e9)" />
          <span>Explainable Threat Risk Fusion</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.35rem' }}>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted, #94a3b8)' }}>Final Risk:</span>
          <span style={{ fontSize: '1.1rem', fontWeight: 800, color: finalColor }}>{fScore}</span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #94a3b8)' }}>/ 100</span>
        </div>
      </div>

      {/* Progress Bars Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Rule Risk Bar */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', marginBottom: '0.3rem' }}>
            <span style={{ color: 'var(--text-muted, #94a3b8)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <ShieldAlert size={12} color="#0ea5e9" />
              <span>Rule Risk ({rPct}%)</span>
            </span>
            <span style={{ fontWeight: 600, color: '#f8fafc' }}>{rScore}%</span>
          </div>
          <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${Math.min(100, Math.max(0, rScore))}%`,
                height: '100%',
                backgroundColor: '#0ea5e9',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>

        {/* ML Risk Bar */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', marginBottom: '0.3rem' }}>
            <span style={{ color: 'var(--text-muted, #94a3b8)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <Brain size={12} color="#a855f7" />
              <span>ML Isolation Forest ({mPct}%)</span>
            </span>
            <span style={{ fontWeight: 600, color: '#f8fafc' }}>{mScore}%</span>
          </div>
          <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${Math.min(100, Math.max(0, mScore))}%`,
                height: '100%',
                backgroundColor: '#a855f7',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>
      </div>

      {/* Mathematical Formulation Tag */}
      {showFormula && (
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted, #64748b)', fontFamily: 'var(--font-mono, monospace)', display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '0.5rem' }}>
          <span>Formula: ({ruleWeight} × Rule) + ({mlWeight} × ML)</span>
          <span>= {fScore}</span>
        </div>
      )}

      {/* Behavioral Indicators */}
      {indicators && indicators.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.1rem' }}>
          {indicators.map((ind, i) => (
            <span
              key={i}
              style={{
                fontSize: '0.7rem',
                backgroundColor: 'rgba(168, 85, 247, 0.12)',
                color: '#d8b4fe',
                padding: '0.15rem 0.45rem',
                borderRadius: '4px',
                border: '1px solid rgba(168, 85, 247, 0.25)',
              }}
            >
              • {ind}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
