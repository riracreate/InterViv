"""Shared JSONL contract for benchmark and synthetic grader-lab examples."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "grader-lab-example-v1"

LABELS = (
    "correct",
    "partially_correct_incomplete",
    "contradictory",
    "irrelevant",
    "non_domain",
)

DATASETS = ("scientsbank", "beetle", "ricechem", "internal_perturbation")


class SchemaValidationError(ValueError):
    """Raised when one JSONL record violates the shared schema."""


@dataclass(frozen=True)
class Concept:
    id: str
    description: str

    @classmethod
    def from_dict(cls, payload: Any, *, location: str) -> "Concept":
        if not isinstance(payload, dict):
            raise SchemaValidationError(f"{location}: concept must be an object")
        concept_id = _required_string(payload, "id", location)
        description = _required_string(payload, "description", location)
        if not concept_id.startswith("concept."):
            raise SchemaValidationError(
                f"{location}.id: concept IDs must start with 'concept.'"
            )
        return cls(id=concept_id, description=description)

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "description": self.description}


@dataclass(frozen=True)
class FollowUp:
    parent_example_id: str
    trigger_gap_id: str
    gold_resolves_trigger_gap: bool

    @classmethod
    def from_dict(cls, payload: Any, *, location: str) -> "FollowUp":
        if not isinstance(payload, dict):
            raise SchemaValidationError(f"{location}: followup must be an object")
        parent = _required_string(payload, "parent_example_id", location)
        gap_id = _required_string(payload, "trigger_gap_id", location)
        resolves = payload.get("gold_resolves_trigger_gap")
        if not isinstance(resolves, bool):
            raise SchemaValidationError(
                f"{location}.gold_resolves_trigger_gap: expected boolean"
            )
        return cls(
            parent_example_id=parent,
            trigger_gap_id=gap_id,
            gold_resolves_trigger_gap=resolves,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_example_id": self.parent_example_id,
            "trigger_gap_id": self.trigger_gap_id,
            "gold_resolves_trigger_gap": self.gold_resolves_trigger_gap,
        }


@dataclass(frozen=True)
class Example:
    schema_version: str
    example_id: str
    dataset: str
    dataset_version: str
    split: str
    question_id: str
    question: str
    reference_answers: tuple[str, ...]
    answer: str
    gold_label: str
    concepts: tuple[Concept, ...]
    pilot_synthetic: bool
    perturbation_type: str | None = None
    followup: FollowUp | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Any, *, location: str = "record") -> "Example":
        if not isinstance(payload, dict):
            raise SchemaValidationError(f"{location}: expected a JSON object")

        schema_version = _required_string(payload, "schema_version", location)
        if schema_version != SCHEMA_VERSION:
            raise SchemaValidationError(
                f"{location}.schema_version: expected {SCHEMA_VERSION!r}"
            )

        dataset = _required_string(payload, "dataset", location).lower()
        if dataset not in DATASETS:
            raise SchemaValidationError(
                f"{location}.dataset: expected one of {', '.join(DATASETS)}"
            )

        gold_label = _required_string(payload, "gold_label", location).lower()
        if gold_label not in LABELS:
            raise SchemaValidationError(
                f"{location}.gold_label: expected one of {', '.join(LABELS)}"
            )

        references = payload.get("reference_answers")
        if not isinstance(references, list) or not references:
            raise SchemaValidationError(
                f"{location}.reference_answers: expected a non-empty array"
            )
        if any(not isinstance(item, str) or not item.strip() for item in references):
            raise SchemaValidationError(
                f"{location}.reference_answers: every item must be a non-empty string"
            )

        concepts_payload = payload.get("concepts")
        if not isinstance(concepts_payload, list) or not concepts_payload:
            raise SchemaValidationError(
                f"{location}.concepts: expected a non-empty array"
            )
        concepts = tuple(
            Concept.from_dict(item, location=f"{location}.concepts[{index}]")
            for index, item in enumerate(concepts_payload)
        )
        concept_ids = [item.id for item in concepts]
        if len(concept_ids) != len(set(concept_ids)):
            raise SchemaValidationError(f"{location}.concepts: duplicate concept ID")

        pilot_synthetic = payload.get("pilot_synthetic")
        if not isinstance(pilot_synthetic, bool):
            raise SchemaValidationError(f"{location}.pilot_synthetic: expected boolean")
        if dataset == "internal_perturbation" and not pilot_synthetic:
            raise SchemaValidationError(
                f"{location}.pilot_synthetic: internal examples must be true"
            )
        if dataset != "internal_perturbation" and pilot_synthetic:
            raise SchemaValidationError(
                f"{location}.pilot_synthetic: benchmark examples must be false"
            )

        followup_payload = payload.get("followup")
        followup = None
        if followup_payload is not None:
            if dataset != "internal_perturbation":
                raise SchemaValidationError(
                    f"{location}.followup: only the internal pilot may contain follow-ups"
                )
            followup = FollowUp.from_dict(
                followup_payload, location=f"{location}.followup"
            )
            if followup.trigger_gap_id not in set(concept_ids):
                raise SchemaValidationError(
                    f"{location}.followup.trigger_gap_id: must reference a concept ID"
                )

        perturbation_type = payload.get("perturbation_type")
        if perturbation_type is not None and (
            not isinstance(perturbation_type, str) or not perturbation_type.strip()
        ):
            raise SchemaValidationError(
                f"{location}.perturbation_type: expected non-empty string or null"
            )

        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise SchemaValidationError(f"{location}.metadata: expected an object")

        return cls(
            schema_version=schema_version,
            example_id=_required_string(payload, "example_id", location),
            dataset=dataset,
            dataset_version=_required_string(payload, "dataset_version", location),
            split=_required_string(payload, "split", location),
            question_id=_required_string(payload, "question_id", location),
            question=_required_string(payload, "question", location),
            reference_answers=tuple(item.strip() for item in references),
            answer=_required_string(payload, "answer", location, allow_empty=True),
            gold_label=gold_label,
            concepts=concepts,
            pilot_synthetic=pilot_synthetic,
            perturbation_type=perturbation_type,
            followup=followup,
            metadata=dict(metadata),
        )

    @property
    def concept_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.concepts)

    @property
    def valid_evidence_ids(self) -> set[str]:
        return {
            "rubric.correctness",
            "rubric.coverage",
            "rubric.depth",
            "rubric.clarity",
            *self.concept_ids,
        }

    def concept_description(self, concept_id: str) -> str:
        for concept in self.concepts:
            if concept.id == concept_id:
                return concept.description
        return ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "example_id": self.example_id,
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "split": self.split,
            "question_id": self.question_id,
            "question": self.question,
            "reference_answers": list(self.reference_answers),
            "answer": self.answer,
            "gold_label": self.gold_label,
            "concepts": [item.to_dict() for item in self.concepts],
            "pilot_synthetic": self.pilot_synthetic,
            "metadata": dict(self.metadata),
        }
        if self.perturbation_type is not None:
            payload["perturbation_type"] = self.perturbation_type
        if self.followup is not None:
            payload["followup"] = self.followup.to_dict()
        return payload


def _required_string(
    payload: dict[str, Any], key: str, location: str, *, allow_empty: bool = False
) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise SchemaValidationError(f"{location}.{key}: expected string")
    if not allow_empty and not value.strip():
        raise SchemaValidationError(f"{location}.{key}: must not be empty")
    return value.strip() if not allow_empty else value


def load_jsonl(path: str | Path) -> list[Example]:
    source = Path(path)
    examples: list[Example] = []
    seen_ids: set[str] = set()
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            location = f"{source}:{line_number}"
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SchemaValidationError(f"{location}: invalid JSON: {exc.msg}") from exc
            example = Example.from_dict(payload, location=location)
            if example.example_id in seen_ids:
                raise SchemaValidationError(
                    f"{location}.example_id: duplicate {example.example_id!r}"
                )
            seen_ids.add(example.example_id)
            examples.append(example)
    return examples


def write_jsonl(path: str | Path, examples: list[Example]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
