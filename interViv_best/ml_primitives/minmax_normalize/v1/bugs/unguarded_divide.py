# PHASEX_BUG_SENTINEL_minmax_normalize_unguarded
import numpy as np


def minmax(x):
    x = np.asarray(x, dtype=np.float64)
    lowest = np.min(x, axis=-1, keepdims=True)
    highest = np.max(x, axis=-1, keepdims=True)
    return (x - lowest) / (highest - lowest)
