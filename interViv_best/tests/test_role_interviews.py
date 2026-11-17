"""Role blueprints and the deterministic planner. No live model calls."""
from __future__ import annotations

import json

import pytest

from modules import interview_llm as routing
from modules.role_blueprints import (
    MAPPING_DECISIONS, blueprint_summary, clear_draft_cache, draft_unknown_blueprint,
    load_blueprints, question_speech_issues, taxonomy_skill, validate_blueprint,
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
        assert doc["level_expectations"]["mid"]
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
    assert "SQL" not in by_id["data-analyst"]["skills_without_bundles"]
    assert by_id["data-analyst"]["long_seeds"]
    assert by_id["devops-cloud-engineer"]["provenance"]["onet"]["status"] == "needs_owner_decision"
    assert "Computer Systems Engineers" in MAPPING_DECISIONS["devops-cloud-engineer"]


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
        assert "easy warm-up" in slots[0].reason
    if doc["family"] in {"business", "product", "design"}:
        assert all(slot.practice_only for slot in slots if slot.kind == "scenario")
    else:
        assert all(not slot.practice_only for slot in slots)
    _show(f"{role} {length} resume={with_resume}", slots)


def test_mid_level_uses_the_harder_band():
    doc = _docs()["backend-engineer"]
    slots = plan_role(doc, level="mid", length="quick")
    assert {slot.difficulty for slot in slots if slot.kind == "core"} == {"hard"}


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
