"""Phase C bank properties: shape, reference solutions, mutant solutions.

This check executes the repository's own checked-in reference and mutant
solutions (trusted fixture code, in-process, in the test only) to prove:
every reference passes all 8 tests, and every mutant passes all visible
tests while failing at least one hidden test. It is bank validation only
and is never a candidate-execution path.
"""

from __future__ import annotations

from collections import Counter

from backend.db.phase_c_coding_bank import CODING_PROBLEMS


def _run(source: str, function: str, args: list, kwargs: dict):
    namespace: dict = {}
    exec(source, namespace)  # noqa: S102 - trusted checked-in fixture
    return namespace[function](*args, **kwargs)


def _outcomes(problem, source):
    results = []
    for group in ("visible_tests", "hidden_tests"):
        for case in problem[group]:
            payload = case.get("input") or {}
            try:
                actual = _run(source, problem["function"],
                              list(payload.get("args", [])),
                              dict(payload.get("kwargs", {})))
            except Exception as exc:  # noqa: BLE001 - a crash fails the case
                results.append((group, False, f"{type(exc).__name__}: {exc}"))
                continue
            results.append((group, actual == case.get("expected"), actual))
    return results


def test_bank_shape_and_counts() -> None:
    assert len(CODING_PROBLEMS) == 15
    ids = [p["id"] for p in CODING_PROBLEMS]
    assert len(set(ids)) == 15
    assert Counter(p["difficulty"] for p in CODING_PROBLEMS) == {
        "easy": 6, "medium": 6, "hard": 3}
    required = {"id", "title", "difficulty", "topics", "statement",
                "constraints", "function", "starter_code", "visible_tests",
                "hidden_tests", "reference_solution", "mutant_solution"}
    for problem in CODING_PROBLEMS:
        assert required <= set(problem), problem["id"]
        assert len(problem["visible_tests"]) == 3, problem["id"]
        assert len(problem["hidden_tests"]) == 5, problem["id"]
        assert problem["topics"], problem["id"]
        compile(problem["starter_code"], problem["id"], "exec")
        compile(problem["reference_solution"], problem["id"], "exec")
        compile(problem["mutant_solution"], problem["id"], "exec")


def test_reference_passes_every_test() -> None:
    failures = []
    for problem in CODING_PROBLEMS:
        for group, passed, detail in _outcomes(
                problem, problem["reference_solution"]):
            if not passed:
                failures.append(f"{problem['id']} {group}: {detail!r}")
    assert failures == []


def test_mutant_passes_visible_and_fails_hidden() -> None:
    failures = []
    for problem in CODING_PROBLEMS:
        outcomes = _outcomes(problem, problem["mutant_solution"])
        visible = [o for o in outcomes if o[0] == "visible_tests"]
        hidden = [o for o in outcomes if o[0] == "hidden_tests"]
        if not all(passed for _, passed, _ in visible):
            failures.append(f"{problem['id']}: mutant must pass visible: "
                            f"{[(p, d) for _, p, d in visible]}")
        if all(passed for _, passed, _ in hidden):
            failures.append(f"{problem['id']}: mutant must fail a hidden test")
    assert failures == []
