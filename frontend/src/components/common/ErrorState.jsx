import React from 'react';
import { AlertCircle, RotateCw } from 'lucide-react';

export default function ErrorState({
  title = 'Failed to Load Data',
  message = 'An error occurred while communicating with the security backend.',
  onRetry = null,
}) {
  return (
    <div
      style={{
        padding: '1.5rem',
        borderRadius: 'var(--radius-md, 10px)',
        backgroundColor: 'rgba(239, 68, 68, 0.08)',
        border: '1px solid rgba(239, 68, 68, 0.25)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        gap: '0.6rem',
        margin: '1rem 0',
      }}
    >
      <AlertCircle size={24} color="#ef4444" />
      <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f8fafc' }}>
        {title}
      </div>
      <p style={{ fontSize: '0.8rem', color: '#fca5a5', maxWidth: '420px', lineHeight: 1.4 }}>
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn btn-outline"
          style={{
            marginTop: '0.5rem',
            fontSize: '0.78rem',
            borderColor: 'rgba(239, 68, 68, 0.4)',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          <RotateCw size={13} />
          <span>Retry Request</span>
        </button>
      )}
    </div>
  );
}
