"""
Smoke test for modules/answer_guard.py — Change 1.

Run with:  python -m pytest tests/test_guard.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.answer_guard import check_answer_quality


def test_empty_answer():
    """Empty string → cap 5, reason 'empty'."""
    result = check_answer_quality("")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 5, f"Expected cap=5, got {result['score_cap']}"
    assert result["reason"] == "empty", f"Expected reason='empty', got {result['reason']}"


def test_gibberish_answer():
    """'asdfasdf' → cap 10, reason 'gibberish'."""
    result = check_answer_quality("asdfasdf qwer hjkl")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 10, f"Expected cap=10, got {result['score_cap']}"
    assert result["reason"] == "gibberish", f"Expected reason='gibberish', got {result['reason']}"


def test_repetition_answer():
    """'docker docker docker docker' → cap 15, reason 'repetition'."""
    result = check_answer_quality("docker docker docker docker docker docker")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 15, f"Expected cap=15, got {result['score_cap']}"
    assert result["reason"] == "repetition", f"Expected reason='repetition', got {result['reason']}"


def test_too_short_answer():
    """'containers are good' (3 words) → cap 20, reason 'too_short'."""
    result = check_answer_quality("containers are good")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 20, f"Expected cap=20, got {result['score_cap']}"
    assert result["reason"] == "too_short", f"Expected reason='too_short', got {result['reason']}"


def test_good_answer_no_cap():
    """A real, substantive answer → no cap applied."""
    answer = (
        "Docker is a containerization platform that packages applications and their dependencies "
        "into isolated containers. Unlike virtual machines, containers share the host OS kernel, "
        "making them lightweight and fast to start. This allows developers to ensure consistency "
        "across development, testing, and production environments, solving the 'works on my machine' "
        "problem. Docker uses a layered filesystem, so image layers are cached and reused efficiently."
    )
    result = check_answer_quality(answer)
    assert result["cap_required"] is False, f"Expected no cap for good answer, got {result}"


def test_question_parroting_exact_copy():
    """Exact copy of the question → cap 25, reason 'question_parroting'."""
    q = "When building a simple interactive form, how would you ensure its accessibility?"
    result = check_answer_quality(q, ideal_keywords="form, accessibility", question_text=q)
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["reason"] == "question_parroting", (
        f"Expected reason='question_parroting', got {result['reason']}"
    )
    assert result["score_cap"] == 25, f"Expected cap=25, got {result['score_cap']}"


def test_question_parroting_paraphrase_passes():
    """Real answer that uses some question words must NOT be flagged."""
    q = "When building a simple interactive form, how would you ensure accessibility?"
    ans = (
        "I would use semantic HTML elements like <form>, <label>, and <input>, "
        "add ARIA attributes for screen readers, ensure keyboard navigation works "
        "for all controls, and validate user input with clear inline error "
        "messages near the relevant field."
    )
    result = check_answer_quality(ans, ideal_keywords="form, accessibility, ARIA", question_text=q)
    assert result["cap_required"] is False, f"False positive: {result}"


def test_no_question_text_old_call_still_works():
    """Backward compat — existing callers that don't pass question_text."""
    result = check_answer_quality("mjgdjrfxhfcjmgjm", "state")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["reason"] == "gibberish", (
        f"Expected reason='gibberish', got {result['reason']}"
    )


