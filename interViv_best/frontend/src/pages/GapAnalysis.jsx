import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchGapAnalysis, fetchMyGapAnalysis } from '../lib/api';
import ResourceLinks from '../components/ResourceLinks';

const SEVERITY_COLORS = {
  Untested: { bar: '#9CA3AF', tag: '#374151', bg: '#F3F4F6' },
  High:     { bar: '#EF4444', tag: '#991B1B', bg: '#FEE2E2' },
  Medium:   { bar: '#F59E0B', tag: '#92400E', bg: '#FEF3C7' },
  Low:      { bar: '#10B981', tag: '#065F46', bg: '#D1FAE5' },
};

function SeverityBadge({ severity }) {
  const c = SEVERITY_COLORS[severity] || SEVERITY_COLORS.Low;
  return (
    <span
      className="text-xs font-medium rounded-full px-2 py-0.5"
      style={{ color: c.tag, backgroundColor: c.bg, fontFamily: "'Inter', sans-serif" }}
    >
      {severity}
    </span>
  );
}

function SkillBar({ gap }) {
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
                style={{ fontFamily: "'Inter', sans-serif" }}>
            {gap.display_name}
          </span>
          <SeverityBadge severity={gap.gap_severity} />
        </div>
        <span className="text-xs text-[#6F6F6F] whitespace-nowrap"
              style={{ fontFamily: "'Inter', sans-serif" }}>
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
      <div className="min-h-screen bg-white flex items-center justify-center">
        <p className="text-sm text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>
          Computing your readiness…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white px-6 py-16 max-w-3xl mx-auto">
        <p className="text-sm text-red-700" style={{ fontFamily: "'Inter', sans-serif" }}>
          {error}
        </p>
        <button
          onClick={() => navigate('/upload')}
          className="mt-6 rounded-full px-5 py-2 text-sm font-medium text-white bg-black"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          ← Back to Upload
        </button>
      </div>
    );
  }

  if (!report) return null;

  const readiness = Math.round(report.overall_readiness_percentage);

  return (
    <div className="min-h-screen bg-white" data-testid="gap-analysis-page">
      <nav className="w-full border-b border-black/5">
        <div className="flex items-center justify-between px-8 py-5 max-w-7xl mx-auto">
          <a href="/" onClick={(e) => { e.preventDefault(); navigate('/'); }}
             className="text-2xl tracking-tight text-black"
             style={{ fontFamily: "'Instrument Serif', serif" }}>
            interViv<sup className="text-xs align-super">©</sup>
          </a>
          <button onClick={() => navigate(-1)}
                  className="text-sm text-[#6F6F6F] hover:text-black"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
            ← Back
          </button>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 pt-12 pb-24">
        <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-3"
           style={{ fontFamily: "'Inter', sans-serif" }}>
          Gap analysis · {report.company_name} · {report.role_title}
        </p>

        <div className="flex items-baseline gap-4 mb-2">
          <h1
            className="tracking-tight"
            style={{
              fontFamily: "'Instrument Serif', serif",
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
             style={{ fontFamily: "'Inter', sans-serif" }}>
            readiness against {report.company_name} {report.role_title}
            <br />
            <span className="text-xs">
              over {report.tested_skill_count}/{report.required_skill_count} required skills tested
            </span>
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

        <div className="grid md:grid-cols-3 gap-6 mb-12">
          <div className="md:col-span-2 rounded-2xl border border-black/8 p-6">
            <h2 className="text-xl tracking-tight mb-1"
                style={{ fontFamily: "'Instrument Serif', serif", letterSpacing: '-0.5px' }}>
              Per-skill readiness
            </h2>
            <p className="text-xs text-[#6F6F6F] mb-4"
               style={{ fontFamily: "'Inter', sans-serif" }}>
              Coloured bar = your level; pale track = role target.
              Severity = required − your level (High &gt; 25, Medium 11–25, Low ≤ 10).
            </p>
            <div>
              {report.per_skill_gap.map((g) => <SkillBar key={g.skill} gap={g} />)}
            </div>
          </div>

          <div className="rounded-2xl border border-black/8 p-6"
               data-testid="ranked-weak-areas">
            <h2 className="text-xl tracking-tight mb-1"
                style={{ fontFamily: "'Instrument Serif', serif", letterSpacing: '-0.5px' }}>
              Top weak areas
            </h2>
            <p className="text-xs text-[#6F6F6F] mb-4"
               style={{ fontFamily: "'Inter', sans-serif" }}>
              Ranked by importance × gap.
            </p>
            <ol className="space-y-3">
              {topWeakAreas.map((w, i) => (
                <li key={w.skill} className="flex items-start gap-3">
                  <span
                    className="w-6 h-6 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold flex-shrink-0"
                    style={{ fontFamily: "'Inter', sans-serif" }}
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-black"
                       style={{ fontFamily: "'Inter', sans-serif" }}>
                      {w.display_name}
                    </p>
                    <p className="text-xs text-[#6F6F6F] mt-0.5"
                       style={{ fontFamily: "'Inter', sans-serif" }}>
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
                    style={{ fontFamily: "'Inter', sans-serif" }}>
                  No weak areas — you're matching role targets!
                </li>
              )}
            </ol>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            onClick={startPracticeOnWeakest}
            disabled={topWeakAreas.length === 0}
            className="rounded-full px-6 py-3 text-sm font-medium text-white bg-black disabled:opacity-30 cursor-pointer"
            style={{ fontFamily: "'Inter', sans-serif" }}
            data-testid="start-practice-cta"
          >
            Start practice on weak areas →
          </button>
          <button
            onClick={() => navigate(`/roadmap/${userId}/${roleId}?days=30`)}
            className="rounded-full px-6 py-3 text-sm font-medium text-white bg-black/80 hover:bg-black cursor-pointer"
            style={{ fontFamily: "'Inter', sans-serif" }}
            data-testid="build-roadmap-cta"
          >
            Build my study plan →
          </button>
          <button
            onClick={() => navigate('/practice')}
            className="rounded-full px-6 py-3 text-sm font-medium text-black border border-black/15 hover:border-black/30 cursor-pointer"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            General practice
          </button>
        </div>

        {report.disclaimer && (
          <p
            data-testid="gap-disclaimer"
            className="mt-10 text-xs text-[#6F6F6F] leading-relaxed border-t border-black/5 pt-4"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            <span className="font-medium text-black">Note:</span> {report.disclaimer}
          </p>
        )}
      </div>
    </div>
  );
}
