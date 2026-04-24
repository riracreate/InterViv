"""
nlp_scorer_patch.py — Small patch layer over the existing v11 NLPScorer.

The v11 scorer returns ~20-25 (Poor band) for genuinely good answers when
the ideal_answer is empty (e.g. when a question was LLM-generated or came
from a template fallback). That's because Layer 1 has nothing to compare
against.

This patch wraps compute_overall_score() and, when ideal_answer is empty,
substitutes Layer 1 with a length + depth heuristic so good answers can
still reach the Good band.

Usage in pipeline.py: replace
    scorer = NLPScorer(model_path=...)
    result = scorer.compute_overall_score(answer=..., ideal_answer=..., ...)
with
    from nlp_scorer_patch import PatchedNLPScorer
    scorer = PatchedNLPScorer(model_path=...)
    result = scorer.compute_overall_score(answer=..., ideal_answer=..., ...)
"""
from __future__ import annotations

import re
from typing import Any

try:
    from nlp_scorer import NLPScorer as _BaseNLPScorer  # type: ignore
except ImportError:
    from modules.nlp_scorer import NLPScorer as _BaseNLPScorer  # type: ignore


_DEPTH_MARKERS = [
    r"\b(for example|for instance|e\.?g\.?|such as)\b",
    r"\b(trade-?off|tradeoff|on the other hand|however|whereas)\b",
    r"\b(because|since|therefore|which means|this means)\b",
    r"\b(edge case|corner case|boundary|what if|failure mode)\b",
    r"\b(in production|real-world|in practice|at scale)\b",
    r"\b(O\(n|O\(log|O\(1|complexity|performance|latency)\b",
]


def _heuristic_layer1(answer: str) -> float:
    """Return a Layer 1 score (0-100) computed from answer text alone.

    Blends three signals, each 0-1:
      - length: sigmoid over word count (target 60-80 words)
      - depth: number of analytical markers (trade-offs, examples, reasoning)
      - structure: sentence count and variety
    """
    if not answer.strip():
        return 0.0

    words = answer.split()
    wc = len(words)
    # Length sigmoid — 30 wc = 0.5, 80 wc = ~0.9
    length_score = max(0.0, min(1.0, (wc - 10) / 70))

    text_low = answer.lower()
    depth_hits = sum(1 for pat in _DEPTH_MARKERS if re.search(pat, text_low))
    depth_score = min(1.0, depth_hits / 3.0)

    sentences = [s for s in re.split(r"[.!?]+", answer) if len(s.split()) >= 3]
    sentence_score = min(1.0, len(sentences) / 4.0)

    blended = 0.40 * length_score + 0.35 * depth_score + 0.25 * sentence_score
    return blended * 100


class PatchedNLPScorer(_BaseNLPScorer):
    """Wraps v11 NLPScorer. Only behaviour change: when ideal_answer is empty,
    we substitute the (otherwise near-zero) Layer 1 score with a heuristic
    derived from answer length + depth signals.

    This preserves the full output shape — pipeline.py, dashboard.py and the
    frontend don't need to change.
    """

    def compute_overall_score(
        self,
        answer_text: str | None = None,
        answer: str | None = None,
        question: str | None = None,
        ideal_answer: str | None = None,
        reference_answer: str | None = None,
        ideal_keywords: str | None = None,
        expected_keywords: str | None = None,
        difficulty: str = "medium",
        candidate_baseline: float | None = None,
    ) -> dict[str, Any]:
        kwargs = dict(
            answer_text=answer_text,
            answer=answer,
            question=question,
            ideal_answer=ideal_answer,
            reference_answer=reference_answer,
            ideal_keywords=ideal_keywords,
            expected_keywords=expected_keywords,
            difficulty=difficulty,
            candidate_baseline=candidate_baseline,
        )
        ideal = (ideal_answer or reference_answer or "").strip()

        result = _BaseNLPScorer.get_feature_scores(self, **kwargs)

        if ideal:
            return result  # ideal present — no patching needed

        # ideal is empty → recompute Layer 1 from answer alone
        answer = (answer_text or answer or "").strip()
        if not answer:
            return result

        new_l1 = _heuristic_layer1(answer)
        old_l1 = result.get("layer1_score", 0.0)
        # Take the MAX so a strong ideal-matched score isn't penalised if
        # somehow both paths compute a value. For empty ideal, old_l1 ~0.
        result["layer1_score"] = round(max(new_l1, old_l1), 2)

        # Recompute weighted overall with the new Layer 1
        l1 = result["layer1_score"]
        l2 = result.get("layer2_score", 0.0)
        l3 = result.get("layer3_score", 0.0)
        blended = 0.55 * l1 + 0.25 * l2 + 0.20 * l3

        # apply same modifier family — rough match to v11 behaviour
        bonus = float(result.get("advanced_bonus") or 0.0)
        diff_bonus = float(result.get("difficulty_bonus") or 0.0)
        diff_mult = 1.0 + diff_bonus

        blended_with_mods = min(blended * diff_mult + bonus, 100.0)

        # Apply a small floor only — don't inflate past the genuine value
        result["overall_score"] = round(max(0.0, min(blended_with_mods, 100.0)), 2)
        result["empty_ideal_fallback"] = True
        return result

    # Convenience alias, some callers use get_feature_scores
    def get_feature_scores(self, **kwargs: Any) -> dict[str, Any]:
        return self.compute_overall_score(**kwargs)


if __name__ == "__main__":
    print("=" * 70)
    print("SELF-TEST — PatchedNLPScorer (empty-ideal path)")
    print("=" * 70)

    scorer = PatchedNLPScorer(model_path=None)

    good_docker = (
        "Docker networks: bridge is default for single-host containers and NATs "
        "traffic out through the host. Host networking shares the host's stack "
        "which is faster but loses isolation. Overlay is used in Swarm or "
        "Kubernetes overlay mode for cross-host container communication. For "
        "example, choose overlay when running a multi-host service mesh — the "
        "trade-off is added encapsulation latency."
    )
    poor_docker = "Docker networks are networking."

    for name, ans in [("Good (no ideal)", good_docker), ("Poor (no ideal)", poor_docker)]:
        r = scorer.compute_overall_score(answer=ans, ideal_answer="", difficulty="medium")
        print(f"\n[{name}]")
        print(f"  overall  = {r['overall_score']}")
        print(f"  layer1   = {r['layer1_score']}  (heuristic fallback)")
        print(f"  layer2   = {r['layer2_score']}")
        print(f"  layer3   = {r['layer3_score']}")
        print(f"  empty_fb = {r.get('empty_ideal_fallback')}")
