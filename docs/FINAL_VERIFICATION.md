# TerraMirror final acceptance checkpoint — 2026-11-15

**Later visual update:** The [visual enhancement verification](VISUAL_ENHANCEMENT_VERIFICATION.md) records the NASA/USGS Landsat WELD (2000) local satellite layer, Blue Marble fallback, camera presets, new browser checks and before/after screenshots. Blue Marble-only statements below describe the earlier acceptance baseline.

This report extends the [challenge audit](CHALLENGE_REQUIREMENTS_AUDIT.md) and [model card](MODEL_CARD_AND_EVALUATION.md). It distinguishes tested prototype behavior from scientific validation. The [NASA demonstration checklist](NASA_DEMO_CHECKLIST.md) gives the presentation sequence.

## Submission path and preservation

- A fresh local launch of `src.discovery_api:app` and Vite served the regional discovery page without an API error. The browser reached regional, detailed Mars, detailed Moon, terrain and coverage endpoints; terrain HTTP requests returned 200 in both grid modes. `src/api.py` remains a broken legacy entry point and is not used.
- The working tree contained important untracked frontend, model, output, script and API assets before this batch. No untracked files were deleted; no checkpoint, raster, patch archive or saved ranking was overwritten. Source files modified here were backed up under `/tmp/terramirror-acceptance-*.bak`. No commit or push occurred.
- Final SHA-256 values remained unchanged: model `306066489a3e3c5c8a1cfc925a2d40025a7ad110ef7e1710da4f3c9bb613e13b`; baseline Mars `2a9d66c40f0a73aaf719fb540a9bbaf1d0ffe9b6a67b56d04059da92feb9bd07`; expanded Mars `0dca4c1f85a4383b44a6945ef3ffb2d4ef630d5b3e6b6e8195ef5f8e893fbce7`; lunar `e670d7005918b3521a716b62c8b491ca2c3eca19773e0dd5e56a8387578ce745`.
- `npm ci` was not rerun because it replaces the existing untracked `frontend/node_modules`; the installed lockfile dependencies built and linted successfully. A clean dependency installation remains an untested deployment step.

## Satellite map acceptance

| Scenario | Observed result |
| --- | --- |
| Online NASA imagery | Blue Marble tiles rendered in headless Chrome; NASA and OpenStreetMap credits were visible. A representative tile HEAD request returned HTTP 200 and `image/jpeg`. |
| NASA host blocked | Chrome `Network.setBlockedURLs` caused the selector to return to Street and show the unavailable-imagery notice. |
| Tile HTTP 404 | Chrome Fetch interception returned 404 for NASA tile requests; the central candidate tile probe triggered the same Street fallback and notice. |
| Browser offline | Chrome network emulation triggered Street fallback and disclosed that street tiles also require a connection. Offline basemap tiles are not promised. |
| Candidate fly-to | Selecting rank 2 placed its highlighted marker at the map center after animation. Clicking marker 3 selected it and opened a popup with coordinates, rank, physical distance, neural distance and quality status. |
| Zoom and reset | Zoom-in changed the rendered map frame; zoom-out control was exercised; Reset view returned to the candidate overview, leaving rank 2 about 301 px from map center while keeping its highlight. |
| Mobile | At 390 px viewport, page width was 390 px and map width 358 px. Attribution remained visible in both Street and Satellite modes. |

The fallback probes the selected candidate's z8 tile with a HEAD request and a six-second timeout. This verifies the central tile, not every visible edge tile. MapLibre source errors also cause fallback while Satellite is visible. NASA [Blue Marble Next Generation](https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/) source composites are about 500 m per pixel; the selected [GIBS Web Mercator Level8 grid](https://nasa-gibs.github.io/gibs-api-docs/access-advanced-topics/) is about 611.5 m per pixel at the equator. Zoom above 8 enlarges the same imagery. The map has no local high-resolution satellite product. The UI now keeps linked OpenStreetMap and NASA credits visible, and the README includes NASA GIBS's requested acknowledgment. The code uses the documented HTTPS WMTS endpoint, browser tile requests, and no frontend secret or bulk prefetch. Provider policies and third-party imagery rights remain subject to their published terms.

## 3D and data acceptance

