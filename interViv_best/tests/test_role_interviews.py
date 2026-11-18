"""Role blueprints and the deterministic planner. No live model calls."""
from __future__ import annotations

import json

import pytest

from modules import interview_llm as routing
from modules.role_blueprints import (
    blueprint_summary, clear_draft_cache, draft_unknown_blueprint,
    load_blueprints, question_speech_issues, register_unresolved_skills, taxonomy_skill,
    validate_blueprint,
)
from modules.role_planner import plan_role
from tests.test_ai_interview_routing import catalog


def _docs():
    return {doc["id"]: doc for doc in load_blueprints()}


def test_twelve_starter_blueprints_are_drafts_with_unit_weights():
    docs = load_blueprints()
    assert [doc["id"] for doc in docs] == sorted(doc["id"] for doc in docs)
    assert len(docs) == 12
    for doc in docs:
        assert doc["status"] == "draft"
        assert abs(sum(float(item["weight"]) for item in doc["competencies"]) - 1) <= 0.001
        assert doc["level_expectations"]["intern"]
        assert doc["level_expectations"]["intern"] == doc["level_expectations"]["junior"]
        assert doc["level_expectation_review"]["junior"] == "needs owner edit"
        report = validate_blueprint(doc)
        assert isinstance(report["unresolved_skills"], list)


def test_taxonomy_resolution_reports_unknown_skills_and_keeps_known_ones():
    assert taxonomy_skill("REST APIs") == "REST"
    assert taxonomy_skill("Python") == "Python"
    assert taxonomy_skill("Product Metrics") is None
    summary = blueprint_summary(load_blueprints(), bundle_skills={"Python", "SQL", "Docker", "AWS", "Agile"})
    by_id = {row["id"]: row for row in summary}
    assert "Python" in by_id["backend-engineer"]["resolved_skills"]
    assert "Product Metrics" in by_id["associate-product-manager"]["unresolved_skills"]
    assert by_id["associate-product-manager"]["provenance"]["onet"]["status"] == "none"
    assert "15-1299.08" in by_id["devops-cloud-engineer"]["provenance"]["onet"]["url"]


def test_long_questions_are_flagged_and_existing_text_is_not_rejected():
    long = "This spoken question keeps going. " * 8
    assert question_speech_issues(long)
    assert question_speech_issues("What is a join?") == []
    doc = _docs()["backend-engineer"]
    validate_blueprint(doc)


def _resume(skills, project="shop"):
    return {"projects": [project], "skills": skills}


def _show(title, slots):
    print(f"\n{title}")
    for slot in slots:
        print(f"  {slot.kind:12} {slot.difficulty:6} {slot.reason}")


@pytest.mark.parametrize("role", ["backend-engineer", "data-analyst", "associate-product-manager"])
@pytest.mark.parametrize("length", ["quick", "full"])
@pytest.mark.parametrize("with_resume", [False, True])
def test_plans_for_three_roles(role, length, with_resume, capsys):
    doc = _docs()[role]
    resume = None
    if with_resume and role == "backend-engineer":
        resume = _resume({"Python": "claimed_with_evidence", "Operating Systems": "missing"}, "shop-api")
    elif with_resume and role == "data-analyst":
        resume = _resume({"SQL": "claimed_with_evidence", "Statistics": "missing"}, "churn study")
    elif with_resume and role == "associate-product-manager":
        resume = _resume({"Agile": "claimed_with_evidence", "Product Metrics": "missing"}, "campus app")
    slots = plan_role(doc, level="junior", length=length, resume=resume)
    again = plan_role(doc, level="junior", length=length, resume=resume)
    assert [slot.as_dict() for slot in slots] == [slot.as_dict() for slot in again]
    assert slots[0].kind == "opener"
    kinds = [slot.kind for slot in slots]
    if length == "quick":
        assert len(slots) == 3
        if doc["family"] in {"business", "product", "design"}:
            assert kinds.count("scenario") == 1
        else:
            assert "scenario" not in kinds
    else:
        assert kinds.count("core") == min(3, sum(item["type"] == "technical" for item in doc["competencies"]))
        assert "scenario" in kinds
        assert "behavioural" in kinds
        if doc["practical_track"] == "none":
            assert "practical" not in kinds
        else:
            assert kinds[-1] == "practical"
    if with_resume:
        assert "resume opener" in slots[0].reason
        cores = [slot for slot in slots if slot.kind == "core"]
        if len(cores) >= 2:
            assert any("one level harder" in slot.reason for slot in cores)
            assert any("fundamentals" in slot.reason for slot in cores)
        else:
            assert any("one level harder" in slot.reason or "fundamentals" in slot.reason for slot in cores)
    else:
        if role == "backend-engineer":
            assert slots[0].reason == "Python: easy bank warm-up"
            assert slots[0].scored is True
        else:
            assert slots[0].scored is False
            assert slots[0].reason.startswith("Tell me a little about yourself")
    if doc["family"] in {"business", "product", "design"}:
        assert all(slot.practice_only for slot in slots if slot.kind == "scenario")
    else:
        assert all(not slot.practice_only for slot in slots)
    _show(f"{role} {length} resume={with_resume}", slots)


