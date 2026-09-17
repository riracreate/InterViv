import React from "react";
import { motion } from "motion/react";
import { MessageSquareQuote } from "lucide-react";

type Round = {
  id: string;
  question: string;
  idealAnswer?: string;
  answer?: string;
  score: number;
  /** Optional ±X band derived from layer-score variance (Task 6b). */
  confidenceBand?: number | null;
  difficulty: "Easy" | "Medium" | "Hard" | "Expert";
  feedback: string;
  roundType?: string;
  feedbackSource?: string | null;
};

function shortIdealAnswer(answer?: string) {
  const normalized = (answer || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "Ideal answer is not available for this round.";

  const sentences = normalized.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [normalized];
  const firstTwo = sentences.slice(0, 2).join(" ").trim();
  if (firstTwo.length <= 230) return firstTwo;
  return `${firstTwo.slice(0, 227).trim()}...`;
}

function difficultyTone(diff: Round["difficulty"]) {
  switch (diff) {
    case "Easy":
      return "border-emerald-300/20 bg-emerald-300/10 text-emerald-100";
    case "Medium":
      return "border-cyan-300/20 bg-cyan-300/10 text-cyan-100";
    case "Hard":
      return "border-blue-300/20 bg-blue-300/10 text-blue-100";
    case "Expert":
      return "border-violet-300/20 bg-violet-300/10 text-violet-100";
    default:
      return "border-white/10 bg-white/5 text-white/75";
  }
}

function scoreTone(score: number) {
  if (score >= 90) return "text-cyan-100";
  if (score >= 80) return "text-sky-100";
  if (score >= 70) return "text-indigo-100";
  return "text-fuchsia-100";
}

export function RoundTimeline(props: { rounds: Round[] }) {
  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-white/85">
          <MessageSquareQuote className="h-4 w-4" />
        </div>
        <div>
          <div className="text-2xl font-normal italic tracking-tight sm:text-3xl" style={{ fontFamily: "var(--font-display)" }}>
            Round Timeline
          </div>
          <p className="mt-1 text-sm text-white/65" style={{ fontFamily: "var(--font-body)" }}>
            A clear narrative from first prompt to final performance spike.
          </p>
        </div>
      </div>

      <div className="relative mt-6">
        <div className="absolute left-[18px] top-0 h-full w-px bg-gradient-to-b from-cyan-400/50 via-blue-400/40 to-violet-400/30" />
        <div className="grid gap-4">
          {props.rounds.map((round, index) => (
            <motion.article
              key={round.id}
              initial={{ opacity: 0, y: 10, filter: "blur(8px)" }}
              whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              viewport={{ once: true, amount: 0.25 }}
              transition={{ delay: index * 0.05, duration: 0.45 }}
              className="relative pl-12"
            >
              <span className="absolute left-[8px] top-5 h-5 w-5 rounded-full border border-cyan-300/60 bg-[#0a0a0a] shadow-[0_0_18px_rgba(34,211,238,0.35)]" />
              <div className="rounded-2xl border border-white/10 bg-black/30 p-4 backdrop-blur-xl transition hover:border-white/20 hover:bg-black/35">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs uppercase tracking-[0.2em] text-white/45" style={{ fontFamily: "var(--font-body)" }}>
                      Round {round.id}
                    </span>
                    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] ${difficultyTone(round.difficulty)}`}>
                      {round.difficulty}
                    </span>
                  </div>
                  <div className={`text-lg font-semibold ${scoreTone(round.score)}`} style={{ fontFamily: "var(--font-body)" }} data-testid="round-score">
                    {Math.round(round.score)}%
                    {round.confidenceBand != null && (
                      <span className="ml-1 text-xs text-white/55 font-normal" data-testid="round-confidence-band">
                        ± {round.confidenceBand}
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-[minmax(180px,0.36fr)_1fr]">
                  {round.roundType !== "mcq" && (
                    <div className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.05] p-3">
                      <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-emerald-100/55" style={{ fontFamily: "var(--font-body)" }}>
                        Ideal answer
                      </div>
                      <p className="text-sm leading-relaxed text-white/78" style={{ fontFamily: "var(--font-body)" }}>
                        {shortIdealAnswer(round.idealAnswer)}
                      </p>
                    </div>
                  )}

                  <div className={round.roundType === "mcq" ? "md:col-span-2" : ""}>
                    <p className="text-sm leading-relaxed text-white/90" style={{ fontFamily: "var(--font-body)" }}>
                      {round.question}
                    </p>
                    <div className="mt-3 rounded-xl border border-cyan-300/10 bg-cyan-300/[0.04] p-3">
                      <div className="mb-1 text-[10px] uppercase tracking-[0.18em] text-cyan-100/50" style={{ fontFamily: "var(--font-body)" }}>
                        Answer
                      </div>
                      <p className="text-sm leading-relaxed text-white/75" style={{ fontFamily: "var(--font-body)" }}>
                        {round.answer?.trim() || "No answer captured."}
                      </p>
                    </div>
                    {round.feedbackSource && (
                      <p className="mt-2 text-[10px] uppercase tracking-[0.14em] text-white/45" style={{ fontFamily: "var(--font-body)" }}>
                        Feedback source: {round.feedbackSource}
                      </p>
                    )}
                    <p className="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-white/70" style={{ fontFamily: "var(--font-body)" }}>
                      {round.feedback}
                    </p>
                  </div>
                </div>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}
