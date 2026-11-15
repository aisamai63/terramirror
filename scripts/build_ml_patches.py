import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

PATCH_SIZE = 64
RESOLUTION = 90
NODATA = -9999.0

CATALOG = Path("data/metadata/earth_tile_catalog.csv")
EARTH_CSV = Path("data/processed/global/v3_complete")
MARS_CSV = Path("data/processed/mars/mars_terrain_features.csv")
MARS_DEM = Path("data/processed/mars/jezero_90m.tif")
OUTPUT = Path("data/processed/ml_patches")

BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"


def read_csv(path):
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def make_arrays(dem, valid, records):
    patches = []
    masks = []
    ids = []

    height, width = dem.shape

    for record in records:
        row, col = map(
            int, record["patch_id"].rsplit("_", 2)[-2:]
        )

        if row < 0 or col < 0:
            raise ValueError("Negative patch coordinates")

        if row + PATCH_SIZE > height or col + PATCH_SIZE > width:
            raise ValueError("Patch outside raster")

        r = slice(row, row + PATCH_SIZE)
        c = slice(col, col + PATCH_SIZE)

        z = dem[r, c].astype("float32", copy=True)
        mask = valid[r, c].copy()

        if mask.mean() < 0.95:
            raise ValueError(
                f"Insufficient valid terrain: {record['patch_id']}"
            )

        if not np.isfinite(z[mask]).all():
            raise ValueError("Non-finite elevations")

        # Remove absolute elevation offset but preserve
        # local relief, slope and spatial structure.
        center = float(np.median(z[mask]))
        z[mask] -= center
        z[~mask] = 0.0

        patches.append(z)
        masks.append(mask)
        ids.append(record["patch_id"])

    return (
        np.stack(patches).astype("float32"),
        np.stack(masks).astype("uint8"),
        np.asarray(ids),
    )


def save(path, patches, masks, ids):
    path.parent.mkdir(parents=True, exist_ok=True)

    import os

    temporary = path.with_name(path.name + ".tmp")

    with temporary.open("wb") as f:
        np.savez_compressed(
            f,
            elevation=patches,
            valid_mask=masks,
            patch_ids=ids,
            resolution_m=np.array(RESOLUTION),
        )
        f.flush()
        os.fsync(f.fileno())

    with np.load(temporary, allow_pickle=False) as data:
        z = data["elevation"]
        mask = data["valid_mask"]
        saved_ids = data["patch_ids"]

        assert z.shape == patches.shape
        assert mask.shape == masks.shape
        assert np.array_equal(saved_ids, ids)
        assert np.isfinite(z).all()
        assert np.all(mask.mean(axis=(1, 2)) >= 0.95)
        assert float(data["resolution_m"]) == RESOLUTION

    os.replace(temporary, path)

    print("Saved:", path)
    print("Patch shape:", patches.shape)
    print("Valid coverage minimum:", masks.mean(axis=(1, 2)).min())


def build_mars():
    records = read_csv(MARS_CSV)

    with rasterio.open(MARS_DEM) as src:
        if not np.allclose(src.res, (RESOLUTION, RESOLUTION)):
            raise ValueError("Mars resolution mismatch")

        image = src.read(1, masked=True)
        dem = image.filled(NODATA).astype("float32")
        valid = ~np.ma.getmaskarray(image) & np.isfinite(dem)

    arrays = make_arrays(dem, valid, records)

    save(
        OUTPUT / "mars_jezero.npz",
        *arrays,
    )


def build_earth(tile_id):
    records = read_csv(EARTH_CSV / f"{tile_id}.csv")

    if not records:
        print("Tile contains no retained patches:", tile_id)
        return

    catalog = {
        row["tile_id"]: row
        for row in read_csv(CATALOG)
    }

    tile = catalog[tile_id]

    lat = (float(tile["south"]) + float(tile["north"])) / 2
    lon = (float(tile["west"]) + float(tile["east"])) / 2

    local_crs = CRS.from_string(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} "
        "+datum=WGS84 +units=m +no_defs"
    )

    water_name = tile_id.replace("_DEM", "_WBM")
    water_url = f"{BASE}/{tile_id}/AUXFILES/{water_name}.tif"

    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_MAX_RETRY="3",
    ):
        with rasterio.open(tile["url"]) as dem_src:
            with rasterio.open(water_url) as water_src:
                if (
                    dem_src.crs != water_src.crs
                    or dem_src.width != water_src.width
                    or dem_src.height != water_src.height
                    or not dem_src.transform.almost_equals(
                        water_src.transform
                    )
                ):
                    raise ValueError("DEM/WBM mismatch")

                elevation = dem_src.read(1, masked=True)
                water = water_src.read(1, masked=True)

                z = elevation.filled(np.nan).astype("float32")

                land = (
                    np.isfinite(z)
                    & ~np.ma.getmaskarray(water)
                    & (water.data == 0)
                )

                source = np.where(
                    land, z, NODATA
                ).astype("float32")

                affine, width, height = calculate_default_transform(
                    dem_src.crs,
                    local_crs,
                    dem_src.width,
                    dem_src.height,
                    *dem_src.bounds,
                    resolution=RESOLUTION,
                )

                output_dem = np.full(
                    (height, width), NODATA, dtype="float32"
                )

                land_fraction = np.zeros(
                    (height, width), dtype="float32"
                )

                reproject(
                    source=source,
                    destination=output_dem,
                    src_transform=dem_src.transform,
                    src_crs=dem_src.crs,
                    src_nodata=NODATA,
                    dst_transform=affine,
                    dst_crs=local_crs,
                    dst_nodata=NODATA,
                    resampling=Resampling.average,
                )

                reproject(
                    source=land.astype("float32"),
                    destination=land_fraction,
                    src_transform=dem_src.transform,
                    src_crs=dem_src.crs,
                    dst_transform=affine,
                    dst_crs=local_crs,
                    dst_nodata=0,
                    resampling=Resampling.average,
                )

    valid = (
        np.isfinite(output_dem)
        & (output_dem != NODATA)
        & (land_fraction >= 0.95)
    )

    arrays = make_arrays(output_dem, valid, records)

    save(
        OUTPUT / "earth" / f"{tile_id}.npz",
        *arrays,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mars", action="store_true")
    parser.add_argument("--earth-tile", type=str)
    args = parser.parse_args()

    if args.mars:
        build_mars()

    if args.earth_tile:
        build_earth(args.earth_tile)

    if not args.mars and not args.earth_tile:
        parser.error("Specify --mars or --earth-tile")


if __name__ == "__main__":
    main()
