import React from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileCheck2,
  Flag,
  Layers3,
  ShieldCheck,
  Target,
} from "lucide-react";
import ResourceLinks from "../ResourceLinks";

type SkillSummary = {
  skill: string;
  score: number;
  attempts: number;
};

type PriorityRound = {
  id: string;
  question: string;
  score: number;
};

type Props = {
  /** Null when no measured round was scored; never shown as zero. */
  overallScore: number | null;
  /** True when measured blocks use different metrics (no single overall). */
  blended?: boolean;
  gradeLabel: string;
  completedRounds: number;
  totalRounds: number;
  guardCount: number;
  averageWords: number;
  scoreRange: number;
  prioritySkills: SkillSummary[];
  priorityRound?: PriorityRound | null;
  unscored?: Array<{ round: number; label: string }>;
  nextStep: string;
};

function scoreTone(score: number | null) {
  if (score == null) return "border-white/15 bg-white/5 text-white/70";
  if (score >= 75) return "border-emerald-300/25 bg-emerald-300/10 text-emerald-100";
  if (score >= 55) return "border-cyan-300/25 bg-cyan-300/10 text-cyan-100";
  if (score >= 35) return "border-amber-300/25 bg-amber-300/10 text-amber-100";
  return "border-rose-300/25 bg-rose-300/10 text-rose-100";
}

function scoreBar(score: number) {
  if (score >= 75) return "from-emerald-300 to-cyan-300";
  if (score >= 55) return "from-cyan-300 to-sky-400";
  if (score >= 35) return "from-amber-300 to-orange-400";
  return "from-rose-300 to-fuchsia-400";
}

function summaryText(score: number | null, guardCount: number, completedRounds: number, blended = false) {
  if (score == null && blended) {
    return "This session combined blocks with different metrics, so there is no single overall score. Per-block results below carry each block's own metric; unscored rounds are listed and excluded from every average.";
  }
  if (score == null) {
    return "No round in this session produced a score, so there is no verdict or action plan. Unscored rounds are listed below and excluded from every average.";
  }
  if (score >= 75) {
    return "Interview-ready fundamentals are visible. Preserve the strongest answer patterns and use targeted practice to close the remaining gaps.";
  }
  if (score >= 55) {
    return "The foundation is credible, but the review still shows uneven depth. Prioritize the lowest-scoring skill before increasing question difficulty.";
  }
  if (score >= 35) {
    return "Core concepts are emerging, but answers need clearer structure, stronger coverage, and more concrete examples before the next review.";
  }
  if (guardCount > 0 && completedRounds > 0) {
    return `${guardCount} of ${completedRounds} answers triggered an answer-quality check. Complete, meaningful responses are the immediate priority before subject depth can be assessed reliably.`;
  }
  return "The current evidence is below the readiness threshold. Rebuild the weakest topics with complete answers before attempting harder rounds.";
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/25 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-white/80">{icon}</div>
        <div className="text-right">
          <div className="text-xl font-semibold text-white">{value}</div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-white/40">{label}</div>
        </div>
      </div>
      <p className="mt-3 text-xs leading-5 text-white/55">{detail}</p>
    </div>
  );
}

