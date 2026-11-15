
from pathlib import Path
import csv

import numpy as np
import rasterio

INPUT = Path("data/processed/earth/atacama_40m_utm.tif")
OUTPUT = Path("data/processed/earth_terrain_features.csv")

PATCH_SIZE = 128
MIN_VALID_FRACTION = 0.95

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

records = []

with rasterio.open(INPUT) as src:
    assert src.crs is not None
    assert src.crs.is_projected
    assert abs(src.res[0] - 40) < 1e-6
    assert abs(src.res[1] - 40) < 1e-6

    for row in range(0, src.height - PATCH_SIZE + 1, PATCH_SIZE):
        for col in range(0, src.width - PATCH_SIZE + 1, PATCH_SIZE):
            window = rasterio.windows.Window(
                col, row, PATCH_SIZE, PATCH_SIZE
            )

            patch = src.read(1, window=window, masked=True)
            valid_fraction = patch.count() / patch.size

            if valid_fraction < MIN_VALID_FRACTION:
                continue

            elevation = patch.filled(np.nan).astype("float64")

            # Exclude invalid cells and their immediate neighbours
            # from gradient calculations.
            dz_dy, dz_dx = np.gradient(elevation, 40.0, 40.0)
            slope = np.degrees(
                np.arctan(np.hypot(dz_dx, dz_dy))
            )

            # Neighbouring elevation differences, excluding NaNs.
            dx = np.diff(elevation, axis=1)
            dy = np.diff(elevation, axis=0)
            differences = np.concatenate([
                dx[np.isfinite(dx)],
                dy[np.isfinite(dy)],
            ])

            if differences.size == 0 or not np.isfinite(slope).any():
                continue

            # Geographic centre of this Earth patch
            x, y = rasterio.transform.xy(
                src.transform,
                row + PATCH_SIZE // 2,
                col + PATCH_SIZE // 2,
            )

            from rasterio.warp import transform
            lon, lat = transform(
                src.crs, "EPSG:4326", [x], [y]
            )

            records.append({
                "patch_id": f"atacama_{row}_{col}",
                "latitude": lat[0],
                "longitude": lon[0],
                "mean_slope_deg": float(np.nanmean(slope)),
                "p95_slope_deg": float(np.nanpercentile(slope, 95)),
                "roughness_m": float(np.std(differences)),
                "relief_m": float(
                    np.nanmax(elevation) - np.nanmin(elevation)
                ),
                "elevation_std_m": float(
                    np.nanstd(elevation)
                ),
                "valid_fraction": float(valid_fraction),
            })

fields = [
    "patch_id",
    "latitude",
    "longitude",
    "mean_slope_deg",
    "p95_slope_deg",
    "roughness_m",
    "relief_m",
    "elevation_std_m",
    "valid_fraction",
]

with OUTPUT.open("w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)

print(f"Extracted {len(records)} terrain patches")
print(f"Saved: {OUTPUT}")
