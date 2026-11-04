import React, { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate, useLocation, Link } from "react-router-dom";
import { backDestination } from "../lib/backNavigation";
import { motion } from "motion/react";
import {
  ArrowLeft,
  BarChart3,
  Clock,
  Download,
  Map,
  Play,
  RotateCcw,
  Share2,
  Sparkles,
  Target,
  Upload,
} from "lucide-react";
import { fetchDashboard, fetchLearningSignals, fetchAtsRuns, fetchMe, fetchAccountOverview } from "../lib/api";
import { mapRealDataToDashboard, scoreAccent } from "../lib/dashboardMapping";
import { displayScore, observedReadinessNote, sessionLabel } from "../lib/accountOverview";
import AppNav from "../components/AppNav";
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
  const primary   = "bg-white/10 text-white border border-white/15 shadow-[0_20px_60px_rgba(0,0,0,0.55)] hover:bg-white/14 hover:border-white/25";
  const secondary = "bg-black/20 text-white/90 border border-white/10 hover:bg-black/30 hover:border-white/18";
  return (
    <button className={`${base} ${variant === "secondary" ? secondary : primary}`} type="button" onClick={onClick}>
      <span className="opacity-90 group-hover:opacity-100 transition-opacity">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function DashboardCard({ icon, title, value = null, detail, action = null, muted = false }) {
  return (
    <div className="flex min-h-[172px] flex-col justify-between rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <div>
        <div className="flex items-start justify-between gap-4">
          <div className={`flex h-10 w-10 items-center justify-center rounded-[var(--radius-card)] ${muted ? "bg-slate-100 text-slate-500" : "bg-[var(--color-ink)] text-white"}`}>
            {icon}
          </div>
          {value && <span className="rounded-md bg-[var(--color-success-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--color-success)]">{value}</span>}
        </div>
        <h3 className="mt-4 text-lg font-semibold tracking-normal text-[var(--color-ink)]">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-[var(--color-ink-muted)]">{detail}</p>
      </div>
      {action && <div className="mt-5 border-t border-[var(--color-border)] pt-3 text-sm font-semibold text-[var(--color-ink)]">{action}</div>}
    </div>
  );
}

function formatFrac(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return `${Math.round(Number(value) * 100)}%`;
}

function LearningSignalsBlock({ signals }) {
  const topDelta = (signals?.elo_deltas || []).slice(-3).reverse();
  const topRevisit = (signals?.revisit_rates || []).slice(0, 3);
  const roadmap = signals?.roadmap_completion || {};

  return (
    <section className="mt-6 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold tracking-normal text-[var(--color-ink)]">Learning signals</h2>
        <p className="text-xs uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">Elo · revisit · roadmap</p>
      </div>
      {!signals ? (
        <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]">
          Sign in and complete practice rounds to see Elo deltas, revisit rates, and roadmap completion.
        </p>
      ) : (
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">Elo delta</p>
            {topDelta.length === 0 ? (
              <p className="mt-2 text-sm text-[var(--color-ink-muted)]">No Elo events yet.</p>
            ) : (
              <ul className="mt-2 space-y-1.5 text-sm text-[var(--color-ink)]">
                {topDelta.map((row) => (
                  <li key={`${row.skill}-${row.session_id}`}>
                    {row.skill}: {row.delta >= 0 ? "+" : ""}{row.delta}
                    <span className="text-[var(--color-ink-muted)]"> (cum {row.cumulative_delta >= 0 ? "+" : ""}{row.cumulative_delta})</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">Revisit rate</p>
            {topRevisit.length === 0 ? (
              <p className="mt-2 text-sm text-[var(--color-ink-muted)]">No skill retries yet.</p>
            ) : (
              <ul className="mt-2 space-y-1.5 text-sm text-[var(--color-ink)]">
                {topRevisit.map((row) => (
                  <li key={row.skill}>
                    {row.skill}: {formatFrac(row.rate)}
                    <span className="text-[var(--color-ink-muted)]"> ({row.retries}/{row.sessions})</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">Roadmap</p>
            <ul className="mt-2 space-y-1.5 text-sm text-[var(--color-ink)]">
              <li>7d: {formatFrac(roadmap["7"])}</li>
              <li>14d: {formatFrac(roadmap["14"])}</li>
              <li>30d: {formatFrac(roadmap["30"])}</li>
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}

function DashboardHome() {
  const [signals, setSignals] = useState(null);
  const [lastAts, setLastAts] = useState(null);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  const [overview, setOverview] = useState(null);
  const [overviewError, setOverviewError] = useState("");
  const [overviewLoading, setOverviewLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchLearningSignals()
      .then((data) => {
        if (!cancelled) setSignals(data);
      })
      .catch(() => {
        if (!cancelled) setSignals(null);
      });
    fetchAtsRuns(1)
      .then((data) => {
        if (!cancelled) setLastAts(data.runs?.[0]?.total ?? null);
      })
      .catch(() => {
        if (!cancelled) setLastAts(null);
      });
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        const u = me.user || me;
        setNavUser({
          userId: u.id || u.user_id || null,
          roleId: u.target_role_id || null,
        });
      })
      .catch(() => {});
    fetchAccountOverview()
      .then((data) => {
        if (cancelled) return;
        setOverview(data);
        setOverviewLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setOverviewError(err.message || "Progress is not available.");
        setOverviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const scoredSessions = overviewLoading ? "…" : overviewError ? "Unavailable" : String(overview?.scored_session_count ?? 0);
  const skillsMeasured = overviewLoading
    ? "…"
    : overviewError
      ? "Unavailable"
      : String((overview?.skills || []).filter((skill) => skill.attempts > 0).length);
  const readinessValue = overviewLoading ? "…" : overviewError ? "Unavailable" : displayScore(overview?.readiness);
  const history = overview?.history || [];
  const recent = history.slice(0, 3);
  const weakSkills = [...(overview?.skills || [])]
    .filter((skill) => skill.attempts > 0)
    .sort((a, b) => (a.current_score ?? 0) - (b.current_score ?? 0))
    .slice(0, 3);

  return (
    <main className="dashboard-home min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="app-container">
        <AppNav
          brandTo="/home"
          userId={navUser.userId}
          roleId={navUser.roleId}
          trailing={
            <Link to="/upload" className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-3 py-1.5 text-sm font-semibold text-white">
              Start Interview
            </Link>
          }
        />

        <section className="mt-8 border-b border-[var(--color-border)] pb-8">
          <div className="grid gap-6 lg:grid-cols-[1fr_360px] lg:items-end">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">Interview Readiness Platform</p>
              <h1 className="mt-3 max-w-3xl text-[length:var(--text-3xl)] font-semibold leading-tight tracking-normal text-[var(--color-ink)] sm:text-[length:var(--text-5xl)]">
                Welcome back. Build readiness by company, role, resume, and skill.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--color-ink-muted)]">
                interViv is a company-style, role-style, resume-aware adaptive mock interview platform for students.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
              <Link to="/coach" className="inline-flex items-center justify-center gap-2 rounded-[var(--radius-card)] bg-[var(--color-ink)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
                Don’t know where to start
              </Link>
              <Link to="/practice" className="inline-flex items-center justify-center gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] px-5 py-3 text-sm font-semibold text-slate-800 transition hover:border-slate-300">
                <Play className="h-4 w-4" />
                Open Practice Hub
              </Link>
              <Link to="/upload" className="inline-flex items-center justify-center gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] px-5 py-3 text-sm font-semibold text-slate-800 transition hover:border-slate-300">
                <Upload className="h-4 w-4" />
                Resume Analysis
              </Link>
            </div>
          </div>

          <div className="mt-7 grid gap-3 border-y border-[var(--color-border)] py-4 sm:grid-cols-3">
            <div>
              <p className="text-2xl font-semibold text-[var(--color-ink)]">{scoredSessions}</p>
              <p className="text-xs uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">scored sessions</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-[var(--color-ink)]">{skillsMeasured}</p>
              <p className="text-xs uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">skills measured</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-[var(--color-ink)]">{readinessValue}</p>
              <p className="text-xs uppercase tracking-[0.14em] text-[var(--color-ink-muted)]">readiness</p>
            </div>
          </div>
        </section>

        <LearningSignalsBlock signals={signals} />

        {lastAts != null && (
          <p className="mt-4 text-sm text-[var(--color-ink-muted)]">
            Last ATS score: <Link to="/ats" className="font-semibold text-[var(--color-ink)] underline-offset-2 hover:underline">{Math.round(lastAts)}</Link>
          </p>
        )}

        <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <DashboardCard
            icon={<BarChart3 className="h-5 w-5" />}
            title="Overall Readiness"
            value={overviewLoading ? null : readinessValue}
            detail={
              overviewError
                ? overviewError
                : overview?.readiness == null
                  ? "Readiness is measured against a target role after you practice its required skills."
                  : [`Based on ${overview.target?.tested_skill_count ?? 0} of ${overview.target?.required_skill_count ?? 0} required skills.`, observedReadinessNote(overview)].filter(Boolean).join(' ')
            }
            action={<Link to="/dashboard">Open Progress</Link>}
          />
          <DashboardCard
            icon={<Target className="h-5 w-5" />}
            title="Weak Skills"
            detail={
              overviewError
                ? overviewError
                : weakSkills.length === 0
                  ? "Not measured. Skills appear here after scored rounds."
                  : weakSkills.map((skill) => `${skill.name} ${displayScore(skill.current_score)}`).join(", ")
            }
            action={weakSkills.length === 0 ? "Empty until you practice" : `${weakSkills.length} lowest measured`}
            muted={weakSkills.length === 0}
          />
          <DashboardCard
            icon={<Clock className="h-5 w-5" />}
            title="Recent Sessions"
            detail={
              overviewError
                ? overviewError
                : recent.length === 0
                  ? "No scored sessions yet."
                  : recent.map((session) => `${sessionLabel(session.round_types)} ${displayScore(session.average_score)}`).join(" · ")
            }
            action={recent.length === 0 ? "No sessions yet" : <Link to="/dashboard">View history</Link>}
            muted={recent.length === 0}
          />
          <DashboardCard
            icon={<RotateCcw className="h-5 w-5" />}
            title="Replay / Past Questions"
            detail="Open a session report to review answers and deterministic scoring breakdowns."
            action={history.length === 0 ? "Available after a session" : `${history.length} reports`}
            muted={history.length === 0}
          />
          <DashboardCard
            icon={<Map className="h-5 w-5" />}
            title="Recommended Roadmap"
            detail={
              overview?.target
                ? `${overview.target.company_name} · ${overview.target.role_title}`
                : "Select a target company and role, then generate a gap report."
            }
            action={overview?.target ? <Link to="/home#target">View target</Link> : "Target role required"}
            muted={!overview?.target}
          />
        </section>
      </div>
    </main>
  );
}

export default function Dashboard() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
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
  const accent = data ? scoreAccent(data.overall.score) : { ring: "from-cyan-400/70 to-blue-500/70", text: "text-cyan-200" };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin mb-4 mx-auto" />
          <p className="text-sm text-white/60" style={{ fontFamily: "var(--font-body)" }}>Loading results...</p>
        </div>
      </div>
    );
  }

  if (!sessionId) {
    return <DashboardHome />;
  }

  if (err || !data) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <p role="alert" className="text-sm text-white/60 mb-4" style={{ fontFamily: "var(--font-body)" }}>
            {err || "Session not found."}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button onClick={() => setRetryCount((value) => value + 1)}
              className="rounded-full px-6 py-2.5 text-sm text-white bg-white/10 border border-white/15 hover:bg-white/15 transition-all"
              style={{ fontFamily: "var(--font-body)" }}>
              Try again
            </button>
            <button onClick={() => navigate('/upload')}
              className="rounded-full px-6 py-2.5 text-sm text-white bg-white/10 border border-white/15 hover:bg-white/15 transition-all"
              style={{ fontFamily: "var(--font-body)" }}>
              Start New Session
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-session min-h-screen w-full bg-[var(--color-session-bg)] text-white selection:bg-cyan-300/20 selection:text-white">
      <motion.div {...pageMotion} className="relative mx-auto w-full max-w-7xl px-4 pb-14 pt-8 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Back to wherever the report was opened from; Progress lists reports. */}
          <button onClick={() => {
              const target = backDestination(location, '/dashboard');
              if (typeof target === 'number') navigate(target); else navigate(target);
            }}
            data-testid="report-back"
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/90 backdrop-blur-xl transition hover:bg-white/8"
            style={{ fontFamily: "var(--font-body)" }}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div className="flex flex-wrap items-center gap-2">
            {raw?.target_role_id && raw?.user_id && (
              <Link
                to={`/gap-analysis/${encodeURIComponent(raw.user_id)}/${encodeURIComponent(raw.target_role_id)}`}
                className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm text-cyan-100 backdrop-blur-xl transition hover:bg-cyan-500/20"
                style={{ fontFamily: "var(--font-body)" }}
                data-testid="dashboard-to-gap-analysis"
              >
                Readiness vs. target →
              </Link>
            )}
            <AccountMenu />
            <span className="hidden sm:inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/25 px-3 py-1.5 text-xs text-white/75 backdrop-blur-xl">
              <Sparkles className="h-3.5 w-3.5 text-cyan-200" />
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

          {data.reviewSummary && (
            <motion.div variants={item} className="mt-8">
              <ReviewSummary {...data.reviewSummary} />
            </motion.div>
          )}

          {data.multiBlock && data.blocks.length > 1 && (
            <motion.div variants={item} className="mt-8">
              <BlockResults blocks={data.blocks} />
            </motion.div>
          )}

          {(data.mcqReviews || []).length > 0 && (
            <motion.div variants={item} className="mt-8 space-y-6">
              {data.mcqReviews.map((review, index) => (
                <McqRoundReview key={`mcq-review-${index}`} review={review} />
              ))}
            </motion.div>
          )}

          <motion.div variants={item} className="mt-8">
            <Phase2InsightsPanel
              userId={raw?.user_id || null}
              targetRoleId={raw?.target_role_id || null}
            />
          </motion.div>

          {data.overall.score != null && (
            <div className="mt-8 grid gap-6 lg:grid-cols-12">
              <motion.div variants={item} className="lg:col-span-5">
                <LayerBreakdown layers={data.layers} />
              </motion.div>
              <motion.div variants={item} className="lg:col-span-7">
                <SkillRadar data={data.radar} />
              </motion.div>
            </div>
          )}

          <div className="mt-8 grid gap-6 lg:grid-cols-12">
            <motion.div variants={item} className="lg:col-span-5">
              <PerformanceChart
                finalRating={data.performance.finalRating}
                difficulty={data.performance.difficulty}
                score={data.performance.score}
              />
            </motion.div>
            <motion.div variants={item} className="lg:col-span-7">
              <RoundTimeline rounds={data.rounds} />
            </motion.div>
          </div>

          <motion.div variants={item} className="mt-8">
            <ScoringBreakdownPanel rounds={data.rounds} />
          </motion.div>

          {(data.highlights.strengths.length > 0 || data.highlights.weaknesses.length > 0) && (
            <motion.div variants={item} className="mt-8">
              <StrengthsWeaknesses strengths={data.highlights.strengths} weaknesses={data.highlights.weaknesses} />
            </motion.div>
          )}

          <motion.div variants={item} className="mt-8">
            <FeedbackCards cards={data.feedbackCards as Array<{ id: string; title: string; tag: "Signal" | "Structure" | "Delivery" | "Clarity"; body: string }>} />
          </motion.div>

          <motion.div variants={item} className="mt-8">
            <div className="glass-panel rounded-3xl p-5 sm:p-6">
              <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
                <div>
                  <div className="text-2xl sm:text-3xl font-normal italic tracking-tight"
                    style={{ fontFamily: "var(--font-display)" }}>
                    Next moves
                  </div>
                  <p className="mt-1 text-sm text-white/70" style={{ fontFamily: "var(--font-body)" }}>
                    Export your report, copy its link, or jump into another adaptive session.
                  </p>
                </div>
                <div className="flex w-full flex-col gap-2 sm:w-auto sm:items-end">
                  <div className="report-actions flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:justify-end">
                    <GlassButton variant="primary"   icon={<Download className="h-4 w-4 text-cyan-200" />}   label="Download Report" onClick={() => window.print()} />
                    <GlassButton variant="secondary" icon={<Share2    className="h-4 w-4 text-white/85" />}   label="Copy report link"  onClick={copyReportLink} />
                    <GlassButton variant="secondary" icon={<Sparkles  className="h-4 w-4 text-white/85" />}   label="New Interview"  onClick={() => navigate('/upload')} />
                  </div>
                  <p aria-live="polite" className="text-sm text-white/70 sm:text-right">
                    {copyStatus || 'Reports require sign-in. Copying this link does not grant access on its own.'}
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  );
}
