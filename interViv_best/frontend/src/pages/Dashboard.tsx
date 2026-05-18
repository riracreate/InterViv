import React, { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Download, Share2, Sparkles, ScrollText } from "lucide-react";
import { fetchDashboard } from "../lib/api";

import { ScoreHero } from "../components/dashboard/ScoreHero";
import { LayerBreakdown } from "../components/dashboard/LayerBreakdown";
import { SkillRadar } from "../components/dashboard/SkillRadar";
import { PerformanceChart } from "../components/dashboard/PerformanceChart";
import { RoundTimeline } from "../components/dashboard/RoundTimeline";
import { StrengthsWeaknesses } from "../components/dashboard/StrengthsWeaknesses";
import { FeedbackCards } from "../components/dashboard/FeedbackCards";
import { ScoringBreakdownPanel } from "../components/dashboard/ScoringBreakdownPanel";

function clamp01(n) { return Math.min(1, Math.max(0, n)); }
function scoreAccent(score) {
  const t = clamp01(score / 100);
  if (t >= 0.85) return { ring: "from-cyan-400/70 to-blue-500/70", text: "text-cyan-200" };
  if (t >= 0.7)  return { ring: "from-sky-400/70 to-cyan-500/70",  text: "text-sky-200"  };
  if (t >= 0.55) return { ring: "from-blue-400/70 to-indigo-500/70", text: "text-blue-200" };
  return { ring: "from-fuchsia-400/60 to-indigo-500/60", text: "text-fuchsia-200" };
}

type FeedbackTag = "Signal" | "Structure" | "Delivery" | "Clarity";

function mapRealDataToDashboard(session) {
  const rounds = session.rounds || [];
  const completed = rounds.filter(r => r.final_score != null);
  const avg = session.averages?.final_score || 0;
  const skills = session.skills || [session.skill || "General"];
  const elos = session.elo_progression || [];
  const finalElo = elos.length ? elos[elos.length - 1] : (session.elo_after || 1200);
  const topicScores = session.topic_scores || {};

  const gradeLabel = avg >= 75 ? "Excellent" : avg >= 55 ? "Good" : avg >= 35 ? "Average" : "Needs Work";

  const layers = [
    { label: "Layer 1", subtitle: "Content & Relevance", score: session.averages?.nlp_score ?? avg },
    { label: "Layer 2", subtitle: "Quality & Depth",     score: session.averages?.kg_score  ?? avg * 0.9 },
    { label: "Layer 3", subtitle: "ML Judge Signal",     score: avg * 0.95 },
  ];

  const radarSkills = Object.keys(topicScores).length > 0
    ? Object.entries(topicScores).map(([skill, value]) => ({ skill, value }))
    : skills.map(s => ({ skill: s, value: avg }));

  if (radarSkills.length < 3) {
    const extras = [
      { skill: "Clarity",    value: avg * 0.9  },
      { skill: "Structure",  value: avg * 0.85 },
      { skill: "Depth",      value: avg        },
    ];
    while (radarSkills.length < 3) radarSkills.push(extras[radarSkills.length]);
  }

  const diffProgression = (session.difficulty_progression || []).map((d, i) => ({
    t: `R${i + 1}`,
    value: d === "hard" ? 60 : d === "medium" ? 35 : 15,
  }));
  const scoreProgression = completed.map((r, i) => ({ t: `R${i + 1}`, value: r.final_score }));

  const roundsForTimeline = completed.map((r, i) => ({
    id: String(i + 1),
    question: r.question || r.question_context?.question || `Round ${i + 1}`,
    idealAnswer: r.ideal_answer || r.question_context?.ideal_answer || "",
    answer: r.answer_text || "",
    score: r.final_score,
    difficulty: (r.difficulty || "medium").charAt(0).toUpperCase() + (r.difficulty || "medium").slice(1),
    feedback: r.feedback?.next_step || r.feedback?.content?.[0] || "",
    scoring_breakdown: r.scoring_breakdown || null,
  }));

  const strengths = [];
  const weaknesses = [];
  if (session.breakdown) {
    const { Good = 0, Average = 0, Poor = 0 } = session.breakdown;
    if (Good > 0) strengths.push({ title: `${Good} Strong Round${Good > 1 ? "s" : ""}`, detail: "You achieved Good-band scores on these rounds — keep up this depth." });
    if (Average > 0) weaknesses.push({ title: `${Average} Average Round${Average > 1 ? "s" : ""}`, detail: "These rounds have room for more detail and concrete examples." });
    if (Poor > 0) weaknesses.push({ title: `${Poor} Round${Poor > 1 ? "s" : ""} to Revisit`, detail: "Consider reviewing these topics before your next session." });
  }
  if (strengths.length === 0) strengths.push({ title: "Participation", detail: "You completed all rounds — consistency is key." });
  if (weaknesses.length === 0) weaknesses.push({ title: "Push for depth", detail: "Try to include trade-offs, examples, and edge cases in each answer." });

  const nextStepText = session.next_step || "Continue practising with harder questions to improve your Elo.";
  const feedbackCards: Array<{ id: string; title: string; tag: FeedbackTag; body: string }> = [
    { id: "c1", title: "C4 — Context",    tag: "Structure", body: `Your overall session score was ${Math.round(avg)}%. ${nextStepText}` },
    { id: "c2", title: "C4 — Containers", tag: "Clarity",   body: `Difficulty adapted across ${completed.length} rounds. Final Elo: ${finalElo}.` },
    { id: "c3", title: "C4 — Components", tag: "Signal",    body: `Skills tested: ${skills.join(", ")}.` },
    { id: "c4", title: "C4 — Code",       tag: "Delivery",  body: `Your best round scored ${Math.round(Math.max(...completed.map(r => r.final_score ?? 0), 0))}%. Aim to replicate that depth.` },
  ];

  return {
    session: {
      title: "Adaptive Mock Interview",
      role: skills.join(" + "),
      dateLabel: new Date(session.started_at || Date.now()).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
      durationLabel: `${completed.length} rounds`,
      skillFocus: skills[0] || "General",
    },
    overall: { score: Math.round(avg), gradeLabel, deltaLabel: `${Math.round(avg)}% avg score` },
    layers,
    radar: radarSkills,
    performance: { finalRating: finalElo, difficulty: diffProgression, score: scoreProgression },
    rounds: roundsForTimeline,
    highlights: { strengths, weaknesses },
    feedbackCards,
  };
}

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

