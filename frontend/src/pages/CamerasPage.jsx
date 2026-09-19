import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { CameraService, MonitoringService } from '../services/api';
import { Camera, Plus, Trash2, Edit2, Play, Square, RotateCcw, ShieldAlert, CheckCircle2, XCircle, Eye } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';

export default function CamerasPage() {
  const [cameras, setCameras] = useState([]);
  const [statuses, setStatuses] = useState({});
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingCameraId, setEditingCameraId] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    source: '',
    source_type: 'webcam',
    location: '',
    enabled: true
  });

  const loadData = async () => {
    try {
      setLoading(true);
      const [camsRes, statusRes] = await Promise.all([
        CameraService.getCameras(),
        MonitoringService.getStatus()
      ]);

      if (camsRes.success) setCameras(camsRes.cameras);

      if (statusRes.success && statusRes.cameras) {
        const map = {};
        statusRes.cameras.forEach((c) => {
          map[c.camera_id] = c;
        });
        setStatuses(map);
      }
    } catch (err) {
      console.error('Failed to load cameras and statuses:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, []);

  const openAddModal = () => {
    setEditingCameraId(null);
    setFormData({
      name: '',
      source: '0',
      source_type: 'webcam',
      location: '',
      enabled: true
    });
    setShowModal(true);
  };

  const openEditModal = (cam) => {
    setEditingCameraId(cam.id);
    setFormData({
      name: cam.name,
      source: cam.source,
      source_type: cam.source_type,
      location: cam.location,
      enabled: cam.enabled
    });
    setShowModal(true);
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.source.trim() || !formData.location.trim()) {
      alert('Please fill in all required camera fields.');
      return;
    }

    try {
      if (editingCameraId) {
        await CameraService.updateCamera(editingCameraId, formData);
      } else {
        await CameraService.createCamera({
          ...formData,
          configuration: {
            zones: [
              {
                id: `zone_${Date.now()}`,
                name: 'Default Monitoring Zone',
                type: 'restricted',
                polygon: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
                severity: 'HIGH'
              }
            ],
            operating_hours: { start: '08:00', end: '20:00' },
            fps: 15,
            resolution: [640, 480],
            crowd_threshold: 4,
            loitering_threshold_seconds: 30
          }
        });
      }
      setShowModal(false);
      loadData();
    } catch (err) {
      alert(err.message || 'Error saving camera');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm(`Delete camera #${id}? This will also stop any active background streams.`)) return;
    try {
      await MonitoringService.stopMonitoring(id);
      await CameraService.deleteCamera(id);
      loadData();
    } catch (err) {
      alert(err.message || 'Error deleting camera');
    }
  };

  const handleStartStream = async (id) => {
    try {
      await MonitoringService.startMonitoring(id);
      loadData();
    } catch (err) {
      alert(err.message || 'Failed to start camera stream');
    }
  };

  const handleStopStream = async (id) => {
    try {
      await MonitoringService.stopMonitoring(id);
      loadData();
    } catch (err) {
      alert(err.message || 'Failed to stop camera stream');
    }
  };

  const handleRestartStream = async (id) => {
    try {
      await MonitoringService.restartMonitoring(id);
      loadData();
    } catch (err) {
      alert(err.message || 'Failed to restart camera stream');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Healthcare Camera Fleet Management</h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Register, configure, and operate physical webcams, RTSP network feeds, and video files.
          </p>
        </div>
        <button onClick={openAddModal} className="btn btn-primary">
          <Plus size={16} />
          <span>Add New Camera</span>
        </button>
      </div>

      <div className="panel">
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Camera Name</th>
                <th>Source</th>
                <th>Type</th>
                <th>Location</th>
                <th>Stream Status</th>
                <th>Live FPS</th>
                <th>Stream Control</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {cameras.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                    No cameras registered. Click "Add New Camera" to connect a feed.
                  </td>
                </tr>
              ) : (
                cameras.map((cam) => {
                  const stat = statuses[cam.id];
                  const isRunning = stat?.status === 'RUNNING';
                  const fps = stat?.fps ? stat.fps.toFixed(1) : '0.0';

                  return (
                    <tr key={cam.id}>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>#{cam.id}</td>
                      <td style={{ fontWeight: 600, color: '#fff' }}>{cam.name}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {cam.source_type === 'rtsp' && cam.source.includes('@')
                          ? `rtsp://***:***@${cam.source.split('@')[1]}`
                          : cam.source}
                      </td>
                      <td><StatusBadge status={cam.source_type} /></td>
                      <td>{cam.location}</td>
                      <td>
                        <StatusBadge status={stat?.status || 'OFFLINE'} />
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: isRunning ? '#0ea5e9' : 'var(--text-muted)' }}>
                        {fps}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          {!isRunning ? (
                            <button
                              onClick={() => handleStartStream(cam.id)}
                              className="btn btn-outline"
                              style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', color: '#10b981' }}
                              title="Start Stream"
                            >
                              <Play size={13} />
                              <span>Start</span>
                            </button>
                          ) : (
                            <>
                              <button
                                onClick={() => handleRestartStream(cam.id)}
                                className="btn btn-outline"
                                style={{ padding: '0.3rem 0.5rem', fontSize: '0.75rem' }}
                                title="Restart Stream"
                              >
                                <RotateCcw size={13} />
                              </button>
                              <button
                                onClick={() => handleStopStream(cam.id)}
                                className="btn btn-danger"
                                style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                title="Stop Stream"
                              >
                                <Square size={13} />
                                <span>Stop</span>
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          <Link
                            to={`/monitoring?camera=${cam.id}`}
                            className="btn btn-outline"
                            style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', color: '#0ea5e9', borderColor: 'rgba(14, 165, 233, 0.3)' }}
                            title="View Live Video Feed"
                          >
                            <Eye size={13} />
                          </Link>
                          <button
                            onClick={() => openEditModal(cam)}
                            className="btn btn-outline"
                            style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                            title="Edit Configuration"
                          >
                            <Edit2 size={13} />
                          </button>
                          <button
                            onClick={() => handleDelete(cam.id)}
                            className="btn btn-danger"
                            style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                            title="Delete Camera"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Camera Modal */}
      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: '520px',
            padding: '1.75rem',
            boxShadow: '0 20px 40px rgba(0,0,0,0.5)'
          }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1.25rem', color: '#fff' }}>
              {editingCameraId ? `Configure Camera #${editingCameraId}` : 'Register New Camera'}
            </h3>
            <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Camera Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. CAM-05: Intensive Care Corridor"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  style={{
                    width: '100%', backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)', padding: '0.6rem 0.8rem',
                    borderRadius: 'var(--radius-md)', color: '#fff', outline: 'none'
                  }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                    Source Type
                  </label>
                  <select
                    value={formData.source_type}
                    onChange={(e) => {
                      const type = e.target.value;
                      let defaultSrc = '0';
                      if (type === 'video_file') defaultSrc = 'data/videos/sample.mp4';
                      if (type === 'rtsp') defaultSrc = 'rtsp://192.168.1.100:554/live';
                      setFormData({ ...formData, source_type: type, source: defaultSrc });
                    }}
                    style={{
                      width: '100%', backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)', padding: '0.6rem 0.8rem',
                      borderRadius: 'var(--radius-md)', color: '#fff', outline: 'none'
                    }}
                  >
                    <option value="webcam">Webcam (Index: 0, 1)</option>
                    <option value="video_file">Local Video (MP4)</option>
                    <option value="rtsp">RTSP Network Stream</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                    Hospital Sector / Location
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Wing B - Level 2"
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    style={{
                      width: '100%', backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)', padding: '0.6rem 0.8rem',
                      borderRadius: 'var(--radius-md)', color: '#fff', outline: 'none'
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Source Target
                </label>
                <input
                  type="text"
                  required
                  placeholder={
                    formData.source_type === 'webcam'
                      ? '0 (default webcam index)'
                      : formData.source_type === 'video_file'
                      ? 'data/videos/pharmacy_sample.mp4'
                      : 'rtsp://user:pass@192.168.1.100:554/stream1'
                  }
                  value={formData.source}
                  onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                  style={{
                    width: '100%', backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)', padding: '0.6rem 0.8rem',
                    borderRadius: 'var(--radius-md)', color: '#fff', outline: 'none',
                    fontFamily: 'var(--font-mono)', fontSize: '0.82rem'
                  }}
                />
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {formData.source_type === 'webcam' && 'Use 0 for built-in webcam or 1 for secondary USB camera.'}
                  {formData.source_type === 'video_file' && 'Relative to project directory (e.g. data/videos/sample.mp4).'}
                  {formData.source_type === 'rtsp' && 'Network camera RTSP stream URI.'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="btn btn-outline"
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingCameraId ? 'Update Camera' : 'Save Camera'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
