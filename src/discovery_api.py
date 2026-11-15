"""TerraMirror unified regional and detailed discovery API."""

import json
import csv
import re
import os
import asyncio
import time
from collections import deque
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]

REGIONAL = {
    "mars-jezero": (
        "Mars",
        "mars_jezero_60km_v1_results.json",
    ),
    "moon-shackleton": (
        "Moon",
        "moon_shackleton_60km_v1_results.json",
    ),
    "moon-tranquillitatis": (
        "Moon",
        "moon_tranquillitatis_pit_60km_v1_results.json",
    ),
}

REGIONAL_DIR = ROOT / "data/processed/ml"
DETAILED_PATH = ROOT / "outputs/neural/hybrid_matches.json"
PUBLIC_DEMO = os.getenv("TERRAMIRROR_PUBLIC_DEMO") == "1"
FRONTEND_DIST = ROOT / "frontend/dist"

COPERNICUS_ADAPTED_NOTICE = (
    "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and "
    "© Airbus Defence and Space GmbH 2014-2018 provided under "
    "COPERNICUS by the European Union and ESA; all rights reserved"
)
COPERNICUS_LIABILITY_NOTICE = (
    "The organisations in charge of the Copernicus programme by law or "
    "by delegation do not incur any liability for any use of the "
    "Copernicus WorldDEM-30"
)

app = FastAPI(
    title="TerraMirror Discovery API",
    version="0.2.0",
    description="Experimental Earth analog discovery for Mars and Moon.",
    docs_url=None if PUBLIC_DEMO else "/docs",
    redoc_url=None if PUBLIC_DEMO else "/redoc",
    openapi_url=None if PUBLIC_DEMO else "/openapi.json",
)

if PUBLIC_DEMO:
    _api_requests = deque()
    _terrain_requests = deque()
    _request_limit_lock = asyncio.Lock()

    @app.middleware("http")
    async def public_demo_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            async with _request_limit_lock:
                now = time.monotonic()
                is_terrain = (path.startswith("/api/terrain/") or
                              path.startswith("/api/regional-terrain/"))
                for history in (_api_requests, _terrain_requests):
                    while history and now - history[0] > 60:
                        history.popleft()
                if (len(_api_requests) >= 240 or
                        (is_terrain and len(_terrain_requests) >= 120)):
                    return JSONResponse(
                        {"detail": "Demo request limit reached"},
                        status_code=429,
                        headers={"Retry-After": "60", "Cache-Control": "no-store",
                                 "X-Content-Type-Options": "nosniff"},
                    )
                _api_requests.append(now)
                if is_terrain:
                    _terrain_requests.append(now)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response


@lru_cache(maxsize=8)
def read_json(path: str):
    source = Path(path)

    if not source.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Required data file missing: {source.name}",
        )

    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Data unavailable: {source.name}",
        ) from exc


def get_regional(target_id):
    if target_id not in REGIONAL:
        raise HTTPException(404, "Unknown planetary target")

    planet, filename = REGIONAL[target_id]
    data = read_json(str(REGIONAL_DIR / filename))

    return {
        "target_id": target_id,
        "planet": planet,
        "method": "regional_standardized_euclidean",
        "resolution_m": 1000,
        "comparison_scale_km": 60,
        "scientific_status": "experimental",
        **data,
        "top_analogs": [
            {**candidate, **regional_geographic_label(candidate)}
            for candidate in data["top_analogs"]
        ],
    }


