# TerraMirror

TerraMirror is an experimental response to the [NASA Space Apps 2026 challenge to identify Earth locations that analog permanent Moon base locations and Mars](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/). It ranks sampled Earth DEM patches by **topographic** similarity to Mars Jezero and experimental Moon Site04 targets, maps the candidates, and compares measured elevation grids in 3D. It does not establish geological or operational analog suitability.

## Screenshots and visual evidence

Current application screenshots were captured and reviewed locally. They are **excluded from this source-code publication** while the Copernicus-derived image provenance and redistribution review remains open. The [visual verification report](docs/VISUAL_ENHANCEMENT_VERIFICATION.md) records the local capture paths and browser checks. The satellite layer uses NASA GIBS Landsat WELD with visible map attribution; 3D colour represents relative elevation, not surface composition. The Earth elevation source and liability notices are described in [public deployment preparation](docs/PUBLIC_DEPLOYMENT_PREP.md).

## Run locally

The working API is `src.discovery_api:app`; `src/api.py` is an older incomplete module.

```bash
# From the repository root, with the existing Python environment and data artifacts
.venv/bin/uvicorn src.discovery_api:app --host 127.0.0.1 --port 8000
# In a second terminal
cd frontend
npm ci
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`. Vite proxies same-origin `/api` calls to the local API at `http://127.0.0.1:8000`; check `http://127.0.0.1:8000/api/health`. Python dependencies are listed in `requirements.txt` and `requirements-ml.txt`; the local `.venv` was used for verification. Node and npm must be installed. Map tiles require an internet connection. No API key is embedded in the frontend.

## Local production preview

Build with `cd frontend && npm run build`, then from the repository root run:

```bash
TERRAMIRROR_PUBLIC_DEMO=1 .venv/bin/uvicorn src.discovery_api:app --host 127.0.0.1 --port 8765 --workers 1 --limit-concurrency 20 --timeout-keep-alive 5
```

Open `http://127.0.0.1:8765`. This mode serves only the compiled homepage and `/assets/` through FastAPI, with same-origin read-only `/api` routes. It disables HTTP API documentation and limits requests. Do not expose this local server through a tunnel until the [public deployment preparation review](docs/PUBLIC_DEPLOYMENT_PREP.md) is cleared and approved. No public deployment has been tested or authorized.

## Demonstration

1. Choose **Detailed AI discovery**, then **Mars — Jezero** or **Moon — Site04 (experimental)**.
2. Choose a target patch. Mars offers baseline and expanded Earth indexes; Moon offers two selected target patches.
3. Read the ranked candidates and their physical and embedding distances. Geographic labels appear only where local acquisition metadata or Copernicus tile bounds support them; precise coordinates remain visible. Select a candidate to fly to its Earth coordinate; click its marker for a popup.
4. Switch between OpenStreetMap Street, historical NASA/USGS Landsat WELD Satellite (2000), and NASA Blue Marble Global views. Landsat provides sharper local context where tiles exist. If it fails, the map falls back to Blue Marble, then to Street if NASA imagery is unavailable. Reset the map to the candidate set if needed.
5. Inspect source quality and the measured slope, relief and roughness comparison. Select **Compare in 3D** to scroll to the existing terrain viewer. Use 64×64 measured grid cells or the lighter 32×32 sampled display, Top/Oblique/Side camera presets, orbit, pan, zoom, and disclosed vertical exaggeration. The base grid is a visual guide.
6. Choose another candidate. For a separate 60 km morphology comparison, choose **Regional discovery**.

## Data and methods

