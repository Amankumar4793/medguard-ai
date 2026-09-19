/**
 * Web Audio API Synthesizer for Real-Time Security Incident Alerts
 * Generates crisp, low-latency audio chimes without external mp3 files.
 */

let audioCtx = null;

function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

export function isAudioMuted() {
  return localStorage.getItem('medguard_sound_enabled') === 'false';
}

export function setAudioMuted(muted) {
  localStorage.setItem('medguard_sound_enabled', muted ? 'false' : 'true');
}

/**
 * Plays an urgent or informational chime based on incident severity.
 * @param {string} severity - 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
 */
export function playAlertChime(severity = 'HIGH') {
  if (isAudioMuted()) return;

  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const sev = String(severity).toUpperCase();
    const now = ctx.currentTime;

    if (sev === 'CRITICAL') {
      // Rapid urgent two-tone alert: 880Hz -> 1174Hz (A5 to D6)
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = 'sawtooth';
      osc1.frequency.setValueAtTime(880, now);
      osc1.frequency.exponentialRampToValueAtTime(1174, now + 0.15);

      gain1.gain.setValueAtTime(0.2, now);
      gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.35);

      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.35);

      // Secondary echo ping
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = 'sine';
      osc2.frequency.setValueAtTime(1174, now + 0.18);
      gain2.gain.setValueAtTime(0.18, now + 0.18);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);

      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.start(now + 0.18);
      osc2.stop(now + 0.55);
    } else if (sev === 'HIGH') {
      // High-priority dual chime: 587Hz -> 880Hz (D5 to A5)
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, now);
      osc.frequency.setValueAtTime(880, now + 0.12);

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.45);
    } else {
      // Soft single ping for MEDIUM / LOW (660Hz)
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(659.25, now);

      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.3);
    }
  } catch (err) {
    // Autoplay or audio context permission error - safely ignore
    console.debug('Alert sound synthesis suppressed:', err);
  }
}
