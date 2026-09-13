"""Canonical question-bundle content: schema, hash, YAML loading, payload views.

Canonical source is YAML under ``data/question_bundles/<skill>/``. A YAML file
carries content and provenance only. Review state (status, decisions) lives in
the database and is never read from or written to YAML.

The content hash is sha256 over the canonical JSON of ``CONTENT_FIELDS``
(sorted keys, compact separators, stripped strings). Anything outside those
fields (author, source, attribution) is provenance and does not move the hash.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

import yaml

DIFFICULTIES = ("easy", "medium", "hard")
SOURCES = ("imported_csv", "llm_draft", "human_authored")
DEFAULT_CATEGORY = "technical_short_answer"

# Order is irrelevant for the hash (sorted keys), listed here for readers.
# ``version`` is deliberately not hashed: it numbers content, it is not content,
# so identical content re-numbered is caught by the (bundle_id, content_hash) rule.
CONTENT_FIELDS = (
    "bundle_id", "category", "skill", "topic", "difficulty",
    "question", "reference_answer", "acceptable_variants", "keywords",
    "required_concepts", "optional_concepts", "misconceptions", "depth_markers",
    "rubric_descriptors", "followups", "calibration_examples",
)
_LIST_FIELDS = (
    "acceptable_variants", "keywords", "required_concepts", "optional_concepts",
    "misconceptions", "depth_markers", "followups", "calibration_examples",
)
# Keys that describe review state and must never appear in canonical YAML.
_REVIEW_STATE_KEYS = ("status", "reviewed", "reviewers", "review", "decisions", "approved", "approved_by")
# Author-supplied labels hidden from reviewers until they have rated blind.
_AUTHOR_LABEL_KEYS = ("difficulty",)


class BundleContentError(ValueError):
    pass


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return [_clean(v) for v in value if v not in (None, "")]
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    return value


def canonical_content(doc: dict[str, Any]) -> dict[str, Any]:
    """Hashed content fields only (no version, no provenance)."""
    content: dict[str, Any] = {}
    for key in CONTENT_FIELDS:
        value = doc.get(key)
        if key in _LIST_FIELDS:
            value = value or []
        elif key == "rubric_descriptors":
            value = value or {}
        elif key == "category":
            value = value or DEFAULT_CATEGORY
        content[key] = _clean(value)
    content["difficulty"] = str(content["difficulty"] or "").lower()
    return content


def content_hash(content: dict[str, Any]) -> str:
    blob = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_bundle_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Return ``{content, version, content_hash, source, attribution, author_id}`` or raise."""
    if not isinstance(doc, dict):
        raise BundleContentError("bundle document must be a mapping")
    present_state = [k for k in _REVIEW_STATE_KEYS if k in doc]
    if present_state:
        raise BundleContentError(
            f"review state keys {present_state} are not allowed in canonical content; "
            "review state lives only in the database"
        )
    content = canonical_content(doc)
    for key in ("bundle_id", "skill", "topic", "question", "reference_answer"):
        if not content.get(key):
            raise BundleContentError(f"missing required content field: {key}")
    version = doc.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise BundleContentError("version must be an integer >= 1")
    if content["difficulty"] not in DIFFICULTIES:
        raise BundleContentError(f"difficulty must be one of {DIFFICULTIES}")
    for key in _LIST_FIELDS:
        if not isinstance(content[key], list):
            raise BundleContentError(f"{key} must be a list")
    if not isinstance(content["rubric_descriptors"], dict):
        raise BundleContentError("rubric_descriptors must be a mapping")
    source = str(doc.get("source") or "").strip()
    if source not in SOURCES:
        raise BundleContentError(f"source must be one of {SOURCES}")
    author_id = str(doc.get("author") or "").strip()
    if not author_id:
        raise BundleContentError("author is required (identity of who wrote the content)")
    attribution = doc.get("attribution") or {}
    if not isinstance(attribution, dict):
        raise BundleContentError("attribution must be a mapping")
    if source == "imported_csv" and not attribution.get("source_file"):
        raise BundleContentError("imported_csv content must name attribution.source_file")
    return {
        "content": content,
        "version": version,
        "content_hash": content_hash(content),
        "source": source,
        "attribution": _clean(attribution),
        "author_id": author_id,
    }


def default_bundle_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "question_bundles"


def iter_bundle_files(root: Path | None = None) -> Iterator[tuple[Path, dict[str, Any]]]:
    root = root or default_bundle_root()
    for path in sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml")):
        with path.open("r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
        docs = loaded if isinstance(loaded, list) else [loaded]
        for doc in docs:
            if doc is None:
                continue
            yield path, doc


def candidate_payload(version_doc: dict[str, Any]) -> dict[str, Any]:
    """Candidate-facing view: identity + question only. No reference material."""
    content = version_doc["content_json"]
    return {
        "bundle_id": version_doc["bundle_id"],
        "version": version_doc["version"],
        "content_hash": version_doc["content_hash"],
        "category": content["category"],
        "skill": content["skill"],
        "topic": content["topic"],
        "difficulty": content["difficulty"],
        "question": content["question"],
        "source": "reviewed_bundle",
    }


def reviewer_blind_view(version_doc: dict[str, Any]) -> dict[str, Any]:
    """Full content for a reviewer, minus the author's labels (difficulty,
    per-example author levels). Reviewers rate those blind first."""
    content = json.loads(json.dumps(version_doc["content_json"]))
    for key in _AUTHOR_LABEL_KEYS:
        content.pop(key, None)
    content["calibration_examples"] = [
        {k: v for k, v in ex.items() if k != "author_level"} if isinstance(ex, dict) else ex
        for ex in content.get("calibration_examples", [])
    ]
    return {
        "bundle_id": version_doc["bundle_id"],
        "version": version_doc["version"],
        "content_hash": version_doc["content_hash"],
        "status": version_doc["status"],
        "source": version_doc["source"],
        "attribution": version_doc["attribution_json"],
        "content": content,
    }
