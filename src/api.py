import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------
# Where the model's results live.
# __file__ is this file (src/api.py). parents[1] is the project root.
# So ML_DIR = <project root>/data/processed/ml
# ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ML_DIR = PROJECT_ROOT / "data" / "processed" / "ml"

app = FastAPI(
    title="TERRAVIA API",
    description="Backend for matching Moon/Mars terrain to Earth analog locations.",
    version="0.1.0",
)

# ---------------------------------------------------------------
# CORS: browsers block a web page on one address (React on port 5173)
# from calling an API on another address (FastAPI on port 8000)
# unless the API says it is allowed. This list says who is allowed.
# ---------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DISCLAIMER = (
    "Similarity scores are heuristic terrain-feature comparisons, not probabilities "
    "or proof of operational equivalence. Gravity, atmosphere and radiation differ "
    "from Earth. Scientific suitability has not been validated."
)


# ---------------------------------------------------------------
# Helper functions (used by the endpoints below)
# ---------------------------------------------------------------
def find_result_files():
    """Return {target_id: file_path} for every <target_id>_results.json in the ML folder."""
    if not ML_DIR.is_dir():
        raise HTTPException(
            status_code=503,
            detail="Model results folder not found. Run: python -m src.prepare_model",
        )
    files = {}
    for path in sorted(ML_DIR.glob("*_results.json")):
        target_id = path.name[: -len("_results.json")]
        files[target_id] = path
    return files


def load_target_results(target_id: str) -> dict:
    """Load the saved model results for one target, or raise a clear error."""
    files = find_result_files()
    if target_id not in files:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown target '{target_id}'. See /targets for valid IDs.",
        )
    try:
        return json.loads(files[target_id].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Could not read the results file.")


# ---------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------
@app.get("/health")
def health_check():
    """Quick check that the server is alive and can see the model results."""
    return {
        "status": "ok",
        "service": "TERRAVIA API",
        "results_folder_found": ML_DIR.is_dir(),
    }


@app.get("/targets")
def list_targets():
    """List the Moon/Mars targets the frontend can choose from."""
    targets = []
    for target_id, path in find_result_files().items():
        data = load_target_results(target_id)
        targets.append({"target_id": target_id, "target_site": data.get("target_site")})
    return {"targets": targets}


@app.get("/analogs/{target_id}")
def get_analogs(
    target_id: str,
    top_k: int = Query(5, ge=1, le=15, description="How many matches to return"),
):
    """Ranked Earth matches for one target, as ordinary JSON."""
    data = load_target_results(target_id)
    data["top_analogs"] = data.get("top_analogs", [])[:top_k]
    data["disclaimer"] = DISCLAIMER
    return data


@app.get("/analogs/{target_id}/geojson")
def get_analogs_geojson(
    target_id: str,
    top_k: int = Query(5, ge=1, le=15),
):
    """The same matches as GeoJSON points, ready for Leaflet map markers."""
    data = load_target_results(target_id)
    features = []
    for analog in data.get("top_analogs", [])[:top_k]:
        try:
            lat = float(analog["latitude"])
            lon = float(analog["longitude"])
        except (KeyError, TypeError, ValueError):
            continue  # skip a match with missing coordinates
        if abs(lat) > 90 or abs(lon) > 180:
            continue  # skip invalid coordinates
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],  # GeoJSON order: longitude FIRST
                },
                "properties": {
                    "rank": analog.get("rank"),
                    "location_name": analog.get("location_name"),
                    "similarity_score": analog.get("similarity_score"),
                    "metrics": analog.get("metrics", {}),
                    "caveats": analog.get("caveats"),
                    "source_ids": analog.get("source_ids", []),
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "target_site": data.get("target_site"),
        "disclaimer": DISCLAIMER,
        "features": features,
    }