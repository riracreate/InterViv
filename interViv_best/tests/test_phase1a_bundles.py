"""Phase 1A: immutable question bundles, import idempotency, review workflow,
evaluation overlap, inventory, selector, and admin authorization.

Review records created here are synthetic test evidence in a disposable store.
They are not human reviews.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend import config as app_config
from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.sqlalchemy_store import _sessionmaker, get_engine, get_sqlalchemy_database
from backend.routes.admin import router as admin_router
from modules import bundle_selector, bundle_store
from modules.bundle_store import REQUIRED_CHECKLIST, BundleStoreError
from modules.evaluation_overlap import check_overlap, load_evaluation_items
from modules.question_bundles import candidate_payload, content_hash, validate_bundle_doc
from tests.alembic_helpers import parent_revision
from tests.test_phaseE_system_design import _run_alembic

PHASE1A_REVISION = "20260913_0010"
CHECK_OK = {k: True for k in REQUIRED_CHECKLIST}
CALIB = {"difficulty": "easy"}
REASON = "Reference answer is correct and the wording is unambiguous for this level."


def _clear_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


def make_doc(bundle_id="python.test-lock-release", version=1, **over):
    doc = {
        "bundle_id": bundle_id, "version": version, "skill": "Python", "topic": "Locks",
        "difficulty": "easy",
        "question": "Which Python construct releases a threading lock automatically when a block exits?",
        "reference_answer": "The with statement: a Lock is a context manager whose __exit__ releases it.",
        "required_concepts": ["with statement", "context manager", "release on exit"],
        "source": "human_authored", "author": "author-user",
        "attribution": {"note": "test fixture"},
    }
    doc.update(over)
    return doc


@pytest.fixture
def memory_store(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    _clear_caches()
    bundle_store.reset_memory_store()
    yield
    bundle_store.reset_memory_store()
    _clear_caches()


@pytest.fixture
def sql_store(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'phase1a.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_caches()
    _run_alembic(url, "upgrade", "head")
    assert bundle_store._using_sqlalchemy()
    yield url
    get_engine().dispose()
    _clear_caches()


@pytest.fixture(params=["memory", "sql"])
def any_store(request):
    return request.getfixturevalue(f"{request.param}_store")


def _decide(bundle_id, version, reviewer, decision="approve", **over):
    v = bundle_store.get_version(bundle_id, version)
    kwargs = dict(reviewer_id=reviewer, content_hash=v["content_hash"], decision=decision,
                  checklist=CHECK_OK, reasons=REASON, calibration=CALIB)
    kwargs.update(over)
    return bundle_store.record_decision(bundle_id, version, **kwargs)


def _review_to_reviewed(bundle_id, version=1):
    bundle_store.submit_for_review(bundle_id, version, actor_id="admin-1")
    _decide(bundle_id, version, "reviewer-a")
    return _decide(bundle_id, version, "reviewer-b")["version"]


# ─── content / hash ─────────────────────────────────────────────────────────

def test_hash_ignores_provenance_and_whitespace_but_not_content():
    a = validate_bundle_doc(make_doc())
    b = validate_bundle_doc(make_doc(author="someone-else", attribution={"note": "other"},
                                     question="Which  Python construct releases a threading lock\nautomatically when a block exits?"))
    c = validate_bundle_doc(make_doc(reference_answer="Different reference."))
    assert a["content_hash"] == b["content_hash"] == content_hash(a["content"])
    assert a["content_hash"] != c["content_hash"]


def test_canonical_yaml_rejects_review_state_and_bad_fields():
    with pytest.raises(ValueError, match="review state"):
        validate_bundle_doc(make_doc(status="reviewed"))
    with pytest.raises(ValueError, match="difficulty"):
        validate_bundle_doc(make_doc(difficulty="extreme"))
    with pytest.raises(ValueError, match="author"):
        validate_bundle_doc(make_doc(author=""))
    with pytest.raises(ValueError, match="source_file"):
        validate_bundle_doc(make_doc(source="imported_csv", attribution={}))
    with pytest.raises(ValueError, match="version"):
        validate_bundle_doc(make_doc(version=0))


# ─── import idempotency / conflicts / immutability ─────────────────────────

def test_import_idempotent_and_conflicts(any_store):
    first = bundle_store.import_bundle(make_doc(), actor_id="cli")
    assert first["result"] == "created" and first["version"]["status"] == "draft"
    again = bundle_store.import_bundle(make_doc(), actor_id="cli")
    assert again["result"] == "unchanged"
    assert again["version"]["content_hash"] == first["version"]["content_hash"]
    assert len(bundle_store.list_versions("python.test-lock-release")) == 1

    with pytest.raises(BundleStoreError, match="immutable") as exc:
        bundle_store.import_bundle(make_doc(reference_answer="Edited in place."), actor_id="cli")
    assert exc.value.code == "conflict"
    with pytest.raises(BundleStoreError, match="identical content already exists"):
        bundle_store.import_bundle(make_doc(version=2), actor_id="cli")
    with pytest.raises(BundleStoreError, match="expected version 2"):
        bundle_store.import_bundle(make_doc(version=5, reference_answer="Gap."), actor_id="cli")
    with pytest.raises(BundleStoreError, match="identity is stable"):
        bundle_store.import_bundle(make_doc(version=2, topic="Other", reference_answer="New."), actor_id="cli")

    second = bundle_store.import_bundle(make_doc(version=2, reference_answer="New reference."), actor_id="cli")
    assert second["result"] == "created" and second["version"]["version"] == 2
    assert bundle_store.get_version("python.test-lock-release", 1)["content_hash"] == first["version"]["content_hash"]


def test_reviewed_version_is_immutable_and_edits_become_new_draft(any_store):
    bundle_store.import_bundle(make_doc(), actor_id="cli")
    reviewed = _review_to_reviewed("python.test-lock-release")
    assert reviewed["status"] == "reviewed"
    decisions_before = bundle_store.review_history("python.test-lock-release", 1)["decisions"]
    assert len(decisions_before) == 2

    with pytest.raises(BundleStoreError, match="immutable"):
        bundle_store.import_bundle(make_doc(reference_answer="Silent rewrite."), actor_id="cli")
    # Re-seeding the unchanged canonical file is a no-op and does not undo the review.
    assert bundle_store.import_bundle(make_doc(), actor_id="cli")["result"] == "unchanged"
    v1 = bundle_store.get_version("python.test-lock-release", 1)
    assert v1["status"] == "reviewed" and v1["content_hash"] == reviewed["content_hash"]
    assert bundle_store.review_history("python.test-lock-release", 1)["decisions"] == decisions_before

    v2 = bundle_store.import_bundle(make_doc(version=2, reference_answer="Better reference."), actor_id="cli")
    assert v2["version"]["status"] == "draft"
    assert bundle_store.get_version("python.test-lock-release", 1)["status"] == "reviewed"
    assert not hasattr(bundle_store, "update_content")


def test_sql_unique_constraints_reject_duplicate_version_and_hash(sql_store):
    from sqlalchemy.exc import IntegrityError
    from backend.db.sqlalchemy_models import QuestionBundleVersionRow
    from backend.db.sqlalchemy_store import session_scope

    created = bundle_store.import_bundle(make_doc(), actor_id="cli")["version"]
    for override in ({"id": "x@1"}, {"id": "x@2", "version": 2}):
        row = {**created, **override}
        with pytest.raises(IntegrityError), session_scope() as s:
            s.add(QuestionBundleVersionRow(**row))
    with pytest.raises(IntegrityError), session_scope() as s:
        s.add(QuestionBundleVersionRow(**{**created, "id": "x@3", "version": 3,
                                          "content_hash": "0" * 64, "status": "approved"}))


def test_migration_downgrade_drops_only_bundle_tables(sql_store):
    from sqlalchemy import inspect
    tables = set(inspect(get_engine()).get_table_names())
    assert {"question_bundles", "question_bundle_versions", "bundle_review_decisions", "bundle_status_audit"} <= tables
    get_engine().dispose()
    _run_alembic(sql_store, "downgrade", parent_revision(PHASE1A_REVISION))
    after = set(inspect(get_engine()).get_table_names())
    assert not {t for t in after if "bundle" in t}
    assert "ml_primitives_attempts" in after and "rounds" in after


# ─── review workflow ───────────────────────────────────────────────────────

def test_review_rules_reject_bad_evidence(memory_store):
    bundle_store.import_bundle(make_doc(), actor_id="cli")
    with pytest.raises(BundleStoreError, match="only recorded while in_review"):
        _decide("python.test-lock-release", 1, "reviewer-a")
    bundle_store.submit_for_review("python.test-lock-release", 1, actor_id="admin-1")

    with pytest.raises(BundleStoreError, match="author cannot review") as exc:
        _decide("python.test-lock-release", 1, "author-user")
    assert exc.value.code == "forbidden"
    with pytest.raises(BundleStoreError, match="stale content_hash"):
        _decide("python.test-lock-release", 1, "reviewer-a", content_hash="f" * 64)
    with pytest.raises(BundleStoreError, match="checklist incomplete"):
        _decide("python.test-lock-release", 1, "reviewer-a", checklist={"question_clear": True})
    with pytest.raises(BundleStoreError, match="failing checklist"):
        _decide("python.test-lock-release", 1, "reviewer-a", checklist={**CHECK_OK, "reference_correct": False})
    for bad in ("", "lgtm", "TODO", "ok.", "approved"):
        with pytest.raises(BundleStoreError, match="substantive"):
            _decide("python.test-lock-release", 1, "reviewer-a", reasons=bad)
    with pytest.raises(BundleStoreError, match="calibration.difficulty"):
        _decide("python.test-lock-release", 1, "reviewer-a", calibration={})
    with pytest.raises(BundleStoreError, match="adjudication is only allowed"):
        _decide("python.test-lock-release", 1, "reviewer-a", decision="adjudicate_approve")
    with pytest.raises(BundleStoreError, match="reviewer identity"):
        _decide("python.test-lock-release", 1, "")

    _decide("python.test-lock-release", 1, "reviewer-a")
    with pytest.raises(BundleStoreError, match="already decided"):
        _decide("python.test-lock-release", 1, "reviewer-a")
    assert bundle_store.get_version("python.test-lock-release", 1)["status"] == "in_review"


def test_approval_needs_required_concepts(memory_store):
    bundle_store.import_bundle(make_doc(required_concepts=[]), actor_id="cli")
    bundle_store.submit_for_review("python.test-lock-release", 1, actor_id="admin-1")
    with pytest.raises(BundleStoreError, match="no required_concepts"):
        _decide("python.test-lock-release", 1, "reviewer-a")
    # A reject with the same evidence is fine: the checklist can say what is wrong.
    _decide("python.test-lock-release", 1, "reviewer-a", decision="reject",
            checklist={**CHECK_OK, "required_concepts_right": False})


def test_two_distinct_approvals_then_audit_and_retire(any_store):
    bundle_store.import_bundle(make_doc(), actor_id="cli")
    v = _review_to_reviewed("python.test-lock-release")
    assert v["status"] == "reviewed"
    history = bundle_store.review_history("python.test-lock-release", 1)
    assert [a["to_status"] for a in history["audit"]] == ["draft", "in_review", "reviewed"]
    assert history["audit"][0]["from_status"] is None
    assert all(a["content_hash"] == v["content_hash"] for a in history["audit"])
    assert {d["reviewer_id"] for d in history["decisions"]} == {"reviewer-a", "reviewer-b"}
    assert all(d["content_hash"] == v["content_hash"] for d in history["decisions"])

    with pytest.raises(BundleStoreError, match="only recorded while in_review"):
        _decide("python.test-lock-release", 1, "reviewer-c")
    with pytest.raises(BundleStoreError, match="substantive"):
        bundle_store.retire("python.test-lock-release", 1, actor_id="admin-1", reason="old")
    retired = bundle_store.retire("python.test-lock-release", 1, actor_id="admin-1",
                                  reason="Superseded by version 2 after reference correction.")
    assert retired["status"] == "retired"
    assert bundle_store.review_history("python.test-lock-release", 1)["audit"][-1]["to_status"] == "retired"


def test_split_decision_requires_adjudication_by_third_identity(memory_store):
    bundle_store.import_bundle(make_doc(), actor_id="cli")
    bundle_store.submit_for_review("python.test-lock-release", 1, actor_id="admin-1")
    _decide("python.test-lock-release", 1, "reviewer-a")
    out = _decide("python.test-lock-release", 1, "reviewer-b", decision="reject",
                  checklist={**CHECK_OK, "no_ambiguity": False})
    assert out["version"]["status"] == "in_review"
    assert bundle_store.review_history("python.test-lock-release", 1)["needs_adjudication"] is True
    with pytest.raises(BundleStoreError, match="already decided"):
        _decide("python.test-lock-release", 1, "reviewer-a", decision="adjudicate_approve")
    final = _decide("python.test-lock-release", 1, "adjudicator", decision="adjudicate_reject",
                    checklist={**CHECK_OK, "no_ambiguity": False})
    assert final["version"]["status"] == "rejected"
    two_rejects = make_doc(bundle_id="python.test-two-rejects", question="Name the Python keyword that defines an asynchronous coroutine function.")
    bundle_store.import_bundle(two_rejects, actor_id="cli")
    bundle_store.submit_for_review("python.test-two-rejects", 1, actor_id="admin-1")
    _decide("python.test-two-rejects", 1, "reviewer-a", decision="reject")
    assert _decide("python.test-two-rejects", 1, "reviewer-b", decision="reject")["version"]["status"] == "rejected"


# ─── evaluation overlap ─────────────────────────────────────────────────────

def test_evaluation_overlap_rejects_exact_and_flags_paraphrase(tmp_path, memory_store):
    items = load_evaluation_items()
    assert len(items) >= 100
    baseline_q = next(i for i in items if i["source"] == "baseline_v2_key")["question"]
    exact = check_overlap("  " + baseline_q.upper() + " ")
    assert exact["exact"] and exact["exact"][0]["question"] == baseline_q
    para = check_overlap("Explain Python's MRO (Method Resolution Order).")
    assert not para["exact"] and para["paraphrase"]
    clean = check_overlap(make_doc()["question"])
    assert clean == {"exact": [], "paraphrase": []}

    from scripts.import_question_bundles import import_directory
    root = tmp_path / "bundles"
    (root / "python").mkdir(parents=True)
    (root / "python" / "ok.yaml").write_text(yaml.safe_dump(make_doc()), encoding="utf-8")
    (root / "python" / "eval.yaml").write_text(
        yaml.safe_dump(make_doc(bundle_id="python.eval-copy", question=baseline_q)), encoding="utf-8")
    (root / "python" / "para.yaml").write_text(
        yaml.safe_dump(make_doc(bundle_id="python.mro", question="Explain Python's MRO (Method Resolution Order).")),
        encoding="utf-8")
    report = import_directory(root, actor_id="cli")
    assert {c[0].split("[")[1] for c in report["created"]} == {"python.mro v1]", "python.test-lock-release v1]"}
    assert len(report["failed"]) == 1 and "evaluation overlap (exact)" in report["failed"][0][1]
    assert len(report["flagged"]) == 1
    assert bundle_store.get_version("python.mro", 1)["attribution_json"]["evaluation_overlap"]["paraphrase"]
    assert not bundle_store.list_versions("python.eval-copy")


def test_repo_pilot_yaml_imports_as_drafts_with_no_overlap(memory_store):
    from scripts.import_question_bundles import import_directory
    from modules.question_bundles import iter_bundle_files, validate_bundle_doc

    root = Path(__file__).resolve().parents[1] / "data" / "question_bundles"
    report = import_directory(root, actor_id="cli")
    assert report["failed"] == [] and report["flagged"] == []
    # 12 bundles × 2 versions (v1 CSV import + v2 concept authorship drafts)
    assert len(report["created"]) == 24
    inv = bundle_store.inventory()
    assert inv["reviewed_total"] == 0 and inv["status_totals"]["draft"] == 24
    # Two bundles per skill×difficulty at each version → 4 draft versions per cell.
    per = {(s, d): sum(1 for topic in inv["unreviewed"][s].values() for dd, n in topic.items() if dd == d for _ in range(n))
           for s in ("Python", "DBMS") for d in ("easy", "medium", "hard")}
    assert all(n == 4 for n in per.values()), per
    ids = sorted({validate_bundle_doc(d)["content"]["bundle_id"] for _, d in iter_bundle_files()})
    assert len(ids) == 12
    for bid in ids:
        vs = bundle_store.list_versions(bid)
        assert {v["version"] for v in vs} == {1, 2}
        v1 = next(v for v in vs if v["version"] == 1)
        v2 = next(v for v in vs if v["version"] == 2)
        assert v1["status"] == v2["status"] == "draft"
        assert v1["source"] == "imported_csv" and v1["author_id"].startswith("dataset:")
        assert v2["source"] == "human_authored"
        assert not v1["content_json"]["required_concepts"]
        assert v2["content_json"]["required_concepts"]
    assert import_directory(root, actor_id="cli")["unchanged"].__len__() == 24


# ─── inventory + selector ──────────────────────────────────────────────────

def test_inventory_counts_and_selector_reject_unreviewed(memory_store):
    bundle_store.import_bundle(make_doc(), actor_id="cli")
    other = make_doc(bundle_id="python.test-async-def", topic="Async",
                     question="Name the Python keyword that defines an asynchronous coroutine function.")
    bundle_store.import_bundle(other, actor_id="cli")
    with pytest.raises(bundle_selector.ReviewedInventoryUnavailable, match="No reviewed"):
        bundle_selector.select_reviewed_question(skill="Python", difficulty="easy")
    inv = bundle_store.inventory()
    assert inv["reviewed"] == {} and inv["unreviewed"]["Python"] == {"Locks": {"easy": 1}, "Async": {"easy": 1}}

    _review_to_reviewed("python.test-lock-release")
    inv = bundle_store.inventory()
    assert inv["reviewed"] == {"Python": {"Locks": {"easy": 1}}} and inv["reviewed_total"] == 1
    assert inv["unreviewed"] == {"Python": {"Async": {"easy": 1}}}

    picked = bundle_selector.select_reviewed_question(skill="python", difficulty="EASY")
    assert picked["bundle_id"] == "python.test-lock-release" and picked["source"] == "reviewed_bundle"
    with pytest.raises(bundle_selector.ReviewedInventoryUnavailable):
        bundle_selector.select_reviewed_question(skill="Python", difficulty="easy", asked=[picked["question"]])
    with pytest.raises(bundle_selector.ReviewedInventoryUnavailable):
        bundle_selector.select_reviewed_question(skill="Python", difficulty="hard")
    bundle_store.retire("python.test-lock-release", 1, actor_id="admin-1", reason="Retired for the selector test.")
    with pytest.raises(bundle_selector.ReviewedInventoryUnavailable):
        bundle_selector.select_reviewed_question(skill="Python", difficulty="easy")
    assert bundle_selector.reviewed_bundles_only() is False


def test_candidate_payload_excludes_reference_material(memory_store):
    doc = make_doc(keywords=["with"], misconceptions=["lock releases itself"], rubric_descriptors={"depth": "x"},
                   acceptable_variants=["the with block"], depth_markers=["mentions __exit__"],
                   calibration_examples=[{"answer": "with", "author_level": 1}])
    v = bundle_store.import_bundle(doc, actor_id="cli")["version"]
    payload = candidate_payload(v)
    assert set(payload) == {"bundle_id", "version", "content_hash", "category", "skill", "topic",
                            "difficulty", "question", "source"}
    text = str(payload).lower()
    for secret in ("reference", "__exit__", "misconception", "rubric", "author_level", "keyword", "with block"):
        assert secret not in text, secret


# ─── admin routes ──────────────────────────────────────────────────────────

def _user(email):
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id, "email": email, "name": email, "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc), "last_active_at": datetime.now(timezone.utc),
    })
    return user_id, {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.fixture
def admin_client(memory_store, monkeypatch):
    tag = uuid4().hex[:6]
    emails = [f"admin{i}-{tag}@example.com" for i in range(4)]
    monkeypatch.setenv("ADMIN_USER_EMAILS", ",".join(e.upper() for e in emails))
    _clear_caches()
    app = FastAPI()
    app.include_router(admin_router)
    users = [_user(e) for e in emails]
    _, student = _user(f"student-{tag}@example.com")
    return TestClient(app), users, student


def test_admin_routes_authorization_and_review_flow(admin_client):
    client, users, student = admin_client
    (author_id, author), (_, rev_a), (_, rev_b), (_, rev_c) = users
    bundle_store.import_bundle(make_doc(author=author_id), actor_id="cli")

    assert client.get("/admin/bundles").status_code == 401
    assert client.get("/admin/bundles", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/admin/bundles", headers=student).status_code == 403
    assert client.get("/admin/bundles/inventory", headers=student).status_code == 403
    assert client.post("/admin/bundles/python.test-lock-release/versions/1/submit", headers=student).status_code == 403

    listed = client.get("/admin/bundles", headers=rev_a).json()["bundles"]
    assert [b["bundle_id"] for b in listed] == ["python.test-lock-release"]
    assert listed[0]["versions"][0]["status"] == "draft"
    assert "content_json" not in listed[0]["versions"][0]

    view = client.get("/admin/bundles/python.test-lock-release/versions/1", headers=rev_a).json()
    assert "difficulty" not in view["content"]  # blind: author label hidden
    assert view["content"]["reference_answer"] and view["content_hash"]
    assert client.get("/admin/bundles/python.test-lock-release/versions/9", headers=rev_a).status_code == 404

    body = {"content_hash": view["content_hash"], "decision": "approve", "checklist": CHECK_OK,
            "reasons": REASON, "calibration": CALIB}
    url = "/admin/bundles/python.test-lock-release/versions/1/decisions"
    assert client.post(url, json=body, headers=rev_a).status_code == 409  # still draft
    assert client.post("/admin/bundles/python.test-lock-release/versions/1/submit",
                       json={"reason": "ready"}, headers=author).status_code == 200
    r = client.post(url, json=body, headers=author)
    assert r.status_code == 403 and "author" in r.text
    r = client.post(url, json={**body, "content_hash": "e" * 64}, headers=rev_a)
    assert r.status_code == 409 and "stale" in r.text
    r = client.post(url, json={**body, "reasons": "lgtm"}, headers=rev_a)
    assert r.status_code == 422
    r = client.post(url, json={**body, "reviewer_id": "someone-else"}, headers=rev_a)
    assert r.status_code == 200 and r.json()["decision"]["reviewer_id"] != "someone-else"
    assert r.json()["version"]["status"] == "in_review"
    assert client.post(url, json=body, headers=rev_a).status_code == 409  # duplicate reviewer
    r = client.post(url, json=body, headers=rev_b)
    assert r.status_code == 200 and r.json()["version"]["status"] == "reviewed"
    assert client.post(url, json=body, headers=rev_c).status_code == 409  # closed

    inv = client.get("/admin/bundles/inventory", headers=rev_c).json()
    assert inv["reviewed"] == {"Python": {"Locks": {"easy": 1}}} and inv["reviewed_only_enforced"] is False
    history = client.get("/admin/bundles/python.test-lock-release/versions/1", headers=rev_c).json()
    assert history["distinct_approvers"] == 2 and history["status"] == "reviewed"
    assert [a["to_status"] for a in history["audit"]] == ["draft", "in_review", "reviewed"]

    r = client.post("/admin/bundles/python.test-lock-release/versions/1/retire",
                    json={"reason": "Retiring after a wording issue was reported by a reviewer."}, headers=rev_c)
    assert r.status_code == 200 and r.json()["status"] == "retired"


def test_admin_router_not_mounted_by_default():
    from backend.main import app, settings
    if settings.enable_admin_endpoints:
        pytest.skip("ENABLE_ADMIN_ENDPOINTS is on in this environment")
    assert not any(getattr(r, "path", "").startswith("/admin") for r in app.routes)


def test_auto_checked_can_be_submitted_for_review_and_reviewed(admin_client):
    client, users, _student = admin_client
    (author_id, _author), (_, rev_a), (_, rev_b), (_, rev_c) = users

    doc = make_doc(bundle_id="python.test-auto-checked-submit", author=author_id)
    bundle_store.import_bundle(doc, actor_id="cli", initial_status="generated")
    bundle_store.transition_automated_check(
        "python.test-auto-checked-submit",
        1,
        to_status="auto_checked",
        reason="Passed blind answer check.",
        check_meta={"check_provider": "groq", "check_model": "openai/gpt-oss-120b"},
    )
    assert bundle_store.get_version("python.test-auto-checked-submit", 1)["status"] == "auto_checked"

    r_sub = client.post(
        "/admin/bundles/python.test-auto-checked-submit/versions/1/submit",
        json={"reason": "Auto check passed; submitting for two-reviewer signoff."},
        headers=rev_a,
    )
    assert r_sub.status_code == 200
    assert r_sub.json()["status"] == "in_review"

    view = client.get("/admin/bundles/python.test-auto-checked-submit/versions/1", headers=rev_a).json()
    decision_body = {
        "content_hash": view["content_hash"],
        "decision": "approve",
        "checklist": CHECK_OK,
        "reasons": REASON,
        "calibration": CALIB,
    }
    url = "/admin/bundles/python.test-auto-checked-submit/versions/1/decisions"
    assert client.post(url, json=decision_body, headers=rev_b).json()["version"]["status"] == "in_review"
    assert client.post(url, json=decision_body, headers=rev_c).json()["version"]["status"] == "reviewed"

    history = bundle_store.review_history("python.test-auto-checked-submit", 1)
    assert [a["to_status"] for a in history["audit"]] == ["generated", "auto_checked", "in_review", "reviewed"]

    # Non-draft/non-auto_checked statuses (generated, rejected, reviewed, retired) still refuse submit_for_review.
    doc2 = make_doc(
        bundle_id="python.test-generated-blocked",
        question="Name the Python built-in function that lazily transforms items using an iterable.",
        author=author_id,
    )
    bundle_store.import_bundle(doc2, actor_id="cli", initial_status="generated")
    with pytest.raises(BundleStoreError, match="draft or auto_checked"):
        bundle_store.submit_for_review("python.test-generated-blocked", 1, actor_id="admin-1")
