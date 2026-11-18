import { readDevicePreference, writeDevicePreference } from '../accountStorage.js';

const PREF = 'voiceInterviewSessions';

function readIds(read) {
  try {
    const parsed = read(PREF);
    return Array.isArray(parsed) ? parsed.filter(id => typeof id === 'string' && id) : [];
  } catch {
    return [];
  }
}

export function markVoiceInterview(sessionId, enabled, read = readDevicePreference, write = writeDevicePreference) {
  try {
    if (!sessionId) return;
    const ids = new Set(readIds(read));
    if (enabled) ids.add(sessionId);
    else ids.delete(sessionId);
    write(PREF, [...ids]);
  } catch { /* private mode */ }
}

export function isVoiceInterview(sessionId, read = readDevicePreference) {
  try { return Boolean(sessionId) && readIds(read).includes(sessionId); }
  catch { return false; }
}

/** Browser recognition first. Server transcription only when the browser cannot listen. */
export function speechInputMode({ recognitionAvailable = false, transcriptionAvailable = false } = {}) {
  if (recognitionAvailable) return 'browser';
  if (transcriptionAvailable) return 'server';
  return 'type';
}
