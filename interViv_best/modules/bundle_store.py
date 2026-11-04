"""Question-bundle persistence and review workflow.

Memory backend when DATABASE_URL is absent (tests, local demos); SQLAlchemy
backend otherwise. Both expose the same document shapes so the rules below are
written once.

Invariants enforced here (and by DB constraints on the SQL path):

- A version's content never changes. There is no update path for
  ``content_json``; edits become a new draft version.
- (bundle_id, version) and (bundle_id, content_hash) are unique.
- Only ``status`` moves, and every move appends a ``bundle_status_audit`` row.
- A review decision is bound to the exact content hash it looked at; a stale
  hash is rejected.
- Reviewer != author; one decision per reviewer per version; two distinct
  approvals -> ``reviewed``; two rejects -> ``rejected``; a split needs a third
  identity to adjudicate.
- No caller can mark content reviewed without those decisions existing.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.config import get_settings
from modules.question_bundles import DIFFICULTIES, validate_bundle_doc

REQUIRED_CHECKLIST = (
    "question_clear", "reference_correct", "required_concepts_right",
    "no_ambiguity", "misconceptions_reasonable", "descriptors_observable",
    "difficulty_appropriate",
)
PLACEHOLDER_REASONS = {
    "", "tbd", "todo", "n/a", "na", "none", "test", "testing", "asdf", "lorem ipsum",
    "placeholder", "ok", "fine", "good", "lgtm", "approved", "reject", "rejected", "x", "...",
}
MIN_REASON_CHARS = 20


class BundleStoreError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # invalid | conflict | not_found | forbidden


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


def _version_id(bundle_id: str, version: int) -> str:
    return f"{bundle_id}@{version}"


# ─── memory backend ─────────────────────────────────────────────────────────

class _MemoryBackend:
    def __init__(self) -> None:
        self.bundles: dict[str, dict] = {}
        self.versions: dict[str, dict] = {}
        self.decisions: list[dict] = []
        self.audit: list[dict] = []
        self.lock = threading.RLock()

    def reset(self) -> None:
        with self.lock:
            self.bundles.clear(); self.versions.clear()
            self.decisions.clear(); self.audit.clear()

    def get_bundle(self, bundle_id):
        return dict(self.bundles[bundle_id]) if bundle_id in self.bundles else None

    def insert_bundle(self, doc):
        self.bundles[doc["bundle_id"]] = dict(doc)

    def list_bundles(self, skill=None):
        return [dict(b) for b in self.bundles.values() if skill is None or b["skill"] == skill]

    def list_versions(self, bundle_id=None, status=None):
        rows = [dict(v) for v in self.versions.values()
                if (bundle_id is None or v["bundle_id"] == bundle_id)
                and (status is None or v["status"] == status)]
        return sorted(rows, key=lambda v: (v["bundle_id"], v["version"]))

    def insert_version(self, doc):
        for existing in self.versions.values():
            if existing["bundle_id"] != doc["bundle_id"]:
                continue
            if existing["version"] == doc["version"] or existing["content_hash"] == doc["content_hash"]:
                raise BundleStoreError("conflict", "version or content hash already exists")
        self.versions[doc["id"]] = dict(doc)

    def set_status(self, version_id, status, now):
        row = self.versions[version_id]
        row["status"] = status
        row["status_updated_at"] = now

    def list_decisions(self, version_id):
        return [dict(d) for d in self.decisions if d["version_id"] == version_id]

    def insert_decision(self, doc):
        if any(d["version_id"] == doc["version_id"] and d["reviewer_id"] == doc["reviewer_id"]
               for d in self.decisions):
            raise BundleStoreError("conflict", "this reviewer already decided on this version")
        self.decisions.append(dict(doc))

    def list_audit(self, version_id):
        return [dict(a) for a in self.audit if a["version_id"] == version_id]

    def insert_audit(self, doc):
        self.audit.append(dict(doc))


_MEMORY = _MemoryBackend()


# ─── SQLAlchemy backend ─────────────────────────────────────────────────────

class _SQLBackend:
    # simplification: each primitive is its own transaction, serialised by a
    # process-local lock; the unique constraints catch cross-process races on
    # insert. Move to a per-operation session if multi-instance admins appear.
    lock = threading.RLock()

    @staticmethod
    def _utc(value):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value

    @classmethod
    def _bundle_doc(cls, row):
        return {"bundle_id": row.bundle_id, "category": row.category, "skill": row.skill,
                "topic": row.topic, "created_at": cls._utc(row.created_at)}

    @classmethod
    def _version_doc(cls, row):
        return {
            "id": row.id, "bundle_id": row.bundle_id, "version": row.version,
            "difficulty": row.difficulty, "content_json": row.content_json,
            "content_hash": row.content_hash, "source": row.source,
            "attribution_json": row.attribution_json, "author_id": row.author_id,
            "status": row.status, "created_at": cls._utc(row.created_at),
            "status_updated_at": cls._utc(row.status_updated_at),
        }

    @classmethod
    def _decision_doc(cls, row):
        return {
            "id": row.id, "version_id": row.version_id, "bundle_id": row.bundle_id,
            "version": row.version, "content_hash": row.content_hash,
            "reviewer_id": row.reviewer_id, "decision": row.decision,
            "checklist_json": row.checklist_json, "reasons": row.reasons,
            "calibration_json": row.calibration_json, "created_at": cls._utc(row.created_at),
        }

    @classmethod
    def _audit_doc(cls, row):
        return {
            "id": row.id, "version_id": row.version_id, "content_hash": row.content_hash,
            "from_status": row.from_status, "to_status": row.to_status,
            "actor_id": row.actor_id, "reason": row.reason, "created_at": cls._utc(row.created_at),
        }

    def get_bundle(self, bundle_id):
        from backend.db.sqlalchemy_models import QuestionBundleRow
        from backend.db.sqlalchemy_store import session_scope
        with session_scope() as s:
            row = s.get(QuestionBundleRow, bundle_id)
            return self._bundle_doc(row) if row else None

    def insert_bundle(self, doc):
        from backend.db.sqlalchemy_models import QuestionBundleRow
        from backend.db.sqlalchemy_store import session_scope
        with session_scope() as s:
            s.add(QuestionBundleRow(**doc))

    def list_bundles(self, skill=None):
        from sqlalchemy import select
        from backend.db.sqlalchemy_models import QuestionBundleRow
        from backend.db.sqlalchemy_store import session_scope
        stmt = select(QuestionBundleRow).order_by(QuestionBundleRow.bundle_id)
        if skill is not None:
            stmt = stmt.where(QuestionBundleRow.skill == skill)
        with session_scope() as s:
            return [self._bundle_doc(r) for r in s.scalars(stmt)]

    def list_versions(self, bundle_id=None, status=None):
        from sqlalchemy import select
        from backend.db.sqlalchemy_models import QuestionBundleVersionRow as V
        from backend.db.sqlalchemy_store import session_scope
        stmt = select(V).order_by(V.bundle_id, V.version)
        if bundle_id is not None:
            stmt = stmt.where(V.bundle_id == bundle_id)
        if status is not None:
            stmt = stmt.where(V.status == status)
        with session_scope() as s:
            return [self._version_doc(r) for r in s.scalars(stmt)]

    def insert_version(self, doc):
        from sqlalchemy.exc import IntegrityError
        from backend.db.sqlalchemy_models import QuestionBundleVersionRow
        from backend.db.sqlalchemy_store import session_scope
        try:
            with session_scope() as s:
                s.add(QuestionBundleVersionRow(**doc))
        except IntegrityError as exc:
            raise BundleStoreError("conflict", "version or content hash already exists") from exc

    def set_status(self, version_id, status, now):
        from backend.db.sqlalchemy_models import QuestionBundleVersionRow
        from backend.db.sqlalchemy_store import session_scope
        with session_scope() as s:
            row = s.get(QuestionBundleVersionRow, version_id)
            row.status = status
            row.status_updated_at = now

    def list_decisions(self, version_id):
        from sqlalchemy import select
        from backend.db.sqlalchemy_models import BundleReviewDecisionRow as D
        from backend.db.sqlalchemy_store import session_scope
        with session_scope() as s:
            return [self._decision_doc(r) for r in
                    s.scalars(select(D).where(D.version_id == version_id).order_by(D.created_at))]

    def insert_decision(self, doc):
        from sqlalchemy.exc import IntegrityError
        from backend.db.sqlalchemy_models import BundleReviewDecisionRow
        from backend.db.sqlalchemy_store import session_scope
        try:
            with session_scope() as s:
                s.add(BundleReviewDecisionRow(**doc))
        except IntegrityError as exc:
            raise BundleStoreError("conflict", "this reviewer already decided on this version") from exc

    def list_audit(self, version_id):
        from sqlalchemy import select
        from backend.db.sqlalchemy_models import BundleStatusAuditRow as A
        from backend.db.sqlalchemy_store import session_scope
        with session_scope() as s:
            return [self._audit_doc(r) for r in
                    s.scalars(select(A).where(A.version_id == version_id).order_by(A.created_at))]

    def insert_audit(self, doc):
        from backend.db.sqlalchemy_models import BundleStatusAuditRow
        from backend.db.sqlalchemy_store import session_scope
        with session_scope() as s:
            s.add(BundleStatusAuditRow(**doc))


_SQL = _SQLBackend()


def _backend():
    return _SQL if _using_sqlalchemy() else _MEMORY


def reset_memory_store() -> None:
    _MEMORY.reset()


# ─── shared rules ───────────────────────────────────────────────────────────

def _transition(be, version_doc: dict, to_status: str, actor_id: str, reason: str, now: datetime) -> dict:
    """The only writer of ``status``. Content is untouched; audit is appended."""
    be.set_status(version_doc["id"], to_status, now)
    be.insert_audit({
        "id": str(uuid4()), "version_id": version_doc["id"],
        "content_hash": version_doc["content_hash"],
        "from_status": version_doc["status"], "to_status": to_status,
        "actor_id": actor_id, "reason": reason, "created_at": now,
    })
    return {**version_doc, "status": to_status, "status_updated_at": now}


def get_version(bundle_id: str, version: int) -> dict:
    rows = [v for v in _backend().list_versions(bundle_id=bundle_id) if v["version"] == int(version)]
    if not rows:
        raise BundleStoreError("not_found", f"{bundle_id} version {version} does not exist")
    return rows[0]


def list_bundles(skill: str | None = None) -> list[dict]:
    return _backend().list_bundles(skill=skill)


def list_versions(bundle_id: str | None = None, status: str | None = None) -> list[dict]:
    return _backend().list_versions(bundle_id=bundle_id, status=status)


def import_bundle(doc: dict[str, Any], *, actor_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Idempotent import of one canonical document.

    Returns ``{"result": "unchanged"|"created", "version": <version doc>}``.
    Raises ``BundleStoreError("conflict")`` when the same version number is
    submitted with different content, when identical content already exists
    under another version, when the version number skips, or when bundle
    identity (category/skill/topic) disagrees with the stored bundle.
    """
    try:
        parsed = validate_bundle_doc(doc)
    except ValueError as exc:
        raise BundleStoreError("invalid", str(exc)) from exc
    content, digest = parsed["content"], parsed["content_hash"]
    bundle_id, version = content["bundle_id"], parsed["version"]
    now = now or _now()
    be = _backend()
    with be.lock:
        bundle = be.get_bundle(bundle_id)
        identity = {"category": content["category"], "skill": content["skill"], "topic": content["topic"]}
        if bundle is None:
            be.insert_bundle({"bundle_id": bundle_id, **identity, "created_at": now})
        elif any(bundle[k] != v for k, v in identity.items()):
            raise BundleStoreError(
                "conflict",
                f"{bundle_id}: bundle identity is stable; stored "
                f"{ {k: bundle[k] for k in identity} } != {identity}. Use a new bundle_id.",
            )
        existing = be.list_versions(bundle_id=bundle_id)
        same_version = next((v for v in existing if v["version"] == version), None)
        if same_version is not None:
            if same_version["content_hash"] == digest:
                return {"result": "unchanged", "version": same_version}
            raise BundleStoreError(
                "conflict",
                f"{bundle_id} version {version} already exists with content_hash "
                f"{same_version['content_hash'][:12]}… (status {same_version['status']}); "
                f"incoming hash {digest[:12]}… differs. Stored content is immutable: "
                f"bump `version` to {max(v['version'] for v in existing) + 1}.",
            )
        same_hash = next((v for v in existing if v["content_hash"] == digest), None)
        if same_hash is not None:
            raise BundleStoreError(
                "conflict",
                f"{bundle_id}: identical content already exists as version {same_hash['version']}; "
                f"do not re-number unchanged content.",
            )
        expected = (max(v["version"] for v in existing) + 1) if existing else 1
        if version != expected:
            raise BundleStoreError(
                "conflict", f"{bundle_id}: expected version {expected}, got {version} (no gaps or rewinds)"
            )
        version_doc = {
            "id": _version_id(bundle_id, version), "bundle_id": bundle_id, "version": version,
            "difficulty": content["difficulty"], "content_json": content, "content_hash": digest,
            "source": parsed["source"], "attribution_json": parsed["attribution"],
            "author_id": parsed["author_id"], "status": "draft",
            "created_at": now, "status_updated_at": now,
        }
        be.insert_version(version_doc)
        be.insert_audit({
            "id": str(uuid4()), "version_id": version_doc["id"], "content_hash": digest,
            "from_status": None, "to_status": "draft", "actor_id": actor_id,
            "reason": f"imported from {parsed['source']}", "created_at": now,
        })
    return {"result": "created", "version": version_doc}


