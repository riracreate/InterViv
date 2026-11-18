import { fetchAccountOverview, fetchAvailability, startSession } from './api.js';
import { readScoped, writeScoped } from './accountStorage.js';
import { COMMON_SKILLS, addSkills } from './skillChips.js';
import { startQuickInterview } from './stagedSession.js';

export const LAUNCHER_SKILLS = COMMON_SKILLS.filter(skill => skill !== 'HR');
const STORAGE_NAME = 'staged-interview-skills';
const transport = { fetchAccountOverview, fetchAvailability, startSession };
const cleanSkills = skills => addSkills([], Array.isArray(skills) ? skills.join(',') : '', LAUNCHER_SKILLS)
  .filter(skill => skill.toLowerCase() !== 'hr');

export function recentLauncherSkills(userId, overview, available = LAUNCHER_SKILLS) {
  const remembered = readScoped('local', userId, STORAGE_NAME);
  const saved = cleanSkills(remembered?.skills);
  const recent = (overview?.history || []).find(item => cleanSkills(item.skills).length);
  if (recent && (!saved.length || Date.parse(recent.created_at) > Date.parse(remembered.startedAt))) {
    return cleanSkills(recent.skills);
  }
  return saved.length ? saved : available.slice(0, 1);
}

export function initialLauncherState(userId) {
  return { skills: recentLauncherSkills(userId), busy: false, error: '', notice: '' };
}

/** The standalone card never reads legacy mode, target or resume settings. */
export function createStagedLauncherController({ userId, onChange, onStarted, api = transport }) {
  let state = initialLauncherState(userId);
  let edited = false;
  let disposed = false;
  const snapshot = () => ({ ...state, skills: [...state.skills] });
  const publish = () => { if (!disposed) onChange?.(snapshot()); };
  return {
    snapshot,
    async restoreSkills() {
      try {
        const overview = await api.fetchAccountOverview();
        if (!disposed && !edited) {
          state = { ...state, skills: recentLauncherSkills(userId, overview), notice: '' };
          publish();
        }
      } catch {
        if (!disposed && !edited) {
          state = { ...state, notice: 'Recent skills could not be loaded. Choose your skills below or use the current selection.' };
          publish();
        }
      }
    },
    selectSkills(skills) {
      if (disposed || state.busy) return;
      edited = true;
      state = { ...state, skills: cleanSkills(skills), error: '', notice: '' };
      publish();
    },
    async start() {
      if (disposed || state.busy) return false;
      edited = true;
      state = { ...state, busy: true, error: '' };
      publish();
      try {
        const started = await startQuickInterview({
          skills: state.skills, practiceMode: 'coached_practice', allowOptionalFollowUps: true,
        }, api);
        if (disposed) return false;
        writeScoped('local', userId, STORAGE_NAME, { skills: state.skills, startedAt: new Date().toISOString() });
        onStarted?.(started);
        return true;
      } catch (error) {
        state = { ...state, error: error?.message || 'Could not start this interview. Please try again.' };
        return false;
      } finally {
        state = { ...state, busy: false };
        publish();
      }
    },
    dispose() { disposed = true; },
  };
}
