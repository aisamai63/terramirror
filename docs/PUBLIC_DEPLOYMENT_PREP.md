# Public demonstration preparation — 2026-11-15

**Status: local production preview verified; public access not approved or tested.** The exact local URL is `http://127.0.0.1:8765`. Port 8080 was occupied during verification. FastAPI serves the compiled React entry page and `/assets/` from `frontend/dist`; all browser API requests use the same origin. Vite remains a local development server only.

## Start and stop

From the repository root, after `cd frontend && npm run build`:

```bash
TERRAMIRROR_PUBLIC_DEMO=1 .venv/bin/uvicorn src.discovery_api:app --host 127.0.0.1 --port 8765 --workers 1 --limit-concurrency 20 --timeout-keep-alive 5
```

**Only after the rights and exposure blockers below are resolved and the user approves public access**, the exact Cloudflare Quick Tunnel command for this server would be:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

No tunnel was created. The Quick Tunnel URL is public to anyone who has it, changes on restart and has no uptime guarantee. It is suitable for a temporary demonstration, not durable hosting. To stop access, press `Ctrl+C` in the `cloudflared` terminal first, confirm its process has ended, then press `Ctrl+C` in the Uvicorn terminal. Revocation should be confirmed from an external client if a tunnel is ever started. See [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Exposure surface

- Public mode is enabled only by `TERRAMIRROR_PUBLIC_DEMO=1`. The intended routes are GET `/api/health`, `/api/coverage`, regional discovery, Mars baseline and expanded discovery, Moon Site04 discovery, detailed Earth/Mars/Moon terrain and regional terrain. The API remains database-free and reads saved results and local DEMs.
- The compiled homepage and hashed CSS/JS under `/assets/` are the only file-serving routes. `/docs`, `/redoc`, `/openapi.json`, `/data/...`, `/models/...`, `/outputs/...`, `/src/...`, `/frontend/...`, and `/.env` returned 404 in local tests. POST `/api/health` returned 405. Public regional terrain responses omit the internal relative raster path.
- Public mode sends `nosniff`, a referrer policy and `Cache-Control: no-store` for API responses. It has global in-memory limits of 240 API requests and 120 terrain requests per 60 seconds, plus Uvicorn's 20-request concurrency limit. These are basic safeguards, not a substitute for an authenticated or professionally managed edge service. Rate limits reset on restart and are global, so a busy visitor could cause other visitors to see 429 responses.
- The app has no user accounts or write routes. The loopback bind limits direct network reachability, but a tunnel would expose the allowed GET responses to anyone with its URL. Tile providers remain external dependencies. No Vite server, source archive, checkpoint or raw DEM file route should be tunneled.

## Elevation-data rights and public decision

The [Copernicus GLO-30 source page](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) and [public licence](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf) allow public communication and distribution with obligations. For adapted Copernicus WorldDEM-30 data, the required source notice is displayed in the detailed 3D viewer and included in Earth terrain API responses:

> produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved

The licence also requires a no-liability notice and no implication of official endorsement; the viewer and Earth terrain API responses include these notices. The full-resolution source files are not served, but 32×32 and 64×64 API responses **do transmit derived elevation cells** and must be treated as public communication/distribution if tunneled. The current `data/metadata/earth_tile_catalog.csv` links Copernicus tile IDs to URLs, while `data/metadata/sources.csv` does not yet bind all 21 detailed Earth archives to exact GLO-30 product rights, source hashes and processing lineage. **Do not start a public tunnel until each archive is verified as an eligible public GLO-30 instance and the notices are reviewed for that exact data.** This is a provenance and rights gate, not a claim that the licence categorically forbids public access.

Regional Earth terrain uses NASADEM, ArcticDEM and REMA sources. The local `sources.csv` records source-specific notes; [PGC states ArcticDEM and REMA are CC BY 4.0](https://www.pgc.umn.edu/guides/stereo-derived-elevation-models/pgc-dem-products-arcticdem-rema-and-earthdem/). Their public-facing attribution and any Alaska-era restriction need a final candidate-by-candidate review before public access. MapLibre credits NASA GIBS/WELD and OpenStreetMap in the map. No satellite texture is presented as a DEM measurement.

## Local verification

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | 39 passed, 6 subtests passed |
| `cd frontend && npm run build` | Passed; existing main-chunk size warning |
| `cd frontend && npm run lint` | Exit 0 |
| Local HTTP smoke at `127.0.0.1:8765` | Compiled homepage/assets and 17 API routes returned 200; forbidden file/documentation paths returned 404; POST returned 405 |
| Existing Vite development workflow | `curl -sS -i --max-time 5 http://127.0.0.1:5173/api/health` returned HTTP 200 through the new proxy |
| Public-mode terrain rate limit | Unknown-patch requests reached HTTP 429 with `Retry-After: 60` on request 121 |
| Local headless Chrome production walkthrough | Same-origin API requests, Mars baseline/expanded, regional Mars/Moon, Moon Site04, 32/64 terrain, 3D controls, candidate fly-to and scroll, satellite attribution/fallback, 390 px mobile emulation passed |
| Firefox local render attempt | Headless command exited 0 but produced no screenshot; Firefox rendering remains unverified |
| External public HTTPS browser/device | Not tested; no tunnel created |

The HTTP smoke used `/tmp/terramirror-public-smoke.py`; the browser walkthrough used `/tmp/terramirror-public-browser.mjs`. Neither script is packaged with the app. Source dependency pins in `requirements.txt` still differ from the verified local virtual environment, so a fresh independent installation remains unverified. The source and runtime-asset packaging concerns in [SUBMISSION_PACKAGING.md](SUBMISSION_PACKAGING.md) also remain.
