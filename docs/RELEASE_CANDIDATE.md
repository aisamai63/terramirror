# TerraMirror release candidate — 2026-11-15

**Later deployment preparation:** The [public deployment preparation review](PUBLIC_DEPLOYMENT_PREP.md) supersedes the hardcoded-localhost and CORS observations below. A local compiled same-origin server was tested; public HTTPS access and elevation-data rights clearance remain open.

**Assessment:** ready for a local, connected NASA Space Apps demonstration from this working tree. Public deployment and a portable source release remain unverified. See the [acceptance report](FINAL_VERIFICATION.md), [requirements matrix](CHALLENGE_REQUIREMENTS_AUDIT.md), [model card](MODEL_CARD_AND_EVALUATION.md), and [live checklist](NASA_DEMO_CHECKLIST.md).

## Inventory and preservation

| Component | Location and release handling |
| --- | --- |
| Source and tests | Include `src/`, `scripts/`, `tests/`, `frontend/src/`, `frontend/public/`, `frontend/package.json`, `frontend/package-lock.json`, and Python requirements. Much of this working source is untracked; a Git URL alone would omit it. |
| Trained model | Preserve `models/terrain_encoder/best_model.pt` and its metadata exactly. Do not retrain for the demo. |
| Saved retrieval | Preserve `outputs/neural/hybrid_matches.json`, `outputs/neural_candidate/hybrid_matches.json`, `outputs/moon_site04_experimental/hybrid_matches.json`, and their supporting files. Keep baseline and expanded results distinct. |
| Terrain and provenance | `data/` contains patch archives, regional rasters, catalogs, `data/metadata/sources.csv`, processing manifest and evidence. The API needs these local files. `data/` is ignored by Git; a source-only checkout cannot run the complete demo. Review redistribution rights and package size before upload. |
| Documentation | Include root `README.md` and `docs/` with evidence, limitations, checklist and this inventory. |
| Generated/local files | `.venv/`, `frontend/node_modules/`, `frontend/dist/` and caches are recreated locally. The frontend's `.gitignore` excludes dependencies and build output. |

Git reported 161 tracked files, modified `README.md`, and untracked `docs/`, `frontend/`, `models/`, `outputs/`, `scripts/`, `src/discovery_api.py`, and `tests/test_discovery_api.py`. `data/` had 307 local files (145 tracked; the rest ignored), about 422 MB. `frontend/` occupied about 412 MB with installed dependencies. Nothing was staged, deleted, committed, pushed or submitted.

Pinned SHA-256: model `306066489a3e3c5c8a1cfc925a2d40025a7ad110ef7e1710da4f3c9bb613e13b`; baseline Mars `2a9d66c40f0a73aaf719fb540a9bbaf1d0ffe9b6a67b56d04059da92feb9bd07`; expanded Mars `0dca4c1f85a4383b44a6945ef3ffb2d4ef630d5b3e6b6e8195ef5f8e893fbce7`; lunar `e670d7005918b3521a716b62c8b491ca2c3eca19773e0dd5e56a8387578ce745`.

## Release verification

| Command/check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | 38 passed, 6 subtests passed |
| `cd frontend && npm run build` | Passed; 2,274.05 kB main JS chunk and Vite size warning |
| `cd frontend && npm run lint` | Passed, exit 0 |
| `.venv/bin/python -m scripts.evaluate_saved_checkpoint` | 427 saved validation patches, 1,742,419 valid pixels, MAE 12.0199260478 m, RMSE 20.6069403968 m |
| `sha256sum` on four files above | Matched pinned hashes |
| Local `uvicorn` and `npm run preview -- --host 127.0.0.1 --port 5173` | API started; `/api/health` returned HTTP 200, 255 Mars patches, 3,505 baseline Earth patches. Compiled frontend passed browser sequence below. |
| Local CORS origin | `Origin: http://localhost:5173` received matching `access-control-allow-origin` |
| Unconfigured remote origin | `Origin: https://example.org` received no `access-control-allow-origin` |

