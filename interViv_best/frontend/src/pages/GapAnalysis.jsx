import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchGapAnalysis, fetchMyGapAnalysis } from '../lib/api';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';
import '../styles/hub.css';

const SEVERITY_COLORS = {
  Untested: { bar: '#9CA3AF', tag: '#374151', bg: '#F3F4F6' },
  High:     { bar: 'var(--color-danger)', tag: '#991B1B', bg: 'var(--color-danger-soft)' },
  Medium:   { bar: 'var(--color-warn)', tag: '#92400E', bg: 'var(--color-warn-soft)' },
  Low:      { bar: 'var(--color-success)', tag: '#065F46', bg: 'var(--color-success-soft)' },
};

function SeverityBadge({ severity }) {
  const c = SEVERITY_COLORS[severity] || SEVERITY_COLORS.Low;
  return (
    <span
      className="text-xs font-medium rounded-full px-2 py-0.5"
      style={{ color: c.tag, backgroundColor: c.bg, fontFamily: "var(--font-body)" }}
    >
      {severity}
    </span>
  );
}

function SkillBar({ gap, minAttempts = 3 }) {
  const colors = SEVERITY_COLORS[gap.gap_severity] || SEVERITY_COLORS.Low;
  const studentPct = gap.tested && gap.required_level > 0
    ? Math.min(100, (gap.student_level / gap.required_level) * 100)
    : 0;
  const requiredPct = 100;
  return (
    <div className="py-3 border-b border-black/5 last:border-0" data-testid="gap-skill-row">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-medium text-black truncate"
                style={{ fontFamily: "var(--font-body)" }}>
            {gap.display_name}
          </span>
          <SeverityBadge severity={gap.gap_severity} />
          {gap.evidence_level === 'provisional' && (
            <span className="text-[11px] px-2 py-0.5 rounded-full border border-black/10 text-[#6F6F6F]"
                  title="Fewer measured attempts than needed for a settled level; readiness is discounted."
                  data-testid="provisional-chip">
              provisional · {gap.attempts}/{minAttempts}
            </span>
          )}
        </div>
        <span className="text-xs text-[#6F6F6F] whitespace-nowrap"
              style={{ fontFamily: "var(--font-body)" }}>
          {gap.tested
            ? `${Math.round(gap.student_level)} / ${Math.round(gap.required_level)}`
            : `— / ${Math.round(gap.required_level)} (untested)`}
          {' · w '}{Math.round((gap.importance_weight || 0) * 100)}%
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-black/5 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${requiredPct}%`, backgroundColor: '#F3F4F6' }}
        />
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${studentPct}%`, backgroundColor: colors.bar }}
        />
      </div>
    </div>
  );
}