@lru_cache(maxsize=1)
def regional_location_metadata():
    """Optional, tile-centred exploratory labels from the acquisition record."""
    path = ROOT / "data/metadata/earth_acquisition_status.json"
    if not path.is_file():
        return {}
    try:
        records = json.loads(path.read_text(encoding="utf-8"))["candidates"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {row["tile"]: row for row in records if "tile" in row}


def regional_geographic_label(candidate):
    match = re.fullmatch(r"earth_([ns]\d{2}[ew]\d{3})_60km_v1",
                         candidate.get("profile_id", ""))
    if not match:
        return {}
    record = regional_location_metadata().get(match.group(1))
    if not record or not record.get("region") or not record.get("country"):
        return {}
    try:
        same_tile_centre = (
            abs(candidate["latitude"] - record["latitude"]) <= 0.02 and
            abs(candidate["longitude"] - record["longitude"]) <= 0.02
        )
    except (KeyError, TypeError):
        return {}
    if not same_tile_centre:
        return {}
    return {
        "geographic_label": f'{record["region"]} · {record["country"]}',
        "geographic_label_source": "earth_acquisition_status.json",
    }


def get_detailed():
    return read_json(str(DETAILED_PATH))


@app.get("/api/health")
def health():
    detailed = get_detailed()

    return {
        "status": "ok",
        "project": "TerraMirror",
        "regional_targets": len(REGIONAL),
        "detailed_mars_patches": detailed["mars_patches"],
        "indexed_earth_patches": detailed["earth_patches"],
        "search_scope": "sampled_earth_tiles",
        "scientific_status": "experimental",
    }


@app.get("/api/regional")
def regional_targets():
    targets = []

    for target_id in REGIONAL:
        data = get_regional(target_id)

        targets.append({
            "target_id": target_id,
            "planet": data["planet"],
            "target_site": data["target_site"],
            "candidate_count": len(data["top_analogs"]),
            "method": data["method"],
        })

    return {"count": len(targets), "targets": targets}


@app.get("/api/regional/{target_id}")
def regional_matches(target_id: str):
    return get_regional(target_id)


@app.get("/api/detailed/mars")
def detailed_mars():
    data = get_detailed()

    return {
        "count": len(data["results"]),
        "planet": "Mars",
        "target_site": "Jezero crater",
        "method": data["method"],
        "scientific_status": data["status"],
        "search_scope": data["earth_search_scope"],
        "patches": [
            {
                "index": i,
                "patch_id": result["mars_patch_id"],
                "candidate_count": len(result["matches"]),
            }
            for i, result in enumerate(data["results"])
        ],
    }


@app.get("/api/detailed/mars/{patch_id}")
def detailed_mars_matches(patch_id: str):
    data = get_detailed()

    for item in data["results"]:
        if item["mars_patch_id"] == patch_id:
            return {
                "planet": "Mars",
                "target_site": "Jezero crater",
                "method": data["method"],
                "scientific_status": data["status"],
                "search_scope": data["earth_search_scope"],
                "target_features": target_terrain_features("mars", patch_id),
                **{
                    **item,
                    "matches": [
                        enrich_candidate_quality(match)
                        for match in item["matches"]
                    ],
                },
            }

    raise HTTPException(404, "Mars patch not found")


@app.get("/api/detailed/top-candidates")
def detailed_top_candidates():
    data = get_detailed()

    candidates = [
        {
            "mars_patch_id": item["mars_patch_id"],
            **item["matches"][0],
        }
        for item in data["results"]
        if item["matches"]
    ]

    return {
        "count": len(candidates),
        "candidates": candidates,
        "method": data["method"],
        "search_scope": data["earth_search_scope"],
    }


@app.get("/api/coverage")
def coverage():
    import csv

    completed = ROOT / "data/processed/global/v3_complete"
    archives = ROOT / "data/processed/ml_patches/earth"

    wyoming = "Copernicus_DSM_COG_10_N44_00_W105_00_DEM"

    feature_files = list(completed.glob("*.csv"))
    archive_files = list(archives.glob("*.npz"))

    expanded_file_count = len(feature_files)
    expanded_archive_count = len(archive_files)

    baseline_file_count = sum(
        path.stem != wyoming for path in feature_files
    )
    baseline_archive_count = sum(
        path.stem != wyoming for path in archive_files
    )

    catalog_path = ROOT / "data/metadata/earth_tile_catalog.csv"
    if not catalog_path.is_file():
        raise HTTPException(503, "Earth tile catalog unavailable")
    with catalog_path.open(newline="") as file:
        catalog_count = sum(1 for _ in csv.DictReader(file))

    baseline_patches = get_detailed()["earth_patches"]
    expanded_patches = read_json(str(
        ROOT / "outputs/neural_candidate/hybrid_matches.json"
    ))["earth_patches"]
    moon_patches = moon_discovery_index()["earth_patches"]

    return {
        "earth_catalog_tiles": catalog_count,
        "earth_processed_tiles": baseline_file_count,
        "earth_tiles_with_qualifying_patches": baseline_archive_count,
        "earth_indexed_patches": baseline_patches,
        "expanded_processed_tiles": expanded_file_count,
        "expanded_tiles_with_qualifying_patches": expanded_archive_count,
        "expanded_indexed_patches": expanded_patches,
        "moon_indexed_patches": moon_patches,
        "note": (
            "Pilot sampling, not exhaustive global coverage. "
            "Baseline and expanded discovery counts are reported separately."
        ),
    }


# --- Terrain elevation service ---

import numpy as np


@lru_cache(maxsize=1)
def terrain_index():
    """Map patch IDs to their actual elevation archives."""
    root = ROOT / "data/processed/ml_patches"

    index = {"mars": {}, "earth": {}, "moon": {}}

    sources = {
        "mars": [root / "mars_jezero.npz"],
        "earth": sorted((root / "earth").glob("*.npz")),
        "moon": [root / "moon_site04_experimental.npz"],
    }

    for body, paths in sources.items():
        for path in paths:
            if not path.exists():
                continue

            try:
                with np.load(path, allow_pickle=False) as archive:
                    ids = archive["patch_ids"].tolist()
            except (OSError, ValueError, KeyError) as exc:
                raise HTTPException(
                    503, f"Terrain index archive unavailable or corrupt: {path.name}"
                ) from exc

            for position, patch_id in enumerate(ids):
                if patch_id in index[body]:
                    raise HTTPException(
                        503, f"Duplicate terrain patch ID: {patch_id}"
                    )
                index[body][patch_id] = (path, position)

    return index


@app.get("/api/terrain/{body}/{patch_id}")
def terrain_elevation(body: str, patch_id: str, grid: int = 64):
    if body not in ("mars", "earth", "moon"):
        raise HTTPException(404, "Unknown planetary body")
    if grid not in (32, 64):
        raise HTTPException(422, "Grid must be 32 or 64")

    entry = terrain_index()[body].get(patch_id)

    if entry is None:
        raise HTTPException(404, "Terrain patch not found")

    path, position = entry

    try:
        with np.load(path, allow_pickle=False) as archive:
            elevation = archive["elevation"][position].astype(np.float32)
            valid = archive["valid_mask"][position].astype(bool)
            resolution_m = float(archive["resolution_m"])
    except (OSError, ValueError, KeyError, IndexError) as exc:
        raise HTTPException(503, "Terrain archive unavailable or corrupt") from exc

    if (elevation.shape != (64, 64) or valid.shape != elevation.shape
            or not np.isfinite(resolution_m) or resolution_m <= 0):
        raise HTTPException(503, "Invalid terrain archive dimensions or resolution")

    # Downsample for efficient interactive rendering.
    step = 64 // grid
    elevation = elevation[::step, ::step]
    valid = valid[::step, ::step]

    if not np.isfinite(elevation[valid]).all():
        raise HTTPException(503, "Invalid terrain elevations")

    values = elevation[valid]

    if values.size == 0:
        raise HTTPException(503, "Terrain has no valid pixels")

    return {
        "body": body,
        "patch_id": patch_id,
        "grid_size": list(elevation.shape),
        "sampling": "native_patch_grid" if grid == 64 else "every_second_cell",
        "resolution_m": resolution_m * step,
        "elevation_unit": "metres",
        "vertical_reference": "patch-relative elevation",
        "elevation": np.where(valid, elevation, 0).tolist(),
        "valid_mask": valid.astype(int).tolist(),
        "minimum_m": float(values.min()),
        "maximum_m": float(values.max()),
        "relief_m": float(values.max() - values.min()),
        "valid_fraction": float(valid.mean()),
        "scientific_status": "experimental",
        **({
            "source_attribution": COPERNICUS_ADAPTED_NOTICE,
            "source_liability_notice": COPERNICUS_LIABILITY_NOTICE,
        } if body == "earth" else {}),
    }


# --- Manifest-backed regional terrain service ---

import rasterio


@lru_cache(maxsize=1)
def regional_terrain_profiles():
    """Load the verified 60 km regional terrain catalog."""
    manifest_path = (
        ROOT / "data/processed/processing_manifest.json"
    )

    manifest = read_json(str(manifest_path))
    profiles = {}

    for record in manifest["profiles"]:
        profile_id = record["profile_id"]
        raster_path = record["analysis_raster"]

        if profile_id in profiles:
            raise RuntimeError(
                f"Duplicate regional profile: {profile_id}"
            )

        profiles[profile_id] = {
            "raster": raster_path,
            "record": record,
        }

    return profiles


@app.get("/api/regional-terrain/{profile_id}")
def regional_terrain(profile_id: str):
    profiles = regional_terrain_profiles()

    if profile_id not in profiles:
        raise HTTPException(
            status_code=404,
            detail="Unknown regional terrain profile",
        )

    entry = profiles[profile_id]

    terrain_root = (
        ROOT / "data/processed"
    ).resolve()

    path = (
        terrain_root / entry["raster"]
    ).resolve()

    # Never permit manifest paths outside the data directory.
    if not path.is_relative_to(terrain_root):
        raise HTTPException(
            status_code=500,
            detail="Unsafe raster path",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Regional raster unavailable",
        )

    with rasterio.open(path) as ds:
        elevation = ds.read(1, masked=True)

        valid = (
            ~np.ma.getmaskarray(elevation)
            & np.isfinite(elevation.data)
        )

        if not valid.any():
            raise HTTPException(
                status_code=503,
                detail="No valid terrain elevations",
            )

        if ds.transform.a <= 0 or ds.transform.e >= 0:
            raise HTTPException(
                status_code=503,
                detail="Unexpected raster orientation",
            )

        resolution_m = abs(float(ds.transform.a))

        if not np.isclose(
            resolution_m,
            abs(float(ds.transform.e)),
        ):
            raise HTTPException(
                status_code=503,
                detail="Non-square raster cells",
            )

        values = elevation.data[valid].astype("float64")

        # Regional terrain uses the same patch-relative
        # vertical convention as detailed discovery.
        median = float(np.median(values))

        relative = np.zeros(
            elevation.shape,
            dtype="float32",
        )

        relative[valid] = (
            elevation.data[valid] - median
        ).astype("float32")

    if profile_id.startswith("moon_"):
        body = "moon"
    elif profile_id.startswith("mars_"):
        body = "mars"
    else:
        body = "earth"

    valid_values = relative[valid]

    return {
        "body": body,
        "profile_id": profile_id,
        "patch_id": profile_id,
        "grid_size": list(relative.shape),
        "resolution_m": resolution_m,
        "elevation_unit": "metres",
        "vertical_reference": "regional-median-relative elevation",
        "elevation": relative.tolist(),
        "valid_mask": valid.astype(int).tolist(),
        "minimum_m": float(valid_values.min()),
        "maximum_m": float(valid_values.max()),
        "relief_m": float(np.ptp(valid_values)),
        "valid_fraction": float(valid.mean()),
        "coordinate_system": "local projected raster grid",
        "scientific_status": "experimental",
        **({"source_raster": entry["raster"]} if not PUBLIC_DEMO else {}),
        "source_profile": profile_id,
    }


# --- Expanded Earth discovery experiment ---

@lru_cache(maxsize=1)
def expanded_discovery_index():
    path = ROOT / "outputs/neural_candidate/hybrid_matches.json"

    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Expanded discovery index is unavailable",
        )

    data = read_json(str(path))

    if data.get("earth_patches") != 3736:
        raise HTTPException(
            status_code=503,
            detail="Expanded index has an unexpected patch count",
        )

    return {
        row["mars_patch_id"]: row["matches"]
        for row in data["results"]
    }


