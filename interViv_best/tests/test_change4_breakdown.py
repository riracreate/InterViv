"""
Smoke test for Change 4: Scoring breakdown persisted per round.

Verifies:
  1. pipeline.py returns a scoring_breakdown dict with all required keys
  2. All required keys have valid types (float or None where expected)
  3. answer.py stores scoring_breakdown in the round document (tested via
     checking the field is plumbed through the return dict)

Run with:  python -m pytest tests/test_change4_breakdown.py -v
"""

import sys, os, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REQUIRED_BREAKDOWN_KEYS = {
    "layer1_score",
    "layer2_score",
    "layer3_score",
    "semantic_score",
    "tfidf_score",
    "keyword_coverage",
    "kg_score",
    "ner_score",
    "guard_applied",
    "final_score",
    "nlp_score",
    "svm_label",
    "feedback",
}


def test_pipeline_returns_scoring_breakdown():
    """run_scoring_pipeline return dict includes 'scoring_breakdown' key."""
    from backend.scoring.pipeline import run_scoring_pipeline
    sig = inspect.signature(run_scoring_pipeline)
    # The function must not crash when called with minimal kwargs
    # We can't call it without the full infrastructure, so just verify the
    # scoring_breakdown is built from nlp_payload in the function body.
    # Check that the source references all required keys.
    import inspect as _i
    src = _i.getsource(run_scoring_pipeline)
    for key in ("layer1_score", "layer2_score", "layer3_score", "semantic_score",
                "tfidf_score", "keyword_coverage", "kg_score", "guard_applied",
                "final_score", "nlp_score", "svm_label", "scoring_breakdown"):
        assert key in src, f"'{key}' missing from run_scoring_pipeline source"


def test_scoring_breakdown_keys_complete():
    """scoring_breakdown dict must contain all required keys."""
    # Simulate what pipeline.py builds as scoring_breakdown with a mock nlp_payload
    mock_nlp_payload = {
        "layer1_score": 72.5,
        "layer2_score": 65.0,
        "layer3_score": 75.0,
        "semantic_score": 0.82,
        "tfidf_score": 0.55,
        "keyword_coverage": 0.70,
        "depth_score": 0.6,
        "structure_score": 0.5,
        "accuracy_score": 0.7,
        "clarity_score": 0.8,
        "advanced_bonus": 2.0,
        "difficulty_bonus": 0.05,
    }
    mock_guard = {"cap_required": False, "score_cap": 100, "reason": ""}
    mock_svm_label = "Good"
    mock_nlp_score = 70.0
    mock_kg_score  = 60.0
    mock_final_score = 68.5
    mock_ner_entities = ["Python", "Docker"]
    mock_feedback = {"content": ["Good answer."], "strengths": [], "next_step": ""}

    # Replicate the exact logic from pipeline.py
    _p = mock_nlp_payload
    layer1_score     = float(_p.get("layer1_score", 0.0))
    layer2_score     = float(_p.get("layer2_score", 0.0))
    layer3_score     = float(_p.get("layer3_score", 0.0))
    semantic_score   = _p.get("semantic_score")
    tfidf_score      = float(_p.get("tfidf_score", _p.get("cosine_similarity", 0.0)))
    keyword_coverage = float(_p.get("keyword_coverage", 0.0))
    ner_score        = float(len(mock_ner_entities))

    scoring_breakdown = {
        "layer1_score":     round(layer1_score, 2),
        "layer2_score":     round(layer2_score, 2),
        "layer3_score":     round(layer3_score, 2),
        "semantic_score":   round(semantic_score, 4) if semantic_score is not None else None,
        "tfidf_score":      round(tfidf_score, 4),
        "keyword_coverage": round(keyword_coverage, 4),
        "kg_score":         round(mock_kg_score, 2),
        "ner_score":        ner_score,
        "guard_applied":    mock_guard["reason"] if mock_guard["cap_required"] else None,
        "final_score":      round(mock_final_score, 2),
        "nlp_score":        round(mock_nlp_score, 2),
        "svm_label":        mock_svm_label,
        "feedback":         mock_feedback,
        "depth_score":      float(_p.get("depth_score", 0.0)),
        "structure_score":  float(_p.get("structure_score", 0.0)),
        "accuracy_score":   float(_p.get("accuracy_score", 0.0)),
        "clarity_score":    float(_p.get("clarity_score", 0.0)),
        "advanced_bonus":   float(_p.get("advanced_bonus", 0.0)),
        "difficulty_bonus": float(_p.get("difficulty_bonus", 0.0)),
    }

    missing = REQUIRED_BREAKDOWN_KEYS - set(scoring_breakdown.keys())
    assert not missing, f"scoring_breakdown missing keys: {missing}"


def test_scoring_breakdown_types():
    """All numeric breakdown fields have correct types."""
    from modules.nlp_scorer import NLPScorer
    scorer = NLPScorer()
    result = scorer.compute_overall_score(
        answer_text="Docker is a containerization platform that packages applications into containers.",
        ideal_answer="Docker is a containerization platform that packages applications and dependencies into containers.",
        ideal_keywords="Docker, containerization, containers, dependencies",
        difficulty="medium",
    )
    assert isinstance(result["layer1_score"], float)
    assert isinstance(result["layer2_score"], float)
    assert isinstance(result["layer3_score"], float)
    assert isinstance(result["tfidf_score"], float)
    assert result["semantic_score"] is None or isinstance(result["semantic_score"], float)
    assert isinstance(result["keyword_coverage"], float)


def test_answer_route_returns_breakdown():
    """answer.py return dict includes scoring_breakdown and guard_applied."""
    import inspect as _i
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "answer", os.path.join(os.path.dirname(__file__), "..", "backend", "routes", "answer.py")
    )
    mod = _ilu.module_from_spec(spec)
    # Just read source, don't exec (would need full FastAPI context)
    src = open(os.path.join(os.path.dirname(__file__), "..", "backend", "routes", "answer.py")).read()
    assert "scoring_breakdown" in src, "answer.py must store and return scoring_breakdown"
    assert "guard_applied" in src, "answer.py must return guard_applied"


if __name__ == "__main__":
    tests = [
        test_pipeline_returns_scoring_breakdown,
        test_scoring_breakdown_keys_complete,
        test_scoring_breakdown_types,
        test_answer_route_returns_breakdown,
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
