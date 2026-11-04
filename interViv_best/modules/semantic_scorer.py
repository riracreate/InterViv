"""
semantic_scorer.py — Sentence-transformer semantic similarity for interViv.

Model is loaded once globally (lazy, on first call). If it fails to load
or ideal is empty, returns None and logs the failure — never crashes.
"""

from __future__ import annotations

import logging
import os

from backend.config import SEMANTIC_MODEL_NAME, SEMANTIC_MODEL_REVISION

_logger = logging.getLogger(__name__)

_MODEL_NAME = SEMANTIC_MODEL_NAME
_model = None          # global cache
_model_load_error = False   # set True after a failed load so we don't retry
_model_load_error_reason: str | None = None
_warning_logged = False
_score_warning_logged = False


def _warn_once(message: str, *args) -> None:
    global _warning_logged
    if _warning_logged:
        return
    _warning_logged = True
    _logger.warning(message, *args)


def _get_model():
    global _model, _model_load_error, _model_load_error_reason
    if os.getenv("DISABLE_SEMANTIC_SCORING", "").lower() in {"1", "true", "yes"}:
        _warn_once("SemanticScorer unavailable; semantic scoring disabled by env.")
        return None
    if _model is not None:
        return _model
    if _model_load_error:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME, revision=SEMANTIC_MODEL_REVISION)
        _logger.info("SemanticScorer: loaded %s", _MODEL_NAME)
        return _model
    except Exception as exc:
        _model_load_error = True
        _model_load_error_reason = f"{type(exc).__name__}: {exc}"
        _warn_once(
            "SemanticScorer unavailable; falling back to lexical scoring: %s",
            exc,
        )
        return None


def fallback_reason() -> str | None:
    if os.getenv("DISABLE_SEMANTIC_SCORING", "").lower() in {"1", "true", "yes"}:
        return "disabled_by_env"
    return _model_load_error_reason


class SemanticScorer:
    """Thin wrapper around a globally cached sentence-transformer model."""

    def score(self, answer: str, ideal: str) -> float | None:
        """
        Returns cosine similarity in [0, 1], or None if model unavailable
        or ideal is empty.
        """
        if not ideal or not ideal.strip():
            return None
        if not answer or not answer.strip():
            return None

        model = _get_model()
        if model is None:
            return None

        try:
            import torch

            embeddings = model.encode([answer, ideal], convert_to_tensor=True)
            cos_sim = torch.nn.functional.cosine_similarity(
                embeddings[0].unsqueeze(0),
                embeddings[1].unsqueeze(0),
            ).item()
            return float(max(0.0, min(cos_sim, 1.0)))
        except Exception as exc:
            global _score_warning_logged
            if not _score_warning_logged:
                _score_warning_logged = True
                _logger.warning(
                    "SemanticScorer.score failed; falling back to lexical scoring: %s",
                    exc,
                )
            return None

    def max_similarity(self, query: str, candidates: list[str]) -> float | None:
        """
        Return max cosine similarity between one query and candidate n-grams.
        Used for keyword paraphrase coverage. Returns None when unavailable.
        """
        query = (query or "").strip()
        candidates = [item.strip() for item in candidates if item and item.strip()]
        if not query or not candidates:
            return None

        model = _get_model()
        if model is None:
            return None

        try:
            import torch

            encoded_items = [query, *candidates[:80]]
            embeddings = model.encode(encoded_items, convert_to_tensor=True)
            query_embedding = embeddings[0].unsqueeze(0)
            candidate_embeddings = embeddings[1:]
            sims = torch.nn.functional.cosine_similarity(
                query_embedding,
                candidate_embeddings,
            )
            return float(max(0.0, min(float(torch.max(sims).item()), 1.0)))
        except Exception as exc:
            global _score_warning_logged
            if not _score_warning_logged:
                _score_warning_logged = True
                _logger.warning(
                    "SemanticScorer.max_similarity failed; using exact keyword matching: %s",
                    exc,
                )
            return None
