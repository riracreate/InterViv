/**
 * Phase 2 dashboard insights — wraps:
 *   - Readiness banner (against the user's target company role)
 *   - Gap analysis mini (top 3 weak areas)
 *   - Skill graph tree (skills with current_score + Elo)
 *   - Concept mastery heatmap (per skill grid)
 *   - Roadmap CTA
 *
 * Each panel is independently fetched and degrades gracefully:
 *   - No userId on the session  -> show a "complete signup to unlock" stub
 *   - No targetRoleId           -> hide readiness/gap; show "pick a target"
 *   - No skill graph yet        -> empty-state copy, no crash
 *
 * The dashboard uses the shared light theme (white cards on slate); these panels
 * follow the same glass-panel aesthetic.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchGapAnalysis, fetchSkillGraph, fetchMastery } from "../../lib/api";

type Props = {
  userId: string | null | undefined;
  targetRoleId: string | null | undefined;
};

type SkillNode = {
  name: string;
  current_score: number;
  current_elo: number;
  attempts: number;
  sub_concepts?: string[];
};

const MASTERY_COLORS: Record<string, string> = {
  Mastered: "#10B981", // emerald
  Strong:   "#22D3EE", // cyan
  Weak:     "#F59E0B", // amber
  Untested: "#6B7280", // gray
};

const SEVERITY_COLORS: Record<string, string> = {
  High:     "#EF4444",
  Medium:   "#F59E0B",
  Low:      "#10B981",
  Untested: "#6B7280",
};

function GlassCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`glass-panel rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 backdrop-blur-xl ${className}`}
    >
      {children}
    </div>
  );
}

function ReadinessBanner({ report, userId, targetRoleId }: { report: any; userId: string; targetRoleId: string }) {
  const readiness = Math.round(report.overall_readiness_percentage);
  const top = (report.ranked_weak_areas || []).slice(0, 3);
  const color = readiness >= 75 ? "#10B981" : readiness >= 50 ? "#F59E0B" : "#EF4444";
  return (
    <GlassCard className="overflow-hidden" data-testid="readiness-banner">
      <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--color-ink-muted)] mb-2">
        Readiness vs. target
      </p>
      <div className="flex flex-wrap items-baseline gap-3 mb-3">
        <span
          className="leading-none"
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "clamp(48px, 9vw, 96px)",
            color,
            fontStyle: "italic",
          }}
          data-testid="dashboard-readiness-pct"
        >
          {readiness}%
        </span>
        <span className="text-sm sm:text-base text-[var(--color-ink-muted)] min-w-0 break-words">
          for <span className="text-[var(--color-ink)] font-medium">{report.company_name} {report.role_title}</span>
          <span className="block text-xs text-[var(--color-ink-muted)] mt-0.5">
            {report.tested_skill_count}/{report.required_skill_count} required skills tested
          </span>
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-[var(--color-surface)] overflow-hidden mb-4">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.min(100, Math.max(2, readiness))}%`,
            backgroundColor: color,
            transition: "width 0.6s ease",
          }}
        />
      </div>
      {top.length > 0 && (
        <div className="mb-4" data-testid="dashboard-gap-mini">
          <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-ink-muted)] mb-2">
            Top gaps to close
          </p>
          <ul className="space-y-1.5">
            {top.map((w: any) => (
              <li key={w.skill} className="flex items-center gap-2 text-sm text-[var(--color-ink)]">
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block"
                  style={{ backgroundColor: SEVERITY_COLORS[w.gap_severity] || SEVERITY_COLORS.Low }}
                />
                <span className="font-medium">{w.display_name}</span>
                <span className="text-xs text-[var(--color-ink-muted)]">
                  · {w.gap_severity}
                  {w.tested
                    ? ` · gap ${Math.round(w.required_level - (w.student_level || 0))}`
                    : ` · target ${Math.round(w.required_level)}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <Link
          to={`/gap-analysis/${encodeURIComponent(userId)}/${encodeURIComponent(targetRoleId)}`}
          className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-4 py-1.5 text-xs text-[var(--color-accent)] hover:bg-cyan-500/20 transition"
          data-testid="dashboard-open-gap-analysis"
        >
          See full gap analysis →
        </Link>
        <Link
          to={`/roadmap/${encodeURIComponent(userId)}/${encodeURIComponent(targetRoleId)}?days=30`}
          className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-1.5 text-xs text-[var(--color-ink)] hover:bg-[var(--color-surface)] transition"
          data-testid="dashboard-open-roadmap"
        >
          Build my study plan →
        </Link>
      </div>
      <p className="mt-3 text-[10px] leading-relaxed text-[var(--color-ink-muted)]">
        {report.disclaimer}
      </p>
    </GlassCard>
  );
}

function NoTargetCard() {
  return (
    <GlassCard data-testid="no-target-card">
      <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--color-ink-muted)] mb-2">
        Readiness vs. target
      </p>
      <p className="text-sm text-[var(--color-ink-muted)] mb-4">
        Pick a target company and role to see your readiness, gap analysis,
        and a personalized study plan.
      </p>
      <Link
        to="/upload"
        className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-1.5 text-xs text-[var(--color-ink)] hover:bg-[var(--color-surface)] transition"
      >
        Pick a target →
      </Link>
    </GlassCard>
  );
}

function NoUserCard() {
  return (
    <GlassCard data-testid="no-user-card">
      <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--color-ink-muted)] mb-2">
        Sign in for full insights
      </p>
      <p className="text-sm text-[var(--color-ink-muted)] mb-4">
        Skill graph and concept mastery track across sessions. Create
        an account to keep your progress.
      </p>
      <Link
        to="/upload"
        className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-1.5 text-xs text-[var(--color-ink)] hover:bg-[var(--color-surface)] transition"
      >
        Continue →
      </Link>
    </GlassCard>
  );
}

function SkillGraphPanel({ skills }: { skills: SkillNode[] }) {
  if (!skills || skills.length === 0) {
    return (
      <GlassCard data-testid="skill-graph-panel">
        <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--color-ink-muted)] mb-2">
          Skill graph
        </p>
        <p className="text-sm text-[var(--color-ink-muted)]">
          You'll see your skill scores and Elo here after your first round.
        </p>
      </GlassCard>
    );
  }
  const sorted = [...skills].sort((a, b) => b.current_score - a.current_score);
  return (
    <GlassCard data-testid="skill-graph-panel">
      <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--color-ink-muted)] mb-3">
        Skill graph · {skills.length} skill{skills.length === 1 ? "" : "s"}
      </p>
      <ul className="space-y-3" data-testid="skill-graph-rows">
        {sorted.map((s) => {
          const pct = Math.max(2, Math.min(100, Math.round(s.current_score)));
          const color = s.current_score >= 75 ? "#10B981" : s.current_score >= 50 ? "#22D3EE" : "#F59E0B";
          return (
            <li key={s.name}>
              <div className="flex items-center justify-between gap-3 mb-1">
                <span className="text-sm text-[var(--color-ink)]">{s.name}</span>
                <span className="text-[11px] text-[var(--color-ink-muted)] whitespace-nowrap">
                  {Math.round(s.current_score)} · Elo {Math.round(s.current_elo)}
                  {s.attempts > 0 ? ` · ${s.attempts} attempt${s.attempts === 1 ? "" : "s"}` : " · new"}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-[var(--color-surface)] overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </GlassCard>
  );
}

function MasteryHeatmap({ mastery, details }: { mastery: Record<string, Record<string, string>>; details: Record<string, Record<string, any>> }) {
  const skills = Object.keys(mastery || {});
  if (skills.length === 0) {
    return (
      <GlassCard data-testid="mastery-panel">
        <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--color-ink-muted)] mb-2">
          Concept mastery
        </p>
        <p className="text-sm text-[var(--color-ink-muted)]">
          Concept-level mastery appears here after your first round. Each
          dot represents a concept the KG can verify in your answer.
        </p>
      </GlassCard>
    );
  }
  return (
    <GlassCard data-testid="mastery-panel">
      <p className="text-[10px] uppercase tracking-[0.25em] text-[var(--color-ink-muted)] mb-3">
        Concept mastery
      </p>
      <div className="space-y-4">
        {skills.map((skill) => {
          const concepts = mastery[skill] || {};
          const conceptNames = Object.keys(concepts);
          return (
            <div key={skill}>
              <p className="text-xs text-[var(--color-ink-muted)] mb-2">
                {skill}{" "}
                <span className="text-[var(--color-ink-muted)]">· {conceptNames.length} concept{conceptNames.length === 1 ? "" : "s"}</span>
              </p>
              <div className="flex flex-wrap gap-1.5" data-testid={`mastery-grid-${skill}`}>
                {conceptNames.map((concept) => {
                  const level = concepts[concept];
                  const color = MASTERY_COLORS[level] || MASTERY_COLORS.Untested;
                  const node = details?.[skill]?.[concept] || {};
                  const tip = `${concept} · ${level} · ${node.demonstrated || 0}/${node.attempts || 0}`;
                  return (
                    <span
                      key={concept}
                      title={tip}
                      className="rounded px-2 py-1 text-[10px] leading-tight"
                      style={{
                        backgroundColor: `${color}22`,
                        color,
                        border: `1px solid ${color}44`,
                      }}
                    >
                      {concept}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-3 text-[10px] text-[var(--color-ink-muted)]">
        {Object.entries(MASTERY_COLORS).map(([level, color]) => (
          <span key={level} className="inline-flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
            {level}
          </span>
        ))}
      </div>
    </GlassCard>
  );
}

export default function Phase2InsightsPanel({ userId, targetRoleId }: Props) {
  const [gap, setGap] = useState<any>(null);
  const [graph, setGraph] = useState<{ skills: SkillNode[] } | null>(null);
  const [mastery, setMastery] = useState<{ mastery: any; details: any } | null>(null);
  const [errors, setErrors] = useState<{ gap?: string; graph?: string; mastery?: string }>({});

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    fetchSkillGraph()
      .then((d) => { if (!cancelled) setGraph(d); })
      .catch((e) => { if (!cancelled) setErrors((p) => ({ ...p, graph: e.message })); });
    fetchMastery()
      .then((d) => { if (!cancelled) setMastery(d); })
      .catch((e) => { if (!cancelled) setErrors((p) => ({ ...p, mastery: e.message })); });
    return () => { cancelled = true; };
  }, [userId]);

  useEffect(() => {
    if (!userId || !targetRoleId) return;
    let cancelled = false;
    fetchGapAnalysis(userId, targetRoleId)
      .then((d) => { if (!cancelled) setGap(d); })
      .catch((e) => { if (!cancelled) setErrors((p) => ({ ...p, gap: e.message })); });
    return () => { cancelled = true; };
  }, [userId, targetRoleId]);

  if (!userId) {
    return (
      <div className="mt-8">
        <NoUserCard />
      </div>
    );
  }

  return (
    <div className="mt-8 space-y-6" data-testid="phase2-insights">
      {targetRoleId && gap ? (
        <ReadinessBanner report={gap} userId={userId} targetRoleId={targetRoleId} />
      ) : targetRoleId && !gap && !errors.gap ? (
        <GlassCard><p className="text-sm text-[var(--color-ink-muted)]">Computing readiness…</p></GlassCard>
      ) : (
        <NoTargetCard />
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <SkillGraphPanel skills={graph?.skills || []} />
        <MasteryHeatmap
          mastery={mastery?.mastery || {}}
          details={mastery?.details || {}}
        />
      </div>
    </div>
  );
}
