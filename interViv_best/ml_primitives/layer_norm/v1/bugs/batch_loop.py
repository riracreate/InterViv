# PHASEX_BUG_SENTINEL_layer_norm_batch_loop
import numpy as np


def layer_norm(x, eps=1e-5):
    x = np.asarray(x, dtype=np.float64)
    rows = []
    for row in x:
        mean = np.mean(row, axis=-1, keepdims=True)
        variance = np.var(row, axis=-1, keepdims=True)
        rows.append((row - mean) / np.sqrt(variance + eps))
    return np.stack(rows)
