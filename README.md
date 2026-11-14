# 🌍 TerraMirror (NASA Space Apps 2026)

AI-powered GIS pipeline to identify novel Earth analogs for lunar and Martian landing sites.

## 👥 Team Workstreams & Files
* **Member 1 (Data Ingestion):** `src/ingestion.py` — Loads and cleans `.tif` rasters (Moon & Earth).
* **Member 2 (Feature Engineering):** `src/features.py` — Extracts sliding-window patch statistics (slope, roughness).
* **Member 3 (ML Model):** `src/model.py` — Runs StandardScaler & Cosine Similarity to score matches.
* **Member 4 (Backend API):** `src/api.py` — Wraps model outputs into a FastAPI endpoint / GeoJSON.

## 📁 Shared Data Output Contract (`data/processed/analog_results.json`)
All scripts must link to output a JSON following this schema so the frontend can read it later:
```json
{
  "target_site": "Artemis Site 01 (Faustini Rim A)",
  "timestamp": "2026-10-12",
  "top_analogs": [
    {
      "rank": 1,
      "location_name": "Altiplano Volcanic Ridge, Chile",
      "latitude": -23.5,
      "longitude": -67.8,
      "similarity_score": 0.946,
      "metrics": {
        "slope_match": 0.962,
        "roughness_match": 0.931
      }
    }
  ]
}
