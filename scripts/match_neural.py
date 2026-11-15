import csv
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.neighbors import NearestNeighbors

from train_terrain_encoder import TerrainAutoencoder

ROOT = Path("data/processed/ml_patches")
MODEL = Path("models/terrain_encoder/best_model.pt")
METADATA = Path("data/processed/global/v3_complete")
import os

OUTPUT = Path(
    os.environ.get(
        "TERRAMIRROR_MATCH_OUTPUT",
        "outputs/neural",
    )
)

OUTPUT.mkdir(parents=True, exist_ok=True)

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

torch.set_grad_enabled(False)

checkpoint = torch.load(
    MODEL,
    map_location="cpu",
    weights_only=True,
)

model = TerrainAutoencoder(
    latent_dim=checkpoint["latent_dim"]
).to(DEVICE)

model.load_state_dict(checkpoint["model_state"])
model.eval()

SCALE = checkpoint["scale_m"]
CLIP = checkpoint["clip"]

print("=== TERRAMIRROR NEURAL MATCHING ===")
print("Device:", DEVICE)
print("Embedding dimensions:", checkpoint["latent_dim"])


def encode_file(path):
    with np.load(path, allow_pickle=False) as data:
        elevation = data["elevation"].astype("float32")
        mask = data["valid_mask"].astype("float32")
        ids = data["patch_ids"].tolist()

    if elevation.shape != mask.shape:
        raise ValueError(f"Shape mismatch: {path}")

    if elevation.ndim != 3 or elevation.shape[1:] != (64, 64):
        raise ValueError(f"Invalid patch shape: {path}")

    if not np.isfinite(elevation).all():
        raise ValueError(f"Non-finite elevations: {path}")

    if np.any(mask.mean(axis=(1, 2)) < 0.95):
        raise ValueError(f"Insufficient valid terrain: {path}")

    normalized = np.clip(
        elevation / SCALE, -CLIP, CLIP
    ) * mask

    inputs = np.stack(
        [normalized, mask],
        axis=1,
    )

    embeddings = []

    for start in range(0, len(inputs), 128):
        batch = torch.from_numpy(
            inputs[start:start + 128]
        ).to(DEVICE)

        vectors = model.encoder(batch)

        embeddings.append(
            vectors.cpu().numpy()
        )

    return (
        np.vstack(embeddings).astype("float32"),
        ids,
    )


# Encode Mars
mars_vectors, mars_ids = encode_file(
    ROOT / "mars_jezero.npz"
)

# Encode all Earth tiles
earth_vectors = []
earth_ids = []

for path in sorted((ROOT / "earth").glob("*.npz")):
    vectors, ids = encode_file(path)

    earth_vectors.append(vectors)
    earth_ids.extend(ids)

earth_vectors = np.vstack(earth_vectors)

if len(set(earth_ids)) != len(earth_ids):
    raise ValueError("Duplicate Earth IDs")

if len(set(mars_ids)) != len(mars_ids):
    raise ValueError("Duplicate Mars IDs")

# Load coordinates, quality flags and land-cover data
earth_info = {}

for path in sorted(METADATA.glob("*.csv")):
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            patch_id = row["patch_id"]

            if patch_id in earth_info:
                raise ValueError(f"Duplicate metadata: {patch_id}")

            earth_info[patch_id] = row

if set(earth_ids) != set(earth_info):
    raise ValueError("Earth vectors and metadata do not match")

# Euclidean distance in the learned embedding space.
# These are experimental distances, not calibrated
# physical-terrain similarity percentages.
neighbors = NearestNeighbors(
    n_neighbors=5,
    metric="euclidean",
    algorithm="brute",
)

neighbors.fit(earth_vectors)

distances, indices = neighbors.kneighbors(mars_vectors)

results = []

for i, mars_id in enumerate(mars_ids):
    candidates = []

    for rank, (distance, index) in enumerate(
        zip(distances[i], indices[i]), 1
    ):
        earth_id = earth_ids[int(index)]
        info = earth_info[earth_id]

        candidates.append({
            "rank": rank,
            "earth_patch_id": earth_id,
            "latitude": float(info["latitude"]),
            "longitude": float(info["longitude"]),
            "tile_id": info["tile_id"],
            "embedding_distance": float(distance),
            "dominant_landcover": info["dominant_landcover"],
            "landcover_status": info["landcover_status"],
            "quality_status": info["quality_status"],
            "hem_coverage": float(info["hem_coverage"]),
        })

    results.append({
        "mars_patch_id": mars_id,
        "matches": candidates,
    })

np.savez_compressed(
    OUTPUT / "embeddings.npz",
    mars_embeddings=mars_vectors,
    earth_embeddings=earth_vectors,
    mars_patch_ids=np.asarray(mars_ids),
    earth_patch_ids=np.asarray(earth_ids),
)

payload = {
    "model": "terrain_convolutional_autoencoder_v1",
    "ranking_method": "euclidean_latent_distance",
    "status": "experimental_not_scientifically_validated",
    "mars_patches": len(mars_ids),
    "earth_patches": len(earth_ids),
    "embedding_dimensions": mars_vectors.shape[1],
    "results": results,
}

(OUTPUT / "neural_matches.json").write_text(
    json.dumps(payload, indent=2)
)

print("Mars patches:", len(mars_ids))
print("Earth patches:", len(earth_ids))
print("Embedding dimensions:", mars_vectors.shape[1])
print("Comparisons:", len(mars_ids) * len(earth_ids))
print("Match records:", sum(len(r["matches"]) for r in results))

print("\nFirst Mars patch:")
for item in results[0]["matches"]:
    print(
        f"Rank {item['rank']}: "
        f"{item['latitude']:.5f}, "
        f"{item['longitude']:.5f} | "
        f"distance={item['embedding_distance']:.5f} | "
        f"cover={item['dominant_landcover']}"
    )

print("\nSaved:", OUTPUT / "embeddings.npz")
print("Saved:", OUTPUT / "neural_matches.json")
print("\nRESULT: PASS")