The regional pipeline uses 60 km projected DEM profiles at 1 km common spacing. Detailed retrieval uses 64×64 patches at 90 m grid spacing; the lighter display samples every second cell and does not synthesize elevation. `data/metadata/sources.csv` and `data/processed/processing_manifest.json` record the regional sources, quality and processing; `data/metadata/earth_tile_catalog.csv` identifies the detailed Copernicus tile URLs. The current `sources.csv` lacks detailed Copernicus DEM rights records, so its derived Earth patch archives need a license-notice review before public distribution. Key sources include [NASA PDS MOLA Mars topography](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/), [NASA LRO LOLA lunar DEMs](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/), [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/copernicus-dem), [NASA LP DAAC NASADEM](https://lpdaac.usgs.gov/products/nasadem_hgtv001/), and [ESA WorldCover](https://worldcover2021.esa.int/). The street basemap uses [OpenStreetMap tiles and attribution](https://operations.osmfoundation.org/policies/tiles/). Satellite imagery uses [NASA/USGS Landsat WELD annual true color for 2000](https://lpdaac.usgs.gov/products/gweldyrv031/) at about 30 m source resolution through [NASA GIBS WMTS](https://nasa-gibs.github.io/gibs-api-docs/access-basics/), with tiles published through Web Mercator zoom 12. Blue Marble Next Generation is the coarse global fallback: 500 m source imagery and about 611 m per pixel on the Level8 Web Mercator grid at the equator. Zooming beyond a layer's maximum enlarges its imagery. We acknowledge imagery provided by NASA GIBS, part of NASA's Earth Science Data and Information System. These historical basemaps are visual context, not DEM input or georeferenced 3D textures; local imagery may be absent, cloudy, or different from present conditions. Tile requests are limited to ordinary interactive map use, with no bulk prefetch.

The model is an Earth-trained PyTorch convolutional autoencoder with 32-dimensional learned embeddings. Detailed matching screens the nearest 50 Earth patches using five standardized physical features—mean slope, 95th-percentile slope, roughness, relief, and elevation variability—then reranks that shortlist by embedding distance and returns the top five. Saved indexes include 255 Jezero target patches, 3,505 Earth patches in baseline Mars matching, 3,736 in expanded Mars matching, and 3,762 available local Earth patches in the Moon experiment. The sampled Earth archive does **not** constitute global terrain coverage. The model and regional method are described in the [model card and evaluation](docs/MODEL_CARD_AND_EVALUATION.md); requirement evidence is in the [challenge audit](docs/CHALLENGE_REQUIREMENTS_AUDIT.md), the presentation path is in the [NASA demonstration checklist](docs/NASA_DEMO_CHECKLIST.md), and the [release candidate inventory](docs/RELEASE_CANDIDATE.md) lists package contents and blockers.

The complete dashboard also needs saved result JSON, regional terrain rasters and metadata, and Earth/Mars/Moon patch archives in the paths recorded by [the runtime asset manifest](docs/RUNTIME_ASSET_MANIFEST.csv). The 21 local Copernicus Earth archives are intentionally ignored by Git. A source-only clone cannot run the complete discovery or 3D workflow until those assets are separately obtained under their applicable terms and verified against the manifest. Do not treat a source clone as a complete scientific data release.

## Reproduce checks

For a **source-only** clone, Python 3.11 and Node 24 were used in the isolated release rehearsal:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q tests/test_features.py tests/test_model.py tests/test_prepare_model.py
cd frontend
npm ci
npm run build
npm run lint
```

The three selected Python test modules exercise the earlier feature/model preparation code with test fixtures; **they do not reproduce Mars/Moon discovery results or establish analog accuracy**. The detailed PyTorch training/evaluation scripts also require a separately installed compatible PyTorch build, the preserved checkpoint, and terrain archives. The current Python requirements files do not pin PyTorch. The complete data-dependent suite requires the runtime assets in the manifest:

```bash
.venv/bin/python -m pytest -q
cd frontend && npm run build
```

The tests pin saved ranking hashes and check representative API contracts, candidate coordinates/metadata, and native terrain elevations/masks. The scripts in `scripts/` document training, ingestion, matching and evaluation; **do not rerun them into existing output paths** without first choosing separate output locations and preserving the original artifacts. Reproducing data acquisition may require large external downloads and source-specific terms. Headless browser acceptance of the production build, satellite failures, camera behavior and mobile emulation is recorded in [final verification](docs/FINAL_VERIFICATION.md). Physical devices, other browsers and public deployment remain untested.

The [submission packaging audit](docs/SUBMISSION_PACKAGING.md) identifies a proposed source allowlist, exact runtime asset hashes, licensing gaps and a distribution plan. The [submission draft and seven-slide outline](docs/NASA_SUBMISSION_DRAFT.md) are review materials, not a submitted project. The [visual enhancement verification](docs/VISUAL_ENHANCEMENT_VERIFICATION.md) records the latest imagery and 3D browser checks.

## Scientific limits

Rankings are experimental. Terrain resemblance does not establish matching geology, resources, climate, gravity, radiation, accessibility, caves or suitability for a permanent base. Planetary DEMs can contain interpolation, and Earth data have quality and geographic sampling limits. Embedding distances are uncalibrated and lunar target distances are especially high. No independent relevance labels exist, so ranking precision and recall are unknown. 3D heights use patch-relative measured DEM values, with invalid cells omitted and vertical exaggeration disclosed.
