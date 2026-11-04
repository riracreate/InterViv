# PHASEX_PROP_SENTINEL_kmeans_lloyd
import numpy as np

SEED = 20260902
TOLERANCE = {"rtol": 1e-8, "atol": 1e-9}


def generate_cases(rng):
    blob_a = rng.normal(loc=0.0, scale=0.15, size=(8, 2))
    blob_b = rng.normal(loc=3.0, scale=0.15, size=(8, 2))
    return [
        {
            "id": "two_blobs",
            "inputs": {
                "points": np.concatenate([blob_a, blob_b]).astype(np.float64),
                "centroids": np.array([[0.0, 0.0], [3.0, 3.0]], dtype=np.float64),
            },
        },
        {
            "id": "empty_cluster",
            "inputs": {
                "points": np.array(
                    [[0.0, 0.0], [0.1, 0.0], [1.0, 1.0], [1.1, 1.0]],
                    dtype=np.float64,
                ),
                "centroids": np.array(
                    [[0.0, 0.0], [1.0, 1.0], [50.0, -50.0]],
                    dtype=np.float64,
                ),
            },
        },
        {
            "id": "jittered",
            "inputs": {
                "points": rng.normal(size=(12, 3)).astype(np.float64),
                "centroids": rng.normal(size=(4, 3)).astype(np.float64),
            },
        },
        {
            "id": "collocated",
            "inputs": {
                "points": np.array([[1.0, 1.0], [1.0, 1.0], [2.0, 2.0]], dtype=np.float64),
                "centroids": np.array([[1.0, 1.0], [2.0, 2.0]], dtype=np.float64),
            },
        },
    ]


def _squared_distances(points, centroids):
    return np.sum((points[:, None, :] - centroids[None, :, :]) ** 2, axis=-1)


def nearest_centroid_assignment(inputs, actual, tolerance):
    expected = np.argmin(_squared_distances(inputs["points"], inputs["centroids"]), axis=1)
    return bool(np.array_equal(actual["assignments"], expected))


def inertia_non_increasing(inputs, actual, tolerance):
    points, centroids = inputs["points"], inputs["centroids"]
    assignments = np.argmin(_squared_distances(points, centroids), axis=1)
    previous = np.sum((points - centroids[assignments]) ** 2)
    return bool(actual["inertia"] <= previous + tolerance.atol)


def empty_clusters_keep_centroid(inputs, actual, tolerance):
    points, centroids = inputs["points"], inputs["centroids"]
    assigned = np.argmin(_squared_distances(points, centroids), axis=1)
    k = centroids.shape[0]
    occupied = np.zeros(k, dtype=bool)
    occupied[assigned] = True
    kept = actual["centroids"][~occupied]
    original = centroids[~occupied]
    if kept.size == 0:
        return True
    return bool(tolerance.close(kept, original))


def assignment_indices_in_range(inputs, actual, tolerance):
    k = inputs["centroids"].shape[0]
    n = inputs["points"].shape[0]
    assignments = actual["assignments"]
    return bool(
        assignments.shape == (n,)
        and np.issubdtype(assignments.dtype, np.integer)
        and np.all((assignments >= 0) & (assignments < k))
    )


PROPERTIES = {
    "nearest-centroid assignment": nearest_centroid_assignment,
    "inertia non-increasing": inertia_non_increasing,
    "empty clusters keep previous centroid": empty_clusters_keep_centroid,
    "assignment indices in range": assignment_indices_in_range,
}
