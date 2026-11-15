import csv
import json
from pathlib import Path
from collections import Counter

import numpy as np

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

mars = read_csv(
    Path("data/processed/mars/mars_terrain_features.csv")
)

earth = []
for path in sorted(
    Path("data/processed/global/v3_complete").glob("*.csv")
):
    earth.extend(read_csv(path))

data = json.loads(
    Path("outputs/neural/neural_matches.json").read_text()
)

mars_by_id = {r["patch_id"]: r for r in mars}
earth_by_id = {r["patch_id"]: r for r in earth}

if len(mars_by_id) != len(mars):
    raise ValueError("Duplicate Mars IDs")
if len(earth_by_id) != len(earth):
    raise ValueError("Duplicate Earth IDs")

mars_ids = list(mars_by_id)
earth_ids = list(earth_by_id)

if len(mars) != 255 or len(earth) != 3505:
    raise ValueError("Unexpected dataset size")

def matrix(rows):
    return np.asarray(
        [[float(r[f]) for f in FEATURES] for r in rows],
        dtype=np.float64,
    )

M = np.log1p(matrix([mars_by_id[i] for i in mars_ids]))
E = np.log1p(matrix([earth_by_id[i] for i in earth_ids]))

if not np.isfinite(M).all() or not np.isfinite(E).all():
    raise ValueError("Invalid feature measurements")

# Standardize using Earth candidate distribution.
mean = E.mean(axis=0)
std = np.maximum(E.std(axis=0), 1e-9)

M = (M - mean) / std
E = (E - mean) / std

distances = np.linalg.norm(
    M[:, None, :] - E[None, :, :],
    axis=2,
)

earth_index = {pid: i for i, pid in enumerate(earth_ids)}
mars_index = {pid: i for i, pid in enumerate(mars_ids)}

best_index = distances.argmin(axis=1)

neural_winners = {}
for result in data["results"]:
    pid = result["mars_patch_id"]
    matches = result["matches"]

    if pid in neural_winners or not matches:
        raise ValueError("Duplicate or empty neural result")

    neural_winners[pid] = matches[0]

if set(neural_winners) != set(mars_ids):
    raise ValueError("Neural results do not match Mars IDs")

same = 0
neural_physical_distances = []
baseline_physical_distances = []
neural_ranks = []
quality = Counter()
landcover = Counter()
tiles = Counter()

for mars_id in mars_ids:
    i = mars_index[mars_id]
    winner = neural_winners[mars_id]
    earth_id = winner["earth_patch_id"]

    if earth_id not in earth_index:
        raise ValueError(f"Unknown Earth patch: {earth_id}")

    j = earth_index[earth_id]
    baseline_j = int(best_index[i])

    same += int(j == baseline_j)

    d = float(distances[i, j])
    best_d = float(distances[i, baseline_j])

    neural_physical_distances.append(d)
    baseline_physical_distances.append(best_d)

    # Rank among all Earth candidates using the
    # physical feature baseline.
    rank = 1 + int(np.sum(distances[i] < d - 1e-9))
    neural_ranks.append(rank)

    quality[winner["quality_status"]] += 1
    landcover[winner["dominant_landcover"]] += 1
    tiles[winner["tile_id"]] += 1

neural_physical_distances = np.asarray(
    neural_physical_distances
)
baseline_physical_distances = np.asarray(
    baseline_physical_distances
)
neural_ranks = np.asarray(neural_ranks)

report = {
    "mars_patches": len(mars),
    "earth_patches": len(earth),
    "top1_agreement_count": same,
    "top1_agreement_fraction": same / len(mars),
    "neural_mean_physical_distance":
        float(neural_physical_distances.mean()),
    "baseline_mean_physical_distance":
        float(baseline_physical_distances.mean()),
    "neural_median_physical_rank":
        float(np.median(neural_ranks)),
    "neural_top10_physical_fraction":
        float(np.mean(neural_ranks <= 10)),
    "unique_neural_winners": len({
        r["earth_patch_id"] for r in neural_winners.values()
    }),
    "quality_counts": dict(quality),
    "landcover_counts": dict(landcover),
    "tile_counts": dict(tiles),
}

output = Path("outputs/neural/evaluation.json")
output.write_text(json.dumps(report, indent=2))

print("=== TERRAMIRROR ML EVALUATION ===")
print("Mars patches:", len(mars))
print("Earth candidates:", len(earth))
print("Exact top-1 agreement:", same)
print("Agreement rate:", round(100 * same / len(mars), 2), "%")

print(
    "Mean physical distance - neural winners:",
    round(report["neural_mean_physical_distance"], 4)
)
print(
    "Mean physical distance - baseline winners:",
    round(report["baseline_mean_physical_distance"], 4)
)
print(
    "Median neural winner's physical rank:",
    report["neural_median_physical_rank"]
)
print(
    "Neural winners within physical top 10:",
    round(100 * report["neural_top10_physical_fraction"], 2),
    "%"
)
print("Unique neural winners:", report["unique_neural_winners"])

print("\nTop Earth tiles:")
for tile, count in tiles.most_common(10):
    print(tile, count)

print("\nQuality status:", dict(quality))
print("Land cover:", dict(landcover))

print("\nSaved:", output)
print("EVALUATION COMPLETE")
