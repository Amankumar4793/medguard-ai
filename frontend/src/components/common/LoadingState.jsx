import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingState({ type = 'spinner', message = 'Loading surveillance data...', count = 3, rows = 5 }) {
  if (type === 'cards') {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', width: '100%' }}>
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            style={{
              height: '110px',
              backgroundColor: 'var(--bg-card, #162032)',
              borderRadius: 'var(--radius-md, 10px)',
              border: '1px solid var(--border-color, #1f2d45)',
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              animation: 'pulse 1.8s infinite',
            }}
          >
            <div style={{ height: '14px', width: '60%', backgroundColor: '#1e293b', borderRadius: '4px' }} />
            <div style={{ height: '28px', width: '40%', backgroundColor: '#334155', borderRadius: '4px' }} />
            <div style={{ height: '12px', width: '75%', backgroundColor: '#1e293b', borderRadius: '4px' }} />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'table') {
    return (
      <div style={{ width: '100%', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div
            key={i}
            style={{
              height: '42px',
              width: '100%',
              backgroundColor: 'rgba(255,255,255,0.03)',
              borderRadius: '6px',
              animation: 'pulse 1.8s infinite',
            }}
          />
        ))}
      </div>
    );
  }

  // Default: Spinner
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 1rem',
        color: 'var(--text-muted, #94a3b8)',
        gap: '0.75rem',
      }}
    >
      <Loader2 size={26} className="spin" color="var(--accent-cyan, #0ea5e9)" />
      <span style={{ fontSize: '0.84rem' }}>{message}</span>
    </div>
  );
}
