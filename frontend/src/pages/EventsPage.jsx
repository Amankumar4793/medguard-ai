import React, { useState, useEffect, useMemo } from 'react';
import { EventService, CameraService } from '../services/api';
import { Activity, Search, Shield, Filter, Eye, Camera, Brain, X } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import EmptyState from '../components/common/EmptyState';
import LoadingState from '../components/common/LoadingState';
import RiskBar from '../components/Risk/RiskBar';
import RiskBreakdown from '../components/Risk/RiskBreakdown';

export default function EventsPage() {
  const [events, setEvents] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCamera, setFilterCamera] = useState('');
  const [filterRisk, setFilterRisk] = useState('');
  const [onlyAnomalies, setOnlyAnomalies] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filterCamera) params.camera_id = filterCamera;
      if (filterRisk) params.risk_level = filterRisk;

      const [eventsRes, camsRes] = await Promise.all([
        EventService.getEvents(params),
        CameraService.getCameras()
      ]);

      if (eventsRes.success) setEvents(eventsRes.events);
      if (camsRes.success) setCameras(camsRes.cameras);
    } catch (err) {
      console.error('Failed to load security events:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filterCamera, filterRisk]);

  const filteredEvents = useMemo(() => {
    return events.filter((evt) => {
      if (onlyAnomalies) {
        const isAnom = evt.metadata?.ml_anomaly === true || evt.metadata?.ml_anomalous === true;
        if (!isAnom) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesDesc = (evt.description || '').toLowerCase().includes(q);
        const matchesType = (evt.event_type || '').toLowerCase().includes(q);
        const matchesCam = (evt.camera_name || '').toLowerCase().includes(q);
        if (!matchesDesc && !matchesType && !matchesCam) return false;
      }
      return true;
    });
  }, [events, onlyAnomalies, searchQuery]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Security Event Audit Log</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Complete audit trail of physical zone intrusions, loitering violations, and security engine detections.
          </p>
        </div>

        {/* Filter Controls */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Search Box */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '10px' }} />
            <input
              type="text"
              placeholder="Search detections..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                padding: '0.45rem 0.85rem 0.45rem 2rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.82rem',
                outline: 'none',
                minWidth: '180px',
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: '8px',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '2px',
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Camera Filter */}
          <select
            value={filterCamera}
            onChange={(e) => setFilterCamera(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              padding: '0.45rem 0.85rem',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.82rem',
              outline: 'none'
            }}
          >
            <option value="">All Cameras</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          {/* Risk Level Filter */}
          <select
            value={filterRisk}
            onChange={(e) => setFilterRisk(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              padding: '0.45rem 0.85rem',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.82rem',
              outline: 'none'
            }}
          >
            <option value="">All Risk Levels</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          {/* ML Anomaly Toggle Button */}
          <button
            type="button"
            onClick={() => setOnlyAnomalies(!onlyAnomalies)}
            className={`btn ${onlyAnomalies ? 'btn-primary' : 'btn-outline'}`}
            style={{
              padding: '0.45rem 0.8rem',
              fontSize: '0.78rem',
              borderColor: onlyAnomalies ? '#a855f7' : 'var(--border-color)',
              backgroundColor: onlyAnomalies ? 'rgba(168, 85, 247, 0.25)' : 'transparent',
              color: onlyAnomalies ? '#d8b4fe' : 'var(--text-secondary)',
            }}
          >
            <Brain size={14} />
            <span>{onlyAnomalies ? 'ML Anomalies Only' : 'All Detections'}</span>
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="table-container">
          {loading ? (
            <LoadingState message="Filtering security audit events..." variant="table" />
          ) : filteredEvents.length === 0 ? (
            <div style={{ padding: '2.5rem' }}>
              <EmptyState
                icon={Activity}
                title="No Events Found"
                description={
                  searchQuery || filterCamera || filterRisk || onlyAnomalies
                    ? 'No security events match the selected filters. Try clearing search criteria.'
                    : 'No security events have been logged yet.'
                }
              />
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Event ID</th>
                  <th>Classification</th>
                  <th>Camera & Location</th>
                  <th>Confidence</th>
                  <th>Threat Score</th>
                  <th>Risk Level</th>
                  <th>Evidence</th>
                  <th>Timestamp</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((evt) => (
                  <tr key={evt.id}>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>#{evt.id}</td>
                    <td style={{ fontWeight: 600, color: '#fff' }}>
                      {evt.event_type.replace(/_/g, ' ').toUpperCase()}
                    </td>
                    <td>
                      <div>{evt.camera_name || `Camera #${evt.camera_id}`}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{evt.camera_location}</div>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                      {Math.round((evt.confidence || 0) * 100)}%
                    </td>
                    <td style={{ minWidth: '130px' }}>
                      <RiskBar score={evt.risk_score} />
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                        R: {evt.metadata?.rule_risk_score ?? evt.risk_score} | ML: {evt.metadata?.ml_risk_score ?? '—'}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <StatusBadge status={evt.risk_level} />
                        {evt.metadata?.ml_anomaly && (
                          <span style={{
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            padding: '0.1rem 0.35rem',
                            borderRadius: '3px',
                            backgroundColor: 'rgba(168, 85, 247, 0.2)',
                            color: '#c084fc',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.2rem'
                          }}>
                            <Brain size={10} /> ML ANOMALY
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      {evt.snapshot_path ? (
                        <span style={{
                          color: '#10b981',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          fontSize: '0.72rem'
                        }}>
                          <Camera size={13} />
                          <span>Saved</span>
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>—</span>
                      )}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                      {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : '—'}
                    </td>
                    <td>
                      <button
                        onClick={() => setSelectedEvent(evt)}
                        className="btn btn-outline"
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                      >
                        <Eye size={13} />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Detail Inspection Modal with Snapshot */}
      {selectedEvent && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '640px',
            padding: '1.75rem',
            boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#fff' }}>
                Security Event #{selectedEvent.id}: {selectedEvent.event_type.replace(/_/g, ' ').toUpperCase()}
              </h3>
              <StatusBadge status={selectedEvent.risk_level} />
            </div>

            <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '1rem', lineHeight: 1.6 }}>
              {selectedEvent.description}
            </p>

            {/* Snapshot Evidence Display */}
            {selectedEvent.snapshot_path && (
              <div style={{
                marginBottom: '1rem',
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
                border: '1px solid var(--border-color)',
                backgroundColor: '#000',
                display: 'flex',
                justifyContent: 'center'
              }}>
                <img
                  src={selectedEvent.snapshot_path}
                  alt={`Incident #${selectedEvent.id} Snapshot`}
                  style={{ maxHeight: '280px', width: '100%', objectFit: 'contain' }}
                />
              </div>
            )}

            {/* Phase 5 Risk Fusion Breakdown */}
            <div style={{ marginBottom: '1rem' }}>
              <RiskBreakdown
                ruleRisk={selectedEvent.metadata?.rule_risk_score ?? selectedEvent.risk_score}
                mlRisk={selectedEvent.metadata?.ml_risk_score ?? 0}
                finalRisk={selectedEvent.risk_score}
                ruleWeight={0.70}
                mlWeight={0.30}
                indicators={selectedEvent.metadata?.ml_indicators || []}
                showFormula={true}
              />
            </div>

            {/* Metadata & Spatial Features */}
            <div style={{
              backgroundColor: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.78rem',
              color: '#38bdf8',
              marginBottom: '1.5rem',
              maxHeight: '180px',
              overflowY: 'auto'
            }}>
              <div style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>// Detection Metadata & Spatial Context</div>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(selectedEvent.metadata, null, 2)}
              </pre>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setSelectedEvent(null)}
                className="btn btn-primary"
                style={{ fontSize: '0.82rem' }}
              >
                Close Audit View
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
