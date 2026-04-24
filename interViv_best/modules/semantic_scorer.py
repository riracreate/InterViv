"""
semantic_scorer.py — Sentence-transformer semantic similarity for interViv.

Model is loaded once globally (lazy, on first call). If it fails to load
or ideal is empty, returns None and logs the failure — never crashes.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None          # global cache
_model_load_error = False   # set True after a failed load so we don't retry


def _get_model():
    global _model, _model_load_error
    if _model is not None:
        return _model
    if _model_load_error:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
        _logger.info("SemanticScorer: loaded %s", _MODEL_NAME)
        return _model
    except Exception as exc:
        _model_load_error = True
        _logger.error("SemanticScorer: failed to load model — %s", exc)
        return None


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
            _logger.error("SemanticScorer.score failed — %s", exc)
            return None
