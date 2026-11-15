import argparse
import csv
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform, transform
from rasterio.windows import Window

CATALOG = Path("data/metadata/earth_tile_catalog.csv")
OUTPUT_DIR = Path("data/processed/global/v2")

RESOLUTION = 90
PATCH_SIZE = 64
MIN_LAND_FRACTION = 0.95

FIELDS = [
    "patch_id", "tile_id", "latitude", "longitude",
    "mean_slope_deg", "p95_slope_deg", "roughness_m",
    "relief_m", "elevation_std_m", "valid_fraction",
    "land_fraction"
]


def get_water_url(tile):
    tile_id = tile["tile_id"]
    water_name = tile_id.replace("_DEM", "_WBM")

    return (
        f"https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/"
        f"{tile_id}/AUXFILES/{water_name}.tif"
    )


def process_tile(tile):
    tile_id = tile["tile_id"]

    lat = (float(tile["south"]) + float(tile["north"])) / 2
    lon = (float(tile["west"]) + float(tile["east"])) / 2

    local_crs = CRS.from_string(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} "
        "+datum=WGS84 +units=m +no_defs"
    )

    records = []

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MAX_RETRY="3",
    ):
        with rasterio.open(tile["url"]) as dem:
            with rasterio.open(get_water_url(tile)) as wbm:

                if (
                    dem.crs != wbm.crs
                    or dem.width != wbm.width
                    or dem.height != wbm.height
                    or not dem.transform.almost_equals(wbm.transform)
                ):
                    raise ValueError("DEM and WBM grids do not align")

                affine, width, height = calculate_default_transform(
                    dem.crs,
                    local_crs,
                    dem.width,
                    dem.height,
                    *dem.bounds,
                    resolution=RESOLUTION,
                )

                common_grid = {
                    "crs": local_crs,
                    "transform": affine,
                    "width": width,
                    "height": height,
                }

                with WarpedVRT(
                    dem,
                    **common_grid,
                    resampling=Resampling.average,
                    nodata=-9999.0,
                ) as dem_vrt:
                    with WarpedVRT(
                        wbm,
                        **common_grid,
                        resampling=Resampling.nearest,
                        nodata=255,
                    ) as wbm_vrt:

                        for row in range(
                            0, height - PATCH_SIZE + 1, PATCH_SIZE
                        ):
                            for col in range(
                                0, width - PATCH_SIZE + 1, PATCH_SIZE
                            ):
                                window = Window(
                                    col, row, PATCH_SIZE, PATCH_SIZE
                                )

                                elevation = dem_vrt.read(
                                    1, window=window, masked=True
                                )

                                water = wbm_vrt.read(
                                    1, window=window, masked=True
                                )

                                z = elevation.filled(np.nan).astype(
                                    "float64"
                                )

                                water_values = water.filled(255)

                                land = (
                                    (water_values == 0)
                                    & np.isfinite(z)
                                )

                                land_fraction = float(land.mean())

                                if land_fraction < MIN_LAND_FRACTION:
                                    continue

                                z[~land] = np.nan

                                dy, dx = np.gradient(
                                    z, RESOLUTION, RESOLUTION
                                )

                                slope = np.degrees(
                                    np.arctan(np.hypot(dx, dy))
                                )

                                valid_slope = slope[np.isfinite(slope)]

                                if valid_slope.size == 0:
                                    continue

                                differences = np.concatenate([
                                    np.diff(z, axis=0).ravel(),
                                    np.diff(z, axis=1).ravel(),
                                ])

                                differences = differences[
                                    np.isfinite(differences)
                                ]

                                if differences.size == 0:
                                    continue

                                valid_z = z[np.isfinite(z)]

                                center_x, center_y = (
                                    rasterio.transform.xy(
                                        affine,
                                        row + (PATCH_SIZE - 1) / 2,
                                        col + (PATCH_SIZE - 1) / 2,
                                    )
                                )

                                longitude, latitude = transform(
                                    local_crs,
                                    "EPSG:4326",
                                    [center_x],
                                    [center_y],
                                )

                                records.append({
                                    "patch_id": f"{tile_id}_{row}_{col}",
                                    "tile_id": tile_id,
                                    "latitude": latitude[0],
                                    "longitude": longitude[0],
                                    "mean_slope_deg": float(
                                        valid_slope.mean()
                                    ),
                                    "p95_slope_deg": float(
                                        np.percentile(valid_slope, 95)
                                    ),
                                    "roughness_m": float(
                                        differences.std()
                                    ),
                                    "relief_m": float(np.ptp(valid_z)),
                                    "elevation_std_m": float(
                                        valid_z.std()
                                    ),
                                    "valid_fraction": float(
                                        np.isfinite(
                                            elevation.filled(np.nan)
                                        ).mean()
                                    ),
                                    "land_fraction": land_fraction,
                                })

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")

    with CATALOG.open(newline="") as f:
        tiles = list(csv.DictReader(f))

    count = min(args.limit, len(tiles))
    indices = np.linspace(
        0, len(tiles) - 1, count, dtype=int
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    failed = 0

    for index, tile_index in enumerate(indices, 1):
        tile = tiles[int(tile_index)]
        tile_id = tile["tile_id"]

        output = OUTPUT_DIR / f"{tile_id}.csv"

        if output.exists():
            print(f"[{index}/{count}] Already completed: {tile_id}")
            continue

        print(
            f"[{index}/{count}] Processing: {tile_id}",
            flush=True,
        )

        try:
            records = process_tile(tile)

            temporary = output.with_suffix(".tmp")

            with temporary.open("w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=FIELDS
                )
                writer.writeheader()
                writer.writerows(records)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temporary, output)

            total += len(records)
            print(f"  Saved {len(records)} land patches")

        except Exception as exc:
            failed += 1
            print(f"  FAILED: {exc}", flush=True)

    print("\nScan finished")
    print("New land patches:", total)
    print("Failed tiles:", failed)
    print("Output directory:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
