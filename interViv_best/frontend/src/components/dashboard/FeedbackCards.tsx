import React, { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Brain, ChevronDown, ListChecks, Mic2, ScanEye } from "lucide-react";

type Card = {
  id: string;
  title: string;
  body: string;
  tag: string;
};

function tagMeta(tag: Card["tag"]) {
  switch (tag) {
    case "Coverage":
      return { icon: <ScanEye className="h-4 w-4" />, pill: "border-cyan-300/20 bg-cyan-300/10 text-[var(--color-accent)]" };
    case "Overview":
      return { icon: <ListChecks className="h-4 w-4" />, pill: "border-blue-300/20 bg-blue-300/10 text-blue-700" };
    case "Highlight":
      return { icon: <Mic2 className="h-4 w-4" />, pill: "border-fuchsia-300/20 bg-fuchsia-300/10 text-fuchsia-700" };
    case "Progress":
    default:
      return { icon: <Brain className="h-4 w-4" />, pill: "border-emerald-300/20 bg-emerald-300/10 text-emerald-700" };
  }
}

export function FeedbackCards(props: { cards: Card[] }) {
  const [open, setOpen] = useState<string | null>(props.cards[0]?.id ?? null);

  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div
            className="text-2xl sm:text-3xl font-normal italic tracking-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Detailed Feedback
          </div>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
            Plain-language notes from this session you can act on.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {props.cards.map((c) => {
          const isOpen = open === c.id;
          const meta = tagMeta(c.tag);
          return (
            <div key={c.id} className="relative overflow-hidden rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 backdrop-blur-2xl">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(34,211,238,0.08),transparent_38%),radial-gradient(circle_at_80%_30%,rgba(59,130,246,0.06),transparent_45%)]" />
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : c.id)}
                className="relative w-full text-left"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-2xl bg-[var(--color-surface)] text-[var(--color-ink)]">
                      {meta.icon}
                    </div>
                    <div className="min-w-0">
                      <div className="text-base font-semibold text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
                        {c.title}
                      </div>
                      <span className={`mt-2 inline-flex items-center rounded-full border px-3 py-1 text-[11px] ${meta.pill}`}>
                        {c.tag}
                      </span>
                    </div>
                  </div>
                  <ChevronDown className={`h-4 w-4 text-[var(--color-ink-muted)] transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </div>
              </button>

              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.p
                    initial={{ opacity: 0, height: 0, y: -4 }}
                    animate={{ opacity: 1, height: "auto", y: 0 }}
                    exit={{ opacity: 0, height: 0, y: -4 }}
                    transition={{ duration: 0.25 }}
                    className="relative mt-4 overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm leading-relaxed text-[var(--color-ink-muted)]"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    {c.body}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </section>
  );
}

