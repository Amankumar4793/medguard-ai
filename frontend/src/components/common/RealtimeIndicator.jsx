import React, { useState, useEffect } from 'react';
import { getSocket } from '../../services/socket';
import { Wifi, WifiOff } from 'lucide-react';

export default function RealtimeIndicator() {
  const [status, setStatus] = useState('CONNECTING');

  useEffect(() => {
    const socket = getSocket();

    if (socket.connected) {
      setStatus('CONNECTED');
    }

    const onConnect = () => setStatus('CONNECTED');
    const onDisconnect = () => setStatus('DISCONNECTED');
    const onConnectError = () => setStatus('DISCONNECTED');

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('connect_error', onConnectError);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('connect_error', onConnectError);
    };
  }, []);

  const isConnected = status === 'CONNECTED';
  const isConnecting = status === 'CONNECTING';

  const dotColor = isConnected ? '#10b981' : isConnecting ? '#f59e0b' : '#ef4444';
  const textColor = isConnected ? '#10b981' : isConnecting ? '#f59e0b' : '#ef4444';
  const textLabel = isConnected ? 'Live Socket.IO' : isConnecting ? 'Connecting...' : 'Disconnected';

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.45rem',
        padding: '0.25rem 0.6rem',
        borderRadius: '999px',
        backgroundColor: 'rgba(255, 255, 255, 0.04)',
        border: `1px solid ${dotColor}40`,
        fontSize: '0.74rem',
        fontWeight: 600,
        color: textColor,
      }}
      title={`Socket.IO Real-time Connection: ${status}`}
    >
      <span
        style={{
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          backgroundColor: dotColor,
          boxShadow: isConnected ? `0 0 8px ${dotColor}` : 'none',
          animation: isConnected ? 'pulse 2s infinite' : 'none',
        }}
      />
      <span>{textLabel}</span>
    </div>
  );
}
