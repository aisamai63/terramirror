import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

SOURCE = Path("data/processed/mars/jezero_90m.tif")
OUTPUT = Path("data/processed/mars/mars_terrain_features.csv")

PATCH_SIZE = 64
RESOLUTION = 90.0
MIN_VALID = 0.95

FEATURES = [
    "mean_slope_deg",
    "p95_slope_deg",
    "roughness_m",
    "relief_m",
    "elevation_std_m",
]

FIELDS = [
    "patch_id",
    "target_site",
    "center_x_mars_m",
    "center_y_mars_m",
    *FEATURES,
    "valid_fraction",
]

records = []

with rasterio.open(SOURCE) as src:

    if src.crs is None or not src.crs.is_projected:
        raise ValueError("Mars DEM must have a projected CRS")

    if not np.allclose(src.res, (RESOLUTION, RESOLUTION)):
        raise ValueError("Unexpected DEM resolution")

    for row in range(0, src.height - PATCH_SIZE + 1, PATCH_SIZE):
        for col in range(0, src.width - PATCH_SIZE + 1, PATCH_SIZE):

            window = Window(
                col,
                row,
                PATCH_SIZE,
                PATCH_SIZE
            )

            patch = src.read(
                1,
                window=window,
                masked=True
            )

            z = patch.filled(np.nan).astype("float64")

            valid = np.isfinite(z)
            fraction = float(valid.mean())

            if fraction < MIN_VALID:
                continue

            dy, dx = np.gradient(
                z,
                RESOLUTION,
                RESOLUTION
            )

            slope = np.degrees(
                np.arctan(np.hypot(dx, dy))
            )

            valid_slope = slope[np.isfinite(slope)]

            if valid_slope.size == 0:
                continue

            differences = np.concatenate([
                np.diff(z, axis=0).ravel(),
                np.diff(z, axis=1).ravel()
            ])

            differences = differences[
                np.isfinite(differences)
            ]

            if differences.size == 0:
                continue

            valid_z = z[valid]

            x, y = rasterio.transform.xy(
                src.transform,
                row + (PATCH_SIZE - 1) / 2,
                col + (PATCH_SIZE - 1) / 2
            )

            record = {
                "patch_id": f"jezero_{row}_{col}",
                "target_site": "Mars Jezero Crater",
                "center_x_mars_m": x,
                "center_y_mars_m": y,
                "mean_slope_deg": float(valid_slope.mean()),
                "p95_slope_deg": float(
                    np.percentile(valid_slope, 95)
                ),
                "roughness_m": float(
                    differences.std()
                ),
                "relief_m": float(
                    np.ptp(valid_z)
                ),
                "elevation_std_m": float(
                    valid_z.std()
                ),
                "valid_fraction": fraction,
            }

            records.append(record)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=FIELDS
    )
    writer.writeheader()
    writer.writerows(records)

print("Mars feature extraction completed")
print("Total patches:", len(records))
print("Output:", OUTPUT)

for feature in FEATURES:
    values = np.array([
        record[feature] for record in records
    ])

    if values.size:
        print(
            feature,
            "min:", round(float(values.min()), 4),
            "mean:", round(float(values.mean()), 4),
            "max:", round(float(values.max()), 4)
        )
