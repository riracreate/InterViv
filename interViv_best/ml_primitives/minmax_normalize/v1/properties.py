# PHASEX_PROP_SENTINEL_minmax_normalize
import numpy as np

SEED = 20260905
TOLERANCE = {"rtol": 1e-9, "atol": 1e-10}


def generate_cases(rng):
    return [
        {"id": "typical", "inputs": {"x": rng.normal(size=(4, 6)).astype(np.float64)}},
        {
            "id": "constant_rows",
            "inputs": {"x": np.array([[2.0, 2.0, 2.0], [0.0, 1.0, 2.0]], dtype=np.float64)},
        },
        {
            "id": "negative",
            "inputs": {"x": np.array([[-5.0, -1.0, 3.0]], dtype=np.float64)},
        },
        {
            "id": "rank3",
            "inputs": {"x": rng.uniform(-2.0, 2.0, size=(2, 3, 5)).astype(np.float64)},
        },
    ]


def range_in_unit_interval(inputs, actual, tolerance):
    return bool(np.all(actual >= -tolerance.atol) and np.all(actual <= 1.0 + tolerance.atol))


def no_nan_on_constant_rows(inputs, actual, tolerance):
    return bool(np.isfinite(actual).all())


def extrema_map_to_bounds(inputs, actual, tolerance):
    x = inputs["x"]
    span = np.max(x, axis=-1) - np.min(x, axis=-1)
    varying = span > 0
    if not np.any(varying):
        return True
    lows = np.min(actual, axis=-1)
    highs = np.max(actual, axis=-1)
    return bool(
        tolerance.close(lows[varying], np.zeros_like(lows[varying]))
        and tolerance.close(highs[varying], np.ones_like(highs[varying]))
    )


def order_preserved(inputs, actual, tolerance):
    return bool(np.array_equal(np.argsort(inputs["x"], axis=-1), np.argsort(actual, axis=-1)))


PROPERTIES = {
    "range in unit interval": range_in_unit_interval,
    "no NaN on constant rows": no_nan_on_constant_rows,
    "extrema map to bounds": extrema_map_to_bounds,
    "order preserved": order_preserved,
}
