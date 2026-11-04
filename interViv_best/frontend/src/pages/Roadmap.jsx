import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { fetchRoadmap, fetchMyRoadmap } from '../lib/api';
import AppNav from '../components/AppNav';
import BackLink from '../components/BackLink';
import { gapAnalysisPath } from '../lib/backNavigation';
import '../styles/hub.css';

const SUPPORTED_DAYS = [7, 14, 30];

const SEVERITY_COLOR = {
  Untested: '#9CA3AF',
  High:     'var(--color-danger)',
  Medium:   'var(--color-warn)',
  Low:      'var(--color-success)',
};

function ConceptPill({ topic }) {
  const color = SEVERITY_COLOR[topic.severity] || SEVERITY_COLOR.Low;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs"
      style={{
        fontFamily: "var(--font-body)",
        backgroundColor: 'rgba(0,0,0,0.04)',
        color: '#000',
      }}
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {topic.concept || topic.display_name}
    </span>
  );
}

function WeekCard({ block, isFirst }) {
  return (
    <div data-testid="roadmap-week-card" className="hub-card relative">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="hub-eyebrow">
            Week {block.index} · {block.day_range}
          </p>
          <h3
            className="text-2xl tracking-tight"
            style={{ fontFamily: "var(--font-display)", letterSpacing: '-0.5px' }}
          >
            {block.label}
          </h3>
        </div>
        {isFirst && (
          <span className="hub-button hub-button-primary" style={{ padding: '6px 12px', pointerEvents: 'none' }}>
            Start here
          </span>
        )}
      </div>

      <div className="mb-4">
        <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
           style={{ fontFamily: "var(--font-body)" }}>
          Focus skills
        </p>
        <div className="flex flex-wrap gap-2">
          {block.focus_skills.length === 0 && (
            <span className="text-sm text-[#6F6F6F]"
                  style={{ fontFamily: "var(--font-body)" }}>
              No focus skills queued.
            </span>
          )}
          {block.focus_skills.map((s) => (
            <span key={s} className="rounded-full border border-black/10 px-3 py-1 text-xs"
                  style={{ fontFamily: "var(--font-body)" }}>
              {s}
            </span>
          ))}
        </div>
      </div>

      {block.focus_topics.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
             style={{ fontFamily: "var(--font-body)" }}>
            Concepts to cover
          </p>
          <div className="flex flex-wrap gap-1.5" data-testid="roadmap-concepts">
            {block.focus_topics.slice(0, 12).map((t, idx) => (
              <ConceptPill key={`${t.skill}-${t.concept || idx}`} topic={t} />
            ))}
            {block.focus_topics.length > 12 && (
              <span className="text-xs text-[#6F6F6F]"
                    style={{ fontFamily: "var(--font-body)" }}>
                +{block.focus_topics.length - 12} more
              </span>
            )}
          </div>
        </div>
      )}

      {block.daily_practice_suggestions.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
             style={{ fontFamily: "var(--font-body)" }}>
            Daily practice
          </p>
          <ul className="space-y-1.5">
            {block.daily_practice_suggestions.map((s, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-black"
                  style={{ fontFamily: "var(--font-body)" }}>
                <span className="text-[#6F6F6F] mt-0.5">·</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function Roadmap() {
  const { userId, roleId } = useParams();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const initialDays = parseInt(search.get('days') || '30', 10);
  const [days, setDays] = useState(
    SUPPORTED_DAYS.includes(initialDays) ? initialDays : 30
  );
  const [roadmap, setRoadmap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    const loader = (userId === 'me')
      ? fetchMyRoadmap(roleId, days)
      : fetchRoadmap(userId, roleId, days);

    loader
      .then((data) => { if (!cancelled) { setRoadmap(data); setLoading(false); } })
      .catch((err) => { if (!cancelled) { setError(err.message || 'Failed to load roadmap.'); setLoading(false); } });
    return () => { cancelled = true; };
  }, [userId, roleId, days]);

  const onDaysChange = (next) => {
    setDays(next);
    setSearch({ days: String(next) }, { replace: true });
  };

  if (loading) {
    return (
      <main className="hub-page">
        <div className="hub-container">
          <AppNav userId={userId === 'me' ? null : userId} roleId={roleId} />
          <p className="hub-loading" role="status">Building your roadmap…</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="hub-page">
        <div className="hub-container">
          <AppNav userId={userId === 'me' ? null : userId} roleId={roleId} />
          <div className="hub-error" role="alert">{error}</div>
          <BackLink fallback="/home" className="hub-button hub-button-primary" />
        </div>
      </main>
    );
  }

  if (!roadmap) return null;

  return (
    <main className="hub-page" data-testid="roadmap-page">
      <div className="hub-container">
        <AppNav userId={roadmap.user_id || (userId === 'me' ? null : userId)} roleId={roadmap.role_id || roleId} />
        <div className="mt-4"><BackLink fallback={gapAnalysisPath(userId, roleId)} /></div>

        <header className="hub-page-hero">
        <p className="hub-eyebrow">
          Roadmap · {roadmap.company_name} · {roadmap.role_title}
        </p>

        <h1 data-testid="roadmap-title">
          Your {roadmap.days}-day study plan
        </h1>

        <p>
          {roadmap.plan_note}
        </p>
        </header>

        <div className="hub-card mb-10 flex flex-wrap items-center gap-4">
          <p className="hub-eyebrow" style={{ margin: 0 }}>
            Plan length
          </p>
          <div className="flex gap-2" data-testid="roadmap-day-toggle">
            {SUPPORTED_DAYS.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => onDaysChange(d)}
                className={d === days ? 'hub-button hub-button-primary' : 'hub-button'}
              >
                {d} days
              </button>
            ))}
          </div>
          <div className="grow" />
          <p className="hub-caption">
            Current readiness:{' '}
            <span className="font-medium text-[var(--color-ink)]" data-testid="roadmap-readiness">
              {roadmap.overall_readiness_percentage == null
                ? 'Not assessed yet'
                : `${Math.round(roadmap.overall_readiness_percentage)}%`}
            </span>
          </p>
          {roadmap.readiness_note && (
            <p className="hub-caption w-full" data-testid="roadmap-readiness-note">
              {roadmap.readiness_note}
            </p>
          )}
          {roadmap.study_plan?.meta?.hours_per_week != null && (
            <p className="hub-caption w-full">
              Study budget: {roadmap.study_plan.meta.hours_per_week} h/week
              {roadmap.study_plan.meta.hours_editable ? ' (editable via Coach)' : ''}
            </p>
          )}
        </div>

        {roadmap.study_plan?.tasks?.length > 0 && (
          <section className="hub-card mb-10" data-testid="roadmap-tasks">
            <p className="hub-eyebrow">Versioned tasks · plan v{roadmap.study_plan.version}</p>
            <p className="hub-caption mb-3">
              Task progress {roadmap.study_plan.task_completion_pct}% — not an assessment metric.
            </p>
            <ul className="space-y-3">
              {roadmap.study_plan.tasks.slice(0, 8).map((task) => (
                <li key={task.task_id} className="text-sm">
                  <div className="font-medium">{task.title}</div>
                  <div className="text-[var(--color-ink-muted)]">{task.rationale}</div>
                  <div className="mt-1 text-xs uppercase tracking-wide text-[var(--color-ink-muted)]">
                    {task.population} · {task.status}
                  </div>
                  <button
                    type="button"
                    className="hub-button mt-2"
                    style={{ padding: '4px 10px' }}
                    onClick={() => navigate('/practice?mode=full', {
                      state: {
                        prefilledSkills: task.skill ? [task.skill] : [],
                        prefillSource: 'study plan task',
                        targetRoleId: roadmap.role_id || '',
                      },
                    })}
                  >
                    Start this task
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        <div className="grid gap-6 md:grid-cols-2" data-testid="roadmap-weeks">
          {roadmap.weekly_blocks.map((b, i) => (
            <WeekCard key={b.index} block={b} isFirst={i === 0} />
          ))}
        </div>

        <div className="hub-toolbar mt-12">
          <button type="button" onClick={() => navigate('/practice?mode=full', {
                    state: {
                      prefilledSkills: roadmap.focus_skills || [],
                      prefillSource: 'study plan',
                      targetCompanyId: roadmap.company_id || '',
                      targetRoleId: roadmap.role_id || '',
                    },
                  })}
                  className="hub-button hub-button-primary"
                  data-testid="roadmap-start-practice">
            Start practice now →
          </button>
          <button type="button" onClick={() => navigate(gapAnalysisPath(userId, roleId))}
                  className="hub-button">
            ← Back to gap analysis
          </button>
        </div>

        {roadmap.disclaimer && (
          <p
            data-testid="roadmap-disclaimer"
            className="hub-caption mt-10 border-t border-[var(--color-border)] pt-4"
          >
            <span className="font-medium text-[var(--color-ink)]">Note:</span> {roadmap.disclaimer}
          </p>
        )}
      </div>
    </main>
  );
}
