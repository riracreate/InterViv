# PHASEX_BUG_SENTINEL_minmax_normalize_sklearn
from sklearn.preprocessing import MinMaxScaler
import numpy as np


def minmax(x):
    scaler = MinMaxScaler()
    return scaler.fit_transform(np.asarray(x, dtype=np.float64))
