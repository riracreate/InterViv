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
        <p className="mt-1 text-sm text-white/65" style={{ fontFamily: "var(--font-body)" }}>
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
            className="rounded-2xl border border-white/10 bg-black/25 p-4"
            data-testid="mcq-review-item"
          >
            <p className="text-sm text-white/90" style={{ fontFamily: "var(--font-body)" }}>
              <span className="text-white/50">Q{index + 1}. </span>
              {item.stem}
            </p>
            <p className="mt-2 text-xs text-white/70" style={{ fontFamily: "var(--font-body)" }}>
              Your answer: {item.selectedLabels.length ? item.selectedLabels.join(", ") : "No selection"}
              {item.isCorrect != null && (
                <span className={item.isCorrect ? " text-emerald-200" : " text-rose-200"}>
                  {item.isCorrect ? " · correct" : " · incorrect"}
                </span>
              )}
            </p>
            {review.keysVisible && item.correctLabels.length > 0 && (
              <p className="mt-1 text-xs text-cyan-100/85" style={{ fontFamily: "var(--font-body)" }}>
                Correct: {item.correctLabels.join(", ")}
              </p>
            )}
            {review.keysVisible && item.explanation && (
              <p className="mt-2 text-xs leading-5 text-white/60" style={{ fontFamily: "var(--font-body)" }}>
                {item.explanation}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
