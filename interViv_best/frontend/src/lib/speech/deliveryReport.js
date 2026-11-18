import { deliverySignals } from './stt.js';

const FILLERS = [/\bum\b/gi, /\buh\b/gi, /\berm\b/gi, /\byou know\b/gi, /\bbasically\b/gi];

/** Count filler words. Whole words only, so "humble" is not "um". */
export function fillerCount(text) {
  const source = String(text || '');
  return FILLERS.reduce((total, pattern) => total + (source.match(pattern) || []).length, 0);
}

/** Row name for the delivery table. Never a raw stage key. */
export function deliveryAnswerLabel({ stage, skill, isFollowUp = false } = {}) {
  const name = String(skill || '').trim();
  if (isFollowUp || stage === 'follow_up') return name ? `${name} follow-up` : 'Follow-up';
  if (stage === 'warm_up') return 'Warm-up';
  if (stage === 'behavioural') return name || 'Behavioural';
  if (name) return name;
  if (stage === 'core') return 'Core';
  return 'Answer';
}

export function speakingCell(speakingMs) {
  const ms = Number(speakingMs) || 0;
  if (ms <= 0) return 'Typed';
  return `${(ms / 1000).toFixed(1)} s`;
}

export function paceCell({ speakingMs = 0, wpm = null } = {}) {
  if (!(Number(speakingMs) > 0) || wpm == null) return '—';
  return String(wpm);
}

export function deliveryReport({ text = '', speakingMs = 0, faceSamples = [] } = {}) {
  const signals = deliverySignals(text, Number(speakingMs) || 0);
  const samples = Array.isArray(faceSamples) ? faceSamples : [];
  const visible = samples.filter(count => Number(count) >= 1).length;
  return {
    speakingMs: Number(speakingMs) || 0,
    words: signals.words,
    wpm: signals.wpm,
    fillerWords: fillerCount(text),
    faceVisiblePercent: samples.length ? Math.round((visible / samples.length) * 100) : null,
    multipleFaceSamples: samples.filter(count => Number(count) > 1).length,
  };
}
