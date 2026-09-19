import React from 'react';

export default function StatusBadge({ status, type = 'risk' }) {
  if (!status) return null;

  const cleanStatus = status.toString().toUpperCase();
  let badgeClass = 'badge-neutral';

  if (cleanStatus === 'CRITICAL' || cleanStatus === 'HIGH' || cleanStatus === 'NEW') {
    badgeClass = cleanStatus === 'CRITICAL' ? 'badge-critical' : 'badge-high';
  } else if (cleanStatus === 'MEDIUM' || cleanStatus === 'INVESTIGATING') {
    badgeClass = 'badge-medium';
  } else if (cleanStatus === 'LOW' || cleanStatus === 'RESOLVED' || cleanStatus === 'ACKNOWLEDGED' || cleanStatus === 'ONLINE' || cleanStatus === 'HEALTHY') {
    badgeClass = 'badge-low';
  }

  return (
    <span className={`badge ${badgeClass}`}>
      {cleanStatus}
    </span>
  );
}
