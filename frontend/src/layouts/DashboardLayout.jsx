import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from '../components/common/Sidebar';
import Navbar from '../components/common/Navbar';
import AlertToast from '../components/AlertToast';
import { StatisticsService } from '../services/api';


const routeTitles = {
  '/': 'Security Operations Center - Overview',
  '/monitoring': 'Live Video Monitoring & Detection Feeds',
  '/cameras': 'Camera Source & Zone Management',
  '/alerts': 'Real-Time Alert Triage & Incident Queue',
  '/events': 'Security Events & Anomaly Audit Log',
  '/analytics': 'Healthcare Facility Security Analytics',
  '/settings': 'System & Detection Rule Configuration',
};

export default function DashboardLayout() {
  const location = useLocation();
  const [stats, setStats] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const fetchStats = async () => {
    try {
      const data = await StatisticsService.getStatistics();
      if (data.success) {
        setStats(data);
      }
    } catch (err) {
      console.warn('Could not fetch dashboard summary statistics:', err);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000); // 10s refresh
    return () => clearInterval(interval);
  }, []);

  // Close mobile drawer on navigation
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const currentTitle = routeTitles[location.pathname] || 'Healthcare Security Operations Center';
  const activeAlertCount = stats?.summary?.new_alerts || 0;

  return (
    <div className="app-layout">
      {mobileMenuOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}
      <Sidebar
        alertCount={activeAlertCount}
        mobileOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      />
      <div className="main-wrapper">
        <Navbar
          title={currentTitle}
          onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)}
        />
        <main className="content-area">
          <Outlet context={{ stats, refreshStats: fetchStats }} />
        </main>
      </div>
      <AlertToast />
    </div>
  );
}