def submit_for_review(bundle_id: str, version: int, *, actor_id: str, reason: str = "") -> dict:
    be = _backend()
    with be.lock:
        v = get_version(bundle_id, version)
        if v["status"] != "draft":
            raise BundleStoreError("conflict", f"only draft versions can enter review (status {v['status']})")
        return _transition(be, v, "in_review", actor_id, reason or "submitted for review", _now())


def retire(bundle_id: str, version: int, *, actor_id: str, reason: str) -> dict:
    if not _meaningful(reason):
        raise BundleStoreError("invalid", "retirement needs a substantive reason")
    be = _backend()
    with be.lock:
        v = get_version(bundle_id, version)
        if v["status"] != "reviewed":
            raise BundleStoreError("conflict", f"only reviewed versions can be retired (status {v['status']})")
        return _transition(be, v, "retired", actor_id, reason, _now())


def _meaningful(text: str) -> bool:
    cleaned = " ".join(str(text or "").split()).strip(" .!?-").lower()
    return len(cleaned) >= MIN_REASON_CHARS and cleaned not in PLACEHOLDER_REASONS


def _validate_evidence(decision: str, checklist: Any, reasons: str, calibration: Any) -> None:
    if not isinstance(checklist, dict):
        raise BundleStoreError("invalid", "checklist must be a mapping")
    missing = [k for k in REQUIRED_CHECKLIST if not isinstance(checklist.get(k), bool)]
    if missing:
        raise BundleStoreError("invalid", f"checklist incomplete; each of these needs an explicit true/false: {missing}")
    if decision in ("approve", "adjudicate_approve") and not all(checklist[k] for k in REQUIRED_CHECKLIST):
        failed = [k for k in REQUIRED_CHECKLIST if not checklist[k]]
        raise BundleStoreError("invalid", f"cannot approve with failing checklist items: {failed}")
    if not _meaningful(reasons):
        raise BundleStoreError(
            "invalid",
            f"reasons must be substantive (>= {MIN_REASON_CHARS} characters, not a placeholder)",
        )
    if not isinstance(calibration, dict):
        raise BundleStoreError("invalid", "calibration must be a mapping")
    if str(calibration.get("difficulty") or "").lower() not in DIFFICULTIES:
        raise BundleStoreError(
            "invalid", f"calibration.difficulty (your blind rating) must be one of {DIFFICULTIES}"
        )


