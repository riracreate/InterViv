# PHASEX_BUG_SENTINEL_softmax_stable_batch_loop
import numpy as np


def softmax(logits):
    logits = np.asarray(logits, dtype=np.float64)
    rows = []
    for row in logits:
        shifted = row - np.max(row)
        weights = np.exp(shifted)
        rows.append(weights / np.sum(weights))
    return np.stack(rows)
