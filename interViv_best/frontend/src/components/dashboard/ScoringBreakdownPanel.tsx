import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight } from "lucide-react";

interface KeywordMatch {
  keyword?: string;
  covered?: boolean;
}

interface RubricScores {
  version?: string;
  scale?: string;
  correctness?: number;
  coverage?: number;
  depth?: number;
  clarity?: number;
  weighted_score?: number;
  guard_capped?: boolean;
}

interface ConceptsSummary {
  covered?: string[];
  missing?: string[];
}

interface GuardSummary {
  applied?: boolean;
  reason?: string | null;
  score_cap?: number | null;
  softened?: boolean;
}

interface ScoringBreakdown {
  scoring_schema_version?: string;
  rubric?: RubricScores;
  concepts?: ConceptsSummary;
  guard?: GuardSummary;
  layer1_score?: number;
  layer2_score?: number;
  layer3_score?: number;
  semantic_score?: number | null;
  tfidf_score?: number;
  keyword_coverage?: number;
  kg_score?: number;
  ner_score?: number;
  svm_label?: string;
  final_score?: number;
  nlp_score?: number;
  guard_applied?: string | null;
  kg_label?: string;
  covered_concepts?: string[];
  missing_concepts?: string[];
  keyword_coverage_details?: {
    matches?: KeywordMatch[];
  };
  structure_score?: number;
}

interface Round {
  id: string;
  question: string;
  idealAnswer?: string;
  score: number;
  difficulty: string;
  topic?: string;
  questionType?: string;
  followups?: string[];
  scoring_breakdown?: ScoringBreakdown;
  scoring_mode?: string;
  scoring_mode_label?: string;
  evidence_kind?: string;
  scorerProvenance?: Record<string, unknown> | string | null;
  feedbackSource?: string | null;
}

function fmt(n?: number | null, decimals = 1): string {
  if (n == null || n === undefined) return "–";
  return Number(n).toFixed(decimals);
}

function pct(n?: number | null): string {
  if (n == null || n === undefined) return "–";
  return `${Math.round(Number(n) * 100)}%`;
}

function textList(items?: string[], fallback = "None recorded."): string {
  const values = (items || []).map(item => item.trim()).filter(Boolean);
  return values.length > 0 ? values.join(", ") : fallback;
}

function missingKeywords(bd?: ScoringBreakdown): string[] {
  return (bd?.keyword_coverage_details?.matches || [])
    .filter(match => match && match.covered === false && match.keyword)
    .map(match => String(match.keyword));
}

function nextTopics(round: Round, bd?: ScoringBreakdown): string[] {
  // Follow-up prompts are teaching content, not diagnosed missing concepts.
  const concepts = bd?.concepts?.missing || bd?.missing_concepts || [];
  const keywords = missingKeywords(bd);
  const values = [...concepts, ...keywords, round.topic || ""]
    .map(item => String(item).trim())
    .filter(Boolean);
  return Array.from(new Set(values)).slice(0, 5);
}