@app.get("/api/detailed-expanded/mars/{patch_id}")
def get_expanded_mars_matches(patch_id: str):
    matches = expanded_discovery_index()

    if patch_id not in matches:
        raise HTTPException(
            status_code=404,
            detail="Mars terrain patch not found",
        )

    return {
        "mars_patch_id": patch_id,
        "target_features": target_terrain_features("mars", patch_id),
        "matches": [
            enrich_candidate_quality(match)
            for match in matches[patch_id]
        ],
        "method": "physical_top50_then_neural_rerank",
        "earth_patches": 3736,
        "scientific_status": "experimental_not_validated",
    }


# --- Detailed Earth candidate source-quality metadata ---

@lru_cache(maxsize=1)
def earth_quality_metadata():
    import csv

    directory = ROOT / "data/processed/global/v3_complete"
    result = {}

    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="") as file:
            for row in csv.DictReader(file):
                patch_id = row["patch_id"]

                if patch_id in result:
                    raise ValueError(
                        f"Duplicate Earth metadata: {patch_id}"
                    )

                result[patch_id] = row

    return result


@lru_cache(maxsize=1)
def earth_tile_bounds():
    path = ROOT / "data/metadata/earth_tile_catalog.csv"
    if not path.is_file():
        return {}
    try:
        with path.open(newline="") as file:
            return {row["tile_id"]: row for row in csv.DictReader(file)}
    except (OSError, ValueError, KeyError):
        return {}