export default function GapAnalysis() {
  const { userId, roleId } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    const loader = (userId === 'me')
      ? fetchMyGapAnalysis(roleId)
      : fetchGapAnalysis(userId, roleId);

    loader
      .then((data) => { if (!cancelled) { setReport(data); setLoading(false); } })
      .catch((err) => { if (!cancelled) { setError(err.message || 'Failed to load gap analysis.'); setLoading(false); } });
    return () => { cancelled = true; };
  }, [userId, roleId]);

  const topWeakAreas = useMemo(() => (report?.ranked_weak_areas || []).slice(0, 5), [report]);

  const startPracticeOnWeakest = () => {
    if (!report || topWeakAreas.length === 0) {
      navigate('/practice');
      return;
    }
    navigate('/practice?mode=full', {
      state: {
        prefilledSkills: topWeakAreas.map(w => w.skill),
        prefillSource: 'gap analysis',
        targetCompanyId: report.company_id || '',
        targetRoleId: report.role_id || '',
      },
    });
  };

  if (loading) {
    return (
      <main className="hub-page">
        <div className="hub-container">
          <AppNav userId={userId === 'me' ? null : userId} roleId={roleId} />
          <p className="hub-loading" role="status">Computing your readiness…</p>
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
          <button type="button" onClick={() => navigate('/upload')} className="hub-button hub-button-primary">
            ← Back to Upload
          </button>
        </div>
      </main>
    );
  }

  if (!report) return null;

  // Headline is the conservative figure: thin evidence (few measured attempts)
  // is discounted toward an average level, never inflated. Observed is shown beside it.
  const observed = Math.round(report.overall_readiness_percentage);
  const hasConservative = typeof report.overall_readiness_conservative === 'number';
  const readiness = hasConservative ? Math.round(report.overall_readiness_conservative) : observed;
  const minAttempts = report.established_min_attempts || 3;

  return (
    <main className="hub-page" data-testid="gap-analysis-page">
      <div className="hub-container">
        <AppNav userId={report.user_id || (userId === 'me' ? null : userId)} roleId={report.role_id || roleId} />

        <header className="hub-page-hero">
        <p className="hub-eyebrow">
          Gap analysis · {report.company_name} · {report.role_title}
        </p>

        <div className="flex items-baseline gap-4 mb-2">
          <h1
            className="tracking-tight"
            style={{
              fontFamily: "var(--font-display)",
              color: '#000',
              letterSpacing: '-2px',
              fontSize: 'clamp(56px, 12vw, 120px)',
              lineHeight: 1,
            }}
            data-testid="overall-readiness"
          >
            {readiness}%
          </h1>
          <p className="text-base text-[#6F6F6F]"
             style={{ fontFamily: "var(--font-body)" }}>
            {hasConservative ? 'conservative readiness' : 'readiness'} against {report.company_name} {report.role_title}
            <br />
            <span className="text-xs">
              over {report.tested_skill_count}/{report.required_skill_count} required skills tested
            </span>
            {hasConservative && (
              <>
                <br />
                <span className="text-xs" data-testid="observed-readiness">
                  Observed average {observed}%
                  {report.provisional_skill_count > 0
                    ? ` · ${report.provisional_skill_count} skill${report.provisional_skill_count === 1 ? '' : 's'} still provisional (fewer than ${minAttempts} measured attempts)`
                    : ''}
                </span>
              </>
            )}
          </p>
        </div>

        <div className="h-2 rounded-full bg-black/5 overflow-hidden mb-12">
          <div
            className="h-full rounded-full"
            style={{
              width: `${Math.min(100, Math.max(2, readiness))}%`,
              backgroundColor: readiness >= 75 ? '#10B981' : readiness >= 50 ? '#F59E0B' : '#EF4444',
              transition: 'width 0.6s ease',
            }}
          />
        </div>

        </header>

        <div className="grid md:grid-cols-3 gap-6 mb-12">
          <div className="hub-card md:col-span-2">
            <h2 className="text-xl tracking-tight mb-1"
                style={{ fontFamily: "var(--font-display)", letterSpacing: '-0.5px' }}>
              Per-skill readiness
            </h2>
            <p className="hub-caption mb-4">
              Coloured bar = your level; pale track = role target.
              Severity = required − your level (High &gt; 25, Medium 11–25, Low ≤ 10).
            </p>
            <div>
              {report.per_skill_gap.map((g) => <SkillBar key={g.skill} gap={g} minAttempts={minAttempts} />)}
            </div>
          </div>

          <div className="hub-card" data-testid="ranked-weak-areas">
            <h2 className="text-xl tracking-tight mb-1"
                style={{ fontFamily: "var(--font-display)", letterSpacing: '-0.5px' }}>
              Top weak areas
            </h2>
            <p className="hub-caption mb-4">
              Ranked by importance × gap.
            </p>
            <ol className="space-y-3">
              {topWeakAreas.map((w, i) => (
                <li key={w.skill} className="flex items-start gap-3">
                  <span
                    className="w-6 h-6 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold flex-shrink-0"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-black"
                       style={{ fontFamily: "var(--font-body)" }}>
                      {w.display_name}
                    </p>
                    <p className="text-xs text-[#6F6F6F] mt-0.5"
                       style={{ fontFamily: "var(--font-body)" }}>
                      <SeverityBadge severity={w.gap_severity} />{' '}
                      {w.tested
                        ? `gap ${Math.round((w.required_level - (w.student_level || 0)))} pts`
                        : 'never tested'}
                    </p>
                    <ResourceLinks
                      skillId={w.skill || w.display_name}
                      heading="Lecture / docs"
                      variant="light"
                      maxPerLevel={3}
                    />
                  </div>
                </li>
              ))}
              {topWeakAreas.length === 0 && (
                <li className="text-sm text-[#6F6F6F]"
                    style={{ fontFamily: "var(--font-body)" }}>
                  No weak areas — you're matching role targets!
                </li>
              )}
            </ol>
          </div>
        </div>

        <div className="hub-toolbar">
          <button
            type="button"
            onClick={startPracticeOnWeakest}
            disabled={topWeakAreas.length === 0}
            className="hub-button hub-button-primary"
            data-testid="start-practice-cta"
          >
            Start practice on weak areas →
          </button>
          <button
            type="button"
            onClick={() => navigate(`/roadmap/${userId}/${roleId}?days=30`)}
            className="hub-button hub-button-primary"
            data-testid="build-roadmap-cta"
          >
            Build my study plan →
          </button>
          <button
            type="button"
            onClick={() => navigate('/practice')}
            className="hub-button"
          >
            General practice
          </button>
        </div>

        {report.disclaimer && (
          <p
            data-testid="gap-disclaimer"
            className="hub-caption mt-10 border-t border-[var(--color-border)] pt-4"
          >
            <span className="font-medium text-[var(--color-ink)]">Note:</span> {report.disclaimer}
          </p>
        )}
      </div>
    </main>
  );
}
