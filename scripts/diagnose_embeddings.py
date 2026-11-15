from pathlib import Path
import numpy as np

ROOT = Path("data/processed/ml_patches")

def summarize(name, paths):
    reliefs = []
    clipped = 0
    total = 0
    patches = 0

    for path in paths:
        with np.load(path, allow_pickle=False) as data:
            z = data["elevation"].astype(np.float32)
            mask = data["valid_mask"].astype(bool)

        for elevation, valid in zip(z, mask):
            values = elevation[valid]

            if values.size == 0:
                continue

            reliefs.append(
                float(np.percentile(values, 95) -
                      np.percentile(values, 5))
            )
            clipped += np.count_nonzero(
                np.abs(values / 200.0) > 5.0
            )
            total += values.size
            patches += 1

    print(f"\n=== {name} ===")
    print("Patches:", patches)
    print("Median P95-P5 relief (m):",
          round(float(np.median(reliefs)), 2))
    print("P95 P95-P5 relief (m):",
          round(float(np.percentile(reliefs, 95)), 2))
    print("Input clipping (%):",
          round(100 * clipped / total, 3))

summarize(
    "EARTH",
    sorted((ROOT / "earth").glob("*.npz"))
)

summarize(
    "MARS",
    [ROOT / "mars_jezero.npz"]
)

path = Path("outputs/neural/embeddings.npz")

with np.load(path, allow_pickle=False) as data:
    earth = data["earth_embeddings"]
    mars = data["mars_embeddings"]

print("\n=== EMBEDDING DISTRIBUTIONS ===")

for name, vectors in [
    ("Earth", earth),
    ("Mars", mars)
]:
    norms = np.linalg.norm(vectors, axis=1)
    print(
        name,
        "mean norm:", round(float(norms.mean()), 4),
        "median norm:", round(float(np.median(norms)), 4),
        "mean dimension std:",
        round(float(vectors.std(axis=0).mean()), 4),
    )

print("\n=== CHECK ===")
print("Earth finite:", np.isfinite(earth).all())
print("Mars finite:", np.isfinite(mars).all())
print("Embedding dimensions equal:",
      earth.shape[1] == mars.shape[1])
print("DIAGNOSTIC COMPLETE")
