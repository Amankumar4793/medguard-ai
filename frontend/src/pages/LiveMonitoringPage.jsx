import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CameraService, MonitoringService, EventService } from '../services/api';
import { getSocket } from '../services/socket';
import {
  Cctv, Play, Square, RotateCcw, Layers, ShieldAlert, Cpu,
  Activity, Clock, Film, Scan, Users, Package, AlertTriangle,
  Crosshair, MapPin, Eye, Radio, Brain
} from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import RiskBreakdown from '../components/Risk/RiskBreakdown';

export default function LiveMonitoringPage() {
  const [cameras, setCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [activeTracks, setActiveTracks] = useState([]);
  const [activeZones, setActiveZones] = useState([]);
  const [liveEvents, setLiveEvents] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [showZones, setShowZones] = useState(true);
  const [loading, setLoading] = useState(true);
  const [streamError, setStreamError] = useState(null);
  const [streamKey, setStreamKey] = useState(Date.now());
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);
  const [searchParams] = useSearchParams();
  const paramCamId = searchParams.get('camera');

  const telemetryInterval = useRef(null);

  // Load cameras on mount
  useEffect(() => {
    loadCameras();
    return () => {
      if (telemetryInterval.current) clearInterval(telemetryInterval.current);
    };
  }, []);

  // Fetch camera-specific events when camera selection changes
  useEffect(() => {
    if (!selectedCameraId) return;
    EventService.getEvents({ camera_id: selectedCameraId, limit: 15 })
      .then((res) => {
        if (res && res.success && Array.isArray(res.events)) {
          setLiveEvents(res.events);
        }
      })
      .catch(() => setLiveEvents([]));
  }, [selectedCameraId]);

  const loadCameras = async () => {
    try {
      setLoading(true);
      const res = await CameraService.getCameras();
      if (res.success && res.cameras.length > 0) {
        setCameras(res.cameras);
        if (paramCamId) {
          const match = res.cameras.find((c) => String(c.id) === String(paramCamId));
          setSelectedCameraId(match ? match.id : res.cameras[0].id);
        } else {
          setSelectedCameraId(res.cameras[0].id);
        }
      }
    } catch (err) {
      console.error('Error fetching cameras:', err);
    } finally {
      setLoading(false);
    }
  };

  // Socket.IO real-time event listener
  useEffect(() => {
    const socket = getSocket();

    const handleDetectionUpdate = (data) => {
      if (data && typeof data === 'object' && data.camera_id === selectedCameraId) {
        if (Array.isArray(data.tracks)) setActiveTracks(data.tracks);
        if (Array.isArray(data.zones)) setActiveZones(data.zones);
      }
    };

    const handleSecurityEvent = (eventData) => {
      if (eventData && typeof eventData === 'object' && (!eventData.camera_id || eventData.camera_id === selectedCameraId)) {
        setLiveEvents((prev) => [eventData, ...prev.slice(0, 19)]);
      }
    };

    const handleCameraStatus = (statusData) => {
      if (statusData && statusData.camera_id === selectedCameraId) {
        if (statusData.status === 'RUNNING') {
          setIsStreaming(true);
          setStreamError(null);
        } else if (statusData.status === 'ERROR') {
          setIsStreaming(false);
          setStreamError(statusData.error || 'Video stream error');
        } else if (statusData.status === 'OFFLINE') {
          setIsStreaming(false);
        }
      }
    };

    socket.on('detection_update', handleDetectionUpdate);
    socket.on('security_event', handleSecurityEvent);
    socket.on('camera_status_changed', handleCameraStatus);

    return () => {
      socket.off('detection_update', handleDetectionUpdate);
      socket.off('security_event', handleSecurityEvent);
      socket.off('camera_status_changed', handleCameraStatus);
    };
  }, [selectedCameraId]);

  // Periodic telemetry polling
  useEffect(() => {
    if (!selectedCameraId) return;

    fetchTelemetry();
    fetchTracksAndZones();

    if (telemetryInterval.current) clearInterval(telemetryInterval.current);
    telemetryInterval.current = setInterval(() => {
      fetchTelemetry();
      fetchTracksAndZones();
    }, 1500);

    return () => {
      if (telemetryInterval.current) clearInterval(telemetryInterval.current);
    };
  }, [selectedCameraId, isStreaming]);

  const fetchTelemetry = async () => {
    if (!selectedCameraId) return;
    try {
      const res = await MonitoringService.getTelemetry(selectedCameraId);
      if (res.success && res.telemetry) {
        setTelemetry(res.telemetry);
        const running = res.telemetry.status === 'RUNNING';
        setIsStreaming(running);
        if (res.telemetry.status === 'ERROR') {
          setStreamError(res.telemetry.error_message || 'Video source error');
        } else {
          setStreamError(null);
        }
      }
    } catch (err) {
      // Stream offline fallback
    }
  };

  const fetchTracksAndZones = async () => {
    if (!selectedCameraId) return;
    try {
      const [tracksRes, zonesRes] = await Promise.all([
        MonitoringService.getTracks(selectedCameraId).catch(() => null),
        MonitoringService.getZones(selectedCameraId).catch(() => null),
      ]);
      if (tracksRes?.success && tracksRes.tracks) {
        setActiveTracks(tracksRes.tracks);
      }
      if (zonesRes?.success && zonesRes.zones) {
        setActiveZones(zonesRes.zones);
      }
    } catch (err) {
      // Ignored for quiet background telemetry
    }
  };

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId) || cameras[0];

  const handleStart = async () => {
    if (!selectedCamera) return;
    try {
      setStreamError(null);
      const res = await MonitoringService.startMonitoring(selectedCamera.id);
      if (res.success) {
        setIsStreaming(true);
        setStreamKey(Date.now());
        setTimeout(() => {
          fetchTelemetry();
          fetchTracksAndZones();
        }, 400);
      }
    } catch (err) {
      setStreamError(err.message || 'Failed to start stream.');
    }
  };

  const handleStop = async () => {
    if (!selectedCamera) return;
    try {
      await MonitoringService.stopMonitoring(selectedCamera.id);
      setIsStreaming(false);
      setActiveTracks([]);
      setTimeout(fetchTelemetry, 200);
    } catch (err) {
      console.error('Failed to stop stream:', err);
    }
  };

  const handleRestart = async () => {
    if (!selectedCamera) return;
    try {
      setStreamError(null);
      await MonitoringService.restartMonitoring(selectedCamera.id);
      setIsStreaming(true);
      setStreamKey(Date.now());
      setTimeout(() => {
        fetchTelemetry();
        fetchTracksAndZones();
      }, 500);
    } catch (err) {
      setStreamError(err.message || 'Failed to restart stream.');
    }
  };

  const streamUrl = selectedCameraId
    ? `${MonitoringService.getStreamUrl(selectedCameraId)}?t=${streamKey}`
    : null;

  const activeViolationsCount = telemetry?.active_zone_violations || 0;

  return (
    <div>
      {/* Top Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: 'var(--bg-card)',
        padding: '0.85rem 1.25rem',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-color)',
        marginBottom: '1.5rem',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}>
            <Cctv size={20} color="#0ea5e9" />
            <span>Surveillance Channel:</span>
          </div>
          <select
            value={selectedCameraId || ''}
            onChange={(e) => {
              setSelectedCameraId(Number(e.target.value));
              setStreamKey(Date.now());
              setActiveTracks([]);
            }}
            style={{
              backgroundColor: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              padding: '0.5rem 0.9rem',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              outline: 'none'
            }}
          >
            {cameras.map((cam) => (
              <option key={cam.id} value={cam.id}>
                {cam.name} ({cam.location})
              </option>
            ))}
          </select>

          {activeViolationsCount > 0 && (
            <span style={{
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#f87171',
              padding: '0.3rem 0.65rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.75rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}>
              <AlertTriangle size={13} />
              <span>{activeViolationsCount} ACTIVE BREACH{activeViolationsCount > 1 ? 'ES' : ''}</span>
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <button
            onClick={() => setShowZones(!showZones)}
            className={`btn ${showZones ? 'btn-primary' : 'btn-outline'}`}
            style={{ fontSize: '0.8rem', padding: '0.45rem 0.85rem' }}
          >
            <Layers size={15} />
            <span>{showZones ? 'Hide Zones' : 'Show Zones'}</span>
          </button>

          {!isStreaming ? (
            <button
              onClick={handleStart}
              className="btn btn-primary"
              style={{ backgroundColor: '#10b981', fontSize: '0.8rem', padding: '0.45rem 0.85rem' }}
            >
              <Play size={15} />
              <span>Start Stream</span>
            </button>
          ) : (
            <>
              <button
                onClick={handleRestart}
                className="btn btn-outline"
                style={{ fontSize: '0.8rem', padding: '0.45rem 0.85rem' }}
                title="Restart Video & AI Engine"
              >
                <RotateCcw size={15} />
                <span>Restart</span>
              </button>
              <button
                onClick={handleStop}
                className="btn btn-danger"
                style={{ fontSize: '0.8rem', padding: '0.45rem 0.85rem' }}
              >
                <Square size={15} />
                <span>Stop Stream</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Stream Viewport and Telemetry Sidebar */}
      <div style={{ display: 'grid', gridTemplateColumns: '2.5fr 1.1fr', gap: '1.5rem', alignItems: 'start' }}>

        {/* Left Column: Stream Display & Live Events Feed */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

          {/* Video Stream Container */}
          <div style={{
            backgroundColor: '#050810',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--border-color)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            minHeight: '480px',
            position: 'relative'
          }}>
            {/* Header Bar Overlay */}
            <div style={{
              padding: '0.65rem 1rem',
              backgroundColor: 'rgba(11, 15, 25, 0.92)',
              borderBottom: '1px solid var(--border-color)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              zIndex: 10
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="pulse-dot" style={{ backgroundColor: isStreaming ? '#10b981' : '#64748b' }}></span>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>
                  {selectedCamera?.name || 'Surveillance Feed'}
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  [{selectedCamera?.source_type?.toUpperCase()}]
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <StatusBadge status={telemetry?.status || (isStreaming ? 'RUNNING' : 'OFFLINE')} />
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  color: '#0ea5e9',
                  backgroundColor: 'var(--bg-secondary)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: '4px'
                }}>
                  FPS: {telemetry?.fps ? telemetry.fps.toFixed(1) : '0.0'}
                </span>
              </div>
            </div>

            {/* Video Canvas Container */}
            <div style={{
              minHeight: '440px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: '#070b14',
              position: 'relative',
              overflow: 'hidden'
            }}>
              {isStreaming && streamUrl ? (
                <div style={{ position: 'relative', width: '100%', display: 'flex', justifyContent: 'center' }}>
                  <img
                    src={streamUrl}
                    alt={`Camera #${selectedCameraId} Stream`}
                    onError={() => {
                      setStreamError('Lost connection to video stream.');
                      setIsStreaming(false);
                    }}
                    style={{
                      width: '100%',
                      maxHeight: '520px',
                      objectFit: 'contain',
                      display: 'block'
                    }}
                  />
                </div>
              ) : (
                <div style={{
                  textAlign: 'center',
                  padding: '3rem 2rem',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '1rem'
                }}>
                  <Cctv size={52} color="#334155" />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
                      {streamError ? 'Camera Stream Error' : 'Stream Paused / Offline'}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem', maxWidth: '420px' }}>
                      {streamError || `Click "Start Stream" above to activate the video processor, real-time object tracking, and zone intrusion evaluation.`}
                    </div>
                  </div>

                  {!isStreaming && (
                    <button onClick={handleStart} className="btn btn-primary" style={{ marginTop: '0.5rem', fontSize: '0.82rem' }}>
                      <Play size={15} />
                      <span>Activate Live Feed</span>
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Footer Bar Overlay */}
            <div style={{
              padding: '0.65rem 1rem',
              backgroundColor: 'var(--bg-secondary)',
              borderTop: '1px solid var(--border-color)',
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.78rem',
              color: 'var(--text-muted)',
              flexWrap: 'wrap',
              gap: '0.5rem'
            }}>
              <div>
                Source: <span style={{ color: '#fff', fontFamily: 'var(--font-mono)' }}>{selectedCamera?.source}</span>
              </div>
              <div>
                Location: <span style={{ color: '#fff' }}>{selectedCamera?.location}</span>
              </div>
            </div>
          </div>

          {/* Real-Time Security Incident Stream */}
          <div className="panel" style={{ margin: 0 }}>
            <div className="panel-header">
              <div className="panel-title">
                <Radio size={16} color="#ef4444" />
                <span>Live Security Events Feed</span>
              </div>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Auto-updating via Socket.IO
              </span>
            </div>
            <div style={{ padding: '1rem' }}>
              {liveEvents.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '1.5rem',
                  color: 'var(--text-muted)',
                  fontSize: '0.82rem',
                  fontStyle: 'italic'
                }}>
                  Surveillance active. No security breaches or loitering violations detected.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '280px', overflowY: 'auto' }}>
                  {liveEvents.map((evt, idx) => (
                    <div
                      key={idx}
                      style={{
                        backgroundColor: 'var(--bg-secondary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '0.75rem 1rem',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '1rem'
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                          <StatusBadge status={evt.risk_level || 'MEDIUM'} />
                          <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#fff' }}>
                            {evt.event_type?.replace(/_/g, ' ').toUpperCase()}
                          </span>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {evt.camera_name}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          {evt.description}
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem', fontFamily: 'var(--font-mono)' }}>
                          Risk Score: {typeof evt.risk_score === 'number' ? evt.risk_score.toFixed(1) : (evt.risk_score ?? '--')} / 100 • {evt.timestamp ? (isNaN(new Date(evt.timestamp).getTime()) ? 'Just now' : new Date(evt.timestamp).toLocaleTimeString()) : 'Just now'}
                        </div>
                      </div>

                      {evt.snapshot_url && (
                        <button
                          onClick={() => setSelectedSnapshot(evt.snapshot_url)}
                          className="btn btn-outline"
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
                          title="View Snapshot"
                        >
                          <Eye size={13} />
                          <span>Snapshot</span>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Right Column: Tracking & Zones Telemetry Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

          {/* Stream Performance Telemetry */}
          <div className="panel" style={{ margin: 0 }}>
            <div className="panel-header">
              <div className="panel-title">
                <Cpu size={16} color="#0ea5e9" />
                <span>Stream Performance</span>
              </div>
            </div>
            <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Status:</span>
                <StatusBadge status={telemetry?.status || 'OFFLINE'} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Measured FPS:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#0ea5e9' }}>
                  {telemetry?.fps ? telemetry.fps.toFixed(1) : '0.0'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>AI Inference Latency:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: '#10b981', fontWeight: 600 }}>
                  {telemetry?.ai_inference_ms ? `${telemetry.ai_inference_ms.toFixed(1)} ms` : '--'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Processed Frames:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: '#fff' }}>
                  {telemetry?.frame_count?.toLocaleString() || '0'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Uptime:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                  {telemetry?.uptime_seconds ? `${telemetry.uptime_seconds}s` : '0s'}
                </span>
              </div>
            </div>
          </div>

          {/* Phase 4 Object Tracking Telemetry */}
          <div className="panel" style={{ margin: 0 }}>
            <div className="panel-header">
              <div className="panel-title">
                <Crosshair size={16} color="#0ea5e9" />
                <span>Object Tracking (Phase 4)</span>
              </div>
              <span style={{
                fontSize: '0.7rem',
                backgroundColor: 'rgba(14, 165, 233, 0.15)',
                color: '#38bdf8',
                padding: '0.15rem 0.45rem',
                borderRadius: '4px',
                fontWeight: 600
              }}>
                CENTROID-IoU
              </span>
            </div>
            <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* Counts Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
                <div style={{
                  backgroundColor: 'rgba(14, 165, 233, 0.08)',
                  border: '1px solid rgba(14, 165, 233, 0.25)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.6rem 0.75rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem'
                }}>
                  <Users size={20} color="#0ea5e9" />
                  <div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Tracked</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0ea5e9' }}>
                      {activeTracks.length}
                    </div>
                  </div>
                </div>

                <div style={{
                  backgroundColor: activeViolationsCount > 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.08)',
                  border: `1px solid ${activeViolationsCount > 0 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.25)'}`,
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.6rem 0.75rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem'
                }}>
                  <ShieldAlert size={20} color={activeViolationsCount > 0 ? '#ef4444' : '#10b981'} />
                  <div>
                    <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Breaches</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: activeViolationsCount > 0 ? '#ef4444' : '#10b981' }}>
                      {activeViolationsCount}
                    </div>
                  </div>
                </div>
              </div>

              {/* Active Tracks List */}
              <div style={{ marginTop: '0.25rem' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Active Entity Tracks:
                </div>
                {activeTracks.length === 0 ? (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    No individuals currently in frame.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: '150px', overflowY: 'auto' }}>
                    {activeTracks.map((trk) => (
                      <div
                        key={trk.track_id}
                        style={{
                          backgroundColor: 'var(--bg-secondary)',
                          border: `1px solid ${trk.is_loitering ? '#f97316' : trk.current_zone_id ? '#ef4444' : 'var(--border-subtle)'}`,
                          borderRadius: 'var(--radius-sm)',
                          padding: '0.45rem 0.65rem',
                          fontSize: '0.75rem',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <div>
                          <span style={{ fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                            Person #{trk.track_id}
                          </span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: '0.4rem' }}>
                            ({Math.round(trk.confidence * 100)}%)
                          </span>
                          {trk.current_zone_name && (
                            <div style={{ fontSize: '0.7rem', color: '#f87171' }}>
                              In: {trk.current_zone_name} ({trk.time_in_zone ? Math.round(trk.time_in_zone) : 0}s)
                            </div>
                          )}
                        </div>

                        {trk.is_loitering ? (
                          <span style={{
                            backgroundColor: 'rgba(249, 115, 22, 0.2)',
                            color: '#fb923c',
                            padding: '0.15rem 0.4rem',
                            borderRadius: '3px',
                            fontWeight: 700,
                            fontSize: '0.65rem'
                          }}>
                            LOITERING
                          </span>
                        ) : trk.current_zone_id ? (
                          <span style={{
                            backgroundColor: 'rgba(239, 68, 68, 0.2)',
                            color: '#f87171',
                            padding: '0.15rem 0.4rem',
                            borderRadius: '3px',
                            fontWeight: 700,
                            fontSize: '0.65rem'
                          }}>
                            RESTRICTED
                          </span>
                        ) : (
                          <span style={{ color: '#10b981', fontSize: '0.68rem', fontWeight: 600 }}>
                            SAFE
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Phase 5 Machine Learning Anomaly Detection (Isolation Forest) */}
          <div className="panel" style={{ margin: 0 }}>
            <div className="panel-header">
              <div className="panel-title">
                <Brain size={16} color="#a855f7" />
                <span>AI Anomaly Detection (Phase 5)</span>
              </div>
              <span style={{
                fontSize: '0.7rem',
                backgroundColor: telemetry?.ml_analysis?.is_anomaly ? 'rgba(239, 68, 68, 0.2)' : 'rgba(168, 85, 247, 0.15)',
                color: telemetry?.ml_analysis?.is_anomaly ? '#f87171' : '#c084fc',
                padding: '0.15rem 0.45rem',
                borderRadius: '4px',
                fontWeight: 600
              }}>
                ISOLATION FOREST
              </span>
            </div>
            <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {/* Score Gauge & Status */}
              <div style={{
                backgroundColor: 'rgba(168, 85, 247, 0.08)',
                border: '1px solid rgba(168, 85, 247, 0.25)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.75rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    ML Anomaly Threat Score
                  </div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: (telemetry?.ml_analysis?.anomaly_score || 0) >= 50 ? '#ef4444' : '#a855f7' }}>
                    {telemetry?.ml_analysis ? `${telemetry.ml_analysis.anomaly_score.toFixed(1)}` : '0.0'}
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 400 }}> / 100</span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{
                    display: 'inline-block',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '999px',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    backgroundColor: telemetry?.ml_analysis?.is_anomaly ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                    color: telemetry?.ml_analysis?.is_anomaly ? '#ef4444' : '#10b981'
                  }}>
                    {telemetry?.ml_analysis?.is_anomaly ? 'ANOMALOUS' : 'NORMAL'}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    Model: {telemetry?.ml_status === 'READY' ? '● Online' : '○ Offline'}
                  </div>
                </div>
              </div>

              {/* Explainable Risk Fusion Component */}
              <RiskBreakdown
                ruleRisk={telemetry?.active_zone_violations > 0 ? 80 : activeTracks.length > 3 ? 60 : 20}
                mlRisk={telemetry?.ml_analysis?.anomaly_score || 0}
                finalRisk={null}
                ruleWeight={0.70}
                mlWeight={0.30}
                indicators={telemetry?.ml_analysis?.indicators || []}
                showFormula={true}
              />
            </div>
          </div>

          {/* Configured Zones & Live Occupancy */}
          <div className="panel" style={{ margin: 0 }}>
            <div className="panel-header">
              <div className="panel-title">
                <MapPin size={16} color="#f59e0b" />
                <span>Zones & Live Occupancy</span>
              </div>
            </div>
            <div style={{ padding: '1rem' }}>
              {(activeZones.length === 0 && selectedCamera?.configuration?.zones?.length === 0) ? (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No designated zones configured.</span>
              ) : (
                (activeZones.length > 0 ? activeZones : selectedCamera?.configuration?.zones || []).map((z, idx) => (
                  <div key={idx} style={{
                    backgroundColor: 'var(--bg-secondary)',
                    padding: '0.65rem 0.75rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.78rem',
                    marginBottom: '0.5rem',
                    border: '1px solid var(--border-subtle)'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontWeight: 600, color: '#fff' }}>{z.name}</div>
                      <StatusBadge status={z.severity || 'HIGH'} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.35rem', fontSize: '0.72rem' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Type: {z.type}</span>
                      <span style={{
                        color: (z.occupant_count || 0) > 0 ? '#f87171' : '#10b981',
                        fontWeight: 600
                      }}>
                        Occupants: {z.occupant_count || 0}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

        </div>

      </div>

      {/* Snapshot Preview Modal */}
      {selectedSnapshot && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.85)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '700px',
            padding: '1.5rem',
            boxShadow: '0 20px 40px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff' }}>
                Security Incident Evidence Snapshot
              </h3>
              <button
                onClick={() => setSelectedSnapshot(null)}
                className="btn btn-outline"
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
              >
                Close
              </button>
            </div>

            <div style={{ backgroundColor: '#000', borderRadius: 'var(--radius-md)', overflow: 'hidden', display: 'flex', justifyContent: 'center' }}>
              <img
                src={selectedSnapshot}
                alt="Security Event Snapshot"
                style={{ width: '100%', maxHeight: '480px', objectFit: 'contain' }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
