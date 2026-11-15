import argparse
import csv
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import (
    calculate_default_transform,
    reproject,
    transform,
)
from rasterio.windows import Window

CATALOG = Path("data/metadata/earth_tile_catalog.csv")
OUTPUT = Path("data/processed/global/v3")

RESOLUTION = 90
PATCH_SIZE = 64
MIN_LAND = 0.95
NODATA = -9999.0

FIELDS = [
    "patch_id", "tile_id", "latitude", "longitude",
    "mean_slope_deg", "p95_slope_deg", "roughness_m",
    "relief_m", "elevation_std_m", "valid_fraction",
    "land_fraction",
]


def water_url(tile_id):
    water_name = tile_id.replace("_DEM", "_WBM")
    return (
        "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/"
        f"{tile_id}/AUXFILES/{water_name}.tif"
    )


def process_tile(tile):
    tile_id = tile["tile_id"]

    lat0 = (float(tile["south"]) + float(tile["north"])) / 2
    lon0 = (float(tile["west"]) + float(tile["east"])) / 2

    crs = CRS.from_string(
        f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} "
        "+datum=WGS84 +units=m +no_defs"
    )

    records = []

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MAX_RETRY="3",
    ):
        with rasterio.open(tile["url"]) as dem:
            with rasterio.open(water_url(tile_id)) as wbm:

                aligned = (
                    dem.crs == wbm.crs
                    and dem.width == wbm.width
                    and dem.height == wbm.height
                    and dem.transform.almost_equals(wbm.transform)
                )
                if not aligned:
                    raise ValueError("DEM and WBM grids differ")

                elevation = dem.read(1, masked=True)
                water = wbm.read(1, masked=True)

                z = elevation.filled(np.nan).astype("float32")
                w = water.filled(255)

                source_land = (
                    np.isfinite(z)
                    & (w == 0)
                )

                if not np.any(source_land):
                    return records

                # Mask ocean, lakes, rivers and missing data
                # BEFORE resampling elevation.
                masked_dem = np.where(
                    source_land, z, NODATA
                ).astype("float32")

                transform_out, width, height = (
                    calculate_default_transform(
                        dem.crs,
                        crs,
                        dem.width,
                        dem.height,
                        *dem.bounds,
                        resolution=RESOLUTION,
                    )
                )

                elevation_out = np.full(
                    (height, width),
                    NODATA,
                    dtype="float32",
                )

                land_out = np.zeros(
                    (height, width),
                    dtype="float32",
                )

                reproject(
                    source=masked_dem,
                    destination=elevation_out,
                    src_transform=dem.transform,
                    src_crs=dem.crs,
                    src_nodata=NODATA,
                    dst_transform=transform_out,
                    dst_crs=crs,
                    dst_nodata=NODATA,
                    resampling=Resampling.average,
                )

                # Reproject the land indicator separately.
                # This measures source land coverage of each
                # destination pixel.
                reproject(
                    source=source_land.astype("float32"),
                    destination=land_out,
                    src_transform=dem.transform,
                    src_crs=dem.crs,
                    dst_transform=transform_out,
                    dst_crs=crs,
                    dst_nodata=0,
                    resampling=Resampling.average,
                )

                for row in range(
                    0, height - PATCH_SIZE + 1, PATCH_SIZE
                ):
                    for col in range(
                        0, width - PATCH_SIZE + 1, PATCH_SIZE
                    ):
                        window = Window(
                            col, row, PATCH_SIZE, PATCH_SIZE
                        )

                        r = slice(row, row + PATCH_SIZE)
                        c = slice(col, col + PATCH_SIZE)

                        land_fraction = float(
                            np.clip(land_out[r, c], 0, 1).mean()
                        )

                        if land_fraction < MIN_LAND:
                            continue

                        patch = elevation_out[r, c].astype(
                            "float64"
                        )

                        valid = (
                            np.isfinite(patch)
                            & (patch != NODATA)
                            & (land_out[r, c] >= MIN_LAND)
                        )

                        valid_fraction = float(valid.mean())

                        if valid_fraction < MIN_LAND:
                            continue

                        patch[~valid] = np.nan

                        dy, dx = np.gradient(
                            patch, RESOLUTION, RESOLUTION
                        )

                        slope = np.degrees(
                            np.arctan(np.hypot(dx, dy))
                        )

                        slopes = slope[np.isfinite(slope)]

                        diffs = np.concatenate([
                            np.diff(patch, axis=0).ravel(),
                            np.diff(patch, axis=1).ravel(),
                        ])
                        diffs = diffs[np.isfinite(diffs)]

                        values = patch[np.isfinite(patch)]

                        if (
                            len(slopes) == 0
                            or len(diffs) == 0
                            or len(values) == 0
                        ):
                            continue

                        x, y = rasterio.transform.xy(
                            transform_out,
                            row + (PATCH_SIZE - 1) / 2,
                            col + (PATCH_SIZE - 1) / 2,
                        )

                        lon, lat = transform(
                            crs, "EPSG:4326", [x], [y]
                        )

                        features = [
                            float(slopes.mean()),
                            float(np.percentile(slopes, 95)),
                            float(diffs.std()),
                            float(np.ptp(values)),
                            float(values.std()),
                        ]

                        if not np.isfinite(features).all():
                            continue

                        records.append(dict(zip(FIELDS, [
                            f"{tile_id}_{row}_{col}",
                            tile_id,
                            lat[0],
                            lon[0],
                            *features,
                            valid_fraction,
                            land_fraction,
                        ])))

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")

    with CATALOG.open(newline="") as f:
        tiles = list(csv.DictReader(f))

    count = min(args.limit, len(tiles))
    indices = np.linspace(
        0, len(tiles) - 1, count, dtype=int
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)

    for number, index in enumerate(indices, 1):
        tile = tiles[int(index)]
        tile_id = tile["tile_id"]
        path = OUTPUT / f"{tile_id}.csv"

        if path.exists():
            print(f"[{number}/{count}] Already processed: {tile_id}")
            continue

        print(f"[{number}/{count}] {tile_id}", flush=True)

        try:
            records = process_tile(tile)

            temporary = path.with_suffix(".tmp")

            with temporary.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(records)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temporary, path)

            print(f"Saved {len(records)} land patches")

        except Exception as exc:
            print(f"FAILED: {type(exc).__name__}: {exc}")

    print("Scanner V3 finished")


if __name__ == "__main__":
    main()
