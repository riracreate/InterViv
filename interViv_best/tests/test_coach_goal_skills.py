"""A goal with no skill list is read for skills. An empty list is not filled with DSA."""

from __future__ import annotations

import os

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from modules.roadmap_plans import ensure_plan  # noqa: E402


def test_goal_text_supplies_skills_when_the_skill_list_is_empty() -> None:
    plan = ensure_plan(
        "u-goal-skills",
        role_id=None,
        confirmed_goal="I want to practise SQL and React",
        planning_context_skills=[],
        days=14,
    )
    skills = {task["skill"] for task in plan["tasks"]}
    assert skills
    assert skills <= {"SQL", "React"}
    assert "DSA" not in skills
    assert plan["meta"].get("prompt") != "needs_goal_skills"
    assert "SQL" in plan["evidence_summary"]["planning_context_skills"]


def test_empty_goal_skills_return_a_prompt_instead_of_dsa() -> None:
    plan = ensure_plan(
        "u-no-skills",
        role_id=None,
        confirmed_goal="become more confident",
        planning_context_skills=[],
        days=14,
    )
    assert plan["tasks"] == []
    assert plan["meta"]["prompt"] == "needs_goal_skills"
    assert plan["meta"]["needs_goal_skills"] is True
    assert plan["meta"]["plan_kind"] == "needs_goal_skills"
    assert all(task["skill"] != "DSA" for task in plan["tasks"])


def test_role_requirements_still_drive_the_plan_when_present() -> None:
    plan = ensure_plan("u-role-still", role_id="amazon_sde_intern", days=14)
    skills = {task["skill"] for task in plan["tasks"]}
    assert len(skills) > 1
    assert plan["meta"].get("prompt") != "needs_goal_skills"
