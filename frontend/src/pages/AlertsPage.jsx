import React, { useState, useEffect } from 'react';
import { AlertService, CameraService } from '../services/api';
import { getSocket } from '../services/socket';
import {
  BellRing,
  ShieldAlert,
  AlertTriangle,
  CheckCircle,
  Clock,
  Search,
  RotateCw,
  MessageSquare,
  Camera,
  Activity,
  User,
  History,
  Check,
  Send,
  X,
  Brain,
  Sliders
} from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCamera, setFilterCamera] = useState('');

  // Selected Alert for Triage Modal
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [alertDetails, setAlertDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [operatorName, setOperatorName] = useState('Security Officer');
  const [noteText, setNoteText] = useState('');
  const [actionInProgress, setActionInProgress] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filterSeverity) params.severity = filterSeverity;
      if (filterStatus) params.status = filterStatus;
      if (filterCamera) params.camera_id = filterCamera;

      const [alertsRes, statsRes, camsRes] = await Promise.all([
        AlertService.getAlerts(params),
        AlertService.getStatistics(),
        CameraService.getCameras()
      ]);

      if (alertsRes.success) setAlerts(alertsRes.alerts);
      if (statsRes.success) setStatistics(statsRes.statistics);
      if (camsRes.success) setCameras(camsRes.cameras);
    } catch (err) {
      console.error('Error loading alerts or statistics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filterSeverity, filterStatus, filterCamera]);

  // Socket.IO real-time updates
  useEffect(() => {
    const socket = getSocket();

    const handleNewAlert = (newAlert) => {
      setAlerts((prev) => [newAlert, ...prev]);
      // Refresh stats
      AlertService.getStatistics().then((res) => {
        if (res.success) setStatistics(res.statistics);
      });
    };

    const handleUpdatedAlert = (updatedAlert) => {
      setAlerts((prev) =>
        prev.map((a) => (a.id === updatedAlert.id ? updatedAlert : a))
      );
      if (selectedAlert && selectedAlert.id === updatedAlert.id) {
        setAlertDetails(updatedAlert);
      }
      // Refresh stats
      AlertService.getStatistics().then((res) => {
        if (res.success) setStatistics(res.statistics);
      });
    };

    socket.on('alert_new', handleNewAlert);
    socket.on('alert_updated', handleUpdatedAlert);

    return () => {
      socket.off('alert_new', handleNewAlert);
      socket.off('alert_updated', handleUpdatedAlert);
    };
  }, [selectedAlert]);

  // Fetch full details with history when an alert is opened
  const handleOpenTriage = async (alertItem) => {
    setSelectedAlert(alertItem);
    setAlertDetails(null);
    setNoteText('');
    try {
      setLoadingDetails(true);
      const res = await AlertService.getAlert(alertItem.id);
      if (res.success) {
        setAlertDetails(res.alert);
      } else {
        setAlertDetails(alertItem);
      }
    } catch (err) {
      console.error('Failed to load alert details:', err);
      setAlertDetails(alertItem);
    } finally {
      setLoadingDetails(false);
    }
  };

  // Lifecycle transition actions
  const handleAcknowledge = async () => {
    if (!selectedAlert) return;
    try {
      setActionInProgress(true);
      const res = await AlertService.acknowledgeAlert(selectedAlert.id, {
        operator: operatorName,
        note: noteText || 'Acknowledged by security operator.'
      });
      if (res.success) {
        setAlertDetails(res.alert);
        setNoteText('');
        loadData();
      }
    } catch (err) {
      alert(err.message || 'Failed to acknowledge alert');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleInvestigate = async () => {
    if (!selectedAlert) return;
    try {
      setActionInProgress(true);
      const res = await AlertService.investigateAlert(selectedAlert.id, {
        operator: operatorName,
        note: noteText || 'Active investigation initiated on site.'
      });
      if (res.success) {
        setAlertDetails(res.alert);
        setNoteText('');
        loadData();
      }
    } catch (err) {
      alert(err.message || 'Failed to start investigation');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedAlert) return;
    try {
      setActionInProgress(true);
      const res = await AlertService.resolveAlert(selectedAlert.id, {
        operator: operatorName,
        note: noteText || 'Incident resolved. Area cleared.'
      });
      if (res.success) {
        setAlertDetails(res.alert);
        setNoteText('');
        loadData();
      }
    } catch (err) {
      alert(err.message || 'Failed to resolve alert');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!selectedAlert || !noteText.trim()) return;
    try {
      setActionInProgress(true);
      const res = await AlertService.addNote(selectedAlert.id, {
        operator: operatorName,
        note: noteText.trim()
      });
      if (res.success) {
        setAlertDetails(res.alert);
        setNoteText('');
        loadData();
      }
    } catch (err) {
      alert(err.message || 'Failed to add note');
    } finally {
      setActionInProgress(false);
    }
  };

  // Filter alerts by search query
  const filteredAlerts = alerts.filter((a) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (a.title && a.title.toLowerCase().includes(q)) ||
      (a.description && a.description.toLowerCase().includes(q)) ||
      (a.camera_name && a.camera_name.toLowerCase().includes(q)) ||
      (a.camera_location && a.camera_location.toLowerCase().includes(q)) ||
      (a.notes && a.notes.toLowerCase().includes(q)) ||
      (a.severity && a.severity.toLowerCase().includes(q))
    );
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 600, color: '#fff' }}>
            Real-Time Security Incident Command Center
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Automated alert triage, multi-tier cooldown suppression, and immutable incident audit history.
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="btn btn-outline"
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}
        >
          <RotateCw size={14} className={loading ? 'spin' : ''} />
          <span>Refresh Incidents</span>
        </button>
      </div>

      {/* KPI Metrics Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div className="card" style={{ padding: '1.1rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
            <span>ACTIVE INCIDENTS</span>
            <BellRing size={16} color="#0ea5e9" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, marginTop: '0.4rem', color: '#fff' }}>
            {statistics?.active_alerts ?? '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#0ea5e9', marginTop: '0.2rem' }}>
            {statistics?.status_counts?.NEW || 0} unacknowledged
          </div>
        </div>

        <div className="card" style={{ padding: '1.1rem', backgroundColor: 'var(--bg-card)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#ef4444', fontSize: '0.78rem' }}>
            <span>CRITICAL BREACHES</span>
            <ShieldAlert size={16} color="#ef4444" style={{ animation: 'pulse 1.5s infinite' }} />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, marginTop: '0.4rem', color: '#ef4444' }}>
            {statistics?.severity_counts?.CRITICAL ?? '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Immediate dispatch priority
          </div>
        </div>

        <div className="card" style={{ padding: '1.1rem', backgroundColor: 'var(--bg-card)', border: '1px solid rgba(249, 115, 22, 0.4)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#f97316', fontSize: '0.78rem' }}>
            <span>HIGH SEVERITY</span>
            <AlertTriangle size={16} color="#f97316" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, marginTop: '0.4rem', color: '#f97316' }}>
            {statistics?.severity_counts?.HIGH ?? '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Rule + ML anomaly fusion
          </div>
        </div>

        <div className="card" style={{ padding: '1.1rem', backgroundColor: 'var(--bg-card)', border: '1px solid rgba(245, 158, 11, 0.4)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#f59e0b', fontSize: '0.78rem' }}>
            <span>INVESTIGATING</span>
            <Activity size={16} color="#f59e0b" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, marginTop: '0.4rem', color: '#f59e0b' }}>
            {statistics?.status_counts?.INVESTIGATING ?? '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Officer dispatched on scene
          </div>
        </div>

        <div className="card" style={{ padding: '1.1rem', backgroundColor: 'var(--bg-card)', border: '1px solid rgba(16, 185, 129, 0.4)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#10b981', fontSize: '0.78rem' }}>
            <span>RESOLVED</span>
            <CheckCircle size={16} color="#10b981" />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, marginTop: '0.4rem', color: '#10b981' }}>
            {statistics?.status_counts?.RESOLVED ?? '—'}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Avg res: {statistics?.avg_resolution_seconds ? `${Math.round(statistics.avg_resolution_seconds / 60)}m` : '0m'}
          </div>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div
        className="panel"
        style={{
          padding: '1rem',
          display: 'flex',
          gap: '0.75rem',
          alignItems: 'center',
          flexWrap: 'wrap',
          backgroundColor: 'var(--bg-card)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)'
        }}
      >
        {/* Search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: '220px', backgroundColor: 'var(--bg-secondary)', padding: '0.45rem 0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
          <Search size={15} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search by title, camera, zone, note..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              background: 'none',
              border: 'none',
              color: '#fff',
              outline: 'none',
              fontSize: '0.82rem',
              width: '100%'
            }}
          />
        </div>

        {/* Severity Filter */}
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          style={{
            backgroundColor: 'var(--bg-secondary)',
            color: '#fff',
            border: '1px solid var(--border-color)',
            padding: '0.45rem 0.75rem',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.82rem',
            outline: 'none'
          }}
        >
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>

        {/* Status Filter */}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={{
            backgroundColor: 'var(--bg-secondary)',
            color: '#fff',
            border: '1px solid var(--border-color)',
            padding: '0.45rem 0.75rem',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.82rem',
            outline: 'none'
          }}
        >
          <option value="">All Statuses</option>
          <option value="NEW">New (Unacknowledged)</option>
          <option value="ACKNOWLEDGED">Acknowledged</option>
          <option value="INVESTIGATING">Investigating</option>
          <option value="RESOLVED">Resolved</option>
        </select>

        {/* Camera Filter */}
        <select
          value={filterCamera}
          onChange={(e) => setFilterCamera(e.target.value)}
          style={{
            backgroundColor: 'var(--bg-secondary)',
            color: '#fff',
            border: '1px solid var(--border-color)',
            padding: '0.45rem 0.75rem',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.82rem',
            outline: 'none'
          }}
        >
          <option value="">All Cameras</option>
          {cameras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.location})
            </option>
          ))}
        </select>
      </div>

      {/* Incidents Table */}
      <div className="panel" style={{ overflow: 'hidden' }}>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Incident Title</th>
                <th>Camera & Location</th>
                <th>Risk Fusion (Rule + ML)</th>
                <th>Snapshot</th>
                <th>Status</th>
                <th>Timestamp</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                    Loading incident alerts...
                  </td>
                </tr>
              ) : filteredAlerts.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                    No security alerts found matching active filters. Perimeter safe.
                  </td>
                </tr>
              ) : (
                filteredAlerts.map((alt) => {
                  const finalRisk = alt.alert_metadata?.final_risk_score ?? alt.event?.risk_score ?? 50;
                  const ruleRisk = alt.alert_metadata?.rule_risk_score ?? alt.event?.risk_score ?? 50;
                  const mlRisk = alt.alert_metadata?.ml_risk_score ?? 0;
                  const isAnomalous = alt.alert_metadata?.ml_anomalous;

                  return (
                    <tr key={alt.id}>
                      <td>
                        <StatusBadge status={alt.severity} />
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: '#f8fafc', fontSize: '0.85rem' }}>
                          {alt.title || 'Security Incident'}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                          {alt.description}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 500, color: '#fff' }}>
                          {alt.camera_name || `Camera #${alt.camera_id || '—'}`}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                          {alt.camera_location || 'Hospital Zone'}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <span
                            style={{
                              fontWeight: 700,
                              fontSize: '0.88rem',
                              color:
                                finalRisk >= 85
                                  ? '#ef4444'
                                  : finalRisk >= 65
                                  ? '#f97316'
                                  : '#eab308'
                            }}
                          >
                            {Math.round(finalRisk)}
                          </span>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                            (R:{Math.round(ruleRisk)} / ML:{Math.round(mlRisk)})
                          </span>
                          {isAnomalous && (
                            <span
                              style={{
                                fontSize: '0.65rem',
                                backgroundColor: 'rgba(168, 85, 247, 0.2)',
                                color: '#c084fc',
                                padding: '0.1rem 0.35rem',
                                borderRadius: '3px',
                                fontWeight: 600
                              }}
                            >
                              ML
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        {alt.snapshot_path ? (
                          <span
                            style={{
                              color: '#10b981',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                              fontSize: '0.72rem',
                              cursor: 'pointer'
                            }}
                            onClick={() => handleOpenTriage(alt)}
                          >
                            <Camera size={13} />
                            <span>Preview</span>
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>—</span>
                        )}
                      </td>
                      <td>
                        <StatusBadge status={alt.status} />
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {alt.created_at ? new Date(alt.created_at).toLocaleTimeString() : '—'}
                      </td>
                      <td>
                        <button
                          onClick={() => handleOpenTriage(alt)}
                          className="btn btn-outline"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                        >
                          Triage & Audit
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Comprehensive Incident Triage & Audit Modal */}
      {selectedAlert && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.82)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            backdropFilter: 'blur(5px)',
            padding: '1.5rem'
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--bg-card, #0f172a)',
              border: '1px solid var(--border-color, #1e293b)',
              borderRadius: 'var(--radius-lg, 12px)',
              width: '100%',
              maxWidth: '740px',
              maxHeight: '92vh',
              overflowY: 'auto',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                backgroundColor: 'rgba(255,255,255,0.02)'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: '#fff' }}>
                    Incident #{selectedAlert.id}: {selectedAlert.title}
                  </h3>
                  <StatusBadge status={selectedAlert.severity} />
                  <StatusBadge status={alertDetails?.status || selectedAlert.status} />
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  Logged: {selectedAlert.created_at ? new Date(selectedAlert.created_at).toLocaleString() : '—'}
                </div>
              </div>

              <button
                onClick={() => setSelectedAlert(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '0.4rem',
                  lineHeight: 0
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Snapshot Image Preview */}
              {selectedAlert.snapshot_path && (
                <div
                  style={{
                    borderRadius: 'var(--radius-md)',
                    overflow: 'hidden',
                    backgroundColor: '#000',
                    border: '1px solid var(--border-color)',
                    display: 'flex',
                    flexDirection: 'column'
                  }}
                >
                  <img
                    src={selectedAlert.snapshot_path}
                    alt="Physical Security Snapshot"
                    style={{ maxHeight: '280px', width: '100%', objectFit: 'contain' }}
                  />
                  <div
                    style={{
                      padding: '0.4rem 0.8rem',
                      backgroundColor: 'rgba(0,0,0,0.7)',
                      fontSize: '0.72rem',
                      color: 'var(--text-muted)',
                      display: 'flex',
                      justifyContent: 'space-between'
                    }}
                  >
                    <span>Camera: {selectedAlert.camera_name || selectedAlert.camera_id}</span>
                    <span>Zone: {selectedAlert.alert_metadata?.zone_name || 'Hospital Perimeter'}</span>
                    <span>Track ID: #{selectedAlert.alert_metadata?.track_id ?? 'N/A'}</span>
                  </div>
                </div>
              )}

              {/* Risk Fusion Breakdown Gauge */}
              <div
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-color)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>
                    <Sliders size={16} color="#0ea5e9" />
                    <span>Explainable Threat Risk Fusion (Phase 5 Isolation Forest)</span>
                  </div>
                  <span
                    style={{
                      fontSize: '0.85rem',
                      fontWeight: 700,
                      color:
                        (selectedAlert.alert_metadata?.final_risk_score || selectedAlert.event?.risk_score) >= 80
                          ? '#ef4444'
                          : '#f97316'
                    }}
                  >
                    Final Score: {Math.round(selectedAlert.alert_metadata?.final_risk_score || selectedAlert.event?.risk_score || 50)} / 100
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '0.5rem' }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                      <span>Rule-Based Score (70% weight)</span>
                      <span>{Math.round(selectedAlert.alert_metadata?.rule_risk_score || selectedAlert.event?.risk_score || 50)}%</span>
                    </div>
                    <div style={{ width: '100%', height: '6px', backgroundColor: '#334155', borderRadius: '3px', overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${selectedAlert.alert_metadata?.rule_risk_score || selectedAlert.event?.risk_score || 50}%`,
                          height: '100%',
                          backgroundColor: '#0ea5e9'
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                      <span>ML Isolation Forest (30% weight)</span>
                      <span>{Math.round(selectedAlert.alert_metadata?.ml_risk_score || 0)}%</span>
                    </div>
                    <div style={{ width: '100%', height: '6px', backgroundColor: '#334155', borderRadius: '3px', overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${selectedAlert.alert_metadata?.ml_risk_score || 0}%`,
                          height: '100%',
                          backgroundColor: '#a855f7'
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* ML Indicator tags */}
                {selectedAlert.alert_metadata?.ml_indicators && selectedAlert.alert_metadata.ml_indicators.length > 0 && (
                  <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                    {selectedAlert.alert_metadata.ml_indicators.map((ind, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: '0.72rem',
                          backgroundColor: 'rgba(168, 85, 247, 0.15)',
                          color: '#d8b4fe',
                          padding: '0.15rem 0.5rem',
                          borderRadius: '4px',
                          border: '1px solid rgba(168, 85, 247, 0.3)'
                        }}
                      >
                        • {ind}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Lifecycle Progression Actions */}
              <div
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-color)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>
                    Incident Triage Status Actions
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Current State: <strong style={{ color: '#fff' }}>{alertDetails?.status || selectedAlert.status}</strong>
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {(alertDetails?.status || selectedAlert.status) === 'NEW' && (
                    <button
                      onClick={handleAcknowledge}
                      disabled={actionInProgress}
                      className="btn btn-outline"
                      style={{
                        flex: 1,
                        fontSize: '0.8rem',
                        borderColor: '#0ea5e9',
                        color: '#0ea5e9',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.35rem'
                      }}
                    >
                      <Check size={14} />
                      <span>1. Acknowledge Incident</span>
                    </button>
                  )}

                  {['NEW', 'ACKNOWLEDGED'].includes(alertDetails?.status || selectedAlert.status) && (
                    <button
                      onClick={handleInvestigate}
                      disabled={actionInProgress}
                      className="btn btn-primary"
                      style={{
                        flex: 1,
                        fontSize: '0.8rem',
                        backgroundColor: '#f59e0b',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.35rem'
                      }}
                    >
                      <Activity size={14} />
                      <span>2. Initiate Investigation</span>
                    </button>
                  )}

                  {(alertDetails?.status || selectedAlert.status) !== 'RESOLVED' && (
                    <button
                      onClick={handleResolve}
                      disabled={actionInProgress}
                      className="btn btn-primary"
                      style={{
                        flex: 1,
                        fontSize: '0.8rem',
                        backgroundColor: '#10b981',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.35rem'
                      }}
                    >
                      <CheckCircle size={14} />
                      <span>3. Mark Resolved</span>
                    </button>
                  )}
                </div>

                {/* Operator Note Input */}
                <form onSubmit={handleAddNote} style={{ marginTop: '0.5rem' }}>
                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                        Responding Security Operator
                      </label>
                      <input
                        type="text"
                        value={operatorName}
                        onChange={(e) => setOperatorName(e.target.value)}
                        style={{
                          width: '100%',
                          backgroundColor: 'var(--bg-card)',
                          border: '1px solid var(--border-color)',
                          padding: '0.45rem 0.65rem',
                          borderRadius: 'var(--radius-md)',
                          color: '#fff',
                          outline: 'none',
                          fontSize: '0.82rem'
                        }}
                      />
                    </div>
                  </div>

                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Operator Inspection Log / Action Reason
                  </label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <textarea
                      rows="2"
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      placeholder="Add dispatch outcome, false alarm verification, or escorted person details..."
                      style={{
                        flex: 1,
                        backgroundColor: 'var(--bg-card)',
                        border: '1px solid var(--border-color)',
                        padding: '0.45rem 0.65rem',
                        borderRadius: 'var(--radius-md)',
                        color: '#fff',
                        outline: 'none',
                        fontSize: '0.82rem',
                        resize: 'none'
                      }}
                    />
                    <button
                      type="submit"
                      disabled={actionInProgress || !noteText.trim()}
                      className="btn btn-primary"
                      style={{ padding: '0 1rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                    >
                      <Send size={14} />
                      <span>Log Note</span>
                    </button>
                  </div>
                </form>
              </div>

              {/* Vertical Audit Trail Timeline */}
              <div
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-color)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', fontWeight: 600, color: '#fff', marginBottom: '0.75rem' }}>
                  <History size={16} color="#0ea5e9" />
                  <span>Immutable Incident Audit Trail</span>
                </div>

                {loadingDetails ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Loading audit history...</div>
                ) : !alertDetails?.history || alertDetails.history.length === 0 ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Initial incident recorded. No triage history logged yet.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', position: 'relative', paddingLeft: '1rem' }}>
                    {/* Vertical line indicator */}
                    <div
                      style={{
                        position: 'absolute',
                        left: '4px',
                        top: '8px',
                        bottom: '8px',
                        width: '2px',
                        backgroundColor: '#334155'
                      }}
                    />

                    {alertDetails.history.map((h) => {
                      const isResolve = h.new_status === 'RESOLVED';
                      const isInvestigate = h.new_status === 'INVESTIGATING';
                      const isAck = h.new_status === 'ACKNOWLEDGED';
                      const dotColor = isResolve ? '#10b981' : isInvestigate ? '#f59e0b' : isAck ? '#0ea5e9' : '#ef4444';

                      return (
                        <div key={h.id} style={{ position: 'relative', paddingLeft: '0.75rem' }}>
                          {/* Dot marker */}
                          <div
                            style={{
                              position: 'absolute',
                              left: '-16px',
                              top: '4px',
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              backgroundColor: dotColor,
                              border: '2px solid var(--bg-card)'
                            }}
                          />
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f8fafc' }}>
                              {h.previous_status ? `${h.previous_status} → ${h.new_status}` : h.new_status}
                            </span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                              {h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : ''}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px' }}>
                            by <strong style={{ color: '#cbd5e1' }}>{h.operator}</strong>: {h.note || 'No comment provided.'}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div
              style={{
                padding: '1rem 1.5rem',
                borderTop: '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'flex-end',
                backgroundColor: 'rgba(255,255,255,0.02)'
              }}
            >
              <button
                onClick={() => setSelectedAlert(null)}
                className="btn btn-outline"
                style={{ fontSize: '0.82rem' }}
              >
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