export function ReviewSummary(props: Props) {
  const unscored = props.unscored || [];
  const completion = props.totalRounds > 0
    ? Math.round((props.completedRounds / props.totalRounds) * 100)
    : 0;
  const weakest = props.prioritySkills[0];
  const guardAction = props.guardCount > 0
    ? `Use 3–5 complete sentences. ${props.guardCount} answer${props.guardCount === 1 ? "" : "s"} triggered a quality guard.`
    : "No answer-quality guard fired. Add trade-offs and examples to improve depth.";

  const actions = [
    {
      title: "Improve answer structure",
      detail: guardAction,
    },
    {
      title: weakest ? `Rebuild ${weakest.skill}` : "Target the weakest skill",
      detail: weakest
        ? `${Math.round(weakest.score)}% across ${weakest.attempts} round${weakest.attempts === 1 ? "" : "s"}. Start with definitions, then explain why each concept matters.`
        : props.nextStep,
    },
    {
      title: props.priorityRound ? `Reattempt Round ${props.priorityRound.id}` : "Apply the feedback",
      detail: props.priorityRound?.question || props.nextStep,
    },
  ];

  return (
    <section className="glass-panel relative overflow-hidden rounded-3xl p-5 sm:p-7" data-testid="review-summary">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_8%_10%,rgba(34,211,238,0.10),transparent_28%),radial-gradient(circle_at_92%_18%,rgba(244,63,94,0.08),transparent_26%)]" />

      <div className="relative">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-200/70">Evaluator snapshot</span>
              <span className={`rounded-full border px-3 py-1 text-[11px] font-medium ${scoreTone(props.overallScore)}`}>
                {props.gradeLabel}
              </span>
            </div>
            <h2 className="mt-3 text-3xl font-normal italic tracking-tight text-white sm:text-4xl" style={{ fontFamily: "var(--font-display)" }}>
              What the review says—and what to do next.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-white/70" style={{ fontFamily: "var(--font-body)" }}>
              {summaryText(props.overallScore, props.guardCount, props.completedRounds, props.blended === true)}
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.05] px-4 py-3 text-xs text-emerald-100/85">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            Deterministic scoring · evidence retained
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Metric
            icon={<FileCheck2 className="h-4 w-4" />}
            label="Completion"
            value={`${props.completedRounds}/${props.totalRounds || props.completedRounds}`}
            detail={unscored.length
              ? `${unscored.length} round${unscored.length === 1 ? "" : "s"} not evaluated (${[...new Set(unscored.map((u) => u.label))].join(", ")}); excluded from every average.`
              : `${completion}% of planned rounds completed.`}
          />
          <Metric
            icon={<Layers3 className="h-4 w-4" />}
            label="Skills assessed"
            value={String(props.prioritySkills.length)}
            detail={props.prioritySkills.map((item) => item.skill).join(" · ") || "No skill evidence recorded."}
          />
          <Metric
            icon={props.guardCount > 0 ? <AlertTriangle className="h-4 w-4 text-amber-200" /> : <CheckCircle2 className="h-4 w-4 text-emerald-200" />}
            label="Quality checks"
            value={`${props.guardCount}`}
            detail={props.guardCount > 0 ? "Rounds where an answer guard affected the score." : "No answer-quality guards were applied."}
          />
          <Metric
            icon={<Flag className="h-4 w-4" />}
            label="Answer evidence"
            value={`${props.averageWords} words`}
            detail={`Average response length · ${Math.round(props.scoreRange)} point score range.`}
          />
        </div>

        {unscored.length > 0 && (
          <ul className="mt-4 grid gap-2" data-testid="unscored-rounds">
            {unscored.map((u) => (
              <li key={u.round} className="rounded-2xl border border-amber-300/20 bg-amber-300/[0.06] p-3.5 text-xs leading-5 text-amber-100/90">
                <span className="font-semibold">Round {u.round} · Unscored ({u.label}).</span>{" "}
                Not evaluated, so it is excluded from averages, skill scores and suggestions.
              </li>
            ))}
          </ul>
        )}

        {props.overallScore != null && (
        <div className="mt-6 grid gap-5 border-t border-white/10 pt-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-cyan-200" />
              <h3 className="text-sm font-semibold text-white">Skill priority</h3>
              <span className="text-xs text-white/40">lowest score first</span>
            </div>
            <div className="mt-4 grid gap-3">
              {props.prioritySkills.map((item, index) => (
                <div key={item.skill} className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/5 text-[11px] text-white/50">{index + 1}</span>
                      <span className="truncate font-medium text-white/90">{item.skill}</span>
                    </div>
                    <span className="shrink-0 font-semibold text-white">{Math.round(item.score)}%</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/8">
                    <div className={`h-full rounded-full bg-gradient-to-r ${scoreBar(item.score)}`} style={{ width: `${Math.max(2, Math.min(100, item.score))}%` }} />
                  </div>
                  {index === 0 && (
                    <ResourceLinks
                      skillId={item.skill}
                      heading={`Resources for ${item.skill}`}
                      variant="dark"
                      maxPerLevel={3}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-white">Recommended action plan</h3>
              <span className="text-xs text-white/40">next session</span>
            </div>
            <ol className="mt-4 grid gap-3">
              {actions.map((action, index) => (
                <li key={action.title} className="flex gap-3 rounded-2xl border border-white/8 bg-black/20 p-3.5">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-cyan-300/20 bg-cyan-300/10 text-xs font-semibold text-cyan-100">{index + 1}</span>
                  <div>
                    <div className="text-sm font-semibold text-white/90">{action.title}</div>
                    <p className="mt-1 text-xs leading-5 text-white/55">{action.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
            <Link
              to="/upload"
              className="mt-4 inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-4 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-300/15"
            >
              Start focused practice
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
        )}
      </div>
    </section>
  );
}
