import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform
from rasterio.windows import Window

TILE = __import__("os").environ.get("TERRAMIRROR_TILE", "Copernicus_DSM_COG_10_S45_00_W072_00_DEM")
BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"

SOURCE = Path("data/processed/global/v3") / f"{TILE}.csv"
OUTPUT = Path("data/processed/global/v3_quality") / f"{TILE}.csv"
CATALOG = Path("data/metadata/earth_tile_catalog.csv")

with CATALOG.open(newline="") as f:
    tile = next(
        r for r in csv.DictReader(f)
        if r["tile_id"] == TILE
    )

with SOURCE.open(newline="") as f:
    reader = csv.DictReader(f)
    fields = list(reader.fieldnames)
    patches = list(reader)

lat0 = (float(tile["south"]) + float(tile["north"])) / 2
lon0 = (float(tile["west"]) + float(tile["east"])) / 2

local_crs = CRS.from_string(
    f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} "
    "+datum=WGS84 +units=m +no_defs"
)

def url(kind):
    if kind == "DEM":
        return f"{BASE}/{TILE}/{TILE}.tif"
    name = TILE.replace("_DEM", f"_{kind}")
    return f"{BASE}/{TILE}/AUXFILES/{name}.tif"

additional = [
    "unedited_fraction",
    "original_source_fraction",
    "hem_coverage",
    "median_height_error_m",
    "quality_status",
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with rasterio.Env(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_MAX_RETRY="3",
):
    from contextlib import ExitStack

    with ExitStack() as stack:
        dem = stack.enter_context(rasterio.open(url("DEM")))

        transform, width, height = calculate_default_transform(
            dem.crs,
            local_crs,
            dem.width,
            dem.height,
            *dem.bounds,
            resolution=90,
        )

        grid = dict(
            crs=local_crs,
            transform=transform,
            width=width,
            height=height,
        )

        vrts = {}

        for kind in ("WBM", "EDM", "FLM", "HEM"):
            src = stack.enter_context(rasterio.open(url(kind)))

            if (
                src.crs != dem.crs
                or src.width != dem.width
                or src.height != dem.height
                or not src.transform.almost_equals(dem.transform)
            ):
                raise ValueError(f"{kind} grid mismatch")

            vrts[kind] = stack.enter_context(
                WarpedVRT(
                    src,
                    **grid,
                    resampling=Resampling.nearest,
                )
            )

        results = []

        for patch in patches:
            row, col = map(
                int, patch["patch_id"].rsplit("_", 2)[-2:]
            )

            window = Window(col, row, 64, 64)

            if row + 64 > height or col + 64 > width:
                raise ValueError("Patch exceeds raster grid")

            data = {
                kind: vrt.read(
                    1, window=window, masked=True
                )
                for kind, vrt in vrts.items()
            }

            wbm = data["WBM"]
            land = (
                ~np.ma.getmaskarray(wbm)
                & (wbm.data == 0)
            )

            count = int(land.sum())

            if count == 0:
                raise ValueError("Patch has no sampled land")

            edm = data["EDM"]
            flm = data["FLM"]
            hem = data["HEM"]

            unedited = (
                land
                & ~np.ma.getmaskarray(edm)
                & (edm.data == 1)
            )

            original = (
                land
                & ~np.ma.getmaskarray(flm)
                & (flm.data == 2)
            )

            hem_valid = (
                land
                & ~np.ma.getmaskarray(hem)
                & np.isfinite(hem.data)
                & (hem.data >= 0)
            )

            coverage = float(hem_valid.sum() / count)

            median_error = (
                float(np.median(hem.data[hem_valid]))
                if hem_valid.any()
                else None
            )

            patch.update({
                "unedited_fraction": float(
                    unedited.sum() / count
                ),
                "original_source_fraction": float(
                    original.sum() / count
                ),
                "hem_coverage": coverage,
                "median_height_error_m": (
                    median_error if median_error is not None else ""
                ),
                "quality_status": (
                    "review"
                    if coverage < 0.90
                    else "measured"
                ),
            })

            results.append(patch)

import os

temporary = OUTPUT.with_suffix(".csv.tmp")

with temporary.open("w", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=fields + additional
    )
    writer.writeheader()
    writer.writerows(results)
    f.flush()
    os.fsync(f.fileno())

with temporary.open(newline="") as f:
    verified = list(csv.DictReader(f))

assert len(verified) == len(results)
assert [r["patch_id"] for r in verified] == [
    r["patch_id"] for r in results
]

os.replace(temporary, OUTPUT)

print("=== QUALITY AUDIT ===")
print("Tile:", TILE)
print("Patches:", len(results))
print("Output:", OUTPUT)

for name in (
    "unedited_fraction",
    "original_source_fraction",
    "hem_coverage",
):
    values = np.array([
        float(r[name]) for r in results
    ])
    print(
        name,
        "mean:", round(float(values.mean()), 4),
        "min:", round(float(values.min()), 4)
    )

print(
    "Patches needing review:",
    sum(r["quality_status"] == "review" for r in results)
)

print("Quality audit complete")
