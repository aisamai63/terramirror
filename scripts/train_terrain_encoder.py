import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

SOURCE = Path("data/processed/ml_patches/earth")
OUTPUT = Path("models/terrain_encoder")
SCALE_M = 200.0
CLIP = 5.0
SEED = 42


class TerrainAutoencoder(nn.Module):
    def __init__(self, latent_dim=32):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Conv2d(2, 16, 3, 2, 1),
            nn.ReLU(),
            nn.Conv2d(16, 32, 3, 2, 1),
            nn.ReLU(),
            nn.Conv2d(32, 64, 3, 2, 1),
            nn.ReLU(),
            nn.Conv2d(64, 64, 3, 2, 1),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(64 * 4 * 4, latent_dim),
        )

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64 * 4 * 4),
            nn.ReLU(),
            nn.Unflatten(1, (64, 4, 4)),
            nn.ConvTranspose2d(64, 64, 4, 2, 1),
            nn.ReLU(),
            nn.ConvTranspose2d(64, 32, 4, 2, 1),
            nn.ReLU(),
            nn.ConvTranspose2d(32, 16, 4, 2, 1),
            nn.ReLU(),
            nn.ConvTranspose2d(16, 1, 4, 2, 1),
        )

    def forward(self, x):
        embedding = self.encoder(x)
        reconstruction = self.decoder(embedding)
        return reconstruction, embedding


def load_tile(path):
    with np.load(path, allow_pickle=False) as data:
        z = data["elevation"].astype("float32")
        mask = data["valid_mask"].astype("float32")
        ids = data["patch_ids"].tolist()

    assert z.shape == mask.shape
    assert z.ndim == 3 and z.shape[1:] == (64, 64)
    assert np.isfinite(z).all()

    return z, mask, ids


def make_dataset(paths):
    elevations = []
    masks = []

    for path in paths:
        z, m, _ = load_tile(path)
        elevations.append(z)
        masks.append(m)

    z = np.concatenate(elevations)
    m = np.concatenate(masks)

    # Fixed physical scale, shared across all patches.
    # Do not normalize each patch independently.
    z = np.clip(z / SCALE_M, -CLIP, CLIP)
    z *= m

    inputs = np.stack([z, m], axis=1)
    targets = z[:, None]
    valid_masks = m[:, None]

    return TensorDataset(
        torch.from_numpy(inputs),
        torch.from_numpy(targets),
        torch.from_numpy(valid_masks),
    )


def masked_loss(prediction, target, mask):
    squared = (prediction - target).square() * mask
    return squared.sum() / mask.sum().clamp(min=1)


def evaluate(model, loader, device):
    model.eval()
    total_error = 0.0
    total_pixels = 0.0

    with torch.no_grad():
        for x, target, mask in loader:
            x = x.to(device)
            target = target.to(device)
            mask = mask.to(device)

            prediction, _ = model(x)

            total_error += (
                (prediction - target).square() * mask
            ).sum().item()

            total_pixels += mask.sum().item()

    return total_error / max(total_pixels, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    if args.epochs < 1 or args.batch_size < 1:
        parser.error("epochs and batch size must be positive")

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    files = sorted(SOURCE.glob("*.npz"))

    if len(files) < 4:
        raise ValueError("Need at least four Earth tile files")

    # Geographic holdout: entire tiles, not random patches.
    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(files))

    val_indices = set(order[:3].tolist())

    train_files = [
        p for i, p in enumerate(files)
        if i not in val_indices
    ]

    val_files = [
        p for i, p in enumerate(files)
        if i in val_indices
    ]

    train_dataset = make_dataset(train_files)
    val_dataset = make_dataset(val_files)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    model = TerrainAutoencoder().to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=0.001,
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)

    best_loss = float("inf")
    history = []

    print("=== TERRAMIRROR TERRAIN TRAINING ===", flush=True)
    print("Device:", device, flush=True)
    print("Training tiles:", len(train_files), flush=True)
    print("Validation tiles:", len(val_files), flush=True)
    print("Training patches:", len(train_dataset), flush=True)
    print("Validation patches:", len(val_dataset), flush=True)
    print("Epochs:", args.epochs, flush=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_error = 0.0
        running_pixels = 0.0

        for x, target, mask in train_loader:
            x = x.to(device)
            target = target.to(device)
            mask = mask.to(device)

            optimizer.zero_grad(set_to_none=True)

            prediction, _ = model(x)

            loss = masked_loss(
                prediction, target, mask
            )

            loss.backward()
            optimizer.step()

            with torch.no_grad():
                running_error += (
                    (prediction - target).square() * mask
                ).sum().item()
                running_pixels += mask.sum().item()

        train_loss = running_error / max(running_pixels, 1)
        val_loss = evaluate(model, val_loader, device)

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
        })

        print(
            f"Epoch {epoch:02d}/{args.epochs} "
            f"| Train MSE: {train_loss:.6f} "
            f"| Val MSE: {val_loss:.6f}",
            flush=True,
        )

        if val_loss < best_loss:
            best_loss = val_loss

            torch.save({
                "model_state": model.state_dict(),
                "latent_dim": 32,
                "scale_m": SCALE_M,
                "clip": CLIP,
                "seed": SEED,
                "validation_loss": best_loss,
            }, OUTPUT / "best_model.pt")

    metadata = {
        "model": "terrain_convolutional_autoencoder_v1",
        "latent_dim": 32,
        "scale_m": SCALE_M,
        "clip": CLIP,
        "seed": SEED,
        "train_tiles": [p.stem for p in train_files],
        "validation_tiles": [p.stem for p in val_files],
        "train_patches": len(train_dataset),
        "validation_patches": len(val_dataset),
        "history": history,
        "best_validation_mse": best_loss,
    }

    (OUTPUT / "training_metadata.json").write_text(
        json.dumps(metadata, indent=2)
    )

    print("\n=== TRAINING COMPLETE ===")
    print("Best validation MSE:", round(best_loss, 6))
    print("Saved model:", OUTPUT / "best_model.pt")
    print(
        "Saved metadata:",
        OUTPUT / "training_metadata.json"
    )


if __name__ == "__main__":
    main()
