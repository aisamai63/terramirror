import csv
from pathlib import Path

import numpy as np

FEATURES = [
    "mean_slope_deg",
    "p95_slope_deg",
    "roughness_m",
    "relief_m",
    "elevation_std_m",
]

def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

mars = read_rows(
    "data/processed/mars/mars_terrain_features.csv"
)

earth = []
for path in sorted(
    Path("data/processed/global/v2").glob("*.csv")
):
    earth.extend(read_rows(path))

def matrix(rows):
    return np.array([
        [float(row[k]) for k in FEATURES]
        for row in rows
    ], dtype=float)

M_raw = matrix(mars)
E_raw = matrix(earth)

M = np.log1p(M_raw)
E = np.log1p(E_raw)

mean = E.mean(axis=0)
std = np.maximum(E.std(axis=0), 1e-9)

M = (M - mean) / std
E = (E - mean) / std

norm_m = np.linalg.norm(M, axis=1)
norm_e = np.linalg.norm(E, axis=1)

cosine = (
    (M @ E.T)
    / np.maximum(
        norm_m[:, None] * norm_e[None, :],
        1e-12
    )
)

dist = np.sqrt(np.maximum(
    (M * M).sum(axis=1, keepdims=True)
    + (E * E).sum(axis=1)[None, :]
    - 2 * M @ E.T,
    0
))

cos_idx = np.argmax(cosine, axis=1)
dst_idx = np.argmin(dist, axis=1)

rows = np.arange(len(mars))

cos_distance = dist[rows, cos_idx]
best_distance = dist[rows, dst_idx]

extra_distance = cos_distance - best_distance

print("=== RANKING QUALITY ===")
print("Exact agreement:", np.mean(cos_idx == dst_idx))
print("Mean nearest distance:", best_distance.mean())
print("Mean cosine-winner distance:", cos_distance.mean())
print("Median distance gap:", np.median(extra_distance))
print("95th percentile gap:", np.percentile(extra_distance, 95))
print("Maximum distance gap:", extra_distance.max())

print("\n=== FEATURE DISTRIBUTIONS ===")
for i, feature in enumerate(FEATURES):
    print(
        feature,
        "| Mars median:", round(float(np.median(M_raw[:, i])), 3),
        "| Earth median:", round(float(np.median(E_raw[:, i])), 3)
    )

print("\n=== MATCH DIVERSITY ===")
print("Unique cosine winners:", len(set(cos_idx)))
print("Unique Euclidean winners:", len(set(dst_idx)))
