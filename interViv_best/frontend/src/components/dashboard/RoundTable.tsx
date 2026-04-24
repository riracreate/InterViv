import React, { useMemo, useState } from "react";
import { ChevronDown, MessageSquareText } from "lucide-react";

type Round = {
  id: string;
  question: string;
  score: number;
  difficulty: "Easy" | "Medium" | "Hard" | "Expert";
  feedback: string;
};

function difficultyPill(diff: Round["difficulty"]) {
  switch (diff) {
    case "Easy":
      return "border-emerald-300/20 bg-emerald-300/10 text-emerald-100";
    case "Medium":
      return "border-cyan-300/20 bg-cyan-300/10 text-cyan-100";
    case "Hard":
      return "border-blue-300/20 bg-blue-300/10 text-blue-100";
    case "Expert":
      return "border-fuchsia-300/20 bg-fuchsia-300/10 text-fuchsia-100";
    default:
      return "border-white/10 bg-white/5 text-white/75";
  }
}

function scoreTone(score: number) {
  if (score >= 88) return "text-cyan-100";
  if (score >= 80) return "text-sky-100";
  if (score >= 72) return "text-blue-100";
  return "text-fuchsia-100";
}

export function RoundTable(props: { rounds: Round[] }) {
  const [openId, setOpenId] = useState<string | null>(props.rounds[0]?.id ?? null);

  const sorted = useMemo(() => [...props.rounds], [props.rounds]);

  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-2xl shadow-[0_28px_90px_rgba(0,0,0,0.55)] sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-white/85">
            <MessageSquareText className="h-4 w-4" />
          </div>
          <div>
            <div
              className="text-2xl sm:text-3xl font-normal italic tracking-tight"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Round-by-Round
            </div>
            <p className="mt-1 text-sm text-white/65" style={{ fontFamily: "var(--font-body)" }}>
              Question, score, difficulty, and a fast feedback snippet per round.
            </p>
          </div>
        </div>
      </div>

      {/* Desktop table */}
      <div className="mt-5 hidden overflow-hidden rounded-2xl border border-white/10 bg-black/25 backdrop-blur-xl lg:block">
        <table className="w-full text-left">
          <thead className="border-b border-white/10">
            <tr className="text-xs uppercase tracking-[0.18em] text-white/45" style={{ fontFamily: "var(--font-body)" }}>
              <th className="px-5 py-4">Round</th>
              <th className="px-5 py-4">Question</th>
              <th className="px-5 py-4">Score</th>
              <th className="px-5 py-4">Difficulty</th>
              <th className="px-5 py-4">Feedback</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.id} className="border-b border-white/5 last:border-b-0">
                <td className="px-5 py-4 text-sm text-white/75" style={{ fontFamily: "var(--font-body)" }}>
                  R{r.id}
                </td>
                <td className="px-5 py-4">
                  <div className="text-sm text-white/90" style={{ fontFamily: "var(--font-body)" }}>
                    {r.question}
                  </div>
                </td>
                <td className="px-5 py-4">
                  <div className={`text-sm font-semibold ${scoreTone(r.score)}`} style={{ fontFamily: "var(--font-body)" }}>
                    {Math.round(r.score)}%
                  </div>
                </td>
                <td className="px-5 py-4">
                  <span className={`inline-flex items-center rounded-full border px-3 py-1.5 text-xs ${difficultyPill(r.difficulty)}`}>
                    {r.difficulty}
                  </span>
                </td>
                <td className="px-5 py-4">
                  <div className="text-sm text-white/70" style={{ fontFamily: "var(--font-body)" }}>
                    {r.feedback}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile/Tablet: expandable glass cards */}
      <div className="mt-5 grid gap-3 lg:hidden">
        {sorted.map((r) => {
          const open = openId === r.id;
          return (
            <button
              key={r.id}
              type="button"
              onClick={() => setOpenId(open ? null : r.id)}
              className="w-full rounded-2xl border border-white/10 bg-black/25 p-4 text-left backdrop-blur-xl transition hover:border-white/18 hover:bg-black/30"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs uppercase tracking-[0.18em] text-white/45" style={{ fontFamily: "var(--font-body)" }}>
                      Round {r.id}
                    </span>
                    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] ${difficultyPill(r.difficulty)}`}>
                      {r.difficulty}
                    </span>
                  </div>
                  <div className="mt-2 text-sm text-white/90" style={{ fontFamily: "var(--font-body)" }}>
                    {r.question}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <div className={`text-sm font-semibold ${scoreTone(r.score)}`} style={{ fontFamily: "var(--font-body)" }}>
                    {Math.round(r.score)}%
                  </div>
                  <ChevronDown
                    className={`h-4 w-4 text-white/50 transition-transform ${open ? "rotate-180" : ""}`}
                  />
                </div>
              </div>
              {open && (
                <div
                  className="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-white/70"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  {r.feedback}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}

