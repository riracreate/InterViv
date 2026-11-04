# PHASEX_PROP_SENTINEL_attention_scores
import numpy as np

SEED = 20260903
TOLERANCE = {"rtol": 1e-6, "atol": 1e-7}


def generate_cases(rng):
    return [
        {
            "id": "typical",
            "inputs": {
                "query": rng.normal(size=(2, 3, 8)).astype(np.float64),
                "key": rng.normal(size=(2, 5, 8)).astype(np.float64),
            },
        },
        {
            "id": "large_scores",
            "inputs": {
                "query": rng.normal(loc=40.0, scale=1.0, size=(2, 2, 4)).astype(np.float64),
                "key": rng.normal(loc=40.0, scale=1.0, size=(2, 3, 4)).astype(np.float64),
            },
        },
        {
            "id": "single_key",
            "inputs": {
                "query": rng.normal(size=(1, 4, 6)).astype(np.float64),
                "key": rng.normal(size=(1, 1, 6)).astype(np.float64),
            },
        },
        {
            "id": "aligned",
            "inputs": {
                "query": np.eye(4, dtype=np.float64)[None, :, :],
                "key": np.eye(4, dtype=np.float64)[None, :, :],
            },
        },
    ]


def _softmax(scores):
    shifted = scores - np.max(scores, axis=-1, keepdims=True)
    weights = np.exp(shifted)
    return weights / np.sum(weights, axis=-1, keepdims=True)


def last_axis_sums_to_1(inputs, actual, tolerance):
    totals = np.sum(actual, axis=-1)
    return bool(tolerance.close(totals, np.ones_like(totals)))


def no_nan_on_large_scores(inputs, actual, tolerance):
    return bool(np.isfinite(actual).all())


def non_negative(inputs, actual, tolerance):
    return bool(np.all(actual >= -tolerance.atol))


def scale_applied(inputs, actual, tolerance):
    query = np.asarray(inputs["query"], dtype=np.float64)
    key = np.asarray(inputs["key"], dtype=np.float64)
    dots = np.matmul(query, np.swapaxes(key, -1, -2))
    scaled = _softmax(dots / np.sqrt(np.array(query.shape[-1], dtype=np.float64)))
    unscaled = _softmax(dots)
    if tolerance.close(scaled, unscaled):
        return True
    return bool(tolerance.close(actual, scaled) and not tolerance.close(actual, unscaled))


PROPERTIES = {
    "last-axis sums to 1": last_axis_sums_to_1,
    "no NaN on large scores": no_nan_on_large_scores,
    "non-negative": non_negative,
    "scale applied": scale_applied,
}
