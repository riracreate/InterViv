import React, { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate, useLocation, useSearchParams, Link } from "react-router-dom";
import { backDestination } from "../lib/backNavigation";
import { motion } from "motion/react";
import {
  ArrowLeft,
  Download,
  Share2,
  Sparkles,
} from "lucide-react";
import { fetchDashboard } from "../lib/api";
import { mapRealDataToDashboard, scoreAccent } from "../lib/dashboardMapping";
import AccountMenu from "../components/AccountMenu";

import { ScoreHero } from "../components/dashboard/ScoreHero";
import { ReviewSummary } from "../components/dashboard/ReviewSummary";
import { BlockResults } from "../components/dashboard/BlockResults";
import { LayerBreakdown } from "../components/dashboard/LayerBreakdown";
import { SkillRadar } from "../components/dashboard/SkillRadar";
import { PerformanceChart } from "../components/dashboard/PerformanceChart";
import { RoundTimeline } from "../components/dashboard/RoundTimeline";
import { StrengthsWeaknesses } from "../components/dashboard/StrengthsWeaknesses";
import { FeedbackCards } from "../components/dashboard/FeedbackCards";
import { ScoringBreakdownPanel } from "../components/dashboard/ScoringBreakdownPanel";
import Phase2InsightsPanel from "../components/dashboard/Phase2InsightsPanel";
import { McqRoundReview } from "../components/dashboard/McqRoundReview";
import TranscriptReview from "../components/dashboard/TranscriptReview";


const pageMotion = {
  initial: { opacity: 0, y: 18, filter: "blur(10px)" },
  animate: { opacity: 1, y: 0,  filter: "blur(0px)"  },
  transition: { duration: 0.7, ease: [0.2, 0.8, 0.2, 1] },
};
const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } } };
const item = {
  hidden: { opacity: 0, y: 14, filter: "blur(10px)" },
  show:   { opacity: 1, y: 0,  filter: "blur(0px)",  transition: { duration: 0.55, ease: [0.2, 0.8, 0.2, 1] } },
};