def detailed_geographic_label(candidate):
    patch_id = candidate.get("earth_patch_id", "")
    tile_id = candidate.get("tile_id") or patch_id.split("_DEM_")[0] + "_DEM"
    row = earth_tile_bounds().get(tile_id)
    if not row:
        return {}
    try:
        south, north = float(row["south"]), float(row["north"])
        west, east = float(row["west"]), float(row["east"])
        latitude, longitude = candidate["latitude"], candidate["longitude"]
        if not (south <= latitude <= north and west <= longitude <= east):
            return {}
        lat_label = f'{abs(int(south))}°{"N" if south >= 0 else "S"}'
        lon_label = f'{abs(int(west))}°{"E" if west >= 0 else "W"}'
    except (ValueError, KeyError, TypeError):
        return {}
    return {
        "geographic_label": f'Copernicus DEM tile {lat_label}, {lon_label}',
        "geographic_label_source": "earth_tile_catalog.csv",
    }


def enrich_candidate_quality(candidate):
    patch_id = candidate["earth_patch_id"]
    metadata = earth_quality_metadata().get(patch_id)

    if metadata is None:
        raise HTTPException(
            status_code=503,
            detail=f"Earth quality metadata unavailable: {patch_id}",
        )

    return {
        **candidate,
        **detailed_geographic_label(candidate),
        "terrain_features": {
            key: float(metadata[key]) for key in TERRAIN_FEATURES
        },
        "quality_status": metadata["quality_status"],
        "hem_coverage": float(metadata["hem_coverage"]),
        "original_source_fraction": float(
            metadata["original_source_fraction"]
        ),
        "landcover_status": metadata["landcover_status"],
        "dominant_landcover": metadata["dominant_landcover"],
    }


