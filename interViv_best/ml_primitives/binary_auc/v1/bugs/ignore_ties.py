# PHASEX_BUG_SENTINEL_binary_auc_ignore_ties
import numpy as np


def binary_auc(y_true, y_score):
    y_true = np.asarray(y_true).reshape(-1)
    y_score = np.asarray(y_score, dtype=np.float64).reshape(-1)
    positives = y_score[y_true == 1]
    negatives = y_score[y_true == 0]
    greater = positives[:, None] > negatives[None, :]
    value = greater.sum() / (positives.size * negatives.size)
    return np.array(value, dtype=np.float64)
