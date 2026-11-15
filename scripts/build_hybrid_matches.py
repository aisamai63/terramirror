import csv
import json
from pathlib import Path

import numpy as np

FEATURES = [
    "mean_slope_deg",
    "p95_slope_deg",
    "roughness_m",
    "relief_m",
    "elevation_std_m",
]

import os

OUT = Path(
    os.environ.get(
        "TERRAMIRROR_MATCH_OUTPUT",
        "outputs/neural",
    )
)
OUT.mkdir(parents=True, exist_ok=True)


def read_rows(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


mars = read_rows(
    Path("data/processed/mars/mars_terrain_features.csv")
)

earth = []
for path in sorted(
    Path("data/processed/global/v3_complete").glob("*.csv")
):
    earth.extend(read_rows(path))

with np.load(OUT / "embeddings.npz", allow_pickle=False) as data:
    mars_vectors = data["mars_embeddings"].copy()
    earth_vectors = data["earth_embeddings"].copy()
    mars_ids = data["mars_patch_ids"].tolist()
    earth_ids = data["earth_patch_ids"].tolist()

mars_rows = {r["patch_id"]: r for r in mars}
earth_rows = {r["patch_id"]: r for r in earth}

# Validate consistency without fixing the Earth catalog size.
# The index must accept newly discovered Earth patches.

if len(mars_ids) == 0 or len(earth_ids) == 0:
    raise ValueError("Mars and Earth embeddings must not be empty")

if len(mars_ids) != len(set(mars_ids)):
    raise ValueError("Duplicate Mars patch IDs")

if len(earth_ids) != len(set(earth_ids)):
    raise ValueError("Duplicate Earth patch IDs")

if len(mars_ids) != len(mars_vectors):
    raise ValueError("Mars embedding count mismatch")

if len(earth_ids) != len(earth_vectors):
    raise ValueError("Earth embedding count mismatch")

if set(mars_ids) != set(mars_rows):
    raise ValueError("Mars features and embeddings do not match")

if set(earth_ids) != set(earth_rows):
    raise ValueError("Earth features and embeddings do not match")

print("Validated Mars patches:", len(mars_ids))
print("Validated Earth patches:", len(earth_ids))


def feature_matrix(rows, ids):
    return np.log1p(np.array([
        [float(rows[pid][key]) for key in FEATURES]
        for pid in ids
    ], dtype=np.float64))


E = feature_matrix(earth_rows, earth_ids)
M = feature_matrix(mars_rows, mars_ids)

mean = E.mean(axis=0)
std = np.maximum(E.std(axis=0), 1e-9)

E = (E - mean) / std
M = (M - mean) / std

results = []

for i, mars_id in enumerate(mars_ids):
    physical = np.linalg.norm(E - M[i], axis=1)

    # Physical preselection, without arbitrary weighted blending.
    pool = np.argsort(physical, kind="stable")[:50]

    neural = np.linalg.norm(
        earth_vectors[pool] - mars_vectors[i],
        axis=1
    )

    order = np.argsort(neural, kind="stable")[:5]

    matches = []
    for rank, k in enumerate(order, 1):
        j = int(pool[k])
        info = earth_rows[earth_ids[j]]

        matches.append({
            "rank": rank,
            "earth_patch_id": earth_ids[j],
            "latitude": float(info["latitude"]),
            "longitude": float(info["longitude"]),
            "physical_feature_distance": float(physical[j]),
            "neural_embedding_distance": float(neural[k]),
            "physical_candidate_rank": int(
                np.sum(physical < physical[j] - 1e-9) + 1
            ),
            "dominant_landcover": info["dominant_landcover"],
            "quality_status": info["quality_status"],
            "tile_id": info["tile_id"],
        })

    results.append({
        "mars_patch_id": mars_id,
        "matches": matches,
    })

payload = {
    "method": "physical_top50_then_neural_rerank",
    "status": "experimental_not_validated",
    "earth_search_scope": "processed_pilot_tiles_only",
    "mars_patches": len(mars_ids),
    "earth_patches": len(earth_ids),
    "results": results,
}

path = OUT / "hybrid_matches.json"
path.write_text(json.dumps(payload, indent=2))

print("=== TERRAMIRROR HYBRID DISCOVERY ===")
print("Mars patches:", len(mars_ids))
print("Earth patches:", len(earth_ids))
print("Shortlist size:", 50)
print("Top matches per Mars patch:", 5)
print("Total results:", sum(len(r["matches"]) for r in results))

print("\nFirst Mars patch:")
for match in results[0]["matches"]:
    print(
        f"Rank {match['rank']} | "
        f"{match['latitude']:.5f}, "
        f"{match['longitude']:.5f} | "
        f"physical={match['physical_feature_distance']:.4f} | "
        f"neural={match['neural_embedding_distance']:.4f} | "
        f"physical rank={match['physical_candidate_rank']}"
    )

print("\nSaved:", path)
print("RESULT: PASS")
