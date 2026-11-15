# TerraMirror challenge requirements audit

Audited 2026-11-15 against the [official NASA Space Apps challenge](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/). The official page returned HTTP 502 to the page reader during this audit; its search-indexed challenge statement was accessible. This matrix uses that statement, not inferred requirements from the unavailable detail/resources tabs. The statement asks for open Earth, Moon, and Mars data to identify and characterize terrestrial analogs for future bases or landing sites and present findings as a map, visualization, or tool. Deserts, polar, volcanic, arid, caves and other analogous environments are examples, not a requirement to process every environment.

## Repository inventory and entry points

| Area | Current evidence |
| --- | --- |
| API | `src/discovery_api.py` is the working FastAPI app: `/api/health`, regional discovery, detailed Mars and Moon discovery, coverage, detailed terrain, regional terrain. `src/api.py` is a stale incomplete entry point with imports of absent `novelty_engine` and `llm_brain`; do not start it. |
| Regional pipeline | `src/ingestion.py`, `src/features.py`, `src/model.py`, `src/prepare_model.py`; manifest and profile data in `data/processed/`; regional result JSON files in `data/processed/ml/`. |
| Detailed pipeline | `scripts/build_ml_patches.py`, `train_terrain_encoder.py`, `match_neural.py`, `build_hybrid_matches.py`, Earth scanning and quality scripts. Saved 64×64 NPZ patches, checkpoint, and rankings in `data/processed/ml_patches/`, `models/`, `outputs/`. |
| Frontend | `frontend/src/App.tsx` coordinates selection, MapLibre, candidate details and API calls; `components/TerrainComparison.tsx` builds masked Three.js meshes from API elevation. No frontend automated test suite exists. |
| Data provenance | `data/metadata/sources.csv`, `processing_manifest.json`, evidence JSON/XML/PDF files and `data/catalog/planetary_rois.json`. Product-specific source quality is recorded but is not an independent site validation. |
| Existing tests | `tests/test_features.py`, `test_model.py`, `test_prepare_model.py`, and new `test_discovery_api.py`. Run via `.venv/bin/python -m pytest -q`; direct `.venv/bin/pytest` fails collection because the repository root is absent from its import path. |

## Requirement to evidence matrix

| Challenge or submission need | Status | Evidence and limit |
| --- | --- | --- |
| Use real open Earth terrain data | Complete and verified | Local Earth patch archives and metadata exist; sampled Copernicus/other source products are described in `sources.csv`. Current archives hold 3,762 Earth patches; only subsets enter saved Mars indexes. |
| Use real Mars and Moon data | Complete and verified | Mars MOLA and Moon LOLA source records, 255 Mars 64×64 patches, four Site04 64×64 patches, regional Moon rasters. Site04 is an experimental local target; do not call it a designated base. |
| Identify ranked terrestrial candidates | Complete and verified | Saved baseline Mars 3,505, expanded Mars 3,736, and experimental Moon 3,762-index result files. Output hashes and coordinate/metadata checks are tested. These are rankings within sampled inputs. |
| Characterize candidate topography and quality | Partially implemented | Feature CSVs contain slope, roughness, relief, elevation spread and quality fields. Detailed API and UI now expose target and Earth feature values plus distance, cover and quality. Browser presentation and expert interpretation remain unverified. |
| Present results on an interactive map | Complete and verified | Headless Chrome verified street and NASA Blue Marble rendering, visible linked attribution, candidate fly-to, marker popup, zoom, reset and 390 px width. Blocked host, tile 404 and offline tests returned to Street. Fallback probes the selected central tile; Blue Marble remains a coarse mosaic. |
| Compare actual planetary and Earth terrain in 3D | Complete and verified | API elevations and masks match saved archives. Headless Chrome rendered Mars–Earth and Moon–Earth surfaces and exercised 64×64/32×32 sampling, orbit, pan, zoom, presets and reset. Invalid-cell exclusion is tested at the data level; cross-browser and physical-device appearance remain open. |
| Establish analog suitability beyond terrain | Missing | No independent field geology, mineralogy, radiation, climate, resource, access or operations suitability labels. Terrain similarity alone cannot establish a mission analog. |
| Search all geographic environments or the whole Earth | Outside justified prototype scope | Earth catalog lists 26,450 tiles; only a small pilot sample has been processed. A global coverage claim is unsupported. Cave interiors are not resolved by regional DEMs. |
| Scientifically validate rank quality | Missing | No expert relevance labels or independent ground truth. Recall@K, Precision@K, NDCG@K and Hit Rate@K cannot be calculated legitimately. Reconstruction error measures the autoencoder, not analog relevance. |
| Reproduce and explain the discovery | Partially implemented | Pipeline scripts, source manifest, updated README and model card exist. Full data reacquisition and end-to-end replay have not been verified. |

## Priority gaps and risks

1. **P0:** `src/api.py` remains a broken legacy entry point; run `src.discovery_api:app`. Coverage counts now come from the catalog and saved discovery indexes. Preserve result files before changing discovery code.
2. **P1:** Extend the tested browser path to physical devices, more browsers, partial tile outages and production hosting. Blue Marble supports a global satellite view but does not provide local high-resolution imagery.
3. **P2:** Review the displayed detailed feature differences with domain experts. Validate ranking with independent criteria before any accuracy or mission suitability claim.
4. **P2:** Expand spatially independent Earth samples. Existing tile-level model validation does not prove generalization to all Earth environments or to Moon/Mars.

## Preservation plan used

- No trained weights, source rasters, patch archives, or saved result JSON files were modified. The baseline, expanded and lunar result SHA-256 values are pinned in `tests/test_discovery_api.py`.
- Original source files modified in this batch were copied to `/tmp/terramirror-*.bak` before editing. Untracked project directories remain in place. No commit or push was made.
- Changes are confined to the discovery API, frontend, tests, and documentation. New results are marked experimental until independent scientific validation exists.
