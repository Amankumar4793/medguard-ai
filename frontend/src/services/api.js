import axios from 'axios';

const rawApiUrl = import.meta.env?.VITE_API_URL || '';
const baseURL = rawApiUrl ? (rawApiUrl.endsWith('/api') ? rawApiUrl : `${rawApiUrl}/api`) : '/api';

export const getAssetUrl = (path) => {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const cleanUrl = rawApiUrl.endsWith('/api') ? rawApiUrl.slice(0, -4) : rawApiUrl;
  return `${cleanUrl}${path.startsWith('/') ? path : '/' + path}`;
};

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const errorMsg =
      error.response?.data?.message ||
      error.response?.data?.error ||
      error.message ||
      'API Communication Error';
    console.error('[API Error]:', errorMsg);
    return Promise.reject(new Error(errorMsg));
  }
);

export const HealthService = {
  getHealth: () => api.get('/health'),
};

export const StatisticsService = {
  getStatistics: () => api.get('/statistics/'),
  getDashboardStats: () => api.get('/statistics/dashboard'),
  getAnalytics: (range = '24h') => api.get('/statistics/analytics', { params: { range } }),
};


export const CameraService = {
  getCameras: () => api.get('/cameras/'),
  getCamera: (id) => api.get(`/cameras/${id}`),
  createCamera: (data) => api.post('/cameras/', data),
  updateCamera: (id, data) => api.put(`/cameras/${id}`, data),
  deleteCamera: (id) => api.delete(`/cameras/${id}`),
};

export const EventService = {
  getEvents: (params) => api.get('/events/', { params }),
  getEvent: (id) => api.get(`/events/${id}`),
  createEvent: (data) => api.post('/events/', data),
};

export const AlertService = {
  getAlerts: (params) => api.get('/alerts/', { params }),
  getAlert: (id) => api.get(`/alerts/${id}`),
  updateAlert: (id, data) => api.patch(`/alerts/${id}`, data),
  acknowledgeAlert: (id, data) => api.post(`/alerts/${id}/acknowledge`, data),
  investigateAlert: (id, data) => api.post(`/alerts/${id}/investigate`, data),
  resolveAlert: (id, data) => api.post(`/alerts/${id}/resolve`, data),
  addNote: (id, data) => api.post(`/alerts/${id}/notes`, data),
  getStatistics: () => api.get('/alerts/statistics'),
};


export const MonitoringService = {
  getStatus: () => api.get('/monitoring/status'),
  startMonitoring: (cameraId) => api.post('/monitoring/start', { camera_id: cameraId }),
  stopMonitoring: (cameraId) => api.post('/monitoring/stop', { camera_id: cameraId }),
  restartMonitoring: (cameraId) => api.post('/monitoring/restart', { camera_id: cameraId }),
  getTelemetry: (cameraId) => api.get(`/monitoring/telemetry/${cameraId}`),
  getDetections: (cameraId) => api.get(`/monitoring/detections/${cameraId}`),
  getTracks: (cameraId) => api.get(`/monitoring/tracks/${cameraId}`),
  getZones: (cameraId) => api.get(`/monitoring/zones/${cameraId}`),
  getStreamUrl: (cameraId) => getAssetUrl(`/api/monitoring/stream/${cameraId}`),
};

export const SettingsService = {
  getSettings: () => api.get('/settings/'),
  updateSettings: (data) => api.put('/settings/', data),
};

export const MLService = {
  getStatus: () => api.get('/ml/status'),
  getAnalysis: (cameraId) => api.get(`/ml/analysis/${cameraId}`),
  getFeatures: () => api.get('/ml/features'),
  reloadModel: () => api.post('/ml/reload'),
};

export default api;
