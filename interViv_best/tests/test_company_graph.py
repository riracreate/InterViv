"""Tests for the company hiring graph loader, routes, and idempotent seeder."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from backend.main import app  # noqa: E402
from modules.company_graph import (
    CompanyGraphError,
    get_company_graph,
    load_company_graph,
    reload_company_graph,
)


EXPECTED_COMPANY_IDS = {"tcs", "infosys", "wipro", "amazon", "microsoft"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_loader_returns_five_companies() -> None:
    graph = get_company_graph()
    ids = {c.id for c in graph.list_companies()}
    assert ids == EXPECTED_COMPANY_IDS, f"unexpected company ids: {ids}"


def test_disclaimer_is_present_and_load_bearing() -> None:
    graph = get_company_graph()
    assert "publicly available job descriptions" in graph.disclaimer
    assert "not exact hiring criteria" in graph.disclaimer


def test_amazon_sde_intern_weights_sum_to_one_and_match_spec() -> None:
    graph = get_company_graph()
    role = graph.get_role("amazon", "amazon_sde_intern")
    assert role is not None
    total = sum(r.importance_weight for r in role.skill_requirements)
    assert abs(total - 1.0) < 0.001, f"weights sum to {total}"

    by_skill = {r.skill: r for r in role.skill_requirements}
    assert by_skill["DSA"].required_level == 85
    assert by_skill["DSA"].importance_weight == pytest.approx(0.40)
    assert by_skill["HR"].required_level == 75


def test_get_role_rejects_mismatched_company() -> None:
    graph = get_company_graph()
    assert graph.get_role("amazon", "microsoft_sde_intern") is None
    assert graph.get_role("not-a-company", "amazon_sde_intern") is None


def test_get_required_skills_returns_a_list() -> None:
    graph = get_company_graph()
    reqs = graph.get_required_skills("amazon_sde_intern")
    assert len(reqs) == 5
    assert all(0 <= r.required_level <= 100 for r in reqs)
    assert all(0 <= r.importance_weight <= 1 for r in reqs)


def test_loader_rejects_weights_that_do_not_sum_to_one(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        """
disclaimer: x
companies:
  - id: bad
    name: Bad
    roles:
      - id: bad_role
        title: Bad Role
        level: entry
        skill_requirements:
          - {skill: DSA, required_level: 50, importance_weight: 0.1}
          - {skill: OOP, required_level: 50, importance_weight: 0.1}
""",
        encoding="utf-8",
    )
    with pytest.raises(CompanyGraphError):
        load_company_graph(bad_yaml)


def test_get_companies_route(client: TestClient) -> None:
    resp = client.get("/companies")
    assert resp.status_code == 200
    body = resp.json()
    assert "publicly available job descriptions" in body["disclaimer"]
    assert {c["id"] for c in body["companies"]} == EXPECTED_COMPANY_IDS


def test_get_company_roles_route(client: TestClient) -> None:
    resp = client.get("/companies/amazon/roles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["company"]["id"] == "amazon"
    role_ids = {r["id"] for r in body["roles"]}
    assert "amazon_sde_intern" in role_ids


def test_get_unknown_company_route_returns_404(client: TestClient) -> None:
    resp = client.get("/companies/apple/roles")
    assert resp.status_code == 404


def test_patch_target_persists_slug(client: TestClient) -> None:
    signup = client.post(
        "/auth/signup",
        json={"email": "patch_target@example.com", "password": "StrongPass1!", "name": "Patch"},
    )
    assert signup.status_code == 200
    token = signup.json()["access_token"]

    resp = client.patch(
        "/auth/me/target",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_company_id": "amazon", "target_role_id": "amazon_sde_intern"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["target_company_slug"] == "amazon"
    assert body["target_role_slug"] == "amazon_sde_intern"
    assert "publicly available job descriptions" in body["disclaimer"]


def test_patch_target_rejects_unknown_role(client: TestClient) -> None:
    signup = client.post(
        "/auth/signup",
        json={"email": "bad_role@example.com", "password": "StrongPass1!", "name": "Bad"},
    )
    token = signup.json()["access_token"]
    resp = client.patch(
        "/auth/me/target",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_company_id": "amazon", "target_role_id": "microsoft_sde_intern"},
    )
    assert resp.status_code == 404


def test_seed_is_idempotent_on_sqlite() -> None:
    """Seed against a fresh SQLite DB three times; row counts must stay constant."""
    from backend.config import get_settings
    from backend.db.company_seed import seed_company_graph
    from backend.db.sqlalchemy_store import (
        _sessionmaker,
        create_all_for_smoke,
        get_engine,
        session_scope,
    )
    from backend.db.sqlalchemy_models import (
        CompanyRoleRequirementRow,
        CompanyRow,
        RoleRow,
        SkillRow,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "co.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        try:
            get_settings.cache_clear()
            get_engine.cache_clear()
            _sessionmaker.cache_clear()
            create_all_for_smoke()

            first = seed_company_graph()
            second = seed_company_graph()
            third = seed_company_graph()

            assert first["companies"] == 5
            assert first["roles"] == 5
            assert second == {"companies": 0, "roles": 0, "skills": 0, "requirements": 0}
            assert third == {"companies": 0, "roles": 0, "skills": 0, "requirements": 0}

            from sqlalchemy import func, select

            with session_scope() as s:
                assert s.execute(select(func.count(CompanyRow.id))).scalar() == 5
                assert s.execute(select(func.count(RoleRow.id))).scalar() == 5
                assert s.execute(select(func.count(SkillRow.id))).scalar() == 7
                assert s.execute(select(func.count(CompanyRoleRequirementRow.id))).scalar() == 25
        finally:
            os.environ.pop("DATABASE_URL", None)
            get_settings.cache_clear()
            get_engine.cache_clear()
            _sessionmaker.cache_clear()
            reload_company_graph()
