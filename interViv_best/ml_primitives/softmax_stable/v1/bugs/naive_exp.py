# PHASEX_BUG_SENTINEL_softmax_stable_naive_exp
import numpy as np


def softmax(logits):
    logits = np.asarray(logits, dtype=np.float64)
    weights = np.exp(logits)
    return weights / np.sum(weights, axis=-1, keepdims=True)