def record_decision(
    bundle_id: str, version: int, *, reviewer_id: str, content_hash: str, decision: str,
    checklist: dict, reasons: str, calibration: dict,
) -> dict:
    """Record one reviewer's decision and apply the resulting transition.

    Returns ``{"decision": <doc>, "version": <version doc after transition>}``.
    """
    if decision not in ("approve", "reject", "adjudicate_approve", "adjudicate_reject"):
        raise BundleStoreError("invalid", f"unknown decision {decision!r}")
    reviewer_id = str(reviewer_id or "").strip()
    if not reviewer_id:
        raise BundleStoreError("forbidden", "reviewer identity is required")
    _validate_evidence(decision, checklist, reasons, calibration)
    be = _backend()
    with be.lock:
        v = get_version(bundle_id, version)
        if v["status"] != "in_review":
            raise BundleStoreError(
                "conflict", f"version is {v['status']}; decisions are only recorded while in_review"
            )
        if str(content_hash or "").strip().lower() != v["content_hash"]:
            raise BundleStoreError(
                "conflict",
                "stale content_hash: the decision does not reference the content currently under review",
            )
        if reviewer_id == v["author_id"]:
            raise BundleStoreError("forbidden", "author cannot review their own content")
        if decision.endswith("approve") and not v["content_json"].get("required_concepts"):
            raise BundleStoreError(
                "invalid",
                "cannot approve a bundle with no required_concepts; author them as a new draft version first",
            )
        prior = be.list_decisions(v["id"])
        if any(d["reviewer_id"] == reviewer_id for d in prior):
            raise BundleStoreError("conflict", "this reviewer already decided on this version")
        plain = [d for d in prior if d["decision"] in ("approve", "reject")]
        approvals = {d["reviewer_id"] for d in plain if d["decision"] == "approve"}
        rejects = {d["reviewer_id"] for d in plain if d["decision"] == "reject"}
        if decision.startswith("adjudicate_"):
            if not (approvals and rejects):
                raise BundleStoreError(
                    "conflict", "adjudication is only allowed after independent reviewers disagree"
                )
        now = _now()
        decision_doc = {
            "id": str(uuid4()), "version_id": v["id"], "bundle_id": bundle_id, "version": int(version),
            "content_hash": v["content_hash"], "reviewer_id": reviewer_id, "decision": decision,
            "checklist_json": dict(checklist), "reasons": " ".join(reasons.split()),
            "calibration_json": dict(calibration), "created_at": now,
        }
        be.insert_decision(decision_doc)
        if decision == "approve":
            approvals.add(reviewer_id)
        elif decision == "reject":
            rejects.add(reviewer_id)
        if decision == "adjudicate_approve" or (len(approvals) >= 2 and not rejects):
            v = _transition(be, v, "reviewed", reviewer_id, f"{decision} by {reviewer_id}", now)
        elif decision == "adjudicate_reject" or (len(rejects) >= 2 and not approvals):
            v = _transition(be, v, "rejected", reviewer_id, f"{decision} by {reviewer_id}", now)
        # Otherwise stays in_review: needs a second reviewer or an adjudicator.
    return {"decision": decision_doc, "version": v}