function shortText(value?: string, max = 420): string {
  const normalized = (value || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "Ideal answer is not available for this round.";
  return normalized.length > max ? `${normalized.slice(0, max - 3).trim()}...` : normalized;
}

function RoundBreakdown({ round }: { round: Round }) {
  const [open, setOpen] = useState(false);
  const bd = round.scoring_breakdown;
  const hasData = bd && (bd.layer1_score != null || bd.final_score != null);
  const scoringMode = round.scoring_mode || "unknown";
  const scoringModeLabel =
    round.scoring_mode_label
    || (scoringMode === "lexical_fallback_degraded"
      ? "Lexical fallback (semantic scorer unavailable)"
      : scoringMode === "self_reported"
        ? "Self-reported (not measured)"
        : scoringMode === "practice_estimate"
          ? "Practice estimate (not measured)"
        : scoringMode === "full"
          ? "Full semantic scoring"
          : "Scoring mode unknown");

  const layer1Contrib = bd ? (0.55 * (bd.layer1_score ?? 0)).toFixed(1) : "–";
  const layer2Contrib = bd ? (0.25 * (bd.layer2_score ?? 0)).toFixed(1) : "–";
  const layer3Contrib = bd ? (0.20 * (bd.layer3_score ?? 0)).toFixed(1) : "–";
  const kgScore       = bd?.kg_score ?? 0;
  const missedKeywords = missingKeywords(bd);
  const recommendedTopics = nextTopics(round, bd);
  const rubric = bd?.rubric;
  const guardReason = bd?.guard?.reason || bd?.guard_applied;
  const guardCap = bd?.guard?.score_cap;
  const coveredConcepts = bd?.concepts?.covered || bd?.covered_concepts || [];
  const missingConcepts = bd?.concepts?.missing || bd?.missing_concepts || [];

  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      {/* Header row */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[var(--color-surface)] transition-colors"
        onClick={() => setOpen(o => !o)}
        type="button"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-[var(--color-ink-muted)]">R{round.id}</span>
          <span className="text-sm text-[var(--color-ink)] truncate max-w-[280px]" style={{ fontFamily: "var(--font-body)" }}>
            {round.question}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            round.difficulty === "Hard" ? "bg-red-500/15 text-red-700" :
            round.difficulty === "Medium" ? "bg-amber-500/15 text-amber-700" :
            "bg-green-500/15 text-green-700"
          }`}>{round.difficulty}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm font-medium text-[var(--color-accent)]">{Math.round(round.score)}</span>
          {open
            ? <ChevronDown className="h-4 w-4 text-[var(--color-ink-muted)]" />
            : <ChevronRight className="h-4 w-4 text-[var(--color-ink-muted)]" />}
        </div>
      </button>

      {/* Collapsible breakdown */}
      {open && (
        <div className="border-t border-[var(--color-border)] px-4 py-3 space-y-2">
          {!hasData ? (
            <p className="text-xs text-[var(--color-ink-muted)] italic">No scoring breakdown available for this round.</p>
          ) : (
            <div className="font-mono text-xs text-[var(--color-ink-muted)] space-y-1">
              {/* Guard warning */}
              {guardReason && (
                <div className="mb-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-amber-700 text-xs">
                  Guard applied: <strong>{guardReason}</strong>.
                  {guardCap ? ` Score cap: ${Math.round(Number(guardCap))}.` : ""}
                  {" "}Your answer looks incomplete or gibberish. Please write a meaningful explanation.
                </div>
              )}

              {(scoringMode === "lexical_fallback_degraded" || scoringMode === "unknown" || scoringMode === "self_reported" || scoringMode === "practice_estimate") && (
                <div className="mb-2 rounded-lg bg-sky-500/10 border border-sky-500/20 px-3 py-2 text-sky-700 text-xs">
                  Scoring mode: <strong>{scoringModeLabel}</strong>
                  {scoringMode === "lexical_fallback_degraded"
                    ? ". This score used lexical fallback — it is not equivalent to a full semantic-scorer result."
                    : scoringMode === "unknown"
                      ? ". Mode was not recorded when this attempt was scored."
                      : scoringMode === "practice_estimate"
                        ? ". A heuristic estimate from your written notes; it is not measured mastery and does not change Elo or readiness."
                        : ". This result is self-reported and is not measured mastery."}
                </div>
              )}

              {(round.feedbackSource || round.scorerProvenance) && (
                <details className="mb-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs text-[var(--color-ink-muted)]">
                  <summary className="cursor-pointer text-[var(--color-ink)]">Detailed scoring provenance</summary>
                  <ul className="mt-2 space-y-1">
                    {round.feedbackSource && <li>Feedback source: {String(round.feedbackSource)}</li>}
                    {round.evidence_kind && <li>Evidence: {String(round.evidence_kind)}</li>}
                    {round.scorerProvenance && (
                      <li className="break-all whitespace-pre-wrap">
                        {typeof round.scorerProvenance === "string"
                          ? round.scorerProvenance
                          : JSON.stringify(round.scorerProvenance, null, 2)}
                      </li>
                    )}
                  </ul>
                </details>
              )}

              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="text-[var(--color-ink-muted)]">Overall score</div>
                  <div className="mt-1 text-base font-semibold text-[var(--color-accent)]">{fmt(bd?.final_score, 0)}</div>
                </div>
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="text-[var(--color-ink-muted)]">Content match</div>
                  <div className="mt-1 text-base font-semibold text-[var(--color-ink)]">{fmt(bd?.layer1_score, 0)}</div>
                </div>
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="text-[var(--color-ink-muted)]">Semantic similarity</div>
                  <div className="mt-1 text-base font-semibold text-[var(--color-ink)]">{pct(bd?.semantic_score)}</div>
                </div>
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="text-[var(--color-ink-muted)]">Keyword coverage</div>
                  <div className="mt-1 text-base font-semibold text-[var(--color-ink)]">{pct(bd?.keyword_coverage)}</div>
                </div>
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="text-[var(--color-ink-muted)]">Structure score</div>
                  <div className="mt-1 text-base font-semibold text-[var(--color-ink)]">{pct(bd?.structure_score)}</div>
                </div>
                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="text-[var(--color-ink-muted)]">Classifier signal</div>
                  <div className="mt-1 text-base font-semibold text-[var(--color-ink)]">{bd?.svm_label ?? "–"}</div>
                </div>
              </div>

              {rubric && (
                <div className="mt-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="text-[var(--color-ink-muted)]">Rubric view</div>
                    <div className="text-[10px] uppercase tracking-wider text-[var(--color-ink-muted)]">
                      {rubric.version || bd?.scoring_schema_version || "rubric"}
                    </div>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                      <div className="text-[var(--color-ink-muted)]">Correctness</div>
                      <div className="mt-0.5 text-sm font-semibold text-[var(--color-ink)]">{fmt(rubric.correctness, 1)}/10</div>
                    </div>
                    <div>
                      <div className="text-[var(--color-ink-muted)]">Coverage</div>
                      <div className="mt-0.5 text-sm font-semibold text-[var(--color-ink)]">{fmt(rubric.coverage, 1)}/10</div>
                    </div>
                    <div>
                      <div className="text-[var(--color-ink-muted)]">Depth</div>
                      <div className="mt-0.5 text-sm font-semibold text-[var(--color-ink)]">{fmt(rubric.depth, 1)}/10</div>
                    </div>
                    <div>
                      <div className="text-[var(--color-ink-muted)]">Clarity</div>
                      <div className="mt-0.5 text-sm font-semibold text-[var(--color-ink)]">{fmt(rubric.clarity, 1)}/10</div>
                    </div>
                  </div>
                  {rubric.guard_capped && (
                    <div className="mt-2 text-[11px] text-amber-700">
                      Rubric dimensions were capped by the answer guard.
                    </div>
                  )}
                </div>
              )}

              {/* Layer 1 */}
              <div className="mt-3 pl-2 text-[var(--color-ink-muted)]">
                ├── Content match &nbsp;&nbsp;×55% = <span className="text-[var(--color-ink)]">{layer1Contrib}</span>
                <span className="ml-2 text-[var(--color-ink-muted)]">
                  (Semantic: {fmt(bd?.semantic_score, 2)},&nbsp;
                  TF-IDF: {fmt(bd?.tfidf_score, 2)},&nbsp;
                  Keywords: {pct(bd?.keyword_coverage)})
                </span>
              </div>

              {/* Layer 2 */}
              <div className="pl-2 text-[var(--color-ink-muted)]">
                ├── Answer quality ×25% = <span className="text-[var(--color-ink)]">{layer2Contrib}</span>
              </div>

              {/* Layer 3 */}
              <div className="pl-2 text-[var(--color-ink-muted)]">
                ├── Classifier signal ×20% = <span className="text-[var(--color-ink)]">{layer3Contrib}</span>
                <span className="ml-2 text-[var(--color-ink-muted)]">(predicted: {bd?.svm_label ?? "–"})</span>
              </div>

              {/* KG */}
              <div className="pl-2 text-[var(--color-ink-muted)]">
                └── Knowledge graph: <span className="text-[var(--color-ink)]">{fmt(kgScore, 0)}</span>
                <span className="ml-2 text-[var(--color-ink-muted)]">(blended at 15%)</span>
              </div>

              {/* NLP score */}
              <div className="mt-1 pl-2 text-[var(--color-ink-muted)] border-t border-[var(--color-border)] pt-1">
                NLP score: {fmt(bd?.nlp_score, 1)}&nbsp;·&nbsp;
                KG score: {fmt(bd?.kg_score, 1)}&nbsp;·&nbsp;
                Final: {fmt(bd?.final_score, 1)}
              </div>

              {/* Concept hits / misses (KG) */}
              {(coveredConcepts.length > 0 || missingConcepts.length > 0) && (
                <div className="mt-2 pt-2 border-t border-[var(--color-border)] space-y-1 text-xs">
                  {coveredConcepts.length > 0 && (
                    <div className="text-[var(--color-ink-muted)]">
                      <span className="text-emerald-700">Concepts you covered:</span>{" "}
                      <span className="text-[var(--color-ink)]">{coveredConcepts.join(", ")}</span>
                    </div>
                  )}
                  {missingConcepts.length > 0 && (
                    <div className="text-[var(--color-ink-muted)]">
                      <span className="text-amber-700">Concepts you missed:</span>{" "}
                      <span className="text-[var(--color-ink)]">{missingConcepts.join(", ")}</span>
                    </div>
                  )}
                </div>
              )}

              {missedKeywords.length > 0 && (
                <div className="mt-2 rounded-xl border border-amber-300/15 bg-amber-300/[0.05] p-3 text-xs">
                  <div className="text-amber-700">Missing keywords</div>
                  <div className="mt-1 text-[var(--color-ink-muted)]">{textList(missedKeywords)}</div>
                </div>
              )}

              <div className="mt-2 rounded-xl border border-emerald-300/15 bg-emerald-300/[0.04] p-3 text-xs">
                <div className="text-emerald-700">Ideal answer</div>
                <p className="mt-1 leading-relaxed text-[var(--color-ink-muted)]">{shortText(round.idealAnswer)}</p>
              </div>

              <div className="mt-2 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.04] p-3 text-xs">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="text-[var(--color-accent)]">Next recommended topics</div>
                    <div className="mt-1 text-[var(--color-ink-muted)]">{textList(recommendedTopics, "Review this question's core topic again.")}</div>
                    {round.questionType && (
                      <div className="mt-1 text-[var(--color-ink-muted)]">Question type: {round.questionType}</div>
                    )}
                  </div>
                  <Link
                    to="/upload"
                    className="inline-flex shrink-0 items-center justify-center rounded-full border border-cyan-200/20 bg-cyan-200/10 px-3 py-1.5 text-[11px] font-medium text-[var(--color-accent)] transition hover:bg-cyan-200/15"
                  >
                    Reattempt topic
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ScoringBreakdownPanelProps {
  rounds: Round[];
}

export function ScoringBreakdownPanel({ rounds }: ScoringBreakdownPanelProps) {
  if (!rounds || rounds.length === 0) return null;

  return (
    <div className="glass-panel rounded-3xl p-5 sm:p-6">
      <div className="mb-4">
        <div className="text-xl font-normal italic tracking-tight"
          style={{ fontFamily: "var(--font-display)" }}>
          How this was scored
        </div>
        <p className="mt-0.5 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
          Click a round to expand its scoring breakdown.
        </p>
      </div>
      <div className="space-y-2">
        {rounds.map(r => (
          <RoundBreakdown key={r.id} round={r} />
        ))}
      </div>
    </div>
  );
}
