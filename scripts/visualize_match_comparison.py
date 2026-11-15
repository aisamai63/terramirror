import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path("data/processed/ml_patches")
OUTPUT = Path("outputs/neural")
OUTPUT.mkdir(parents=True, exist_ok=True)

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

def load_patches(paths):
    result = {}

    for path in paths:
        with np.load(path, allow_pickle=False) as data:
            z = data["elevation"]
            mask = data["valid_mask"].astype(bool)
            ids = data["patch_ids"]

            for i, patch_id in enumerate(ids):
                if str(patch_id) in result:
                    raise ValueError(f"Duplicate patch {patch_id}")

                result[str(patch_id)] = (
                    z[i].copy(),
                    mask[i].copy(),
                )

    return result

mars_patches = load_patches([ROOT / "mars_jezero.npz"])
earth_patches = load_patches(
    sorted((ROOT / "earth").glob("*.npz"))
)

mars_rows = read_csv(
    Path("data/processed/mars/mars_terrain_features.csv")
)

earth_rows = []
for path in sorted(
    Path("data/processed/global/v3_complete").glob("*.csv")
):
    earth_rows.extend(read_csv(path))

mars_by_id = {r["patch_id"]: r for r in mars_rows}
earth_by_id = {r["patch_id"]: r for r in earth_rows}

matches = json.loads(
    (OUTPUT / "neural_matches.json").read_text()
)

match_by_id = {
    row["mars_patch_id"]: row["matches"][0]
    for row in matches["results"]
}

def feature_array(rows):
    return np.log1p(np.array([
        [float(row[name]) for name in FEATURES]
        for row in rows
    ], dtype=np.float64))

E = feature_array(earth_rows)
M = feature_array(mars_rows)

mean = E.mean(axis=0)
std = np.maximum(E.std(axis=0), 1e-9)

E = (E - mean) / std
M = (M - mean) / std

mars_ids = [r["patch_id"] for r in mars_rows]
earth_ids = [r["patch_id"] for r in earth_rows]

# First, middle and final Mars patches.
selected = sorted(set([0, len(mars_ids)//2, len(mars_ids)-1]))

fig, axes = plt.subplots(
    len(selected), 3, figsize=(13, 4 * len(selected)),
    constrained_layout=True
)

if len(selected) == 1:
    axes = axes[None, :]

for row_number, mars_index in enumerate(selected):
    mars_id = mars_ids[mars_index]

    neural_id = match_by_id[mars_id]["earth_patch_id"]

    physical_distances = np.linalg.norm(
        E - M[mars_index], axis=1
    )

    baseline_idx = int(np.argmin(physical_distances))
    baseline_id = earth_ids[baseline_idx]

    choices = [
        (mars_id, "Mars — Jezero"),
        (neural_id, "Neural top match"),
        (baseline_id, "Physical-feature top match"),
    ]

    # One elevation scale within each row, so differences
    # in relief remain visible rather than being hidden
    # by separate automatic color scaling.
    limits = []
    for pid, _ in choices:
        z, valid = (
            mars_patches[pid]
            if pid in mars_patches
            else earth_patches[pid]
        )
        limits.append(
            np.percentile(np.abs(z[valid]), 98)
        )

    color_limit = max(float(max(limits)), 1.0)

    for col_number, (pid, title) in enumerate(choices):
        ax = axes[row_number, col_number]

        z, valid = (
            mars_patches[pid]
            if pid in mars_patches
            else earth_patches[pid]
        )

        image = np.ma.masked_where(~valid, z)

        ax.imshow(
            image,
            cmap="terrain",
            vmin=-color_limit,
            vmax=color_limit,
            interpolation="nearest",
        )

        if pid == mars_id:
            distance_text = f"Patch {mars_index}"
        else:
            j = earth_ids.index(pid)
            distance_text = (
                f"Feature distance: "
                f"{physical_distances[j]:.3f}"
            )

        ax.set_title(
            f"{title}\n{distance_text}",
            fontsize=10
        )
        ax.set_xticks([])
        ax.set_yticks([])

    print(
        f"Mars {mars_index}: "
        f"neural={neural_id} | "
        f"baseline={baseline_id}",
        flush=True
    )

path = OUTPUT / "terrain_comparison.png"
fig.savefig(path, dpi=160)
plt.close(fig)

print("\nSaved:", path)
print("VISUALIZATION COMPLETE")
