"""Read-only reconstruction evaluation on the saved tile-level validation split."""

import json
from pathlib import Path

import numpy as np
import torch

from scripts.train_terrain_encoder import TerrainAutoencoder


ROOT = Path(__file__).resolve().parents[1]


def main():
    model_dir = ROOT / "models/terrain_encoder"
    metadata = json.loads((model_dir / "training_metadata.json").read_text())
    checkpoint = torch.load(
        model_dir / "best_model.pt", map_location="cpu", weights_only=True,
    )
    model = TerrainAutoencoder(checkpoint["latent_dim"])
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    absolute_error = squared_error = valid_pixels = clipped_pixels = patch_count = 0
    scale = float(checkpoint["scale_m"])
    clip = float(checkpoint["clip"])

    with torch.no_grad():
        for tile in metadata["validation_tiles"]:
            path = ROOT / "data/processed/ml_patches/earth" / f"{tile}.npz"
            with np.load(path, allow_pickle=False) as archive:
                elevation = archive["elevation"].astype("float32")
                mask = archive["valid_mask"].astype("float32")
            if elevation.shape != mask.shape or elevation.shape[1:] != (64, 64):
                raise ValueError(f"Invalid validation archive: {path.name}")
            patch_count += len(elevation)
            clipped_pixels += int(np.count_nonzero((np.abs(elevation / scale) > clip) & (mask > 0)))
            target = np.clip(elevation / scale, -clip, clip) * mask

            for start in range(0, len(target), 64):
                batch = slice(start, start + 64)
                inputs = torch.from_numpy(np.stack((target[batch], mask[batch]), axis=1))
                prediction = model(inputs)[0].numpy()[:, 0] * scale
                error = (prediction - target[batch] * scale) * mask[batch]
                absolute_error += float(np.abs(error).sum(dtype=np.float64))
                squared_error += float(np.square(error).sum(dtype=np.float64))
                valid_pixels += int(mask[batch].sum())

    report = {
        "split": "saved_tile_level_validation",
        "patches": patch_count,
        "valid_pixels": valid_pixels,
        "clipped_valid_pixels": clipped_pixels,
        "mae_m_against_clipped_target": absolute_error / valid_pixels,
        "rmse_m_against_clipped_target": (squared_error / valid_pixels) ** 0.5,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