- Detailed Mars–Earth and Moon–Earth canvases rendered actual elevation surfaces in headless Chrome. Switching Mars Earth candidates changed the Earth relief label from 180.6 m to 153.6 m and updated the canvas without a terrain error. The Moon Site04 comparison showed 1,892.5 m lunar relief and 1,057.3 m Earth relief for the selected patch pair.
- The 64×64 mode used 90 m sample spacing; the 32×32 mode sampled every second cell at 180 m. Automated tests compared API values and masks with the NPZ archive. Relief values can change under downsampling; the UI discloses the sampling.
- Oblique and top presets produced distinct rendered frames. Orbit drag, wheel zoom, right-drag pan and Reset camera each changed the rendered frame; reset to the top preset returned the same top-view frame. The vertical exaggeration control reached and displayed 10×. Mesh coordinates convert horizontal metres and vertical metres to kilometres consistently; the slider multiplies vertical display only.
- A real Earth archive patch with invalid cells retained its mask and zero placeholders in the API; reported min/max excluded invalid cells. The mesh construction omits triangles touching invalid cells. No actual selected top-five patch with visible gaps was inspected in the browser, so gap appearance remains a visual QA limit. Valid raster coverage does not mean direct measurement coverage.
- No satellite or planetary image texture is applied to the 3D surfaces. Colour is a relative-elevation visualization, not a measured material property.

## Scientific evaluation

- `.venv/bin/python -m scripts.evaluate_saved_checkpoint` reloaded the frozen checkpoint and reproduced 12.0199260478 m reconstruction MAE and 20.6069403968 m RMSE on 427 saved tile-level validation Earth patches, 1,742,419 valid pixels and zero clipped validation pixels. This is the training-selected validation split, not a new test set.
- Read-only recomputation using saved embeddings and five physical feature columns reproduced **all 255 neural-only and hybrid Mars top-five patch-ID lists** in both the 3,505- and 3,736-Earth indexes. Physical-only and hybrid top-one winners agreed on 7/255 baseline targets and 8/255 expanded targets. The existing neural-only versus physical-only winner agreement is 4/255 in the saved baseline evaluation. Agreement is not relevance accuracy.
- Exact coordinate comparison found 74 expanded top-five coordinates absent from baseline top fives. All 74 remained retrievable through the expanded Mars patch endpoints. They are newly returned results, not proven newly acquired sites.
- No independent relevance labels, expert site judgments or field validation are available. Recall@K, Precision@K, NDCG@K, Hit Rate@K and ranking accuracy remain unavailable. Physical screening can exclude a globally close neural candidate outside its top-50 shortlist; lunar embeddings remain out of the Earth training domain.

## Final checks

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | **38 passed, 6 subtests passed** |
| `cd frontend && npm run build` | **Passed**; Vite warns that the main JS chunk exceeds 500 kB |
| `cd frontend && npm run lint` | **Passed** |
| `git diff --check` | **Passed** |
| Source and regional data inventory | 50 source records covering Earth, Mars and Moon; 19/19 manifest regional analysis rasters present |
| Browser acceptance | Desktop and 390 px mobile paths above passed in headless Chrome; service workers/tiles were not predownloaded |

## Remaining risks and missing challenge evidence

1. The Earth sample is limited; the catalog is not globally processed. Terrain similarity does not establish geology, resources, caves, radiation, climate, access or permanent-base suitability. The lunar Site04 experiment is not a designated base location.
2. No independent labeled relevance set exists. Rank stability, shortlist recall against expert judgments, and geological/operational analog quality remain unverified.
3. Satellite fallback checks the selected central tile; partial edge-tile outages and every browser/network combination are untested. Street tiles also require network. Blue Marble is too coarse for local site inspection.
4. Browser tests covered one desktop headless Chrome session and one 390 px emulation. Physical mobile devices, accessibility tooling, more browsers and long-running stability have not been checked. Development logs intermittently reported a MapLibre worker-load error during reloads even though the tested map paths rendered; production-mode browser behavior has not been assessed.
5. The frontend API base URL and API CORS origins are configured for local development, not a remote deployment. Vite's large bundle warning and a clean dependency install remain open release concerns.

## Release candidate follow-up — 2026-11-15

The [release inventory and presentation script](RELEASE_CANDIDATE.md) record the intended package and submission blockers. The same 38 tests/6 subtests, build, lint, saved-checkpoint evaluation and four artifact hashes passed again. The compiled `frontend/dist` was served with `npm run preview -- --host 127.0.0.1 --port 5173` against a fresh local `src.discovery_api:app` process. The full browser acceptance sequence above passed on that production build, including Mars and Moon retrieval, 32/64 terrain, map interaction, satellite failure modes and mobile emulation. `/api/health` returned HTTP 200. A configured local browser origin received an `access-control-allow-origin` header; an unconfigured remote origin did not. This verifies local production-build behavior, not public deployment.

`frontend/node_modules` and `frontend/dist` are ignored by `frontend/.gitignore`; the other untracked project directories remain required release content. No slides, video or public deployment artifact was found. The current source-only Git state is not a portable submission because the working frontend, API, model and saved rankings are untracked and local terrain archives are ignored. No files were deleted, staged, committed, pushed or submitted.
