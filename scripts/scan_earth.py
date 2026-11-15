import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform, transform
from rasterio.enums import Resampling

CATALOG = Path("data/metadata/earth_tile_catalog.csv")
OUTPUT = Path("data/processed/global/earth_features.csv")
COMPLETED = Path("data/processed/global/completed_tiles.txt")

RESOLUTION = 90
PATCH_SIZE = 64
MIN_VALID = 0.95

FIELDS = [
    "patch_id",
    "tile_id",
    "latitude",
    "longitude",
    "mean_slope_deg",
    "p95_slope_deg",
    "roughness_m",
    "relief_m",
    "elevation_std_m",
    "valid_fraction",
    "zero_fraction",
]


def process_tile(tile):
    lat = (float(tile["south"]) + float(tile["north"])) / 2
    lon = (float(tile["west"]) + float(tile["east"])) / 2

    # Local metric projection, including high latitudes.
    local_crs = CRS.from_string(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} " "+datum=WGS84 +units=m +no_defs"
    )

    results = []

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MAX_RETRY="2",
    ):
        with rasterio.open(tile["url"]) as src:
            affine, width, height = calculate_default_transform(
                src.crs,
                local_crs,
                src.width,
                src.height,
                *src.bounds,
                resolution=RESOLUTION,
            )

            with WarpedVRT(
                src,
                crs=local_crs,
                transform=affine,
                width=width,
                height=height,
                resampling=Resampling.average,
                nodata=-9999.0,
            ) as vrt:
                for row in range(0, height - PATCH_SIZE + 1, PATCH_SIZE):
                    for col in range(0, width - PATCH_SIZE + 1, PATCH_SIZE):
                        window = rasterio.windows.Window(
                            col, row, PATCH_SIZE, PATCH_SIZE
                        )

                        patch = vrt.read(1, window=window, masked=True)
                        fraction = patch.count() / patch.size

                        if fraction < MIN_VALID:
                            continue

                        z = patch.filled(np.nan).astype("float64")
                        dy, dx = np.gradient(z, RESOLUTION)
                        slope = np.degrees(np.arctan(np.hypot(dx, dy)))

                        if not np.isfinite(slope).any():
                            continue

                        differences = np.concatenate(
                            [
                                np.diff(z, axis=0).ravel(),
                                np.diff(z, axis=1).ravel(),
                            ]
                        )
                        differences = differences[np.isfinite(differences)]

                        if not differences.size:
                            continue

                        center_x, center_y = rasterio.transform.xy(
                            affine,
                            row + PATCH_SIZE // 2,
                            col + PATCH_SIZE // 2,
                        )
                        longitude, latitude = transform(
                            local_crs,
                            "EPSG:4326",
                            [center_x],
                            [center_y],
                        )

                        valid = z[np.isfinite(z)]

                        results.append(
                            {
                                "patch_id": f'{tile["tile_id"]}_{row}_{col}',
                                "tile_id": tile["tile_id"],
                                "latitude": latitude[0],
                                "longitude": longitude[0],
                                "mean_slope_deg": float(np.nanmean(slope)),
                                "p95_slope_deg": float(np.nanpercentile(slope, 95)),
                                "roughness_m": float(np.std(differences)),
                                "relief_m": float(np.ptp(valid)),
                                "elevation_std_m": float(np.std(valid)),
                                "valid_fraction": float(fraction),
                                "zero_fraction": float(np.mean(valid == 0)),
                            }
                        )

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")

    with CATALOG.open(newline="") as file:
        tiles = list(csv.DictReader(file))

    # Pilot samples span the full catalog rather than known analogs.
    count = min(args.limit, len(tiles))
    indices = np.linspace(0, len(tiles) - 1, count, dtype=int)
    selected = [tiles[int(i)] for i in indices]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    completed = set(COMPLETED.read_text().splitlines()) if COMPLETED.exists() else set()

    with OUTPUT.open("a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)

        if OUTPUT.stat().st_size == 0:
            writer.writeheader()

        for index, tile in enumerate(selected, 1):
            tile_id = tile["tile_id"]

            if tile_id in completed:
                print(f"[{index}/{count}] Already processed: {tile_id}")
                continue

            print(f"[{index}/{count}] Processing: {tile_id}", flush=True)

            try:
                records = process_tile(tile)
            except Exception as exc:
                print(f"FAILED: {tile_id}: {exc}", flush=True)
                continue

            writer.writerows(records)
            file.flush()

            with COMPLETED.open("a") as checkpoint:
                checkpoint.write(tile_id + "\n")

            completed.add(tile_id)
            print(f"  Saved {len(records)} patches", flush=True)

    print("Pilot scan finished")
    print("Results:", OUTPUT)


if __name__ == "__main__":
    main()