def test_unresolved_skills_register_through_the_audit_path(monkeypatch, tmp_path):
    monkeypatch.setenv("NEW_CANONICAL_SKILLS_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    from modules import role_skills
    role_skills.reset_role_skill_cache()
    registered = register_unresolved_skills(load_blueprints())
    assert "Statistics" in registered
    assert "Data Visualisation" in registered
    assert "Product Metrics" in registered
    assert "Prioritisation" in registered
    audit = (tmp_path / "audit.jsonl").read_text()
    assert "Statistics" in audit
    role_skills.reset_role_skill_cache()


def test_scripted_opener_when_no_easy_bank_question():
    docs = _docs()
    for role, title in (
        ("associate-product-manager", "Associate Product Manager"),
        ("ui-ux-designer", "UI/UX Designer"),
    ):
        slots = plan_role(docs[role], level="junior", length="quick")
        assert slots[0].reason == f"Tell me a little about yourself and what draws you to the {title} role."
        assert slots[0].scored is False
        assert "What is" not in slots[0].reason


def test_mid_level_uses_the_harder_band():
    doc = _docs()["backend-engineer"]
    slots = plan_role(doc, level="mid", length="quick")
    assert {slot.difficulty for slot in slots if slot.kind == "core"} == {"hard"}


def test_role_practice_is_off_until_the_flag_is_set(monkeypatch):
    monkeypatch.delenv("ROLE_PRACTICE_ENABLED", raising=False)
    from fastapi import HTTPException
    from backend.routes.role_practice import PlanRequest, catalog, plan
    with pytest.raises(HTTPException) as off:
        catalog()
    assert off.value.status_code == 404
    monkeypatch.setenv("ROLE_PRACTICE_ENABLED", "1")
    assert any(role["id"] == "data-analyst" for role in catalog()["roles"])
    without = plan(PlanRequest(role_id="data-analyst", level="junior", length="quick"))
    assert without["estimated_minutes"] == 15
    assert without["slots"][0]["scored"] is False
    with_resume = plan(PlanRequest(
        role_id="data-analyst", level="junior", length="quick",
        resume={"projects": ["churn study"], "skills": {"SQL": "claimed_with_evidence", "Statistics": "missing"}},
    ))
    assert with_resume["slots"][0]["reason"] == "churn study: resume opener"
    assert with_resume["estimated_minutes"] == 15
    full = plan(PlanRequest(role_id="data-analyst", level="junior", length="full"))
    assert full["estimated_minutes"] == 48


def test_unknown_role_draft_uses_override_and_caches(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_INTERVIEW_ROUTING_ENABLED", "1")
    monkeypatch.setenv("DATABASE_URL", "")
    from backend.config import get_settings
    get_settings.cache_clear()
    router = routing.InterviewRouter(
        routing.RoutingSettings(state_path=tmp_path / "limits.json", content_models=("fixture/alpha:free",)),
        catalog_source=catalog,
    )
    calls = []
    payload = {"id": "site-reliability", "title": "Site Reliability", "family": "engineering", "status": "reviewed"}

    def override(model):
        calls.append(model)
        return json.dumps(payload), (1, 1, 2)

    clear_draft_cache()
    first = draft_unknown_blueprint("Site Reliability", router=router, override=override)
    second = draft_unknown_blueprint("site   reliability", router=router, override=override)
    assert calls == ["fixture/alpha:free"]
    assert first["status"] == "draft"
    assert second == first
    clear_draft_cache()
    get_settings.cache_clear()


def test_data_scientist_rename_and_legacy_alias(monkeypatch):
    docs = _docs()
    assert "data-scientist" in docs
    assert "data-scientist-ml" not in docs
    ds = docs["data-scientist"]
    assert ds["title"] == "Data Scientist"
    assert "data-scientist-ml" in ds["aliases"]
    tech_skills = [skill for item in ds["competencies"] if item["type"] == "technical" for skill in item["skills"]]
    assert tech_skills == ["Statistics", "Machine Learning", "Python", "SQL"]

    from modules.role_blueprints import get_blueprint, resolve_blueprint_id
    assert resolve_blueprint_id("data-scientist-ml") == "data-scientist"
    assert get_blueprint("data-scientist-ml")["id"] == "data-scientist"

    monkeypatch.setenv("ROLE_PRACTICE_ENABLED", "1")
    from backend.routes.role_practice import PlanRequest, plan
    planned = plan(PlanRequest(role_id="data-scientist-ml", level="junior", length="quick"))
    assert planned["role_id"] == "data-scientist"
    assert planned["title"] == "Data Scientist"


def test_bundle_generator_prompt_enforces_reference_numbers_and_primary_sources():
    from modules.bundle_generator import _build_prompt_b_messages, _build_regeneration_messages

    prompt_b = "\n".join(m["content"] for m in _build_prompt_b_messages(
        skill="RAG & Vector Databases", topic="Hybrid search", difficulty="medium",
    ))
    regen = "\n".join(m["content"] for m in _build_regeneration_messages(
        skill="RAG & Vector Databases",
        topic="Hybrid search",
        difficulty="medium",
        previous_content={},
        blind_answer="answer",
        eval_res={},
        audit_diagnosis={},
    ))
    for text in (prompt_b, regen):
        assert "never in required_concepts" in text
        assert "cite primary sources" in text
        assert "not blogs" in text


def test_every_scripted_or_resume_opener_slot_is_unscored():
    for doc in load_blueprints():
        for length in ("quick", "full"):
            with_resume = plan_role(
                doc, level="junior", length=length,
                resume={"projects": ["capstone"], "skills": {}},
            )
            assert with_resume[0].kind == "opener"
            assert with_resume[0].name == "Resume opener"
            assert with_resume[0].scored is False

            without_resume = plan_role(doc, level="junior", length=length)
            assert without_resume[0].kind == "opener"
            if without_resume[0].name == "Role opener":
                assert without_resume[0].scored is False
