import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { fetchRoadmap, fetchMyRoadmap } from '../lib/api';

const SUPPORTED_DAYS = [7, 14, 30];

const SEVERITY_COLOR = {
  Untested: '#9CA3AF',
  High:     '#EF4444',
  Medium:   '#F59E0B',
  Low:      '#10B981',
};

function ConceptPill({ topic }) {
  const color = SEVERITY_COLOR[topic.severity] || SEVERITY_COLOR.Low;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs"
      style={{
        fontFamily: "'Inter', sans-serif",
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
    <div
      data-testid="roadmap-week-card"
      className="rounded-2xl border border-black/8 p-6 relative"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F]"
             style={{ fontFamily: "'Inter', sans-serif" }}>
            Week {block.index} · {block.day_range}
          </p>
          <h3
            className="text-2xl tracking-tight"
            style={{ fontFamily: "'Instrument Serif', serif", letterSpacing: '-0.5px' }}
          >
            {block.label}
          </h3>
        </div>
        {isFirst && (
          <span className="rounded-full text-xs px-2 py-0.5 bg-black text-white"
                style={{ fontFamily: "'Inter', sans-serif" }}>
            Start here
          </span>
        )}
      </div>

      <div className="mb-4">
        <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
           style={{ fontFamily: "'Inter', sans-serif" }}>
          Focus skills
        </p>
        <div className="flex flex-wrap gap-2">
          {block.focus_skills.length === 0 && (
            <span className="text-sm text-[#6F6F6F]"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
              No focus skills queued.
            </span>
          )}
          {block.focus_skills.map((s) => (
            <span key={s} className="rounded-full border border-black/10 px-3 py-1 text-xs"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
              {s}
            </span>
          ))}
        </div>
      </div>

      {block.focus_topics.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
             style={{ fontFamily: "'Inter', sans-serif" }}>
            Concepts to cover
          </p>
          <div className="flex flex-wrap gap-1.5" data-testid="roadmap-concepts">
            {block.focus_topics.slice(0, 12).map((t, idx) => (
              <ConceptPill key={`${t.skill}-${t.concept || idx}`} topic={t} />
            ))}
            {block.focus_topics.length > 12 && (
              <span className="text-xs text-[#6F6F6F]"
                    style={{ fontFamily: "'Inter', sans-serif" }}>
                +{block.focus_topics.length - 12} more
              </span>
            )}
          </div>
        </div>
      )}

      {block.daily_practice_suggestions.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-2"
             style={{ fontFamily: "'Inter', sans-serif" }}>
            Daily practice
          </p>
          <ul className="space-y-1.5">
            {block.daily_practice_suggestions.map((s, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-black"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
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
      <div className="min-h-screen bg-white flex items-center justify-center">
        <p className="text-sm text-[#6F6F6F]" style={{ fontFamily: "'Inter', sans-serif" }}>
          Building your roadmap…
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
        <button onClick={() => navigate(-1)}
                className="mt-6 rounded-full px-5 py-2 text-sm font-medium text-white bg-black">
          ← Back
        </button>
      </div>
    );
  }

  if (!roadmap) return null;

  return (
    <div className="min-h-screen bg-white" data-testid="roadmap-page">
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

      <div className="max-w-5xl mx-auto px-6 pt-12 pb-24">
        <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F] mb-3"
           style={{ fontFamily: "'Inter', sans-serif" }}>
          Roadmap · {roadmap.company_name} · {roadmap.role_title}
        </p>

        <h1
          className="tracking-tight mb-4"
          style={{
            fontFamily: "'Instrument Serif', serif",
            letterSpacing: '-1.5px',
            fontSize: 'clamp(40px, 6vw, 64px)',
          }}
          data-testid="roadmap-title"
        >
          Your {roadmap.days}-day study plan
        </h1>

        <p className="text-base text-[#6F6F6F] mb-6 max-w-2xl leading-relaxed"
           style={{ fontFamily: "'Inter', sans-serif" }}>
          {roadmap.plan_note}
        </p>

        <div className="rounded-2xl border border-black/8 p-4 mb-10 flex flex-wrap items-center gap-4">
          <p className="text-xs font-medium uppercase tracking-wider text-[#6F6F6F]"
             style={{ fontFamily: "'Inter', sans-serif" }}>
            Plan length
          </p>
          <div className="flex gap-2" data-testid="roadmap-day-toggle">
            {SUPPORTED_DAYS.map((d) => (
              <button
                key={d}
                onClick={() => onDaysChange(d)}
                className="rounded-full px-4 py-1.5 text-xs font-medium cursor-pointer border transition-all"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  borderColor: d === days ? '#000' : 'rgba(0,0,0,0.10)',
                  backgroundColor: d === days ? '#000' : 'transparent',
                  color: d === days ? '#fff' : '#000',
                }}
              >
                {d} days
              </button>
            ))}
          </div>
          <div className="grow" />
          <p className="text-xs text-[#6F6F6F]"
             style={{ fontFamily: "'Inter', sans-serif" }}>
            Current readiness:{' '}
            <span className="font-medium text-black">
              {Math.round(roadmap.overall_readiness_percentage)}%
            </span>
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2" data-testid="roadmap-weeks">
          {roadmap.weekly_blocks.map((b, i) => (
            <WeekCard key={b.index} block={b} isFirst={i === 0} />
          ))}
        </div>

        <div className="mt-12 flex flex-wrap gap-3">
          <button onClick={() => navigate('/practice?mode=full', {
                    state: {
                      prefilledSkills: roadmap.focus_skills || [],
                      prefillSource: 'study plan',
                      targetCompanyId: roadmap.company_id || '',
                      targetRoleId: roadmap.role_id || '',
                    },
                  })}
                  className="rounded-full px-6 py-3 text-sm font-medium text-white bg-black cursor-pointer"
                  style={{ fontFamily: "'Inter', sans-serif" }}
                  data-testid="roadmap-start-practice">
            Start practice now →
          </button>
          <button onClick={() => navigate(`/gap-analysis/${userId}/${roleId}`)}
                  className="rounded-full px-6 py-3 text-sm font-medium text-black border border-black/15 hover:border-black/30 cursor-pointer"
                  style={{ fontFamily: "'Inter', sans-serif" }}>
            ← Back to gap analysis
          </button>
        </div>

        {roadmap.disclaimer && (
          <p
            data-testid="roadmap-disclaimer"
            className="mt-10 text-xs text-[#6F6F6F] leading-relaxed border-t border-black/5 pt-4"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            <span className="font-medium text-black">Note:</span> {roadmap.disclaimer}
          </p>
        )}
      </div>
    </div>
  );
}
