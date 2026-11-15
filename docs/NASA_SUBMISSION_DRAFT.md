# NASA Space Apps 2026 submission draft — TerraMirror

**Draft only.** No slide deck, public link, Project Tab entry or submission was created. This follows the [official 2026 Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) and the [official challenge](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/). The guide's page was retrieved for this audit after the page reader timed out; its field list also matches [NASA Space Apps organizer guidance](https://github.com/nasa/spaceapps/discussions/1858). Check the live form before pasting. Scientific claims are tied to the [model card](MODEL_CARD_AND_EVALUATION.md) and [verification report](FINAL_VERIFICATION.md).

## Exact Project page fields and submission checks

| Official field | Prepared content/status |
| --- | --- |
| **Project Name** | TerraMirror |
| **High-Level Project Summary** | Draft below |
| **Link to Project Demo** | **Missing**. Public URL to either a slide deck of at most seven slides **including title/intro**, or a video no longer than 30 seconds. Test without login. |
| **Link to Final Project** | **Missing**. Publicly accessible project/repository/artifact URL. A local-only app is not a valid public URL. |
| **Detailed Project Description** | Draft below, including method/results/limits |
| **Use of Super Intelligence (SI)** | Draft disclosure below; team must verify all tools and uses |
| **NASA Data** | Draft NASA source list below |
| **Space Agency Partner Data and Other References** | Draft other-source/tool list below; verify every citation and asset right |

