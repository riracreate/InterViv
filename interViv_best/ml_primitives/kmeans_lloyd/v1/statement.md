Implement one iteration of Lloyd's algorithm as `lloyd_step(points, centroids)`.

Assign every point to the nearest current centroid under squared Euclidean
distance. Then replace each centroid with the mean of the points assigned
to it. If a centroid receives no points, leave that centroid unchanged.

Also return the inertia after the update: the sum of squared distances
from each point to its new centroid. Inertia after the update is never
larger than inertia under the original centroids with the same nearest
assignment.

Return a dict with keys `assignments`, `centroids`, and `inertia`.