The compiled frontend in headless Chrome passed Mars and Moon retrieval/terrain, both grid sizes, candidate switch, camera presets/orbit/pan/zoom/reset, map marker popup/fly-to/reset, NASA and OSM attribution, blocked/404/offline satellite fallback, and 390 px mobile emulation. This does not establish physical-device or public-host behavior. The acceptance browser script was run from `/tmp/terramirror-acceptance.mjs`, outside the source package.

An optional `fastapi.testclient.TestClient` probe could not start because this Python environment lacks Starlette's `httpx2` extra. The actual running API's CORS behavior was then checked with HTTP requests as recorded above; the 38 project tests did not require TestClient. The first Vite Preview bind attempt was denied by the command sandbox (`EPERM`); the approved localhost retry started and passed browser testing.

## Final presentation script

1. Open the dashboard and introduce TerraMirror as **experimental topographic retrieval over sampled Earth DEM patches**.
2. Select **Detailed AI discovery → Mars — Jezero** and a target patch. Explain the separate baseline and expanded Earth indexes.
3. Select a ranked candidate. Read its coordinates, physical terrain evidence, source quality, physical distance and neural embedding distance. These distances are matching scores, not probabilities or relevance accuracy.
4. Switch Street to **Satellite · NASA Blue Marble** and show the visible NASA/OSM credits. The mosaic is coarse global context, not local high-resolution site imagery. Select a candidate to fly to its highlighted marker, click a marker for its popup, then reset the view.
5. Compare actual Mars and Earth DEM surfaces at 64×64. Orbit, pan, zoom, show 32×32, reset the camera, and explain coverage and vertical exaggeration. Choose another Earth candidate to show a different surface/relief.
6. Switch to **Moon — Site04 (experimental)** and compare one of its two selected targets with an Earth candidate. Site04 is not a designated base site; lunar embedding distances are high and uncalibrated.
7. Close with the evidence boundary: saved rankings reproduce and Earth validation reconstruction error is measurable; independent geological/operational analog relevance and global Earth discovery are not established.

## Submission assets and blockers

**Available locally:** source/lockfile, startup instructions, model/terrain/result artifacts, 50 source records with nonempty rights notes, model card, requirement matrix, acceptance report, checklist and script. Dataset/basemap references are in the README and `sources.csv`. No 3D imagery texture is presented as measured elevation.

**Still needed for actual submission:** choose and verify a portable artifact or data delivery plan; review redistribution rights and size; prepare slides or a short demo video with public access if requested by the live 2026 form or local event; complete the team Project Tab and source/reference fields. No slides, video, public artifact URL or verified public deployment was found in this repository. The official 2026 site says submission is through the team's Project Tab by November 15 at 11:59 PM local time; confirm the live form and event rules for exact fields and formats.

**Remote live-app blockers:** `App.tsx` and `TerrainComparison.tsx` hardcode `http://127.0.0.1:8000`; API CORS permits only local Vite origins; `src/api.py` is an incomplete legacy entry point; ignored DEM archives and saved rankings are absent from a source-only clone. No public host or data delivery has been configured or tested. None blocks the verified local demo.

**Scientific/QA limits:** Earth coverage is sampled, not global. There are no independent relevance labels, expert field judgments or geological/operational validation. Full acquisition, clean dependency install, physical devices, other browsers, partial edge-tile outages and long-running stability are untested. Development reloads intermittently logged a MapLibre worker error despite successful tested views. Reconstruction MAE/RMSE are training-selected validation metrics, not retrieval accuracy.

**Hygiene:** filename and pattern scans found no `.env`, key, certificate or obvious credential in authored source files; this is not a forensic secret audit. `frontend/src/assets/vite.svg`, `react.svg`, `hero.png`, `frontend/public/icons.svg` and the Vite-template `frontend/README.md` appear unused or generic. Review their necessity and rights before packaging; none was deleted.
