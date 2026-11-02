"""
scoring_regression.py — End-to-end regression for the scoring pipeline.

Runs `backend.scoring.pipeline.run_scoring_pipeline` against 8 fixture answers
that span the quality spectrum and the gaming-attack vectors that guard v2
(see modules/answer_guard.py and Task 2 in docs/post_eval_task_2.md) is meant
to defend against.

Each case asserts a final-score band and, when applicable, the expected
`guard_applied` reason. The script prints a per-case table and exits non-zero
if any assertion fails so it can be wired into CI.

Run:
    python scripts/scoring_regression.py
    python scripts/scoring_regression.py --json out.json   # also dump JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.runtime_env import apply_runtime_env  # noqa: E402

apply_runtime_env()

from backend.scoring.pipeline import run_scoring_pipeline  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

OOP_QUESTION = "Explain the four pillars of OOP."
OOP_IDEAL = (
    "The four pillars are encapsulation, inheritance, polymorphism, and "
    "abstraction. Encapsulation hides internal state behind methods; "
    "inheritance lets subclasses reuse behaviour; polymorphism allows "
    "subtypes to be used interchangeably via method overriding; abstraction "
    "exposes only essential operations and follows SOLID design principles."
)
OOP_KEYWORDS = ["encapsulation", "inheritance", "polymorphism", "abstraction"]


def _ctx(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    # The pipeline reads ideal_keywords as a comma-separated string
    # (see backend/scoring/pipeline.py).
    base = {
        "question": OOP_QUESTION,
        "ideal_answer": OOP_IDEAL,
        "ideal_keywords": ", ".join(OOP_KEYWORDS),
        "keywords": list(OOP_KEYWORDS),
        "skill": "OOP",
    }
    if extra:
        base.update(extra)
    return base


@dataclass
class Case:
    name: str
    answer: str
    min_score: float = 0.0
    max_score: float = 100.0
    expect_guard: str | None = None  # None = any/no guard; "" = must be no guard
    notes: str = ""
    context: dict[str, Any] = field(default_factory=_ctx)


CASES: list[Case] = [
    Case(
        name="excellent",
        answer=(
            "The four pillars are encapsulation, inheritance, polymorphism, "
            "and abstraction. Encapsulation hides internal state behind "
            "public methods so callers depend only on the interface. "
            "Inheritance lets a subclass reuse behaviour from a base class. "
            "Polymorphism allows method overriding so subtypes can be "
            "substituted at runtime. Abstraction exposes only the essential "
            "operations and is reinforced by SOLID design principles."
        ),
        min_score=70.0,
        max_score=100.0,
        expect_guard="",
        notes="Full ideal coverage with explanations — should score in the upper band.",
    ),
    Case(
        name="paraphrase",
        answer=(
            "Object oriented design rests on four ideas. First, hiding the "
            "internal data of an object behind its public methods. Second, "
            "letting a child class reuse the behaviour of its parent. "
            "Third, allowing one interface to take many forms by overriding "
            "methods on derived types. Fourth, surfacing only the essential "
            "operations to clients while keeping implementation details "
            "private."
        ),
        min_score=45.0,
        max_score=100.0,
        expect_guard="",
        notes=(
            "Same meaning as the ideal but expressed without naming the "
            "four pillars (zero shared content tokens). The 45-floor is "
            "cleanly separated from every gaming-attack case (all ≤35), "
            "so this regression confirms the L1 semantic blend rescues "
            "paraphrases from the attack-vector floor — the property the "
            "Task 3 calibration (kept 60/40 per Δ=+0.0061<0.05) preserves."
        ),
    ),
    Case(
        name="partial",
        answer=(
            "OOP is built on encapsulation and inheritance. Encapsulation "
            "is about wrapping data and methods together so the internal "
            "state stays hidden. Inheritance lets one class reuse another."
        ),
        min_score=30.0,
        max_score=70.0,
        expect_guard="",
        notes="Covers two of four pillars correctly — should land in the middle band.",
    ),
    Case(
        name="empty",
        answer="",
        min_score=0.0,
        max_score=10.0,
        expect_guard="empty",
        notes="Guard v1 — empty answer must short-circuit.",
    ),
    Case(
        name="gibberish",
        answer="qzqzqz xkxkxk vwvwvw zzzz xxxx vvvv qqqq jjjj kkkk",
        min_score=0.0,
        max_score=25.0,
        expect_guard="gibberish",
        notes="Guard v1 — low vowel ratio / not real words should cap hard.",
    ),
    Case(
        name="excessive_repetition",
        answer=(
            "really really really really really really really really "
            "really really really really really really good answer."
        ),
        min_score=0.0,
        max_score=30.0,
        expect_guard="repetition",
        notes=(
            "Guard v1 — single token dominates >40% of tokens; the rule's "
            "label is 'repetition' (see modules/answer_guard.py)."
        ),
    ),
    Case(
        name="keyword_stuffing",
        answer=(
            "encapsulation inheritance polymorphism abstraction "
            "encapsulation inheritance polymorphism abstraction "
            "encapsulation inheritance polymorphism abstraction"
        ),
        min_score=0.0,
        max_score=40.0,
        expect_guard="keyword_stuffing",
        notes=(
            "Guard v1 — high keyword density without sentence structure "
            "should not earn a high score from coverage alone."
        ),
    ),
    Case(
        name="off_topic",
        answer=(
            "I spent the weekend cooking risotto. The trick is to add warm "
            "stock one ladle at a time and stir constantly over a low flame "
            "for about thirty minutes until the rice releases its starch."
        ),
        min_score=0.0,
        max_score=35.0,
        expect_guard="off_topic",
        notes=(
            "Guard v2 (Task 2) — off-topic answer with zero keyword overlap "
            "and low semantic similarity must be capped."
        ),
    ),
    Case(
        name="entity_swap",
        answer=(
            "UDP is connection-oriented: it does a three-way handshake, then "
            "guarantees reliable ordered delivery with acknowledgements and "
            "retransmission, plus flow control and congestion control. TCP is "
            "connectionless and best-effort, with no handshake and no ordering "
            "guarantee, so it has lower overhead and latency, which suits "
            "streaming, gaming and DNS."
        ),
        min_score=0.0,
        max_score=35.0,
        expect_guard="entity_swap",
        notes=(
            "TCP and UDP properties exchanged. Before the guard this scored "
            "88 (correct version: 90) because embeddings and keywords ignore "
            "which side a property is attached to."
        ),
        context=_ctx({
            "question": "What is the difference between TCP and UDP?",
            "ideal_answer": (
                "TCP is a connection-oriented protocol that establishes a "
                "connection with a three-way handshake and guarantees reliable, "
                "ordered delivery using acknowledgements, retransmission, flow "
                "control and congestion control. UDP is connectionless and "
                "best-effort: it has no handshake, no ordering or delivery "
                "guarantee, and lower overhead, so it suits latency-sensitive "
                "uses like video streaming, gaming and DNS."
            ),
            "ideal_keywords": "connection-oriented, connectionless, handshake, reliable, ordered, best-effort, latency, overhead",
            "keywords": ["connection-oriented", "connectionless", "handshake", "reliable"],
            "skill": "CN",
        }),
    ),
]


# --------------------------------------------------------------------------- #
# Runner                                                                      #
# --------------------------------------------------------------------------- #

@dataclass
class Result:
    name: str
    final_score: float
    guard_applied: str | None
    nlp_score: float
    kg_score: float
    expected_min: float
    expected_max: float
    expected_guard: str | None
    score_ok: bool
    guard_ok: bool
    failures: list[str] = field(default_factory=list)


def _score_one(case: Case) -> Result:
    pipeline_out = run_scoring_pipeline(
        answer_text=case.answer,
        word_count=len(case.answer.split()),
        engagement_label="engaged",
        wpm=140.0,
        pause_count=2,
        question_context=case.context,
        difficulty="medium",
        candidate_baseline=None,
    )
    final = float(pipeline_out.get("final_score", 0.0))
    guard = pipeline_out.get("guard_applied")
    nlp = float(pipeline_out.get("nlp_score", 0.0))
    kg = float(pipeline_out.get("kg_score", 0.0))

    failures: list[str] = []

    score_ok = case.min_score <= final <= case.max_score
    if not score_ok:
        failures.append(
            f"final_score={final:.2f} outside [{case.min_score}, {case.max_score}]"
        )

    if case.expect_guard is None:
        guard_ok = True
    elif case.expect_guard == "":
        guard_ok = guard in (None, "", "none")
        if not guard_ok:
            failures.append(f"unexpected guard_applied={guard!r}")
    else:
        guard_ok = guard == case.expect_guard
        if not guard_ok:
            failures.append(
                f"guard_applied={guard!r}, expected {case.expect_guard!r}"
            )

    return Result(
        name=case.name,
        final_score=round(final, 2),
        guard_applied=guard,
        nlp_score=round(nlp, 2),
        kg_score=round(kg, 2),
        expected_min=case.min_score,
        expected_max=case.max_score,
        expected_guard=case.expect_guard,
        score_ok=score_ok,
        guard_ok=guard_ok,
        failures=failures,
    )


def _print_table(results: list[Result]) -> None:
    header = f"{'case':22s}  {'final':>6s}  {'band':>14s}  {'guard':>26s}  status"
    print(header)
    print("-" * len(header))
    for r in results:
        band = f"[{r.expected_min:>4.0f},{r.expected_max:>4.0f}]"
        eg = "(none)" if r.expected_guard == "" else (r.expected_guard or "any")
        guard_str = f"{r.guard_applied or '-'}/{eg}"
        status = "PASS" if (r.score_ok and r.guard_ok) else "FAIL"
        print(
            f"{r.name:22s}  {r.final_score:>6.2f}  {band:>14s}  {guard_str:>26s}  {status}"
        )
    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None, help="Optional path to dump JSON results.")
    parser.add_argument(
        "--filter",
        default=None,
        help="Substring filter on case name (useful while iterating).",
    )
    args = parser.parse_args()

    cases = CASES
    if args.filter:
        cases = [c for c in CASES if args.filter in c.name]
        if not cases:
            print(f"No cases matched filter {args.filter!r}", file=sys.stderr)
            return 2

    print(f"Running {len(cases)} regression case(s)...\n")
    results = [_score_one(c) for c in cases]
    _print_table(results)

    failed = [r for r in results if not (r.score_ok and r.guard_ok)]
    for r in failed:
        print(f"FAIL {r.name}:")
        for f in r.failures:
            print(f"   - {f}")

    if args.json:
        Path(args.json).write_text(json.dumps([asdict(r) for r in results], indent=2))
        print(f"Wrote results to {args.json}")

    if failed:
        print(f"\n{len(failed)}/{len(results)} case(s) failed.")
        return 1

    print(f"\nAll {len(results)} cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
