import React, { useState, useEffect } from 'react';
import { SettingsService } from '../services/api';
import { Settings, Save, Clock, Users, ShieldAlert, Cpu, Bell, Brain, Volume2, VolumeX } from 'lucide-react';
import { isAudioMuted, setAudioMuted } from '../utils/audio';

export default function SettingsPage() {
  const [settings, setSettings] = useState({});
  const [audioEnabled, setAudioEnabled] = useState(!isAudioMuted());
  const [loading, setLoading] = useState(true);

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const res = await SettingsService.getSettings();
      if (res.success) {
        setSettings(res.settings);
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key, val) => {
    setSettings((prev) => ({
      ...prev,
      [key]: val,
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setAudioMuted(!audioEnabled);
      const res = await SettingsService.updateSettings(settings);
      if (res.success) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      alert(err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };


  return (
    <div style={{ maxWidth: '850px' }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>System & Detection Rules Configuration</h2>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Configure physical security boundary rules, operating hours, and anomaly detection thresholds.
        </p>
      </div>

      <form onSubmit={handleSave}>
        {/* Hospital Operational Hours */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <Clock size={18} color="#0ea5e9" />
              <span>Hospital Operational Visiting Hours</span>
            </div>
          </div>
          <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Activity detected in designated restricted zones outside normal hours automatically incurs higher risk scores.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                  Visiting Hours Start (HH:MM)
                </label>
                <input
                  type="text"
                  value={settings.operating_hours?.start || '08:00'}
                  onChange={(e) => handleChange('operating_hours', { ...settings.operating_hours, start: e.target.value })}
                  style={{
                    width: '100%',
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    padding: '0.55rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
                    outline: 'none',
                    fontFamily: 'var(--font-mono)'
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                  Visiting Hours End (HH:MM)
                </label>
                <input
                  type="text"
                  value={settings.operating_hours?.end || '20:00'}
                  onChange={(e) => handleChange('operating_hours', { ...settings.operating_hours, end: e.target.value })}
                  style={{
                    width: '100%',
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    padding: '0.55rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                    color: '#fff',
                    outline: 'none',
                    fontFamily: 'var(--font-mono)'
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Security Thresholds */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <ShieldAlert size={18} color="#f59e0b" />
              <span>Detection & Density Thresholds</span>
            </div>
          </div>
          <div style={{ padding: '1.25rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Crowd Density Threshold (Persons)
              </label>
              <input
                type="number"
                min="2"
                max="25"
                value={settings.crowd_threshold_count || 4}
                onChange={(e) => handleChange('crowd_threshold_count', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Trigger crowd event if zone exceeds this count.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Loitering Duration Cutoff (Seconds)
              </label>
              <input
                type="number"
                min="5"
                max="300"
                value={settings.loitering_threshold_seconds || 30}
                onChange={(e) => handleChange('loitering_threshold_seconds', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Duration before loitering event is raised.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Alert Cooldown Window (Seconds)
              </label>
              <input
                type="number"
                min="5"
                max="120"
                value={settings.alert_cooldown_seconds || 20}
                onChange={(e) => handleChange('alert_cooldown_seconds', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Deduplication window per camera/event.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Detection Confidence Minimum (0.1 - 0.9)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="0.95"
                value={settings.detection_confidence_threshold || 0.45}
                onChange={(e) => handleChange('detection_confidence_threshold', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Filter out noisy low-confidence detections.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Crowd Persistence Window (Seconds)
              </label>
              <input
                type="number"
                min="5"
                max="60"
                value={settings.crowd_duration_seconds || 15}
                onChange={(e) => handleChange('crowd_duration_seconds', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Seconds crowd count must sustain before alerting.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Repeated Entry Threshold (Visits)
              </label>
              <input
                type="number"
                min="2"
                max="10"
                value={settings.repeated_entry_threshold || 3}
                onChange={(e) => handleChange('repeated_entry_threshold', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Number of zone entries that trigger suspicious ingress flag.</span>
            </div>
          </div>
        </div>

        {/* Machine Learning & Risk Fusion Settings (Phase 5) */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <Brain size={18} color="#a855f7" />
              <span>Machine Learning & Risk Fusion (Isolation Forest)</span>
            </div>
            <span style={{
              fontSize: '0.72rem',
              backgroundColor: 'rgba(168, 85, 247, 0.15)',
              color: '#c084fc',
              padding: '0.2rem 0.5rem',
              borderRadius: '4px',
              fontWeight: 600
            }}>
              PHASE 5
            </span>
          </div>
          <div style={{ padding: '1.25rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                Rule Risk Weight (0.0 - 1.0)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="0.9"
                value={settings.rule_risk_weight ?? 0.70}
                onChange={(e) => {
                  const rVal = parseFloat(e.target.value) || 0.7;
                  const mVal = parseFloat((1.0 - rVal).toFixed(2));
                  handleChange('rule_risk_weight', rVal);
                  handleChange('ml_risk_weight', mVal);
                }}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Proportion of deterministic security rules in final threat score.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                ML Anomaly Weight (0.0 - 1.0)
              </label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="0.9"
                value={settings.ml_risk_weight ?? 0.30}
                onChange={(e) => {
                  const mVal = parseFloat(e.target.value) || 0.3;
                  const rVal = parseFloat((1.0 - mVal).toFixed(2));
                  handleChange('ml_risk_weight', mVal);
                  handleChange('rule_risk_weight', rVal);
                }}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Proportion of Isolation Forest anomaly score in final threat score.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                ML Feature Sliding Window (Seconds)
              </label>
              <input
                type="number"
                min="15"
                max="300"
                value={settings.ml_feature_window_seconds || 60}
                onChange={(e) => handleChange('ml_feature_window_seconds', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Temporal lookback window for aggregating the 19 surveillance features.</span>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                ML Inference Cadence (Seconds)
              </label>
              <input
                type="number"
                min="2"
                max="60"
                value={settings.ml_inference_interval_seconds || 10}
                onChange={(e) => handleChange('ml_inference_interval_seconds', Number(e.target.value))}
                style={{
                  width: '100%',
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  padding: '0.55rem 0.75rem',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  outline: 'none',
                  fontFamily: 'var(--font-mono)'
                }}
              />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Evaluation periodicity to avoid CPU overload.</span>
            </div>
          </div>
        </div>

        {/* Automated Alert Cooldowns & Notifications (Phase 6) */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">
              <Bell size={18} color="#f59e0b" />
              <span>Automated Alert Deduplication & Notification Preferences</span>
            </div>
            <span style={{
              fontSize: '0.72rem',
              backgroundColor: 'rgba(245, 158, 11, 0.15)',
              color: '#fbbf24',
              padding: '0.2rem 0.5rem',
              borderRadius: '4px',
              fontWeight: 600
            }}>
              PHASE 6
            </span>
          </div>
          <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Audio Toggle */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'var(--bg-secondary)',
              padding: '0.85rem 1rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-color)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                {audioEnabled ? <Volume2 size={18} color="#10b981" /> : <VolumeX size={18} color="#64748b" />}
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>
                    Browser Web Audio Synthesizer Chimes
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Play audible dual-tone security alarms on incoming HIGH and CRITICAL security incidents.
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setAudioEnabled(!audioEnabled)}
                className="btn btn-outline"
                style={{
                  fontSize: '0.8rem',
                  borderColor: audioEnabled ? '#10b981' : 'var(--border-color)',
                  color: audioEnabled ? '#10b981' : 'var(--text-muted)'
                }}
              >
                {audioEnabled ? '✓ Chimes Enabled' : 'Muted'}
              </button>
            </div>

            {/* Cooldown Grid */}
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#fff', marginBottom: '0.4rem' }}>
                Multi-Tier Incident Deduplication Cooldown Windows (Seconds)
              </label>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.85rem' }}>
                Consecutive security events for the same camera, rule, and zone within this window are grouped to prevent operator alert fatigue.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#ef4444', fontWeight: 600, marginBottom: '0.3rem' }}>
                    CRITICAL (sec)
                  </label>
                  <input
                    type="number"
                    min="5"
                    max="300"
                    value={settings.alert_cooldowns?.CRITICAL ?? 15}
                    onChange={(e) => handleChange('alert_cooldowns', {
                      ...(settings.alert_cooldowns || { CRITICAL: 15, HIGH: 30, MEDIUM: 60, LOW: 120 }),
                      CRITICAL: Number(e.target.value)
                    })}
                    style={{
                      width: '100%',
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      padding: '0.5rem 0.65rem',
                      borderRadius: 'var(--radius-md)',
                      color: '#fff',
                      outline: 'none',
                      fontFamily: 'var(--font-mono)'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#f97316', fontWeight: 600, marginBottom: '0.3rem' }}>
                    HIGH (sec)
                  </label>
                  <input
                    type="number"
                    min="5"
                    max="300"
                    value={settings.alert_cooldowns?.HIGH ?? 30}
                    onChange={(e) => handleChange('alert_cooldowns', {
                      ...(settings.alert_cooldowns || { CRITICAL: 15, HIGH: 30, MEDIUM: 60, LOW: 120 }),
                      HIGH: Number(e.target.value)
                    })}
                    style={{
                      width: '100%',
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      padding: '0.5rem 0.65rem',
                      borderRadius: 'var(--radius-md)',
                      color: '#fff',
                      outline: 'none',
                      fontFamily: 'var(--font-mono)'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#eab308', fontWeight: 600, marginBottom: '0.3rem' }}>
                    MEDIUM (sec)
                  </label>
                  <input
                    type="number"
                    min="10"
                    max="600"
                    value={settings.alert_cooldowns?.MEDIUM ?? 60}
                    onChange={(e) => handleChange('alert_cooldowns', {
                      ...(settings.alert_cooldowns || { CRITICAL: 15, HIGH: 30, MEDIUM: 60, LOW: 120 }),
                      MEDIUM: Number(e.target.value)
                    })}
                    style={{
                      width: '100%',
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      padding: '0.5rem 0.65rem',
                      borderRadius: 'var(--radius-md)',
                      color: '#fff',
                      outline: 'none',
                      fontFamily: 'var(--font-mono)'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: '#38bdf8', fontWeight: 600, marginBottom: '0.3rem' }}>
                    LOW (sec)
                  </label>
                  <input
                    type="number"
                    min="15"
                    max="1200"
                    value={settings.alert_cooldowns?.LOW ?? 120}
                    onChange={(e) => handleChange('alert_cooldowns', {
                      ...(settings.alert_cooldowns || { CRITICAL: 15, HIGH: 30, MEDIUM: 60, LOW: 120 }),
                      LOW: Number(e.target.value)
                    })}
                    style={{
                      width: '100%',
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      padding: '0.5rem 0.65rem',
                      borderRadius: 'var(--radius-md)',
                      color: '#fff',
                      outline: 'none',
                      fontFamily: 'var(--font-mono)'
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Save Bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '1rem', marginTop: '1.5rem' }}>

          {saveSuccess && (
            <span style={{ color: '#10b981', fontSize: '0.85rem', fontWeight: 500 }}>
              ✓ Settings saved successfully!
            </span>
          )}
          <button
            type="submit"
            disabled={saving}
            className="btn btn-primary"
            style={{ padding: '0.65rem 1.25rem' }}
          >
            <Save size={16} />
            <span>{saving ? 'Saving...' : 'Save Configuration'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
