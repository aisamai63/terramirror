import csv
from pathlib import Path
from collections import Counter

import numpy as np

MARS = Path("data/processed/mars/mars_terrain_features.csv")
EARTH = Path("data/processed/global/v2")

FEATURES = [
    "mean_slope_deg",
    "p95_slope_deg",
    "roughness_m",
    "relief_m",
    "elevation_std_m",
]

def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))

mars = read_csv(MARS)
earth = []

for path in sorted(EARTH.glob("*.csv")):
    earth.extend(read_csv(path))

def features(rows):
    return np.array([
        [float(row[key]) for key in FEATURES]
        for row in rows
    ], dtype=np.float64)

M = np.log1p(features(mars))
E = np.log1p(features(earth))

# Establish scaling from the Earth candidate distribution.
mean = E.mean(axis=0)
std = np.maximum(E.std(axis=0), 1e-9)

M = (M - mean) / std
E = (E - mean) / std

# Cosine similarity
M_unit = M / np.maximum(
    np.linalg.norm(M, axis=1, keepdims=True), 1e-12
)
E_unit = E / np.maximum(
    np.linalg.norm(E, axis=1, keepdims=True), 1e-12
)

cosine = M_unit @ E_unit.T

# Standardized Euclidean distance
distance = np.sqrt(np.maximum(
    np.sum(M**2, axis=1, keepdims=True)
    + np.sum(E**2, axis=1)[None, :]
    - 2 * M @ E.T,
    0,
))

cosine_best = np.argmax(cosine, axis=1)
distance_best = np.argmin(distance, axis=1)

agreement = np.mean(cosine_best == distance_best)

print("Mars patches:", len(mars))
print("Earth patches:", len(earth))
print("Total comparisons:", distance.size)
print("Top-1 ranking agreement:", round(agreement * 100, 2), "%")

print("\nTop Earth tiles by Euclidean distance:")
counts = Counter(
    earth[int(j)]["tile_id"]
    for j in distance_best
)

for tile, count in counts.most_common(10):
    print(tile, count)

print("\nFirst Mars patch comparison:")

for label, index in [
    ("Cosine winner", cosine_best[0]),
    ("Distance winner", distance_best[0]),
]:
    index = int(index)
    print(
        label,
        earth[index]["patch_id"],
        "cosine =", round(float(cosine[0, index]), 6),
        "distance =", round(float(distance[0, index]), 6),
    )