The guide says the Project page accepts JPG/PNG/GIF images up to 10 MB, but videos/documents need an externally hosted public link. English is required on the page and linked materials; another spoken language in a demo video needs English subtitles. A slide deck must be in English. The guide requires all members to be confirmed at the same Local Event, all form fields completed, agreement to **Terms and Conditions** and **Confirm All Work is Original**, and an explicit **Submit for Judging** click. A saved draft alone is not submitted. The stated deadline is November 15, 2026, 11:59 p.m. in the Local Event timezone (or Team Owner's local area for the Universal Event); local judging may have a separate deadline. The guide bars likenesses of people under 18 in the demo/final project. The team must verify its event, membership and final confirmation state; this document does not do those actions.

## Ready-to-review field text

### High-Level Project Summary

TerraMirror is an experimental tool for finding Earth terrain patches whose surface shape resembles selected Mars Jezero or Moon Site04 DEM patches. It uses open planetary and Earth elevation data, screens sampled Earth patches with physical terrain features, reranks a shortlist with an Earth-trained convolutional autoencoder, and shows candidates on an interactive map beside measured 3D elevation surfaces. The tool helps explore and characterize **topographic** candidates. It does not validate geology, environment, resources or suitability for a permanent base, and its Earth sample is not global.

### Detailed Project Description, methodology and results

TerraMirror compares planetary and Earth topography at two scales. Its regional workflow compares 60 km projected DEM profiles. Its detailed Jezero workflow uses 64×64 elevation patches at 90 m grid spacing. Five standardized physical features shortlist 50 Earth patches; 32-dimensional autoencoder embeddings rerank that shortlist. Saved Mars indexes contain 255 Jezero target patches and 3,505 baseline or 3,736 expanded Earth patches. A separate experimental Moon Site04 workflow ranks two selected lunar patches against 3,762 available local Earth patches. Site04 is an experimental target, not a designated lunar base.

The dashboard lets a user choose a planetary patch, inspect five ranked Earth candidates with coordinates, slope/roughness/relief, source-quality flags and physical/neural distances, then fly to a candidate on a Street or NASA GIBS Blue Marble map. The side-by-side 3D view renders actual DEM cells and valid-data masks at 64×64 or a sampled 32×32 mode. Its vertical exaggeration is disclosed. Blue Marble is coarse global visual context, not a local terrain measurement or 3D texture.

The frozen autoencoder reproduced a **12.0199 m reconstruction MAE** and **20.6069 m reconstruction RMSE** on 427 saved Earth validation patches. The saved Mars ranking algorithm reproduced all 255 top-five patch-ID lists in both indexes. These establish reconstruction behavior and computational reproducibility; they are **not** analog relevance or geological accuracy. No independent relevance labels or expert field validation are available. Earth coverage is sampled, planetary DEM cells may be interpolated, and source quality varies.

The local implementation uses Python, FastAPI, NumPy, Rasterio and PyTorch, plus React, TypeScript, Vite, MapLibre GL JS and Three.js/React Three Fiber. The documented local demo has passed 38 Python tests and six subtests, frontend build/lint and a browser acceptance walkthrough. A public deployment and portable installation remain unverified.

### Use of Super Intelligence (SI) — team review required

The project uses a trained convolutional autoencoder to reconstruct Earth terrain patches and produce 32-dimensional embeddings used in candidate reranking. This is machine learning for retrieval, not a classifier of geological suitability. OpenAI Codex assisted with software review, implementation, testing and documentation in the verified engineering sessions. **The team must add or correct every other SI/AI tool used and describe each contribution before submission.** No synthetic elevation is used as a terrain measurement. If the final slides/video contain SI-generated visuals, follow the guide's visible watermark rule; acknowledge SI-generated code/data in descriptive text and metadata. Do not present an AI-created scientific map or site photograph as observed data.

### NASA Data

- [NASA PDS MOLA Mars topography](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/) underlies the Jezero terrain source record. Cite the MOLA team and specific product/version from `data/metadata/sources.csv`.
- [NASA LRO LOLA lunar topography](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/) underlies the lunar source records. Cite the LRO LOLA team and exact product/version.
- [NASA LP DAAC NASADEM](https://lpdaac.usgs.gov/products/nasadem_hgtv001/) appears in the regional Earth source records; cite NASA JPL/LP DAAC. Do not imply every detailed Earth archive uses NASADEM.
- [NASA Earth Observatory Blue Marble Next Generation](https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/) via [NASA GIBS WMTS](https://nasa-gibs.github.io/gibs-api-docs/access-basics/) provides the coarse satellite basemap. It is visual context, not the elevation input.

### Space Agency Partner Data and Other References

- [Copernicus DEM GLO-30](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) is the source named by the 21 detailed Earth patch archives and Earth tile catalog. **Add exact product/license notices before distributing any derived archive**; `sources.csv` currently lacks Copernicus rows.
- [ESA WorldCover 2021 v200](https://esa-worldcover.org/en/data-access) supplies categorical Earth land-cover context; cite the dataset and article/DOI and CC BY 4.0 terms.
- [PGC ArcticDEM and REMA](https://www.pgc.umn.edu/guides/stereo-derived-elevation-models/pgc-dem-products-arcticdem-rema-and-earthdem/) and USGS elevation products appear in regional Earth provenance. Cite their exact source records and required attribution.
- [OpenStreetMap raster tiles](https://operations.osmfoundation.org/policies/tiles/) provide the Street basemap with visible linked attribution.
- Software/tools: Python, FastAPI, NumPy, Rasterio, PyTorch, React, TypeScript, Vite, MapLibre GL JS, Three.js/React Three Fiber, and their applicable licenses. Source links and exact versions are in `requirements.txt`, `requirements-ml.txt`, and `frontend/package-lock.json`; review the final public package's third-party notices.

## Seven-slide presentation outline

**The official maximum is seven slides total, including title and introduction.** Use real screenshots captured from the running build. Add actual team and member names on slide 1; do not invent them.

| Slide | Main message | Evidence/visual to prepare |
| --- | --- | --- |
| 1. Problem and challenge | NASA's challenge asks for terrestrial analog candidates for Moon/Mars exploration. TerraMirror narrows the claim to topographic exploration. | Official challenge title, team/member names, one authentic dashboard screenshot. |
| 2. Solution | Choose a target, retrieve ranked Earth candidates, inspect evidence, map and 3D surfaces. | Genuine dashboard screenshot with Mars target selector and candidate list. |
| 3. Open data and method | MOLA/LOLA + Earth DEMs; five physical features shortlist 50, then 32-dimensional embedding rerank. | Simple labeled pipeline diagram; source citations and “sampled Earth index.” |
| 4. Mars-to-Earth | 255 Jezero target patches; 3,505 baseline and 3,736 expanded Earth index patches. Results are candidates, not confirmed analogs. | Genuine candidate card/map screenshot with readable coordinates, quality and distances; label the selected target/index. |
| 5. Moon-to-Earth | Two selected Site04 targets in an experimental domain-shift test; 3,762 local Earth patches. | Genuine Moon Site04 candidate and terrain screenshot; state high, uncalibrated embedding distances and no base-site designation. |
| 6. Map and measured 3D | Street/Blue Marble with visible credits and fallback; actual 64×64 DEM values and mask, optional 32×32 sampling, disclosed exaggeration. | Genuine satellite map screenshot with credits and selected marker plus real Mars–Earth 3D screenshot. No fabricated imagery. |
| 7. Evidence, limits, impact | 38 tests/6 subtests pass; reconstruction 12.0199 m MAE and 20.6069 m RMSE on saved validation split; rankings reproduce. Relevance remains unvalidated. | Compact evidence/limitations panel and a realistic future-work statement. |

Capture screenshots from a freshly started API and the compiled frontend. Required frames: dashboard with Mars selection; a Mars target and ranked candidate with coordinate/quality/distance text; selected marker/popup in Street and Satellite with visible NASA/OSM attribution; Mars–Earth 3D with both relief/coverage labels; Moon Site04 candidate and Moon–Earth 3D. Record the chosen patch/candidate IDs and screenshot time. Do not use simulated images or temporary QA frames as polished evidence without checking their labels and provenance. No slide deck or demo video has been produced yet.
