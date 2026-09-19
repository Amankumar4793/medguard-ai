import React, { useState, useEffect, useCallback } from 'react';
import { StatisticsService } from '../services/api';
import {
  BarChart3,
  TrendingUp,
  ShieldAlert,
  Brain,
  Activity,
  Calendar,
  Layers,
  Cctv,
  AlertTriangle,
  Clock,
  RefreshCw,
  CheckCircle2,
  Sliders
} from 'lucide-react';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import LoadingState from '../components/common/LoadingState';
import EmptyState from '../components/common/EmptyState';
import ErrorState from '../components/common/ErrorState';
import TrendLineChart from '../components/Charts/TrendLineChart';
import DonutChart from '../components/Charts/DonutChart';
import DistributionBarChart from '../components/Charts/DistributionBarChart';
import RiskBar from '../components/Risk/RiskBar';

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [range, setRange] = useState('24h');
  const [trendMetric, setTrendMetric] = useState('events'); // 'events' or 'risk'
  const [refreshing, setRefreshing] = useState(false);

  const fetchAnalytics = useCallback(async (selectedRange = range, isSilent = false) => {
    try {
      if (!isSilent) setRefreshing(true);
      const res = await StatisticsService.getAnalytics(selectedRange);
      if (res.success) {
        setAnalytics(res);
        setError(null);
      }
    } catch (err) {
      console.error('Failed to load analytics:', err);
      if (!analytics) {
        setError(err.message || 'Failed to load surveillance analytics data');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [range, analytics]);

  useEffect(() => {
    setLoading(true);
    fetchAnalytics(range, false);
  }, [range]);

  const handleRangeChange = (newRange) => {
    setRange(newRange);
  };

  if (loading && !analytics) {
    return <LoadingState message="Aggregating surveillance & AI analytics..." variant="dashboard" />;
  }

  if (error && !analytics) {
    return (
      <ErrorState
        title="Analytics Data Unavailable"
        message={error}
        onRetry={() => {
          setLoading(true);
          fetchAnalytics(range, false);
        }}
      />
    );
  }

  const totalEvents = analytics?.total_events || 0;
  const totalAlerts = analytics?.total_alerts || 0;
  const mlMetrics = analytics?.ml_metrics || {};
  const timeline = analytics?.timeline || [];
  const severityDist = analytics?.severity_distribution || [];
  const statusDist = analytics?.status_distribution || [];
  const eventTypes = analytics?.event_types || [];
  const cameraActivity = analytics?.camera_activity || [];

  return (
    <div>
      {/* Top Header & Range Selector */}
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
            Healthcare Security Analytics & Threat Intelligence
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Empirical telemetry covering temporal incident volumes, spatial zone breaches, and ML anomaly trends.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Time Range Selector Tabs */}
          <div style={{
            display: 'inline-flex',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-md)',
            padding: '3px',
            gap: '2px',
          }}>
            {[
              { id: 'today', label: 'Today' },
              { id: '24h', label: 'Last 24 Hours' },
              { id: '7d', label: 'Last 7 Days' },
              { id: '30d', label: 'Last 30 Days' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleRangeChange(tab.id)}
                style={{
                  background: range === tab.id ? 'var(--accent-cyan)' : 'transparent',
                  color: range === tab.id ? '#fff' : 'var(--text-secondary)',
                  border: 'none',
                  padding: '0.35rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.76rem',
                  fontWeight: range === tab.id ? 600 : 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => fetchAnalytics(range, false)}
            disabled={refreshing}
            className="btn btn-outline"
            style={{ padding: '0.45rem 0.75rem', fontSize: '0.78rem' }}
            title="Refresh analytics data"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
            <span>{refreshing ? 'Syncing...' : 'Sync'}</span>
          </button>
        </div>
      </div>

      {/* Top Overview Stat Cards */}
      <div className="stats-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1rem',
        marginBottom: '1.5rem',
      }}>
        <StatCard
          label="Total Security Events"
          value={totalEvents}
          icon={TrendingUp}
          color="cyan"
          subtitle={`Logged in ${range === 'today' ? 'today\'s shift' : range}`}
        />
        <StatCard
          label="Incident Alerts"
          value={totalAlerts}
          icon={AlertTriangle}
          color={totalAlerts > 0 ? 'amber' : 'green'}
          subtitle={totalAlerts === 0 ? 'No escalated incidents' : 'Multi-tier deduplicated alerts'}
        />
        <StatCard
          label="ML Anomaly Detections"
          value={mlMetrics.total_anomalies || 0}
          icon={Brain}
          color="purple"
          subtitle={`${mlMetrics.anomalous_percentage || 0}% of all events in period`}
        />
        <StatCard
          label="Average Facility Threat"
          value={mlMetrics.avg_final_risk !== undefined ? `${mlMetrics.avg_final_risk}/100` : '0/100'}
          icon={ShieldAlert}
          color={mlMetrics.avg_final_risk >= 60 ? 'red' : mlMetrics.avg_final_risk >= 35 ? 'orange' : 'teal'}
          subtitle="Fused 70% Rule + 30% ML score"
        />
      </div>

      {/* Primary Trend Line Chart Panel */}
      <div className="panel" style={{ marginBottom: '1.5rem' }}>
        <div className="panel-header">
          <div className="panel-title">
            <Activity size={18} color="#0ea5e9" />
            <span>Temporal Surveillance Activity & Threat Trends</span>
          </div>

          {/* Metric Switcher */}
          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <button
              type="button"
              onClick={() => setTrendMetric('events')}
              className={`btn ${trendMetric === 'events' ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '0.3rem 0.65rem', fontSize: '0.74rem' }}
            >
              Event Volume
            </button>
            <button
              type="button"
              onClick={() => setTrendMetric('risk')}
              className={`btn ${trendMetric === 'risk' ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '0.3rem 0.65rem', fontSize: '0.74rem' }}
            >
              Threat Score
            </button>
          </div>
        </div>

        <div style={{ padding: '1.25rem' }}>
          {timeline.length === 0 ? (
            <div style={{ padding: '2rem' }}>
              <EmptyState
                icon={Activity}
                title="Insufficient Data for Period"
                description="No security events or telemetry recorded in this time window."
              />
            </div>
          ) : (
            <TrendLineChart
              data={timeline}
              metric={trendMetric}
              height={260}
              title={trendMetric === 'events' ? 'Event Detection Volume' : 'Mean Threat Score Trend'}
            />
          )}
        </div>
      </div>

      {/* Row 2: Categorical Distributions (Donut Charts) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
        gap: '1.5rem',
        marginBottom: '1.5rem',
      }}>
        {/* Severity Distribution */}
        <div className="panel" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title">
              <ShieldAlert size={18} color="#ef4444" />
              <span>Incident Severity Distribution</span>
            </div>
          </div>
          <div style={{ padding: '1.25rem' }}>
            {severityDist.length === 0 || severityDist.every((d) => (d.count || d.value) === 0) ? (
              <EmptyState
                icon={CheckCircle2}
                title="No Active Alerts"
                description="No escalated security incidents recorded in this timeframe."
              />
            ) : (
              <DonutChart data={severityDist} size={180} />
            )}
          </div>
        </div>

        {/* Triage Status Distribution */}
        <div className="panel" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title">
              <Layers size={18} color="#f59e0b" />
              <span>Incident Triage Lifecycle Distribution</span>
            </div>
          </div>
          <div style={{ padding: '1.25rem' }}>
            {statusDist.length === 0 || statusDist.every((d) => (d.count || d.value) === 0) ? (
              <EmptyState
                icon={CheckCircle2}
                title="No Triage Activity"
                description="All security incidents have been triaged or none occurred."
              />
            ) : (
              <DonutChart data={statusDist} size={180} />
            )}
          </div>
        </div>
      </div>

      {/* Row 3: Event Types Breakdown & ML Model Telemetry */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
        gap: '1.5rem',
        marginBottom: '1.5rem',
      }}>
        {/* Events by Classification Type */}
        <div className="panel" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title">
              <BarChart3 size={18} color="#0ea5e9" />
              <span>Events by Security Rule Type</span>
            </div>
          </div>
          <div style={{ padding: '1.25rem' }}>
            {eventTypes.length === 0 ? (
              <EmptyState
                icon={BarChart3}
                title="No Detection Records"
                description="No zone intrusions, loitering, or crowd events logged in this range."
              />
            ) : (
              <DistributionBarChart items={eventTypes} maxItems={8} />
            )}
          </div>
        </div>

        {/* Machine Learning Model Performance */}
        <div className="panel" style={{ margin: 0 }}>
          <div className="panel-header">
            <div className="panel-title">
              <Brain size={18} color="#a855f7" />
              <span>Machine Learning Anomaly Engine</span>
            </div>
            <span style={{
              fontSize: '0.7rem',
              fontWeight: 700,
              padding: '0.15rem 0.45rem',
              borderRadius: '4px',
              backgroundColor: mlMetrics.model_status === 'READY' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(245, 158, 11, 0.2)',
              color: mlMetrics.model_status === 'READY' ? '#c084fc' : '#f59e0b',
            }}>
              {mlMetrics.model_status || 'STANDBY'}
            </span>
          </div>

          <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{
              backgroundColor: 'var(--bg-secondary)',
              padding: '1rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.65rem',
              fontSize: '0.8rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Algorithm:</span>
                <span style={{ color: '#fff', fontWeight: 600 }}>Isolation Forest</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Feature Dimension:</span>
                <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>19-dimensional spatial & temporal vector</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Anomaly Detection Rate:</span>
                <span style={{ color: '#a855f7', fontWeight: 700 }}>
                  {mlMetrics.anomalous_percentage || 0}% ({mlMetrics.total_anomalies || 0} events)
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Fusion Weighting:</span>
                <span style={{ color: '#fff', fontFamily: 'var(--font-mono)' }}>70% Rule + 30% ML</span>
              </div>
            </div>

            {/* Average Threat Score Comparison */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div style={{
                backgroundColor: 'var(--bg-secondary)',
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Mean ML Anomaly Risk</div>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#a855f7', marginTop: '0.2rem' }}>
                  {mlMetrics.avg_ml_risk !== undefined ? mlMetrics.avg_ml_risk : '0.0'}
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}> / 100</span>
                </div>
              </div>

              <div style={{
                backgroundColor: 'var(--bg-secondary)',
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Mean Fused Risk</div>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0ea5e9', marginTop: '0.2rem' }}>
                  {mlMetrics.avg_final_risk !== undefined ? mlMetrics.avg_final_risk : '0.0'}
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}> / 100</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Row 4: Monitored Facility Camera Fleet Activity Table */}
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title">
            <Cctv size={18} color="#14b8a6" />
            <span>Monitored Facility Surveillance Channel Activity</span>
          </div>
        </div>

        <div className="table-container">
          {cameraActivity.length === 0 ? (
            <div style={{ padding: '2rem' }}>
              <EmptyState
                icon={Cctv}
                title="No Camera Feeds Active"
                description="Connect webcams or RTSP network streams to inspect facility channel metrics."
              />
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Channel</th>
                  <th>Hospital Sector</th>
                  <th>Status</th>
                  <th>Events in Range</th>
                  <th>Escalated Alerts</th>
                  <th>ML Anomalies</th>
                  <th>Average Threat Score</th>
                  <th>Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {cameraActivity.map((cam) => (
                  <tr key={cam.camera_id}>
                    <td>
                      <div style={{ fontWeight: 600, color: '#fff' }}>{cam.name}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        Channel #{cam.camera_id}
                      </div>
                    </td>
                    <td>{cam.location}</td>
                    <td><StatusBadge status={cam.status} /></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      {cam.events_count}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: cam.alerts_count > 0 ? '#ef4444' : 'var(--text-secondary)' }}>
                      {cam.alerts_count}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: cam.anomalies_count > 0 ? '#c084fc' : 'var(--text-secondary)' }}>
                      {cam.anomalies_count}
                    </td>
                    <td style={{ minWidth: '130px' }}>
                      <RiskBar score={cam.avg_risk} />
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.74rem' }}>
                      {cam.last_activity ? new Date(cam.last_activity).toLocaleTimeString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

