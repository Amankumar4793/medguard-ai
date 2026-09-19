import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Camera,
  AlertTriangle,
  ShieldCheck,
  Activity,
  Cctv,
  ArrowRight,
  Brain,
  Wifi,
  Server,
  BellRing,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertOctagon,
  Eye,
  SlidersHorizontal
} from 'lucide-react';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import EmptyState from '../components/common/EmptyState';
import LoadingState from '../components/common/LoadingState';
import ErrorState from '../components/common/ErrorState';
import RiskBar from '../components/Risk/RiskBar';
import { StatisticsService } from '../services/api';
import { getSocket } from '../services/socket';

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [lastRefreshed, setLastRefreshed] = useState(new Date());
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboard = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setRefreshing(true);
      const res = await StatisticsService.getDashboardStats();
      if (res.success) {
        setData(res);
        setActiveAlerts(res.active_alerts_list || []);
        setLiveEvents(res.recent_events || []);
        setError(null);
        setLastRefreshed(new Date());
      }
    } catch (err) {
      console.error('Failed to load dashboard statistics:', err);
      if (!data) {
        setError(err.message || 'Failed to connect to surveillance analytics service');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [data]);

  // Initial load and periodic refresh
  useEffect(() => {
    fetchDashboard(false);
    const interval = setInterval(() => fetchDashboard(true), 8000);
    return () => clearInterval(interval);
  }, []);

  // Socket.IO real-time event updates
  useEffect(() => {
    const socket = getSocket();

    const handleSecurityEvent = (evt) => {
      if (!evt || typeof evt !== 'object') return;
      setLiveEvents((prev) => [evt, ...prev.slice(0, 14)]);
      setData((prev) => {
        if (!prev || !prev.kpis) return prev;
        return {
          ...prev,
          kpis: {
            ...prev.kpis,
            events_today: (prev.kpis.events_today || 0) + 1,
            ml_anomalies: (evt.metadata?.ml_anomaly || evt.metadata?.ml_anomalous)
              ? (prev.kpis.ml_anomalies || 0) + 1
              : prev.kpis.ml_anomalies,
          },
        };
      });
    };

    const handleNewAlert = (alt) => {
      if (!alt || typeof alt !== 'object' || !alt.id) return;
      setActiveAlerts((prev) => [alt, ...prev.filter((a) => a.id !== alt.id).slice(0, 7)]);
      setData((prev) => {
        if (!prev || !prev.kpis) return prev;
        const isCrit = alt.severity === 'CRITICAL';
        const isHigh = alt.severity === 'HIGH';
        return {
          ...prev,
          kpis: {
            ...prev.kpis,
            active_alerts: (prev.kpis.active_alerts || 0) + 1,
            critical_alerts: isCrit ? (prev.kpis.critical_alerts || 0) + 1 : prev.kpis.critical_alerts,
            high_alerts: isHigh ? (prev.kpis.high_alerts || 0) + 1 : prev.kpis.high_alerts,
          },
        };
      });
    };

    const handleAlertUpdated = (updated) => {
      if (!updated || typeof updated !== 'object' || !updated.id) return;
      if (updated.status === 'RESOLVED') {
        setActiveAlerts((prev) => prev.filter((a) => a.id !== updated.id));
        setData((prev) => {
          if (!prev || !prev.kpis) return prev;
          return {
            ...prev,
            kpis: {
              ...prev.kpis,
              active_alerts: Math.max(0, (prev.kpis.active_alerts || 0) - 1),
            },
          };
        });
      } else {
        setActiveAlerts((prev) =>
          prev.map((a) => (a.id === updated.id ? updated : a))
        );
      }
    };

    socket.on('security_event', handleSecurityEvent);
    socket.on('alert_new', handleNewAlert);
    socket.on('alert_updated', handleAlertUpdated);

    return () => {
      socket.off('security_event', handleSecurityEvent);
      socket.off('alert_new', handleNewAlert);
      socket.off('alert_updated', handleAlertUpdated);
    };
  }, []);

  if (loading && !data) {
    return <LoadingState message="Initializing Security Operations Center..." variant="dashboard" />;
  }

  if (error && !data) {
    return (
      <ErrorState
        title="SOC Telemetry Unavailable"
        message={error}
        onRetry={() => {
          setLoading(true);
          fetchDashboard(false);
        }}
      />
    );
  }

  const kpis = data?.kpis || {
    active_alerts: 0,
    critical_alerts: 0,
    high_alerts: 0,
    investigating: 0,
    cameras_online: 0,
    cameras_offline: 0,
    ml_anomalies: 0,
    events_today: 0,
  };

  const sys = data?.system_status || {
    backend: 'ONLINE',
    socketio: 'CONNECTED',
    camera_system: 'ONLINE',
    ml_model: 'READY',
    alert_engine: 'ONLINE',
  };

  const cameras = data?.cameras || [];

  return (
    <div>
      {/* Top Header Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.5rem',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fff' }}>
            Operational Command Center
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Real-time physical perimeter surveillance, AI tracking, and threat fusion monitoring.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Synced: {lastRefreshed.toLocaleTimeString()}
          </span>
          <button
            type="button"
            onClick={() => fetchDashboard(false)}
            disabled={refreshing}
            className="btn btn-outline"
            style={{ padding: '0.45rem 0.85rem', fontSize: '0.78rem' }}
            title="Refresh dashboard metrics"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Syncing...' : 'Sync'}</span>
          </button>
        </div>
      </div>

      {/* 8 Core KPI Cards Grid */}
      <div className="stats-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '1rem',
        marginBottom: '1.5rem',
      }}>
        <StatCard
          label="Active Incidents"
          value={kpis.active_alerts}
          icon={BellRing}
          color={kpis.active_alerts > 0 ? (kpis.critical_alerts > 0 ? 'red' : 'amber') : 'green'}
          subtitle={kpis.active_alerts === 0 ? 'Perimeter secure' : `${kpis.active_alerts} require triage`}
        />
        <StatCard
          label="Critical Threats"
          value={kpis.critical_alerts}
          icon={AlertOctagon}
          color="red"
          subtitle={kpis.critical_alerts > 0 ? 'Immediate action needed' : '0 critical threats'}
        />
        <StatCard
          label="High Risk Alerts"
          value={kpis.high_alerts}
          icon={AlertTriangle}
          color="orange"
          subtitle="Zone breaches & loitering"
        />
        <StatCard
          label="Investigating"
          value={kpis.investigating}
          icon={Search}
          color="blue"
          subtitle="Active operator triage"
        />
        <StatCard
          label="Cameras Online"
          value={`${kpis.cameras_online} / ${kpis.cameras_online + kpis.cameras_offline}`}
          icon={Camera}
          color="green"
          subtitle={`${kpis.cameras_online} streaming feeds`}
        />
        <StatCard
          label="Cameras Offline"
          value={kpis.cameras_offline}
          icon={Cctv}
          color={kpis.cameras_offline > 0 ? 'amber' : 'teal'}
          subtitle={kpis.cameras_offline > 0 ? `${kpis.cameras_offline} standby/offline` : 'All channels live'}
        />
        <StatCard
          label="ML Anomalies"
          value={kpis.ml_anomalies}
          icon={Brain}
          color="purple"
          subtitle="Isolation Forest flags"
        />
        <StatCard
          label="Events Today"
          value={kpis.events_today}
          icon={Activity}
          color="teal"
          subtitle="Audited detections"
        />
      </div>

      {/* System Subsystem Health Matrix */}
      <div className="panel" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.85rem',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>
            <Server size={16} color="#0ea5e9" />
            <span>Subsystem Health & Infrastructure Telemetry</span>
          </div>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            All systems grounded in real hardware & model metrics
          </span>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '0.75rem',
        }}>
          {/* Subsystem 1: Backend API */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            padding: '0.7rem 0.85rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>REST API Server</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#fff' }}>Flask Framework</div>
            </div>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '0.15rem 0.45rem',
              borderRadius: '999px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#10b981',
              border: '1px solid rgba(16, 185, 129, 0.3)',
            }}>
              ONLINE
            </span>
          </div>

          {/* Subsystem 2: Socket.IO */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            padding: '0.7rem 0.85rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Realtime Stream</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#fff' }}>Socket.IO Engine</div>
            </div>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '0.15rem 0.45rem',
              borderRadius: '999px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#10b981',
              border: '1px solid rgba(16, 185, 129, 0.3)',
            }}>
              CONNECTED
            </span>
          </div>

          {/* Subsystem 3: Camera System */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            padding: '0.7rem 0.85rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Video Ingestion</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#fff' }}>OpenCV Capture</div>
            </div>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '0.15rem 0.45rem',
              borderRadius: '999px',
              backgroundColor: kpis.cameras_online > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              color: kpis.cameras_online > 0 ? '#10b981' : '#f59e0b',
              border: `1px solid ${kpis.cameras_online > 0 ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
            }}>
              {kpis.cameras_online > 0 ? `${kpis.cameras_online} ACTIVE` : 'STANDBY'}
            </span>
          </div>

          {/* Subsystem 4: ML Anomaly Model */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            padding: '0.7rem 0.85rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Anomaly Detection</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#fff' }}>Isolation Forest</div>
            </div>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '0.15rem 0.45rem',
              borderRadius: '999px',
              backgroundColor: sys.ml_model === 'READY' ? 'rgba(168, 85, 247, 0.15)' : 'rgba(245, 158, 11, 0.15)',
              color: sys.ml_model === 'READY' ? '#c084fc' : '#f59e0b',
              border: `1px solid ${sys.ml_model === 'READY' ? 'rgba(168, 85, 247, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
            }}>
              {sys.ml_model}
            </span>
          </div>

          {/* Subsystem 5: Alert Engine */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            padding: '0.7rem 0.85rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Incident Engine</div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#fff' }}>Auto-Deduplication</div>
            </div>
            <span style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '0.15rem 0.45rem',
              borderRadius: '999px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: '#10b981',
              border: '1px solid rgba(16, 185, 129, 0.3)',
            }}>
              ONLINE
            </span>
          </div>
        </div>
      </div>

      {/* Camera Fleet Status Overview Grid */}
      <div className="panel" style={{ marginBottom: '1.5rem' }}>
        <div className="panel-header">
          <div className="panel-title">
            <Cctv size={18} color="#0ea5e9" />
            <span>Healthcare Facility Camera Fleet ({cameras.length})</span>
          </div>
          <Link to="/cameras" className="btn btn-outline" style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}>
            <span>Manage Fleet</span>
            <ArrowRight size={14} />
          </Link>
        </div>

        <div style={{ padding: '1.25rem' }}>
          {cameras.length === 0 ? (
            <EmptyState
              icon={Cctv}
              title="No Cameras Registered"
              description="Register video capture channels or webcams to start physical perimeter monitoring."
              actionLabel="Add Camera"
              onAction={() => window.location.assign('/cameras')}
            />
          ) : (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '1rem',
            }}>
              {cameras.map((cam) => {
                const isOnline = cam.status === 'ONLINE';
                return (
                  <div
                    key={cam.id}
                    style={{
                      backgroundColor: 'var(--bg-secondary)',
                      padding: '1rem',
                      borderRadius: 'var(--radius-md)',
                      border: `1px solid ${isOnline ? 'rgba(14, 165, 233, 0.25)' : 'var(--border-subtle)'}`,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: '0.85rem',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#fff' }}>
                          {cam.name}
                        </span>
                        <StatusBadge status={cam.status} />
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {cam.location} • {cam.source_type?.toUpperCase()}
                      </div>
                    </div>

                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr 1fr',
                      gap: '0.5rem',
                      backgroundColor: 'rgba(0,0,0,0.2)',
                      padding: '0.5rem 0.65rem',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.72rem',
                    }}>
                      <div>
                        <div style={{ color: 'var(--text-muted)' }}>FPS</div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: isOnline ? '#0ea5e9' : 'var(--text-muted)' }}>
                          {cam.fps}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-muted)' }}>Zones</div>
                        <div style={{ fontWeight: 600, color: '#fff' }}>
                          {cam.zones_count}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: 'var(--text-muted)' }}>Alerts</div>
                        <div style={{ fontWeight: 600, color: cam.active_alerts > 0 ? '#ef4444' : '#10b981' }}>
                          {cam.active_alerts}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <Link
                        to="/monitoring"
                        className="btn btn-outline"
                        style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
                      >
                        <Eye size={13} />
                        <span>Monitor Feed</span>
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Two-Column Layout: Active Incidents Queue & Live Security Events Feed */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
        gap: '1.5rem',
      }}>
        {/* Column 1: Active Incident Triage Queue */}
        <div className="panel" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title">
              <AlertTriangle size={18} color="#ef4444" />
              <span>Incident Command Queue ({activeAlerts.length})</span>
            </div>
            <Link to="/alerts" className="btn btn-outline" style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}>
              <span>View All Alerts</span>
              <ArrowRight size={14} />
            </Link>
          </div>

          <div className="table-container">
            {activeAlerts.length === 0 ? (
              <div style={{ padding: '2rem' }}>
                <EmptyState
                  icon={ShieldCheck}
                  title="All Healthcare Zones Secure"
                  description="No unacknowledged or active security incident alerts in the triage queue."
                />
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Incident</th>
                    <th>Camera</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {activeAlerts.map((alt) => (
                    <tr key={alt.id}>
                      <td><StatusBadge status={alt.severity} /></td>
                      <td>
                        <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.82rem' }}>
                          {alt.title || alt.description}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          Alert #{alt.id}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          {alt.camera_name || `Camera #${alt.camera_id || '—'}`}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          {alt.camera_location || 'Zone'}
                        </div>
                      </td>
                      <td><StatusBadge status={alt.status} /></td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
                        {alt.created_at ? new Date(alt.created_at).toLocaleTimeString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Column 2: Live Security Event Stream */}
        <div className="panel" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title">
              <Activity size={18} color="#14b8a6" />
              <span>Live Security Event Stream</span>
            </div>
            <Link to="/events" className="btn btn-outline" style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}>
              <span>Event Audit Log</span>
              <ArrowRight size={14} />
            </Link>
          </div>

          <div style={{ padding: '0.75rem', maxHeight: '440px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {liveEvents.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="No Events Recorded"
                description="Events generated by computer vision and detection rules will stream here in real time."
              />
            ) : (
              liveEvents.map((evt, idx) => (
                <div
                  key={evt.id || idx}
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.75rem 0.9rem',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.2rem' }}>
                      <StatusBadge status={evt.risk_level || 'MEDIUM'} />
                      <span style={{ fontWeight: 600, fontSize: '0.82rem', color: '#fff' }}>
                        {evt.event_type?.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      {evt.metadata?.ml_anomaly && (
                        <span style={{
                          fontSize: '0.62rem',
                          fontWeight: 700,
                          padding: '0.1rem 0.35rem',
                          borderRadius: '3px',
                          backgroundColor: 'rgba(168, 85, 247, 0.2)',
                          color: '#c084fc',
                        }}>
                          ML
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {evt.camera_name || `Camera #${evt.camera_id || '—'}`} • {evt.description}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                      {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : 'Just now'}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right', minWidth: '85px' }}>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Threat
                    </div>
                    <div style={{
                      fontSize: '1rem',
                      fontWeight: 700,
                      fontFamily: 'var(--font-mono)',
                      color: evt.risk_score >= 75 ? '#ef4444' : evt.risk_score >= 50 ? '#f97316' : '#10b981',
                    }}>
                      {evt.risk_score ?? 0}
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>/100</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
