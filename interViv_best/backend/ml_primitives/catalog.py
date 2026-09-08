"""Public pack metadata only. Never import Python from a problem pack here."""

import json
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[2] / "ml_primitives"
PUBLIC_FIELDS = (
    "id", "version", "title", "difficulty", "topics", "constraints",
    "function", "starter_code",
)
UNAVAILABLE_MESSAGE = (
    "Scoring is unavailable. Your submission was stored without being run or "
    "graded. No score was recorded; the round remains open for retry."
)


def list_problems():
    items = []
    for path in sorted(PACK_ROOT.glob("*/v*/manifest.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        expected_id = f"{path.parent.parent.name}.{path.parent.name}"
        if metadata["id"] != expected_id:
            raise ValueError(f"Pack identity does not match directory: {expected_id}")
        item = {key: metadata[key] for key in PUBLIC_FIELDS}
        item.update(
            statement=(path.parent / "statement.md").read_text(encoding="utf-8"),
            category="ml_primitives", type="ml_primitives", language="python",
            scoring_available=False,
        )
        items.append(item)
    return items


def select_problems(*, problem_ids=None, topics=None, difficulty=None, count=1):
    pool = list_problems()
    by_id = {p["id"]: p for p in pool}
    if problem_ids:
        unknown = [pid for pid in problem_ids if pid not in by_id]
        if unknown:
            raise ValueError(f"Unknown ML primitive problem IDs: {unknown}.")
        pool = [by_id[pid] for pid in problem_ids]
    wanted_topics = {t.strip().lower() for t in (topics or [])}
    wanted_topics -= {"ml primitives", "ml_primitives"}
    selected = [p for p in pool if (
        (not difficulty or p["difficulty"] == difficulty)
        and (not wanted_topics or wanted_topics & {t.lower() for t in p["topics"]})
    )]
    if problem_ids and len(selected) != len(problem_ids):
        raise ValueError("ML primitive problems do not match the requested topics/difficulty.")
    if len(selected) < count:
        raise ValueError(
            f"Not enough ML primitive problems available: found {len(selected)}, "
            f"need {count}. Adjust count, topics or difficulty."
        )
    return selected if problem_ids else selected[:count]


def public_problem(problem_id):
    return select_problems(problem_ids=[problem_id])[0]