if __name__ == "__main__":
    tests = [
        test_empty_answer,
        test_gibberish_answer,
        test_repetition_answer,
        test_too_short_answer,
        test_good_answer_no_cap,
        test_question_parroting_exact_copy,
        test_question_parroting_paraphrase_passes,
        test_no_question_text_old_call_still_works,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")


# ── Entity-swap guard (check_answer_quality_v2) ──────────────────────────────

from modules.answer_guard import (  # noqa: E402
    _contrast_pair,
    check_answer_quality_v2,
    entity_swap_evidence,
)

_TCP_Q = "What is the difference between TCP and UDP?"
_TCP_IDEAL = (
    "TCP is a connection-oriented protocol that establishes a connection with a "
    "three-way handshake and guarantees reliable, ordered delivery using "
    "acknowledgements and retransmission. UDP is connectionless and best-effort: "
    "it has no handshake, no ordering guarantee, and lower overhead, so it suits "
    "latency-sensitive uses like video streaming, gaming and DNS."
)
_TCP_CORRECT = (
    "TCP is connection-oriented: it does a three-way handshake, then guarantees "
    "reliable ordered delivery with acknowledgements and retransmission. UDP is "
    "connectionless and best-effort with lower overhead, which suits streaming, "
    "gaming and DNS."
)
_TCP_SWAPPED = (
    "UDP is connection-oriented: it does a three-way handshake, then guarantees "
    "reliable ordered delivery with acknowledgements and retransmission. TCP is "
    "connectionless and best-effort with lower overhead, which suits streaming, "
    "gaming and DNS."
)


def _v2(answer: str, question: str = _TCP_Q, ideal: str = _TCP_IDEAL) -> dict:
    return check_answer_quality_v2(answer, question_text=question, ideal_answer=ideal)


def test_entity_swap_caps_swapped_comparison():
    result = _v2(_TCP_SWAPPED)
    assert result["cap_required"] is True
    assert result["reason"] == "entity_swap"
    assert result["score_cap"] == 35


def test_entity_swap_allows_correct_comparison():
    assert _v2(_TCP_CORRECT)["reason"] != "entity_swap"


def test_entity_swap_allows_paraphrase():
    paraphrase = (
        "TCP first sets up a session between the two hosts and then makes sure "
        "every byte arrives in sequence, resending anything that gets lost. UDP "
        "just fires off datagrams with no setup and no promise they arrive, which "
        "makes it cheaper and faster for live video, games or DNS lookups."
    )
    assert _v2(paraphrase)["reason"] != "entity_swap"


def test_entity_swap_ignores_negated_statements():
    negated = (
        "UDP is not connection-oriented and does not guarantee ordered delivery. "
        "TCP is not connectionless; it uses a three-way handshake and "
        "acknowledgements for reliable delivery."
    )
    assert _v2(negated)["reason"] != "entity_swap"


def test_entity_swap_needs_both_directions():
    # Only one side carries the other's properties: not a clear swap.
    one_way = (
        "TCP is connection-oriented with a three-way handshake and reliable "
        "ordered delivery. UDP also does a handshake and retransmission."
    )
    assert _v2(one_way)["reason"] != "entity_swap"


def test_entity_swap_noop_without_comparison_question():
    assert _contrast_pair("Explain the four pillars of OOP.") is None
    assert entity_swap_evidence(_TCP_SWAPPED, "Explain the four pillars of OOP.", _TCP_IDEAL) is None


def test_contrast_pair_handles_shared_and_elided_heads():
    assert _contrast_pair("What is the difference between shallow copy and deep copy?") == (
        {"shallow"}, {"deep"}, {"copy"},
    )
    assert _contrast_pair("Explain the difference between supervised and unsupervised learning.") == (
        {"supervised"}, {"unsupervised"}, {"learning"},
    )
    assert _contrast_pair("Explain the difference between lists and tuples in Python.")[:2] == (
        {"list"}, {"tuple"},
    )


def test_entity_swap_pronoun_clause_keeps_subject():
    # "It guarantees ordered pod deployment" is about the StatefulSet even
    # though it uses the word "deployment"; a correct answer must not fire.
    question = "Explain the difference between a Deployment and a StatefulSet in Kubernetes."
    ideal = (
        "A Deployment manages stateless applications. Pods are interchangeable. "
        "A StatefulSet manages stateful applications like databases. It guarantees "
        "ordered pod deployment, stable network identities, and persistent storage per pod."
    )
    answer = (
        "Deployment is for stateless apps and StatefulSet is for stateful ones like "
        "databases. StatefulSet keeps persistent storage and stable pod names."
    )
    assert _v2(answer, question, ideal)["reason"] != "entity_swap"


# ── v3: nonsense detection that does not flag ordinary words ────────────────

from modules import answer_guard as _guard  # noqa: E402
from modules.answer_guard import check_answer_quality_v2  # noqa: E402


def test_common_words_are_not_nonsense():
    for word in ("solves", "optimal", "global", "allows", "objects", "patterns",
                 "reusable", "solutions", "polymorphism", "abstraction",
                 "instruction", "constructor", "branch", "deadlock"):
        assert not _guard._looks_like_nonsense_token(word), word


def test_letter_strings_are_still_nonsense():
    for token in ("qzqzqz", "zzzz", "asdfgh", "xqoizv", "pfuejq", "zvoykx", "kxuevb"):
        assert _guard._looks_like_nonsense_token(token), token


def test_real_comparison_answer_is_not_gibberish():
    answer = ("DP solves subproblems and stores results for optimal global solution; "
              "Greedy makes locally optimal choices hoping for a global optimum.")
    result = check_answer_quality_v2(
        answer,
        question_text="What is the difference between dynamic programming and greedy algorithms?",
        ideal_keywords="subproblems, optimal substructure, memoization, greedy choice",
        ideal_answer=("Dynamic programming solves overlapping subproblems once and stores "
                      "their results; greedy algorithms make the locally optimal choice at "
                      "each step and never revisit it."),
    )
    assert result["reason"] != "gibberish", result


def test_reference_terms_are_never_nonsense():
    # Names a letter-pair table cannot know still count when the question uses them.
    question = "Compare Dijkstra and Kruskal."
    ideal = "Dijkstra finds shortest paths from a source; Kruskal builds a minimum spanning tree."
    assert _guard._looks_like_nonsense_token("kruskal")
    known = _guard._reference_vocabulary(question, "", ideal)
    assert _guard._nonsense_token_ratio(["dijkstra", "kruskal"], known) == 0.0


def test_short_fragment_of_long_reference_is_too_short():
    result = check_answer_quality_v2(
        "Deadlock occurs when processes are permanently.",
        question_text="What is a deadlock?",
        ideal_answer=("A deadlock is a state where each process in a set waits for a resource "
                      "held by another process in the set, so none of them can proceed."),
    )
    assert result["reason"] == "too_short"
    assert result["score_cap"] == 20


def test_short_answer_to_short_reference_is_not_capped():
    # The length rule compares with the reference answer, so a complete short
    # answer to a short question passes. (With these words also listed as
    # keywords, the separate keyword_stuffing rule would still apply.)
    result = check_answer_quality_v2(
        "Atomicity, Consistency, Isolation, Durability.",
        question_text="What does ACID stand for?",
        ideal_answer="Atomicity, Consistency, Isolation and Durability.",
    )
    assert result["cap_required"] is False, result


def test_bigram_table_matches_reference_text():
    import subprocess

    root = os.path.join(os.path.dirname(__file__), "..")
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "scripts", "build_guard_bigrams.py")],
        capture_output=True, text=True, cwd=root,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