TERRAIN_FEATURES = (
    "mean_slope_deg", "p95_slope_deg", "roughness_m",
    "relief_m", "elevation_std_m",
)


@lru_cache(maxsize=2)
def target_feature_rows(body):
    import csv

    path = (ROOT / "data/processed/mars/mars_terrain_features.csv"
            if body == "mars" else
            ROOT / "outputs/moon_site04_experimental/lunar_terrain_features.csv")
    if not path.is_file():
        raise HTTPException(503, "Target terrain features unavailable")
    try:
        with path.open(newline="") as file:
            rows = list(csv.DictReader(file))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Target terrain features unavailable") from exc
    return {row["patch_id"]: row for row in rows}


def target_terrain_features(body, patch_id):
    row = target_feature_rows(body).get(patch_id)
    if row is None:
        raise HTTPException(503, "Target terrain features missing")
    return {key: float(row[key]) for key in TERRAIN_FEATURES}


# --- Experimental detailed Moon-to-Earth discovery ---

MOON_DISCOVERY_PATH = (
    ROOT / "outputs/moon_site04_experimental/hybrid_matches.json"
)


@lru_cache(maxsize=1)
def moon_discovery_index():
    data = read_json(str(MOON_DISCOVERY_PATH))

    if data.get("planet") != "Moon":
        raise HTTPException(503, "Invalid lunar discovery dataset")

    if data.get("earth_patches") != 3762:
        raise HTTPException(503, "Unexpected lunar Earth index size")

    results = data.get("results", [])
    if len(results) != 2:
        raise HTTPException(503, "Unexpected lunar target count")

    ids = [item["moon_patch_id"] for item in results]
    if len(set(ids)) != len(ids):
        raise HTTPException(503, "Duplicate lunar target IDs")

    for item in results:
        if len(item.get("matches", [])) != 5:
            raise HTTPException(503, "Invalid lunar match count")

        if any(
            match.get("earth_patch_id") not in earth_quality_metadata()
            for match in item["matches"]
        ):
            raise HTTPException(503, "Lunar candidate metadata missing")

    return data


