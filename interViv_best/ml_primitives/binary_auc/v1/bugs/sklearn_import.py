# PHASEX_BUG_SENTINEL_binary_auc_sklearn
from sklearn.metrics import roc_auc_score
import numpy as np


def binary_auc(y_true, y_score):
    return np.array(roc_auc_score(y_true, y_score), dtype=np.float64)
