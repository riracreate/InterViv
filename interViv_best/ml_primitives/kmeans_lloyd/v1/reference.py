# PHASEX_REF_SENTINEL_kmeans_lloyd
import numpy as np


def lloyd_step(points, centroids):
    points = np.asarray(points, dtype=np.float64)
    centroids = np.asarray(centroids, dtype=np.float64)
    k = centroids.shape[0]
    dist2 = np.sum((points[:, None, :] - centroids[None, :, :]) ** 2, axis=-1)
    assignments = np.argmin(dist2, axis=1).astype(np.int64)
    membership = np.eye(k, dtype=np.float64)[assignments]
    counts = np.sum(membership, axis=0, keepdims=True).T
    occupied = counts[:, 0] > 0
    updated = (membership.T @ points) / np.maximum(counts, 1.0)
    new_centroids = np.where(occupied[:, None], updated, centroids)
    inertia = np.sum((points - new_centroids[assignments]) ** 2)
    return {
        "assignments": assignments,
        "centroids": new_centroids,
        "inertia": np.array(inertia, dtype=np.float64),
    }
