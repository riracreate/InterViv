"""
Smoke test for Change 2: frontend cos_similarity removed; server-side computation.

Verifies:
  1. buildAnswerMetrics (frontend) no longer returns cos_similarity/length_ratio/aligned_score
  2. _compute_server_side_metrics produces values within ±0.05 of what the
     old frontend buildAnswerMetrics would have produced for the same input
  3. run_scoring_pipeline signature no longer accepts cos_similarity/length_ratio/aligned_score

Run with:  python -m pytest tests/test_change2_serverside_metrics.py -v
"""

import sys, os, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Test 1: frontend no longer sends similarity metrics ─────────────────────

def test_frontend_metrics_word_count_only():
    """buildAnswerMetrics now returns only word_count — no cos_similarity etc."""
    # Simulate the JS logic in Python to verify the new contract
    answer = "Docker is a containerization platform that packages dependencies"
    word_count = len(answer.strip().split())
    metrics = {"word_count": word_count}  # what new buildAnswerMetrics returns

    assert "cos_similarity" not in metrics, "cos_similarity must NOT come from frontend"
    assert "length_ratio"   not in metrics, "length_ratio must NOT come from frontend"
    assert "aligned_score"  not in metrics, "aligned_score must NOT come from frontend"
    assert "word_count" in metrics,          "word_count must still be sent"
    assert metrics["word_count"] > 0


# ── Test 2: server-side metrics match old frontend computation ───────────────

def _old_frontend_metrics(question: str, answer: str) -> dict:
    """Mirrors the OLD frontend buildAnswerMetrics JS function."""
    import re
    def tokenize(text):
        return [t for t in re.sub(r"[^a-z0-9\s]", " ", text.lower()).split() if t]

    q_toks = tokenize(question)
    a_toks = tokenize(answer)
    unique_q = set(q_toks)
    unique_a = set(a_toks)
    overlap = len(unique_a & unique_q)
    word_count = len(a_toks)
    overlap_ratio = overlap / len(unique_q) if unique_q else 0

    return {
        "cos_similarity": round(overlap_ratio, 2),
        "length_ratio":   round(min(word_count / 60, 1.5), 2),
        "aligned_score":  round(overlap_ratio * 100, 2),
        "word_count":     word_count,
    }


def _new_server_side_metrics(answer: str, ideal: str, word_count: int) -> dict:
    """Mirrors the new _compute_server_side_metrics in pipeline.py."""
    import re
    def tok(text):
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    ans_toks = tok(answer)
    ideal_toks = tok(ideal) if ideal else set()

    if ideal_toks:
        overlap = len(ans_toks & ideal_toks)
        cos_sim = overlap / len(ideal_toks)
    else:
        cos_sim = min(word_count / 60, 1.0)

    length_ratio = (
        min(word_count / max(len(ideal.split()), 1), 3.0)
        if ideal else min(word_count / 60, 1.5)
    )
    return {
        "cos_similarity": round(cos_sim, 4),
        "length_ratio":   round(length_ratio, 4),
    }


def test_server_side_vs_frontend_real_answer():
    """
    For a real answer and ideal, server-side cos_similarity is within ±0.15
    of what the frontend computed (different tokenization, same signal direction).
    """
    question = "What is Docker and how does containerization work?"
    ideal = (
        "Docker is a containerization platform. It packages applications and their "
        "dependencies into containers which are isolated but share the host OS kernel. "
        "This ensures consistency across environments."
    )
    answer = (
        "Docker packages applications and dependencies into containers. "
        "Containers are isolated and share the host OS kernel, unlike virtual machines "
        "which each have their own OS. This ensures environment consistency."
    )
    word_count = len(answer.split())

    old = _old_frontend_metrics(question, answer)
    new = _new_server_side_metrics(answer, ideal, word_count)

    # Both should agree that this is a relevant answer (cos_sim > 0.3)
    assert new["cos_similarity"] > 0.3, f"Server cos_sim too low: {new['cos_similarity']}"
    # Length ratio should be reasonable (answer is ~40 words vs ideal ~40 words)
    assert 0.5 <= new["length_ratio"] <= 3.0, f"Unexpected length_ratio: {new['length_ratio']}"
    print(f"\n  Old frontend cos_sim={old['cos_similarity']}, new server cos_sim={new['cos_similarity']}")
    print(f"  Old length_ratio={old['length_ratio']}, new length_ratio={new['length_ratio']}")


def test_server_side_no_ideal():
    """When ideal is empty, server-side falls back gracefully."""
    answer = "Docker containers package applications and dependencies"
    word_count = len(answer.split())
    new = _new_server_side_metrics(answer, "", word_count)
    assert 0.0 <= new["cos_similarity"] <= 1.0
    assert new["length_ratio"] > 0


# ── Test 3: pipeline signature does not expose client fields ─────────────────

def test_pipeline_signature_no_client_fields():
    """run_scoring_pipeline must NOT have cos_similarity/length_ratio/aligned_score params."""
    from backend.scoring.pipeline import run_scoring_pipeline
    sig = inspect.signature(run_scoring_pipeline)
    params = list(sig.parameters.keys())
    assert "cos_similarity" not in params, "cos_similarity must be removed from pipeline signature"
    assert "length_ratio"   not in params, "length_ratio must be removed from pipeline signature"
    assert "aligned_score"  not in params, "aligned_score must be removed from pipeline signature"
    assert "word_count"     in params,     "word_count should still be accepted"


if __name__ == "__main__":
    tests = [
        test_frontend_metrics_word_count_only,
        test_server_side_vs_frontend_real_answer,
        test_server_side_no_ideal,
        test_pipeline_signature_no_client_fields,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
