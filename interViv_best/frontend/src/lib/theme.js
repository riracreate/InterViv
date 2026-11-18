import { readDevicePreference, writeDevicePreference } from './accountStorage.js';

export function readTheme() {
  return readDevicePreference('theme') === 'dark' ? 'dark' : 'light';
}

export function setTheme(theme) {
  const next = theme === 'dark' ? 'dark' : 'light';
  if (typeof document !== 'undefined') document.documentElement.dataset.theme = next;
  writeDevicePreference('theme', next);
  return next;
}
