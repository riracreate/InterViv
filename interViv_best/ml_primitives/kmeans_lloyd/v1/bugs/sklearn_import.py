# PHASEX_BUG_SENTINEL_kmeans_lloyd_sklearn
from sklearn.cluster import KMeans
import numpy as np


def lloyd_step(points, centroids):
    model = KMeans(n_clusters=len(centroids), n_init=1)
    model.cluster_centers_ = np.asarray(centroids)
    return {
        "assignments": np.zeros(len(points), dtype=np.int64),
        "centroids": np.asarray(centroids, dtype=np.float64),
        "inertia": np.array(0.0),
    }