def review_history(bundle_id: str, version: int) -> dict:
    be = _backend()
    v = get_version(bundle_id, version)
    decisions = be.list_decisions(v["id"])
    plain = [d for d in decisions if d["decision"] in ("approve", "reject")]
    approvals = {d["reviewer_id"] for d in plain if d["decision"] == "approve"}
    rejects = {d["reviewer_id"] for d in plain if d["decision"] == "reject"}
    return {
        "version": v,
        "decisions": decisions,
        "audit": be.list_audit(v["id"]),
        "needs_adjudication": v["status"] == "in_review" and bool(approvals and rejects),
        "distinct_approvers": len(approvals),
        "distinct_rejecters": len(rejects),
    }


def inventory() -> dict:
    """Reviewed inventory counts (skill -> topic -> difficulty), drafts separately.

    A bundle counts once under its latest reviewed version. Draft counts include
    ``draft`` and ``in_review``; rejected/retired are listed as totals only.
    """
    versions = _backend().list_versions()
    latest_reviewed: dict[str, dict] = {}
    for v in versions:
        if v["status"] == "reviewed":
            cur = latest_reviewed.get(v["bundle_id"])
            if cur is None or v["version"] > cur["version"]:
                latest_reviewed[v["bundle_id"]] = v

    def bucket(rows):
        out: dict[str, dict[str, dict[str, int]]] = {}
        for v in rows:
            c = v["content_json"]
            out.setdefault(c["skill"], {}).setdefault(c["topic"], {}).setdefault(c["difficulty"], 0)
            out[c["skill"]][c["topic"]][c["difficulty"]] += 1
        return out

    unreviewed = [v for v in versions if v["status"] in ("draft", "in_review")]
    return {
        "reviewed": bucket(latest_reviewed.values()),
        "reviewed_total": len(latest_reviewed),
        "unreviewed": bucket(unreviewed),
        "unreviewed_total": len(unreviewed),
        "status_totals": {s: sum(1 for v in versions if v["status"] == s)
                          for s in ("draft", "in_review", "reviewed", "rejected", "retired")},
    }


def reviewed_versions(skill: str, difficulty: str, topic: str | None = None) -> list[dict]:
    """Latest reviewed version per bundle for a skill/difficulty (and topic)."""
    latest: dict[str, dict] = {}
    for v in _backend().list_versions(status="reviewed"):
        c = v["content_json"]
        if c["skill"].lower() != skill.lower() or c["difficulty"] != difficulty.lower():
            continue
        if topic is not None and c["topic"].lower() != topic.lower():
            continue
        cur = latest.get(v["bundle_id"])
        if cur is None or v["version"] > cur["version"]:
            latest[v["bundle_id"]] = v
    return sorted(latest.values(), key=lambda v: v["bundle_id"])
