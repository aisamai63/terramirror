import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform
from rasterio.windows import Window

import os
from math import floor

TILE = os.environ.get(
    "TERRAMIRROR_TILE",
    "Copernicus_DSM_COG_10_S15_00_E134_00_DEM",
)

SOURCE = Path(
    "data/processed/global/v3_quality"
) / f"{TILE}.csv"

OUTPUT = Path(
    "data/processed/global/v3_landcover"
) / f"{TILE}.csv"

CATALOG = Path("data/metadata/earth_tile_catalog.csv")

def worldcover_tile(south, west):
    latitude = 3 * floor(south / 3)
    longitude = 3 * floor(west / 3)

    lat_code = (
        f"N{latitude:02d}" if latitude >= 0
        else f"S{abs(latitude):02d}"
    )

    lon_code = (
        f"E{longitude:03d}" if longitude >= 0
        else f"W{abs(longitude):03d}"
    )

    return lat_code + lon_code


WORLDCOVER_URL = None

CLASSES = {
    10: "tree",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse",
    70: "snow_ice",
    80: "water",
    90: "wetland",
    95: "mangroves",
    100: "moss_lichen",
}

VEGETATION = {10, 20, 30, 40, 90, 95, 100}

with CATALOG.open(newline="") as file:
    tile = next(
        r for r in csv.DictReader(file)
        if r["tile_id"] == TILE
    )

WORLDCOVER_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
    "v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_"
    + worldcover_tile(
        float(tile["south"]),
        float(tile["west"]),
    )
    + "_Map.tif"
)

print("WorldCover URL:", WORLDCOVER_URL)

with SOURCE.open(newline="") as file:
    reader = csv.DictReader(file)
    fields = list(reader.fieldnames)
    patches = list(reader)

lat = (float(tile["south"]) + float(tile["north"])) / 2
lon = (float(tile["west"]) + float(tile["east"])) / 2

local_crs = CRS.from_string(
    f"+proj=aeqd +lat_0={lat} +lon_0={lon} "
    "+datum=WGS84 +units=m +no_defs"
)

new_fields = [
    "dominant_landcover",
    "bare_fraction",
    "vegetation_fraction",
    "snow_ice_fraction",
    "built_fraction",
    "landcover_coverage",
]

with rasterio.Env(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_MAX_RETRY="3",
):
    with rasterio.open(tile["url"]) as dem:
        transform, width, height = calculate_default_transform(
            dem.crs,
            local_crs,
            dem.width,
            dem.height,
            *dem.bounds,
            resolution=90,
        )

        with rasterio.open(WORLDCOVER_URL) as worldcover:
            with WarpedVRT(
                worldcover,
                crs=local_crs,
                transform=transform,
                width=width,
                height=height,
                resampling=Resampling.mode,
                nodata=0,
            ) as vrt:

                for patch in patches:
                    row, col = map(
                        int,
                        patch["patch_id"].rsplit("_", 2)[-2:]
                    )

                    if row + 64 > height or col + 64 > width:
                        raise ValueError("Patch outside output grid")

                    data = vrt.read(
                        1,
                        window=Window(col, row, 64, 64),
                    )

                    valid = np.isin(
                        data,
                        list(CLASSES.keys())
                    )

                    coverage = float(valid.mean())

                    values = data[valid]

                    if values.size:
                        codes, counts = np.unique(
                            values, return_counts=True
                        )

                        dominant = int(
                            codes[np.argmax(counts)]
                        )

                        patch["dominant_landcover"] = (
                            CLASSES[dominant]
                        )

                        patch["bare_fraction"] = float(
                            np.mean(values == 60)
                        )

                        patch["vegetation_fraction"] = float(
                            np.isin(
                                values, list(VEGETATION)
                            ).mean()
                        )

                        patch["snow_ice_fraction"] = float(
                            np.mean(values == 70)
                        )

                        patch["built_fraction"] = float(
                            np.mean(values == 50)
                        )
                    else:
                        patch["dominant_landcover"] = "unknown"

                        for field in (
                            "bare_fraction",
                            "vegetation_fraction",
                            "snow_ice_fraction",
                            "built_fraction",
                        ):
                            patch[field] = ""

                    patch["landcover_coverage"] = coverage

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

temporary = OUTPUT.with_suffix(".csv.tmp")

with temporary.open("w", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=fields + new_fields,
    )
    writer.writeheader()
    writer.writerows(patches)
    file.flush()
    os.fsync(file.fileno())

with temporary.open(newline="") as file:
    verified = list(csv.DictReader(file))

assert len(verified) == len(patches)
assert [r["patch_id"] for r in verified] == [
    r["patch_id"] for r in patches
]

os.replace(temporary, OUTPUT)

print("=== WORLDCOVER INTEGRATION ===")
print("Tile:", TILE)
print("Patches enriched:", len(patches))
print("Output:", OUTPUT)

from collections import Counter

counts = Counter(
    patch["dominant_landcover"]
    for patch in patches
)

print("\nDominant land-cover classes:")
for name, count in counts.most_common():
    print(f"{name}: {count}")

coverages = [
    float(p["landcover_coverage"])
    for p in patches
]

print(
    "\nMinimum coverage:",
    round(min(coverages), 4)
)

print(
    "Mean coverage:",
    round(float(np.mean(coverages)), 4)
)

print("WorldCover integration complete")
