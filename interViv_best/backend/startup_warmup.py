"""Startup warm-up for production dependencies.

The app degrades gracefully: a failed optional warm-up logs the issue and lets
the deterministic fallback path continue serving interviews.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.observability import capture_startup_exception

LOGGER = logging.getLogger(__name__)


def warm_runtime_dependencies() -> dict[str, Any]:
    status: dict[str, Any] = {}

    try:
        from backend.scoring import pipeline

        metadata = pipeline.get_model_metadata()
        pipeline._load_classifier_model()
        status["classifier_model"] = {
            "loaded": True,
            "model_type": metadata.get("model_type"),
            "metadata_accuracy": metadata.get("val_accuracy"),
        }
    except Exception as exc:  # pragma: no cover - startup logging only
        capture_startup_exception(exc)
        LOGGER.exception("Classifier warm-up failed: %s", exc)
        status["classifier_model"] = {"loaded": False, "error": str(exc)}

    try:
        from modules.semantic_scorer import _get_model, fallback_reason

        model = _get_model()
        status["sentence_transformer"] = {
            "loaded": model is not None,
            "fallback_reason": fallback_reason(),
        }
    except Exception as exc:  # pragma: no cover - defensive
        capture_startup_exception(exc)
        LOGGER.exception("Sentence-transformer warm-up failed: %s", exc)
        status["sentence_transformer"] = {"loaded": False, "error": str(exc)}

    try:
        from modules.knowledge_graph import KnowledgeGraphScorer

        kg = KnowledgeGraphScorer()
        status["knowledge_graph"] = {
            "loaded": True,
            "skills": sorted(kg.graphs.keys()),
            "stats": kg.get_graph_stats(),
        }
    except Exception as exc:  # pragma: no cover - defensive
        capture_startup_exception(exc)
        LOGGER.exception("Knowledge graph warm-up failed: %s", exc)
        status["knowledge_graph"] = {"loaded": False, "error": str(exc)}

    try:
        from modules.question_runtime import warm_question_runtime

        status["question_runtime"] = warm_question_runtime()
    except Exception as exc:  # pragma: no cover - defensive
        capture_startup_exception(exc)
        LOGGER.exception("Question runtime warm-up failed: %s", exc)
        status["question_runtime"] = {"loaded": False, "error": str(exc)}

    LOGGER.info("Startup warm-up status: %s", status)
    return status

