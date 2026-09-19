import React from 'react';
import { ShieldCheck } from 'lucide-react';

export default function EmptyState({
  icon: Icon = ShieldCheck,
  title = 'No Records Found',
  description = 'There are currently no records or events to display in this view.',
  action = null,
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 1.5rem',
        textAlign: 'center',
        color: 'var(--text-muted, #64748b)',
        backgroundColor: 'rgba(255, 255, 255, 0.01)',
        borderRadius: 'var(--radius-md, 10px)',
        border: '1px dashed var(--border-color, #1f2d45)',
        margin: '0.5rem 0',
      }}
    >
      <div
        style={{
          width: '46px',
          height: '46px',
          borderRadius: '50%',
          backgroundColor: 'rgba(14, 165, 233, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--accent-cyan, #0ea5e9)',
          marginBottom: '0.85rem',
        }}
      >
        <Icon size={22} />
      </div>
      <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.35rem' }}>
        {title}
      </h4>
      <p style={{ fontSize: '0.8rem', maxWidth: '380px', lineHeight: 1.5, marginBottom: action ? '1rem' : 0 }}>
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}
