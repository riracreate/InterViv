import React from 'react';
import SkillChipInput from '../SkillChipInput';
import { LAUNCHER_SKILLS } from '../../lib/stagedLauncher';

export default function StagedLauncherCard({ skills = LAUNCHER_SKILLS.slice(0, 1), busy = false,
  error = '', notice = '', voiceInterview = false, onVoiceChange, onSkillsChange, onStart }) {
  return <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5" aria-labelledby="quick-interview-title">
    <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">Guided interview · about 15 minutes</p>
    <h2 id="quick-interview-title" className="mt-2 text-xl font-semibold">Quick interview</h2>
    <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-ink-muted)]">Coached practice: one warm-up, two core questions and optional follow-ups. Behavioural questions are included when available. Feedback arrives after the interview; there is no practical round.</p>
    <fieldset className="mt-4" disabled={busy}>
      <SkillChipInput label="Skills" value={skills} suggestions={LAUNCHER_SKILLS}
        testId="quick-interview-skills" onChange={onSkillsChange} />
      <label className="mt-4 flex items-start gap-2 text-sm leading-6">
        <input type="checkbox" className="mt-1" checked={Boolean(voiceInterview)}
          data-testid="voice-interview-toggle"
          onChange={event => onVoiceChange?.(event.target.checked)} />
        <span>Voice interview (camera and microphone)</span>
      </label>
    </fieldset>
    {notice && <p className="mt-3 text-sm text-[var(--color-ink-muted)]" role="status">{notice}</p>}
    {error && <p className="mt-3 text-sm text-[var(--color-danger)]" role="alert">{error}</p>}
    <button type="button" className="app-button app-button-primary mt-4" disabled={busy} onClick={onStart}>
      {busy ? 'Starting…' : 'Start Quick interview'}
    </button>
  </section>;
}
