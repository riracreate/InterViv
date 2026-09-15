import React from "react";

export type BlockResultView = {
  position: number;
  title: string;
  metric: string;
  average: number | null;
  selfReportedAverage: number | null;
  skills: string[];
  rounds: number;
  attempted: number;
  scored: number;
  unscored: number;
  scoringModes: string[];
  suggestion: string | null;
};

function countsLine(block: BlockResultView) {
  const noun = block.rounds === 1 ? "round" : "rounds";
  return `Attempted ${block.attempted} · Scored ${block.scored} · Unscored ${block.unscored} of ${block.rounds} ${noun}`;
}

export function BlockResults(props: { blocks: BlockResultView[] }) {
  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6" data-testid="block-results">
      <div>
        <div
          className="text-2xl sm:text-3xl font-normal italic tracking-tight"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Per-block results
        </div>
        <p className="mt-1 text-sm text-white/65" style={{ fontFamily: "var(--font-body)" }}>
          Each block carries its own metric. Block scores are never blended into one percentage.
        </p>
      </div>

      <div className="mt-5 grid gap-4">
        {props.blocks.map((block) => (
          <div
            key={`${block.position}-${block.title}`}
            className="rounded-2xl border border-white/10 bg-black/25 p-4 backdrop-blur-xl"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-white/50" style={{ fontFamily: "var(--font-body)" }}>
                  {block.title}
                </div>
                <div className="mt-1 text-base text-white/90" style={{ fontFamily: "var(--font-body)" }}>
                  {block.metric}
                  {block.skills.length > 0 && (
                    <span className="text-white/55"> · {block.skills.join(", ")}</span>
                  )}
                </div>
              </div>
              <div className="text-right">
                {block.average != null ? (
                  <div className="text-2xl font-semibold text-white" style={{ fontFamily: "var(--font-body)" }}>
                    {Math.round(block.average)}%
                  </div>
                ) : (
                  <div className="text-lg font-medium text-white/60" style={{ fontFamily: "var(--font-body)" }}>
                    Not measured
                  </div>
                )}
                <div className="text-xs text-white/50" style={{ fontFamily: "var(--font-body)" }}>
                  {countsLine(block)}
                </div>
              </div>
            </div>
            {block.selfReportedAverage != null && (
              <p className="mt-2 text-xs leading-5 text-white/55" style={{ fontFamily: "var(--font-body)" }}>
                Self-reported {Math.round(block.selfReportedAverage)}% — kept separate from measured scores.
              </p>
            )}
            {block.suggestion && (
              <p className="mt-2 text-xs leading-5 text-cyan-100/80" style={{ fontFamily: "var(--font-body)" }}>
                {block.suggestion}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
