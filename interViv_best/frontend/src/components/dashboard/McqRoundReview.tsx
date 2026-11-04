import React from "react";

export type McqReviewItem = {
  id: string;
  stem: string;
  selectedLabels: string[];
  correctLabels: string[];
  explanation: string | null;
  isCorrect: boolean | null;
};

export type McqReviewView = {
  reviewPolicy: string;
  keysVisible: boolean;
  items: McqReviewItem[];
};

export function McqRoundReview(props: { review: McqReviewView | null }) {
  if (!props.review?.items?.length) return null;
  const { review } = props;
  return (
    <section className="glass-panel rounded-3xl p-5 sm:p-6" data-testid="mcq-round-review">
      <div>
        <div
          className="text-2xl sm:text-3xl font-normal italic tracking-tight"
          style={{ fontFamily: "var(--font-display)" }}
        >
          MCQ review
        </div>
        <p className="mt-1 text-sm text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
          {review.keysVisible
            ? "Answer keys and explanations are shown because this session is completed and review policy is after_session."
            : review.reviewPolicy === "none"
              ? "Review policy is none — selections are shown without answer keys."
              : "Answer keys stay hidden until the session is completed under after_session review."}
        </p>
      </div>
      <div className="mt-5 grid gap-3">
        {review.items.map((item, index) => (
          <article
            key={item.id}
            className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
            data-testid="mcq-review-item"
          >
            <p className="text-sm text-[var(--color-ink)]" style={{ fontFamily: "var(--font-body)" }}>
              <span className="text-[var(--color-ink-muted)]">Q{index + 1}. </span>
              {item.stem}
            </p>
            <p className="mt-2 text-xs text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
              Your answer: {item.selectedLabels.length ? item.selectedLabels.join(", ") : "No selection"}
              {item.isCorrect != null && (
                <span className={item.isCorrect ? " text-emerald-700" : " text-rose-700"}>
                  {item.isCorrect ? " · correct" : " · incorrect"}
                </span>
              )}
            </p>
            {review.keysVisible && item.correctLabels.length > 0 && (
              <p className="mt-1 text-xs text-[var(--color-accent)]" style={{ fontFamily: "var(--font-body)" }}>
                Correct: {item.correctLabels.join(", ")}
              </p>
            )}
            {review.keysVisible && item.explanation && (
              <p className="mt-2 text-xs leading-5 text-[var(--color-ink-muted)]" style={{ fontFamily: "var(--font-body)" }}>
                {item.explanation}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
