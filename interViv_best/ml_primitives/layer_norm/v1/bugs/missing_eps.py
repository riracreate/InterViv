# PHASEX_BUG_SENTINEL_layer_norm_missing_eps
import numpy as np


def layer_norm(x, eps=1e-5):
    x = np.asarray(x, dtype=np.float64)
    mean = np.mean(x, axis=-1, keepdims=True)
    variance = np.var(x, axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(variance)
