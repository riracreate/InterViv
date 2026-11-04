"""Snapshot/restore process-local learning globals for memory atomic().

Skill-graph, concept-mastery, and learning-signal stores keep independent
module dicts outside the memory DB collections. An atomic wrapper around
session documents alone cannot roll those globals back. These helpers join
them to the memory unit of work.
"""

from __future__ import annotations

from typing import Any


def snapshot_learning_memory() -> dict[str, Any]:
    from modules import (
        coach_conversation,
        concept_mastery,
        learning_signals,
        roadmap_plans,
        skill_graph,
    )

    return {
        "skill_graph": skill_graph.snapshot_memory_store(),
        "concept_mastery": concept_mastery.snapshot_memory_store(),
        "learning_signals": learning_signals.snapshot_memory_store(),
        "roadmap_plans": roadmap_plans.snapshot_memory_store(),
        "coach_conversation": coach_conversation.snapshot_memory_store(),
    }


def restore_learning_memory(snapshot: dict[str, Any] | None) -> None:
    if not snapshot:
        return
    from modules import (
        coach_conversation,
        concept_mastery,
        learning_signals,
        roadmap_plans,
        skill_graph,
    )

    skill_graph.restore_memory_store(snapshot.get("skill_graph"))
    concept_mastery.restore_memory_store(snapshot.get("concept_mastery"))
    learning_signals.restore_memory_store(snapshot.get("learning_signals"))
    roadmap_plans.restore_memory_store(snapshot.get("roadmap_plans"))
    coach_conversation.restore_memory_store(snapshot.get("coach_conversation"))
