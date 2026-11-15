# TerraMirror submission packaging audit — 2026-11-15

**Historical checkpoint:** This review predates the same-origin API change and the source-only publication. The current setup is in the [README](../README.md) and [public deployment preparation](PUBLIC_DEPLOYMENT_PREP.md). Dataset redistribution and public elevation API access remain separate reviews.

This is a **proposed export**, not a staged commit, public release, or independently tested package. Preserve the current working tree. The exact paths, byte sizes and SHA-256 values of live data dependencies are in [RUNTIME_ASSET_MANIFEST.csv](RUNTIME_ASSET_MANIFEST.csv); the [release candidate report](RELEASE_CANDIDATE.md) records local acceptance.

## Current Git and local inventory

`git ls-files` listed 161 tracked files. `git status --short --untracked-files=all` reported a modified root `README.md` and untracked `docs/`, `frontend/`, `models/`, `outputs/`, `scripts/`, `src/discovery_api.py`, and `tests/test_discovery_api.py`. `git status --short --ignored` found the 6.1 GB `.venv`, 409 MB `frontend/node_modules`, 2.3 MB `frontend/dist`, `.pytest_cache`, Python bytecode, and 328 MB `data/raw` plus ignored processed Earth/Mars/patch data. Two `.pyc` files are **already tracked** (`src/__pycache__/features.cpython-311.pyc` and `tests/__pycache__/test_features.cpython-311-pytest-8.3.3.pyc`); omit them from a curated export. No file was deleted or staged.

The filename scan found no `.env`, private-key, certificate, credential or temporary log in the proposed source paths. A content-pattern scan over authored source, docs, catalogs and metadata found no obvious credential token/key pattern. This bounded scan cannot prove the entire Git history, binaries, third-party metadata, or external storage is free of sensitive material. `data/metadata/evidence/registration.json` contained selection/integrity keys, not a personal registration form. Review the final export and its history before making it public.

## Precise source allowlist for a curated export

Include these **exact source files** after a human diff/rights review. No staging or export has occurred.

