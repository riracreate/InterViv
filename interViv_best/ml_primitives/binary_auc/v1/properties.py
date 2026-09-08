# PHASEX_PROP_SENTINEL_binary_auc
import numpy as np

SEED = 20260904
TOLERANCE = {"rtol": 0.0, "atol": 1e-12}


def generate_cases(rng):
    mixed_labels = np.array([1, 1, 0, 0, 1, 0], dtype=np.int64)
    mixed_scores = rng.normal(size=mixed_labels.shape).astype(np.float64)
    return [
        {
            "id": "separated",
            "inputs": {
                "y_true": np.array([1, 1, 0, 0], dtype=np.int64),
                "y_score": np.array([0.9, 0.8, 0.2, 0.1], dtype=np.float64),
            },
        },
        {
            "id": "inverted",
            "inputs": {
                "y_true": np.array([1, 1, 0, 0], dtype=np.int64),
                "y_score": np.array([0.1, 0.2, 0.8, 0.9], dtype=np.float64),
            },
        },
        {
            "id": "ties",
            "inputs": {
                "y_true": np.array([1, 1, 0, 0], dtype=np.int64),
                "y_score": np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float64),
            },
        },
        {
            "id": "mixed",
            "inputs": {"y_true": mixed_labels, "y_score": mixed_scores},
        },
        {
            "id": "partial_ties",
            "inputs": {
                "y_true": np.array([1, 1, 0, 0], dtype=np.int64),
                "y_score": np.array([0.7, 0.4, 0.4, 0.1], dtype=np.float64),
            },
        },
    ]


def range_in_unit_interval(inputs, actual, tolerance):
    value = np.asarray(actual, dtype=np.float64)
    return bool(np.isfinite(value) and value >= -tolerance.atol and value <= 1.0 + tolerance.atol)


def perfect_ranking_is_one(inputs, actual, tolerance):
    y_true, y_score = inputs["y_true"], inputs["y_score"]
    if y_score[y_true == 1].min() > y_score[y_true == 0].max():
        return bool(tolerance.close(np.asarray(actual), np.array(1.0)))
    return True


def inverted_ranking_is_zero(inputs, actual, tolerance):
    y_true, y_score = inputs["y_true"], inputs["y_score"]
    if y_score[y_true == 1].max() < y_score[y_true == 0].min():
        return bool(tolerance.close(np.asarray(actual), np.array(0.0)))
    return True


def ties_are_half(inputs, actual, tolerance):
    if np.unique(inputs["y_score"]).size == 1:
        return bool(tolerance.close(np.asarray(actual), np.array(0.5)))
    return True


PROPERTIES = {
    "range in unit interval": range_in_unit_interval,
    "perfect ranking is 1": perfect_ranking_is_one,
    "inverted ranking is 0": inverted_ranking_is_zero,
    "ties are half": ties_are_half,
}