export default function Dashboard() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [raw, setRaw] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!sessionId) { setErr('No session ID.'); setLoading(false); return; }
    fetchDashboard(sessionId)
      .then(data => { setRaw(data); setLoading(false); })
      .catch(e => { setErr(e.message); setLoading(false); });
  }, [sessionId]);

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

  if (err || !data) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-white/60 mb-4" style={{ fontFamily: "var(--font-body)" }}>
            {err || "Session not found."}
          </p>
          <button onClick={() => navigate('/upload')}
            className="rounded-full px-6 py-2.5 text-sm text-white bg-white/10 border border-white/15 hover:bg-white/15 transition-all"
            style={{ fontFamily: "var(--font-body)" }}>
            Start New Session
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-[#0a0a0a] text-white selection:bg-cyan-300/20 selection:text-white">
      {/* Cinematic backplate */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-cyan-500/10 blur-[90px]" />
        <div className="absolute -bottom-56 left-0 h-[520px] w-[720px] rounded-full bg-blue-500/10 blur-[110px]" />
        <div className="absolute right-0 top-1/3 h-[520px] w-[720px] rounded-full bg-indigo-500/10 blur-[120px]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_10%_10%,rgba(34,211,238,0.08),transparent_35%),radial-gradient(circle_at_90%_30%,rgba(59,130,246,0.08),transparent_40%),radial-gradient(circle_at_50%_90%,rgba(99,102,241,0.07),transparent_45%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(10,10,10,0.35),rgba(10,10,10,1))]" />
      </div>

      <motion.div {...pageMotion} className="relative mx-auto w-full max-w-7xl px-4 pb-14 pt-8 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-4">
          <button onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/90 backdrop-blur-xl transition hover:bg-white/8"
            style={{ fontFamily: "var(--font-body)" }}>
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </button>
          <div className="flex items-center gap-3">
            {raw?.target_role_id && raw?.user_id && (
              <Link
                to={`/gap-analysis/${encodeURIComponent(raw.user_id)}/${encodeURIComponent(raw.target_role_id)}`}
                className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 backdrop-blur-xl transition hover:bg-cyan-500/20"
                style={{ fontFamily: "var(--font-body)" }}
                data-testid="dashboard-to-gap-analysis"
              >
                View readiness vs. target →
              </Link>
            )}
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

          <div className="mt-8 grid gap-6 lg:grid-cols-12">
            <motion.div variants={item} className="lg:col-span-5">
              <LayerBreakdown layers={data.layers} />
            </motion.div>
            <motion.div variants={item} className="lg:col-span-7">
              <SkillRadar data={data.radar} />
            </motion.div>
          </div>

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

          <motion.div variants={item} className="mt-8">
            <StrengthsWeaknesses strengths={data.highlights.strengths} weaknesses={data.highlights.weaknesses} />
          </motion.div>

          <motion.div variants={item} className="mt-8">
            <FeedbackCards cards={data.feedbackCards} />
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
                    Export your report, share your run, or jump into another adaptive session.
                  </p>
                </div>
                <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:justify-end">
                  <GlassButton variant="primary"   icon={<Download className="h-4 w-4 text-cyan-200" />}   label="Download Report" onClick={() => window.print()} />
                  <GlassButton variant="secondary" icon={<Share2    className="h-4 w-4 text-white/85" />}   label="Share Results"  onClick={() => navigator.clipboard?.writeText(window.location.href)} />
                  <GlassButton variant="secondary" icon={<Sparkles  className="h-4 w-4 text-white/85" />}   label="New Interview"  onClick={() => navigate('/upload')} />
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  );
}