@app.get("/api/detailed/moon")
def detailed_moon():
    data = moon_discovery_index()

    return {
        "count": len(data["results"]),
        "planet": "Moon",
        "target_site": data["target_site"],
        "method": data["method"],
        "scientific_status": data["status"],
        "search_scope": "sampled_earth_tiles",
        "earth_patches": data["earth_patches"],
        "patches": [
            {
                "index": i,
                "patch_id": item["moon_patch_id"],
                "candidate_count": len(item["matches"]),
            }
            for i, item in enumerate(data["results"])
        ],
    }


@app.get("/api/detailed/moon/{patch_id}")
def detailed_moon_matches(patch_id: str):
    data = moon_discovery_index()

    for item in data["results"]:
        if item["moon_patch_id"] == patch_id:
            return {
                "planet": "Moon",
                "target_site": data["target_site"],
                "method": data["method"],
                "scientific_status": data["status"],
                "search_scope": "sampled_earth_tiles",
                "earth_patches": data["earth_patches"],
                "moon_patch_id": patch_id,
                "target_features": target_terrain_features("moon", patch_id),
                "clipped_fraction": item["clipped_fraction"],
                "matches": [
                    enrich_candidate_quality(match)
                    for match in item["matches"]
                ],
            }

    raise HTTPException(404, "Lunar terrain patch not found")


# Serve only the compiled app and its public build assets in demo mode.
# Raw DEMs, result JSON, model files and source directories have no file routes.
if PUBLIC_DEMO:
    if not (FRONTEND_DIST / "index.html").is_file():
        raise RuntimeError("Production frontend build is missing; run npm run build")
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"),
              name="public-assets")

    @app.get("/", include_in_schema=False)
    def public_index():
        return FileResponse(FRONTEND_DIST / "index.html",
                            media_type="text/html",
                            headers={"Cache-Control": "no-store"})