- Root: `.gitignore`, `README.md`, `requirements.txt`, `requirements-ml.txt`, `requirements-ml.lock`.
- API and model preparation: `src/discovery_api.py`, `src/features.py`, `src/ingestion.py`, `src/model.py`, `src/prepare_model.py`.
- Tests: `tests/test_discovery_api.py`, `tests/test_features.py`, `tests/test_model.py`, `tests/test_prepare_model.py`.
- Frontend build/config: `frontend/.gitignore`, `frontend/index.html`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/eslint.config.js`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`.
- Frontend UI: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/App.css`, `frontend/src/index.css`, `frontend/src/components/MatchExplanation.tsx`, `frontend/src/components/MatchExplanation.css`, `frontend/src/components/TerrainComparison.tsx`.
- Frontend icon: `frontend/public/favicon.svg`, **conditional on checking its authorship/rights**. `frontend/index.html` currently loads it.
- Reproduction scripts: `scripts/add_worldcover.py`, `scripts/audit_earth_quality.py`, `scripts/build_earth_catalog.py`, `scripts/build_hybrid_matches.py`, `scripts/build_ml_patches.py`, `scripts/compare_rankings.py`, `scripts/complete_earth_tile.py`, `scripts/diagnose_embeddings.py`, `scripts/evaluate_match_quality.py`, `scripts/evaluate_neural_matches.py`, `scripts/evaluate_saved_checkpoint.py`, `scripts/extract_earth_features.py`, `scripts/extract_mars_features.py`, `scripts/finalize_worldcover.py`, `scripts/match_neural.py`, `scripts/match_pilot.py`, `scripts/run_discovery_pipeline.py`, `scripts/run_earth_ingestion.py`, `scripts/scan_earth.py`, `scripts/scan_earth_v2.py`, `scripts/scan_earth_v3.py`, `scripts/scan_global_batch.py`, `scripts/train_terrain_encoder.py`, `scripts/visualize_match_comparison.py`. These scripts are retained as historical pipeline evidence; do not execute write-producing defaults over frozen outputs.
- Documentation: `docs/CHALLENGE_REQUIREMENTS_AUDIT.md`, `docs/FINAL_VERIFICATION.md`, `docs/MODEL_CARD_AND_EVALUATION.md`, `docs/NASA_DEMO_CHECKLIST.md`, `docs/RELEASE_CANDIDATE.md`, `docs/SUBMISSION_PACKAGING.md`, `docs/NASA_SUBMISSION_DRAFT.md`, `docs/RUNTIME_ASSET_MANIFEST.csv`.

**Exclude from curated source export:** `src/api.py` (known incomplete legacy entry point), `scripts/add_worldcover_v1_backup.py`, `frontend/README.md` (Vite template), unused `frontend/src/assets/hero.png`, `react.svg`, `vite.svg`, and unused `frontend/public/icons.svg`; all caches, `.venv`, `node_modules`, `dist`, bytecode, raw source downloads and regenerated visual outputs. This is an export recommendation only; these files remain untouched. `MODEL.md` documents the historical regional model but describes the old baseline; prefer the current model card and audit in the submission package. Existing Git history contains some excluded tracked files, so making the existing repository public requires a history/content review or a separately curated export. Do not rewrite history in this working tree.

## Runtime dependency map and byte sizes

The API reads **saved** retrieval products and elevation archives. It does **not** load `best_model.pt` to serve candidates; that checkpoint is needed to reproduce the ML work. The manifest has 82 files, 65,394,085 bytes total: 79 live runtime files plus `sources.csv`, the checkpoint and its training metadata. Relevant grouped on-disk sizes are:

| Dependency | Files | Bytes | Needed for |
| --- | ---: | ---: | --- |
| `data/processed/ml_patches/earth/*.npz` | 21 | 51,805,849 | Earth 3D terrain and terrain index |
| `data/processed/ml_patches/mars_jezero.npz` | 1 | 3,431,010 | Mars detailed 3D |
| `data/processed/ml_patches/moon_site04_experimental.npz` | 1 | 61,144 | Moon detailed 3D |
| `data/processed/global/v3_complete/*.csv` | 27 | 1,311,118 | Candidate quality and physical feature metadata |
| Manifest-referenced `data/processed/terrain/*.tif` | 19 | See CSV; terrain directory 510,203 | Regional 3D terrain |
| `data/metadata/earth_tile_catalog.csv` | 1 | 5,848,274 | Coverage endpoint |
| Three regional result JSON files in `data/processed/ml/` | 3 | See CSV; directory 38,418 | Regional rankings |
| `data/processed/processing_manifest.json` | 1 | 21,722 | Regional raster lookup |
| `data/processed/mars/mars_terrain_features.csv` and lunar feature CSV | 2 | 42,335 + 718 | Target physical features |
| Baseline, expanded and Moon saved hybrid JSON | 3 | 673,022 + 673,429 + 4,992 | Detailed retrieval |
| `models/terrain_encoder/best_model.pt` | 1 | 942,965 | ML reproduction only |

The 343,335,935-byte `data/raw` tree, saved embeddings and exploratory outputs are **not live API dependencies**. The regional model's tracked Parquet/profile artifacts are reproduction inputs, not needed by the already saved dashboard rankings. The frontend requests NASA GIBS and OpenStreetMap tiles over the network; no tile cache is included. A model/data bundle without the code and matching source tree layout has not been tested.

## Dependency and runtime configuration plan

1. Prepare a separate clean checkout/export. Preserve the verified local working tree. Confirm every allowlisted file and audit the export for credentials, personal data, unused assets and license notices.
2. Create an isolated Python environment with a version compatible with `requirements.txt`, install its pinned packages, then run the full tests and API health check. The current verified `.venv` is Python 3.14.4 with FastAPI 0.163.0, Uvicorn 0.54.0, NumPy 2.5.4, Rasterio 1.5.2 and Torch 2.14.1; these **differ** from `requirements.txt` pins. The file also omits Torch, so fresh checkpoint evaluation cannot yet be reproduced from the declared dependencies. A Python 3.11 environment is described in historical `MODEL.md` but was not independently rebuilt in this packaging batch.
3. In `frontend/`, use the committed lockfile with `npm ci`, run `npm run build`, then test `npm run preview` against the extracted data/API. The current tested tools were Node 24.18.0 and npm 11.16.0. A clean install has **not** been tested; copying `node_modules` is not a distribution method.
4. Preserve the paths in the CSV manifest when extracting release assets. Check each SHA-256 before starting the API; verify `/api/health`, `/api/coverage`, regional and detailed endpoints, then complete the Mars/Moon browser checklist on the **independent copy**.
5. For a remote host, first parameterize both hardcoded `http://127.0.0.1:8000` frontend constants and configure a deliberate API CORS origin. No environment-variable contract exists yet. Do not claim a remote deployment or insert arbitrary origins into the verified local app.

## Licensing and distribution decision

The 50 rows in `data/metadata/sources.csv` have nonempty rights notes for NASA PDS MOLA/LOLA, NASADEM, PGC ArcticDEM/REMA and USGS/ESA WorldCover sources. PGC's public ArcticDEM/REMA mosaics are [CC BY 4.0 with attribution](https://www.pgc.umn.edu/guides/stereo-derived-elevation-models/pgc-dem-products-arcticdem-rema-and-earthdem/). [ESA WorldCover](https://esa-worldcover.org/en/data-access) is CC BY 4.0 and requests dataset/article acknowledgment. NASA GIBS and [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/) require visible credits; tiles are fetched live and must not be bulk repackaged.

The current frontend lockfile records React/React DOM 19.3.1, Three.js 0.187.0, React Three Fiber 9.8.2, Drei 10.7.9 and Vite 8.3.8 as MIT; MapLibre GL JS 6.18.0 as BSD-3-Clause. Installed Python package metadata records FastAPI 0.163.0 as MIT, Rasterio 1.5.2 and Uvicorn 0.54.0 as BSD-3-Clause, with NumPy/Torch carrying multiple bundled license expressions. This spot check is **not** a complete notice inventory for transitive dependencies, and the installed Python versions differ from the pinned requirements. Generate and review a full third-party license notice for the exact clean package before public release.

**Unresolved Copernicus gap:** all 21 detailed Earth archives are named for Copernicus GLO-30, and `earth_tile_catalog.csv` identifies their tile URLs, but `sources.csv` contains no Copernicus DEM record or tile checksums/rights. The [Copernicus DEM source page](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) says GLO-30 distribution and adaptation require specified source and liability notices; its [license text](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf) grants redistribution with obligations. Before publishing any raw or derived Copernicus archive, bind each local tile to its exact product/license and put the required notices in the asset package and public references. Do not infer that a free download has no conditions.

**Recommended split, after rights review:** a curated source repository for the allowlist, small result JSON, source citations and optionally the sub-1 MB checkpoint; a versioned GitHub Release asset for the ~60 MB runtime DEM/quality/catalog bundle with its manifest and notices. [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) currently permits files under 2 GiB each, so this size is technically suitable. A discipline/data archive with DOI may be better for long-term provenance or large raw inputs; no host, DOI, public URL or independent extraction test exists. Keep the 343 MB raw source tree out of the small runtime bundle. Nothing has been uploaded.

## Explicit blockers

1. Copernicus GLO-30 provenance and required distribution notices are incomplete for the 21 detailed Earth archives.
2. The public repository/export has not been curated or independently scanned; tracked bytecode and historical files remain in the existing Git history. Frontend icon authorship is unconfirmed.
3. The pinned Python dependency file and the tested environment differ; Torch is undeclared for model reproduction; clean Python and npm installs are untested.
4. The standalone package has not been extracted and exercised independently. Remote API URL/CORS configuration and public hosting are not implemented or tested.
5. No independent scientific relevance labels or global Earth coverage exist. No submission link, slides/video or actual Project Tab entry has been created.
