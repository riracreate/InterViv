# PHASEX_PROP_SENTINEL_softmax_stable
import numpy as np

SEED = 20260901
TOLERANCE = {"rtol": 1e-7, "atol": 1e-8}


def generate_cases(rng):
    return [
        {"id": "typical", "inputs": {"logits": rng.normal(size=(4, 5)).astype(np.float64)}},
        {
            "id": "large_positive",
            "inputs": {"logits": rng.normal(loc=1.0e8, scale=8.0, size=(3, 4)).astype(np.float64)},
        },
        {
            "id": "large_negative",
            "inputs": {"logits": rng.normal(loc=-1.0e8, scale=8.0, size=(3, 4)).astype(np.float64)},
        },
        {
            "id": "peaked",
            "inputs": {"logits": np.array([[0.0, 30.0, 0.0], [4.0, 4.0, 4.2]], dtype=np.float64)},
        },
    ]


def row_sums_to_1(inputs, actual, tolerance):
    totals = np.sum(actual, axis=-1)
    return bool(tolerance.close(totals, np.ones_like(totals)))


def no_nan_on_large_logits(inputs, actual, tolerance):
    return bool(np.isfinite(actual).all())


def non_negative(inputs, actual, tolerance):
    return bool(np.all(actual >= -tolerance.atol))


def argmax_matches_logits(inputs, actual, tolerance):
    return bool(np.array_equal(
        np.argmax(actual, axis=-1),
        np.argmax(inputs["logits"], axis=-1),
    ))


PROPERTIES = {
    "row sums to 1": row_sums_to_1,
    "no NaN on large logits": no_nan_on_large_logits,
    "non-negative": non_negative,
    "argmax matches logits": argmax_matches_logits,
}
