# TerraMirror NASA demonstration checklist

The [release candidate presentation script](RELEASE_CANDIDATE.md#final-presentation-script) provides a spoken walkthrough and the package/risk inventory.

## Before the presentation

- [ ] Keep the existing model, NPZ terrain archives, regional rasters, source metadata and saved rankings available. Start the API with `.venv/bin/uvicorn src.discovery_api:app --host 127.0.0.1 --port 8000` and the frontend with `cd frontend && npm run dev`.
- [ ] Confirm `/api/health` returns `status: ok` and the browser shows five regional candidates. Use a connected browser for NASA and OpenStreetMap tiles; DEM comparisons use local API data.
- [ ] Confirm the map credits link to NASA GIBS, NASA/USGS Landsat WELD, and OpenStreetMap as applicable. Landsat WELD is a historical 2000 composite with about 30 m source imagery and Web Mercator tiles through zoom 12. Blue Marble is a coarse global overview with 500 m source imagery and Level8 tiles.

## Live walkthrough

1. Show **Regional discovery** for Mars Jezero; explain that it compares 60 km surface morphology.
2. Choose **Detailed AI discovery**, Mars Jezero, and a target patch. Show the baseline and expanded Earth indexes separately.
3. Select a ranked Earth candidate. Confirm the highlighted marker flies to the candidate, then click a marker to show coordinates, rank, physical and neural distances, and source-quality status.
4. Switch between **Street · OpenStreetMap**, **Satellite · Landsat WELD (2000)**, and **Global · NASA Blue Marble**. Explain each imagery scale and attribution. Missing Landsat tiles fall back to Blue Marble; missing NASA imagery falls back to Street. A disconnected street layer may also lack tiles.
5. Show measured target/Earth slope, roughness, relief and elevation variability. Explain that the hybrid method screens 50 physical candidates before neural reranking and that distances are not probabilities.
6. Open the 3D comparison. Show 64×64 measured DEM cells, the lighter 32×32 sampling option, valid-coverage indicator, Top/Oblique/Side views, orbit, pan, zoom, camera reset and disclosed vertical exaggeration. Missing cells are omitted from surface triangles; the base grid is a visual guide.
7. Select a second Earth candidate and confirm its displayed relief and terrain surface change.
8. Switch to **Moon — Site04 (experimental)**. Show a lunar target and Earth comparison; state that Site04 is not a designated lunar base and lunar embedding distances are uncalibrated and high.
9. Close with the limits: sampled Earth coverage, planetary interpolation, Earth source-quality flags, no independent relevance labels, and no claims about geology, mineralogy, climate, radiation, resources or operational suitability.

## If a service fails

- Satellite failure: use the Blue Marble or Street fallback and show the provider notice. If offline, basemap tiles may be blank; candidate coordinates, ranked results and local DEM comparison remain available while the local API stays running.
- Terrain/API failure: do not present an empty or stale 3D view as measured terrain. Restart the local API, check `/api/health`, and use the saved result/metadata documentation only if the local source artifact is unavailable.
