import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface ScoringBreakdown {
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
}

interface Round {
  id: string;
  question: string;
  score: number;
  difficulty: string;
  scoring_breakdown?: ScoringBreakdown;
}

function fmt(n?: number | null, decimals = 1): string {
  if (n == null || n === undefined) return "–";
  return Number(n).toFixed(decimals);
}

function pct(n?: number | null): string {
  if (n == null || n === undefined) return "–";
  return `${Math.round(Number(n) * 100)}%`;
}

function RoundBreakdown({ round }: { round: Round }) {
  const [open, setOpen] = useState(false);
  const bd = round.scoring_breakdown;
  const hasData = bd && (bd.layer1_score != null || bd.final_score != null);

  const layer1Contrib = bd ? (0.55 * (bd.layer1_score ?? 0)).toFixed(1) : "–";
  const layer2Contrib = bd ? (0.25 * (bd.layer2_score ?? 0)).toFixed(1) : "–";
  const layer3Contrib = bd ? (0.20 * (bd.layer3_score ?? 0)).toFixed(1) : "–";
  const kgScore       = bd?.kg_score ?? 0;

  return (
    <div className="rounded-2xl border border-white/8 bg-white/3 overflow-hidden">
      {/* Header row */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/4 transition-colors"
        onClick={() => setOpen(o => !o)}
        type="button"
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-white/40">R{round.id}</span>
          <span className="text-sm text-white/85 truncate max-w-[280px]" style={{ fontFamily: "var(--font-body)" }}>
            {round.question}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            round.difficulty === "Hard" ? "bg-red-500/15 text-red-300" :
            round.difficulty === "Medium" ? "bg-amber-500/15 text-amber-300" :
            "bg-green-500/15 text-green-300"
          }`}>{round.difficulty}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm font-medium text-cyan-200">{Math.round(round.score)}</span>
          {open
            ? <ChevronDown className="h-4 w-4 text-white/40" />
            : <ChevronRight className="h-4 w-4 text-white/40" />}
        </div>
      </button>

      {/* Collapsible breakdown */}
      {open && (
        <div className="border-t border-white/6 px-4 py-3 space-y-2">
          {!hasData ? (
            <p className="text-xs text-white/40 italic">No scoring breakdown available for this round.</p>
          ) : (
            <div className="font-mono text-xs text-white/70 space-y-1">
              {/* Guard warning */}
              {bd?.guard_applied && (
                <div className="mb-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-amber-300 text-xs">
                  ⚠ Guard applied: <strong>{bd.guard_applied}</strong> — score capped
                </div>
              )}

              <div className="flex items-center gap-2 text-white/90 text-sm font-medium mb-1">
                <span>Final</span>
                <span className="text-cyan-200">{fmt(bd?.final_score, 0)}</span>
              </div>

              {/* Layer 1 */}
              <div className="pl-2 text-white/65">
                ├── Content match &nbsp;&nbsp;×55% = <span className="text-white/85">{layer1Contrib}</span>
                <span className="ml-2 text-white/40">
                  (Semantic: {fmt(bd?.semantic_score, 2)},&nbsp;
                  TF-IDF: {fmt(bd?.tfidf_score, 2)},&nbsp;
                  Keywords: {pct(bd?.keyword_coverage)})
                </span>
              </div>

              {/* Layer 2 */}
              <div className="pl-2 text-white/65">
                ├── Answer quality ×25% = <span className="text-white/85">{layer2Contrib}</span>
              </div>

              {/* Layer 3 */}
              <div className="pl-2 text-white/65">
                ├── ML judgment &nbsp;&nbsp;&nbsp;×20% = <span className="text-white/85">{layer3Contrib}</span>
                <span className="ml-2 text-white/40">(predicted: {bd?.svm_label ?? "–"})</span>
              </div>

              {/* KG */}
              <div className="pl-2 text-white/65">
                └── Knowledge graph: <span className="text-white/85">{fmt(kgScore, 0)}</span>
                <span className="ml-2 text-white/40">(blended at 15%)</span>
              </div>

              {/* NLP score */}
              <div className="mt-1 pl-2 text-white/35 border-t border-white/5 pt-1">
                NLP score: {fmt(bd?.nlp_score, 1)}&nbsp;·&nbsp;
                KG score: {fmt(bd?.kg_score, 1)}&nbsp;·&nbsp;
                Final: {fmt(bd?.final_score, 1)}
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
        <p className="mt-0.5 text-sm text-white/55" style={{ fontFamily: "var(--font-body)" }}>
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
