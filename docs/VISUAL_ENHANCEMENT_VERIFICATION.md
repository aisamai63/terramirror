# Visual enhancement verification — 2026-11-15

## Scope and imagery evidence

The interactive map now uses the documented NASA GIBS Web Mercator WMTS layer `Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual` for the 2000-12-01 annual composite. The service capabilities advertise `GoogleMapsCompatible_Level12` JPEG tiles. NASA/USGS WELD is a historical approximately 30 m source product; zoom 12 tiles are about 38 m per pixel at the equator before latitude effects. This supports sharper local visual context than Blue Marble, not present-day imagery or a measured 30 m pixel everywhere on the rendered screen. Representative selected-candidate tiles in Brazil, Siberia and Australia returned HTTP 200 and `image/jpeg`. NASA Blue Marble Next Generation remains a global overview and fallback at Level8; a failed Landsat tile returns to Blue Marble, and failed Blue Marble returns to Street. The central-tile HEAD probe has a six-second timeout; MapLibre source errors also trigger fallback. It does not certify every edge tile.

The map makes ordinary interactive tile requests and one central-tile HEAD probe per selected location. No key or paid provider was added. Map attribution links to NASA GIBS, the NASA/USGS WELD product and OpenStreetMap as applicable. See [GIBS WMTS access](https://nasa-gibs.github.io/gibs-api-docs/access-basics/), [GIBS map-library guidance](https://nasa-gibs.github.io/gibs-api-docs/map-library-usage/), [Web Mercator capabilities](https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml), and [WELD product](https://lpdaac.usgs.gov/products/gweldyrv031/). NASA WELD and Blue Marble are basemap context, not DEM input or 3D textures. Regional names remain limited to existing source metadata.

## Before and after screenshots

| View | Before | After |
| --- | --- | --- |
| Map and candidate list | `/tmp/terramirror-before-map.png` | `/tmp/terramirror-after-map.png` |
| Mars–Earth terrain | `/tmp/terramirror-before-terrain.png` | `/tmp/terramirror-after-terrain.png` |

Screenshots were captured from the running local Vite app and API at 1440 × 900 in headless Chrome. They are local `/tmp` files, not portable submission assets. The after map shows the historical WELD layer at the selected candidate. The terrain screenshot uses 64 × 64 measured grids, 3× vertical exaggeration and the oblique preset.

## Checks performed

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | 38 passed, 6 subtests passed |
| `cd frontend && npm run build` | Passed; Vite warned that the main chunk exceeds 500 kB |
| `cd frontend && npm run lint` | Exit 0 |
| Browser: launch, Mars and Moon detailed retrieval, 64 × 64 and 32 × 32 surfaces | Passed in local headless Chrome |
| Browser: Top, Oblique, Side, Reset; orbit, zoom, pan | Passed: preset state and distinct rendered frames, with interactions changing frames |
| Browser: selected card/marker, popup, map zoom/reset | Passed; selected marker reached map center with 0 px measured offset after fly-to |
| Browser: Street, WELD Satellite and Blue Marble modes and visible attribution | Passed |
| Browser: block WELD tiles, then Blue Marble tiles | Passed: WELD → Blue Marble → Street notices and selector changes |
| Browser: mobile 390 px viewport | Passed: five candidate cards and terrain canvas present; document width 390 px |
| Model and saved-ranking SHA-256 against `docs/RELEASE_CANDIDATE.md` | All four matched |
| `git diff --check` | Passed |

The browser checks used `/tmp/terramirror-visual-acceptance.mjs`, a local test script outside the repository. No source raster, model checkpoint, retrieval result or scientific metric was edited.

## Remaining limits

- WELD is historical, may have unavailable or cloudy local tiles, and does not support zoom beyond 12. Blue Marble remains coarse. A street map also requires network access.
- No explicit GIBS per-client interactive request quota was confirmed from the reviewed service documentation. The client makes ordinary map-library requests without bulk prefetch; high-traffic public deployment would need a fresh terms and load review.
- The screenshot and browser checks were local headless Chrome tests, not cross-browser, physical-device or public deployment verification. The browser did not certify visual quality at every candidate coordinate.
- 3D surfaces still accurately depict the available DEM resolution and measured relief; shallow terrain can remain visibly shallow at truthful scale. The base grid and edge outline are visual guides, not extra elevation evidence.
- No satellite or planetary image texture is mapped onto the DEM. Geological relevance remains unvalidated.
