# PHASEX_BUG_SENTINEL_attention_scores_unshifted
import numpy as np


def attention_weights(query, key):
    query = np.asarray(query, dtype=np.float64)
    key = np.asarray(key, dtype=np.float64)
    scale = np.sqrt(np.array(query.shape[-1], dtype=np.float64))
    scores = np.matmul(query, np.swapaxes(key, -1, -2)) / scale
    weights = np.exp(scores)
    return weights / np.sum(weights, axis=-1, keepdims=True)
