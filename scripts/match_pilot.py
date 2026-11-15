import csv
import json
from pathlib import Path

import numpy as np

MARS = Path("data/processed/mars/mars_terrain_features.csv")
EARTH_DIR = Path("data/processed/global/v2")
OUTPUT = Path("data/processed/pilot_matches.json")

FEATURES = [
    "mean_slope_deg",
    "p95_slope_deg",
    "roughness_m",
    "relief_m",
    "elevation_std_m",
]

def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

mars = load_csv(MARS)
earth = []

for path in sorted(EARTH_DIR.glob("*.csv")):
    earth.extend(load_csv(path))

if not mars or not earth:
    raise SystemExit("Missing Mars or Earth feature records")

def matrix(rows):
    return np.array(
        [[float(row[k]) for k in FEATURES] for row in rows],
        dtype=np.float64,
    )

m = matrix(mars)
e = matrix(earth)

if not np.isfinite(m).all() or not np.isfinite(e).all():
    raise ValueError("Non-finite feature values detected")

# Log compression reduces domination by large terrain values.
m = np.log1p(m)
e = np.log1p(e)

# Common scaling using the pooled pilot data.
combined = np.vstack([m, e])
mean = combined.mean(axis=0)
std = combined.std(axis=0)
std = np.maximum(std, 1e-9)

m = (m - mean) / std
e = (e - mean) / std

def unit_vectors(x):
    norm = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(norm, 1e-12)

similarity = unit_vectors(m) @ unit_vectors(e).T

# Standardized Euclidean distance for diagnostic comparison.
distance = np.sqrt(
    np.maximum(
        (m * m).sum(axis=1, keepdims=True)
        + (e * e).sum(axis=1)[None, :]
        - 2 * (m @ e.T),
        0,
    )
)

matches = []

for i, mars_row in enumerate(mars):
    ranked = np.argsort(-similarity[i])[:5]

    for rank, j in enumerate(ranked, 1):
        earth_row = earth[j]

        matches.append({
            "mars_patch_id": mars_row["patch_id"],
            "earth_patch_id": earth_row["patch_id"],
            "rank": rank,
            "latitude": float(earth_row["latitude"]),
            "longitude": float(earth_row["longitude"]),
            "tile_id": earth_row["tile_id"],
            "cosine_similarity": round(
                float(similarity[i, j]), 6
            ),
            "standardized_distance": round(
                float(distance[i, j]), 6
            ),
        })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w") as f:
    json.dump({
        "target_site": "Mars Jezero Crater",
        "experiment": "12-tile Earth pilot",
        "mars_patches": len(mars),
        "earth_patches": len(earth),
        "features": FEATURES,
        "matches": matches,
    }, f, indent=2)

print("Mars patches:", len(mars))
print("Earth patches:", len(earth))
print("Comparisons:", similarity.size)
print("Top-5 match records:", len(matches))
print("Output:", OUTPUT)

print("\nExample matches for first Mars patch:")
for item in matches[:5]:
    print(
        item["rank"],
        item["earth_patch_id"],
        "cosine:", item["cosine_similarity"],
        "distance:", item["standardized_distance"],
    )
