/** English voice order for the opt-in voice interview. The default speaker does not use this. */
import { readDevicePreference, writeDevicePreference } from '../accountStorage.js';

export const VOICE_PREF = 'voiceInterviewVoice';

function isEnglish(voice) {
  return /^en/i.test(voice?.lang || '');
}

export function rankEnglishVoices(voices) {
  const buckets = [[], [], [], [], []];
  (Array.isArray(voices) ? voices : []).forEach(voice => {
    if (!isEnglish(voice)) return;
    const name = String(voice.name || '');
    if (/premium/i.test(name)) buckets[0].push(voice);
    else if (/enhanced/i.test(name)) buckets[1].push(voice);
    else if (name.includes('Google US English') || name.includes('Google UK English Female')) buckets[2].push(voice);
    else if (voice.localService) buckets[3].push(voice);
    else buckets[4].push(voice);
  });
  return buckets.flat();
}

export function pickEnglishVoice(voices, preferredName = '') {
  const ranked = rankEnglishVoices(voices);
  if (preferredName) {
    const chosen = ranked.find(voice => voice.name === preferredName);
    if (chosen) return chosen;
  }
  return ranked[0] || null;
}

export function selectVoiceName(voices, storedName = '') {
  return pickEnglishVoice(voices, storedName)?.name || '';
}

export function readStoredVoiceName(read = readDevicePreference) {
  try {
    const value = read(VOICE_PREF);
    return typeof value === 'string' ? value : '';
  } catch {
    return '';
  }
}

export function writeStoredVoiceName(name, write = writeDevicePreference) {
  try { write(VOICE_PREF, name || ''); }
  catch { /* private mode or a blocked storage API */ }
}
