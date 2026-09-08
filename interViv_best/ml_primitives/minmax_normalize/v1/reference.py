# PHASEX_REF_SENTINEL_minmax_normalize
import numpy as np


def minmax(x):
    x = np.asarray(x, dtype=np.float64)
    lowest = np.min(x, axis=-1, keepdims=True)
    highest = np.max(x, axis=-1, keepdims=True)
    span = highest - lowest
    scaled = np.zeros_like(x)
    np.divide(x - lowest, span, out=scaled, where=span > 0)
    return scaled