function GlassButton({ icon, label, variant = "primary", onClick }) {
  const base = "group inline-flex items-center justify-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium transition-all duration-300 active:translate-y-[1px]";
  const primary   = "bg-[var(--color-surface)] text-[var(--color-ink)] border border-[var(--color-border)] shadow-sm hover:bg-[var(--color-surface)] hover:border-[var(--color-border)]";
  const secondary = "bg-[var(--color-surface)] text-[var(--color-ink)] border border-[var(--color-border)] hover:bg-[var(--color-surface)] hover:border-[var(--color-border)]";
  return (
    <button className={`${base} ${variant === "secondary" ? secondary : primary}`} type="button" onClick={onClick}>
      <span className="opacity-90 group-hover:opacity-100 transition-opacity">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

export const REPORT_TABS = [
  { id: "overview", label: "Overview & readiness" },
  { id: "rounds", label: "Round review" },
  { id: "skills", label: "Skills & next steps" },
] as const;

/** One strength, one weakness and one next action, with a practice CTA. */
export function ExecutiveSummary({ data, onPractice }) {
  const strength = data.highlights.strengths[0];
  const weakness = data.highlights.weaknesses[0];
  const prioritySkills = (data.reviewSummary?.prioritySkills || []).map((p) => p.skill).slice(0, 3);
  return (
    <section aria-label="Summary" data-testid="report-summary" className="grid gap-4 md:grid-cols-3">
      <div className="glass-panel rounded-2xl p-4">
        <p className="text-xs uppercase tracking-wider text-[var(--color-ink-muted)]">Strength</p>
        <p className="mt-1 font-medium">{strength ? strength.title : "Not enough measured rounds yet"}</p>
        {strength && <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{strength.detail}</p>}
      </div>
      <div className="glass-panel rounded-2xl p-4">
        <p className="text-xs uppercase tracking-wider text-[var(--color-ink-muted)]">To improve</p>
        <p className="mt-1 font-medium">{weakness ? weakness.title : "No weak area measured"}</p>
        {weakness && <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{weakness.detail}</p>}
      </div>
      <div className="glass-panel rounded-2xl p-4">
        <p className="text-xs uppercase tracking-wider text-[var(--color-ink-muted)]">Next action</p>
        <p className="mt-1 text-sm text-[var(--color-ink)]">{data.reviewSummary?.nextStep}</p>
        <button type="button" onClick={() => onPractice(prioritySkills)} data-testid="report-practice-next"
          className="mt-3 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-sm font-medium hover:bg-[var(--color-surface)]">
          {prioritySkills.length ? `Practice ${prioritySkills.join(", ")}` : "Practice next"} →
        </button>
      </div>
    </section>
  );
}

export default function Dashboard() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const tab = REPORT_TABS.some((t) => t.id === requestedTab) ? requestedTab : "overview";
  const selectTab = (id) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", id);
    setSearchParams(next, { replace: true });
  };
  const practiceNext = (skills) => navigate("/practice?mode=full", {
    state: skills.length ? { prefilledSkills: skills, prefillSource: "session report" } : undefined,
  });
  const [raw, setRaw] = useState(null);
  const [loading, setLoading] = useState(Boolean(sessionId));
  const [err, setErr] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [copyStatus, setCopyStatus] = useState('');

  useEffect(() => {
    if (!sessionId) { setLoading(false); return; }
    setLoading(true);
    setErr('');
    fetchDashboard(sessionId)
      .then(data => { setRaw(data); setLoading(false); })
      .catch(e => { setErr(e.message); setLoading(false); });
  }, [sessionId, retryCount]);

  async function copyReportLink() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(window.location.href);
      setCopyStatus('Report link copied. Anyone opening it must sign in to view the report.');
    } catch {
      setCopyStatus('Copying failed. Copy the link from your browser address bar instead.');
    }
  }

  const data = useMemo(() => raw ? mapRealDataToDashboard(raw) : null, [raw]);
  const accent = data ? scoreAccent(data.overall.score) : { ring: "from-cyan-400/70 to-blue-500/70", text: "text-[var(--color-accent)]" };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--color-surface)] flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin mb-4 mx-auto" />
          <p className="text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>Loading results...</p>
        </div>
      </div>
    );
  }

  if (err || !data) {
    return (
      <div className="min-h-screen bg-[var(--color-surface)] flex items-center justify-center">
        <div className="text-center">
          <p role="alert" className="text-sm text-[var(--color-ink-muted)] mb-4" style={{ fontFamily: "var(--font-body)" }}>
            {err || "Session not found."}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button onClick={() => setRetryCount((value) => value + 1)}
              className="rounded-full px-6 py-2.5 text-sm text-[var(--color-ink)] bg-[var(--color-surface)] border border-[var(--color-border)] hover:bg-[var(--color-surface)] transition-all"
              style={{ fontFamily: "var(--font-body)" }}>
              Try again
            </button>
            <button onClick={() => navigate('/upload')}
              className="rounded-full px-6 py-2.5 text-sm text-[var(--color-ink)] bg-[var(--color-surface)] border border-[var(--color-border)] hover:bg-[var(--color-surface)] transition-all"
              style={{ fontFamily: "var(--font-body)" }}>
              Start New Session
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-[var(--color-surface)] text-[var(--color-ink)] selection:bg-cyan-300/20 selection:text-[var(--color-ink)]">
      <motion.div {...pageMotion} className="relative mx-auto w-full max-w-7xl px-4 pb-14 pt-8 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Back to wherever the report was opened from; Progress lists reports. */}
          <button onClick={() => {
              const target = backDestination(location, '/dashboard');
              if (typeof target === 'number') navigate(target); else navigate(target);
            }}
            data-testid="report-back"
            className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-sm text-[var(--color-ink)] backdrop-blur-xl transition hover:bg-[var(--color-surface)]"
            style={{ fontFamily: "var(--font-body)" }}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div className="flex flex-wrap items-center gap-2">
            {raw?.target_role_id && raw?.user_id && (
              <Link
                to={`/gap-analysis/${encodeURIComponent(raw.user_id)}/${encodeURIComponent(raw.target_role_id)}`}
                className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm text-[var(--color-accent)] backdrop-blur-xl transition hover:bg-cyan-500/20"
                style={{ fontFamily: "var(--font-body)" }}
                data-testid="dashboard-to-gap-analysis"
              >
                Readiness vs. target →
              </Link>
            )}
            <AccountMenu />
            <span className="hidden sm:inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs text-[var(--color-ink-muted)] backdrop-blur-xl">
              <Sparkles className="h-3.5 w-3.5 text-[var(--color-accent)]" />
              interViv Results
            </span>
          </div>
        </div>

        <motion.div variants={stagger} initial="hidden" animate="show" className="mt-6">
          <motion.div variants={item}>
            <ScoreHero
              accentRingClass={accent.ring}
              accentTextClass={accent.text}
              overallScore={data.overall.score}
              gradeLabel={data.overall.gradeLabel}
              deltaLabel={data.overall.deltaLabel}
              sessionTitle={data.session.title}
              role={data.session.role}
              dateLabel={data.session.dateLabel}
              durationLabel={data.session.durationLabel}
              skillFocus={data.session.skillFocus}
            />
          </motion.div>

          <motion.div variants={item} className="mt-6">
            <ExecutiveSummary data={data} onPractice={practiceNext} />
          </motion.div>

          <div role="tablist" aria-label="Report sections" className="mt-8 flex flex-wrap gap-2" data-testid="report-tabs">
            {REPORT_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                id={`report-tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`report-panel-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                onClick={() => selectTab(t.id)}
                onKeyDown={(e) => {
                  if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
                  const index = REPORT_TABS.findIndex((x) => x.id === tab);
                  const step = e.key === "ArrowRight" ? 1 : REPORT_TABS.length - 1;
                  const nextTab = REPORT_TABS[(index + step) % REPORT_TABS.length];
                  selectTab(nextTab.id);
                  document.getElementById(`report-tab-${nextTab.id}`)?.focus();
                }}
                className={`rounded-full border px-4 py-2 text-sm transition ${
                  tab === t.id ? "border-[var(--color-border)] bg-[var(--color-surface)] font-semibold" : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-ink-muted)] hover:bg-[var(--color-surface)]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div role="tabpanel" id={`report-panel-${tab}`} aria-labelledby={`report-tab-${tab}`} className="mt-6">
            {tab === "overview" && (
              <div className="space-y-8">
                {data.reviewSummary && <ReviewSummary {...data.reviewSummary} />}
                {data.multiBlock && data.blocks.length > 1 && <BlockResults blocks={data.blocks} />}
                {data.overall.score != null && (data.layers.length > 0 || data.radar.length >= 3) && (
                  <div className="grid gap-6 lg:grid-cols-12">
                    {data.layers.length > 0 && (
                      <div className="lg:col-span-5"><LayerBreakdown layers={data.layers} /></div>
                    )}
                    {data.radar.length >= 3 && (
                      <div className="lg:col-span-7"><SkillRadar data={data.radar} /></div>
                    )}
                  </div>
                )}
                <PerformanceChart
                  finalRating={data.performance.finalRating}
                  difficulty={data.performance.difficulty}
                  score={data.performance.score}
                />
              </div>
            )}

            {tab === "rounds" && (
              <div className="space-y-8">
                <TranscriptReview rounds={data.rounds} />
                <RoundTimeline rounds={data.rounds} />
                {(data.mcqReviews || []).map((review, index) => (
                  <McqRoundReview key={`mcq-review-${index}`} review={review} />
                ))}
                <details className="glass-panel rounded-3xl p-5" data-testid="report-scoring-details">
                  <summary className="cursor-pointer text-sm font-medium">Scoring details (how each round was scored)</summary>
                  <div className="mt-4"><ScoringBreakdownPanel rounds={data.rounds} /></div>
                </details>
              </div>
            )}

            {tab === "skills" && (
              <div className="space-y-8">
                <Phase2InsightsPanel
                  userId={raw?.user_id || null}
                  targetRoleId={raw?.target_role_id || null}
                />
                {(data.highlights.strengths.length > 0 || data.highlights.weaknesses.length > 0) && (
                  <StrengthsWeaknesses strengths={data.highlights.strengths} weaknesses={data.highlights.weaknesses} />
                )}
                <FeedbackCards cards={data.feedbackCards} />
                <div className="glass-panel rounded-3xl p-5 sm:p-6">
                  <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
                    <div>
                      <div className="text-2xl sm:text-3xl font-normal tracking-tight"
                        style={{ fontFamily: "var(--font-display)" }}>
                        Next moves
                      </div>
                      <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
                        Export your report, copy its link, or start another session.
                      </p>
                    </div>
                    <div className="flex w-full flex-col gap-2 sm:w-auto sm:items-end">
                      <div className="report-actions flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:justify-end">
                        <GlassButton variant="primary"   icon={<Download className="h-4 w-4 text-[var(--color-accent)]" />}   label="Download report" onClick={() => window.print()} />
                        <GlassButton variant="secondary" icon={<Share2    className="h-4 w-4 text-[var(--color-ink)]" />}   label="Copy report link"  onClick={copyReportLink} />
                        <GlassButton variant="secondary" icon={<Sparkles  className="h-4 w-4 text-[var(--color-ink)]" />}   label="New session"  onClick={() => navigate('/practice')} />
                      </div>
                      <p aria-live="polite" className="text-sm text-[var(--color-ink-muted)] sm:text-right">
                        {copyStatus || 'Reports require sign-in. Copying this link does not grant access on its own.'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
