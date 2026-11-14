**🌍 TerraMirror (NASA Space Apps 2026)**
AI-powered GIS pipeline to identify novel Earth analogs for lunar and Martian landing sites.
**👥 Team Workstreams & Files**
- **Member 1 (Data Ingestion):** `src/ingestion.py` — Loads and cleans `.tif` rasters (Moon & Earth).
- **Member 2 (Feature Engineering):** `src/features.py` — Extracts sliding-window patch statistics (slope, roughness).
- **Member 3 (ML Model):** `src/model.py` — Runs StandardScaler & Cosine Similarity to score matches.
- **Member 4 (Backend API):** `src/api.py` — Wraps model outputs into a FastAPI endpoint / GeoJSON.
**📁 Shared Data Output Contract (**`data/processed/analog_results.json`**)**
All scripts must link to output a JSON following this schema so the frontend can read it later:
```json
{
  "target_site": "Mars Target: Jezero Crater (Delta Front)",
  "timestamp": "2026-10-12",
  "top_analogs": [
    {
      "rank": 1,
      "location_name": "Qaidam Basin, China / Iceland Interior",
      "latitude": 37.2,
      "longitude": 94.3,
      "similarity_score": 0.952,
      "metrics": {
        "slope_match": 0.961,
        "roughness_match": 0.940,
        "thermal_match": 0.955
      },
      "caveats": "Gravity divergence (0.38g vs 1g), thin CO2 atmosphere vs nitrogen/oxygen."
    }
  ]
}
```

The values above illustrate the intended schema; they are not measured results.
See [Model preparation and usage](MODEL.md) for the ML implementation, input
contract, optional thermal data, score definitions, and validation plan.

**ML status:** the real-data runner is ready: `python -m src.prepare_model`.
It fits 15 QA-eligible Earth profiles and ranks all 3 planetary targets using
standardized Euclidean distance; cosine remains available with `--metric cosine`.
See `requirements-ml.lock` for the tested Python 3.11 ML environment. Outputs are
in `data/processed/ml/`, with Jezero exported to the shared JSON path above.
Numerical checks pass; scientific analog suitability remains unvalidated.
