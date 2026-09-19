import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';
import DashboardPage from './pages/DashboardPage';
import LiveMonitoringPage from './pages/LiveMonitoringPage';
import CamerasPage from './pages/CamerasPage';
import AlertsPage from './pages/AlertsPage';
import EventsPage from './pages/EventsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="monitoring" element={<LiveMonitoringPage />} />
          <Route path="cameras" element={<CamerasPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="events" element={<EventsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
