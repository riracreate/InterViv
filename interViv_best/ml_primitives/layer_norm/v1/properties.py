# PHASEX_PROP_SENTINEL_layer_norm
import numpy as np

SEED = 20260906
TOLERANCE = {"rtol": 1e-6, "atol": 1e-6}
EPS = 1e-5


def generate_cases(rng):
    return [
        {"id": "typical", "inputs": {"x": rng.normal(size=(3, 8)).astype(np.float64)}},
        {
            "id": "constant_rows",
            "inputs": {"x": np.array([[4.0, 4.0, 4.0, 4.0], [1.0, 2.0, 3.0, 4.0]], dtype=np.float64)},
        },
        {
            "id": "rank3",
            "inputs": {"x": rng.normal(size=(2, 2, 6)).astype(np.float64)},
        },
        {
            "id": "shifted",
            "inputs": {"x": (rng.normal(size=(4, 5)) + 25.0).astype(np.float64)},
        },
    ]


def last_axis_mean_near_zero(inputs, actual, tolerance):
    means = np.mean(actual, axis=-1)
    return bool(tolerance.close(means, np.zeros_like(means)))


def no_nan_on_constant_rows(inputs, actual, tolerance):
    return bool(np.isfinite(actual).all())


def last_axis_unit_scale(inputs, actual, tolerance):
    variance = np.var(inputs["x"], axis=-1)
    mask = variance > 1e-2
    if not np.any(mask):
        return True
    out_var = np.var(actual, axis=-1)[mask]
    return bool(np.allclose(out_var, np.ones_like(out_var), rtol=0.0, atol=1e-3))


def translation_invariant_per_row(inputs, actual, tolerance):
    x = inputs["x"]
    shifted = x + 11.0
    mean = np.mean(shifted, axis=-1, keepdims=True)
    variance = np.var(shifted, axis=-1, keepdims=True)
    expected = (shifted - mean) / np.sqrt(variance + EPS)
    return bool(tolerance.close(actual, expected))


PROPERTIES = {
    "last-axis mean near zero": last_axis_mean_near_zero,
    "no NaN on constant rows": no_nan_on_constant_rows,
    "last-axis unit scale": last_axis_unit_scale,
    "translation invariant per row": translation_invariant_per_row,
}
