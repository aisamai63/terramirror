import TerrainComparison from './components/TerrainComparison'
import MatchExplanation from './components/MatchExplanation'
import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  Activity, Globe2, Layers3, MapPin, Mountain,
  Satellite, ShieldAlert, Orbit, ExternalLink
} from 'lucide-react'
import './App.css'

const API = ''
const NASA_BLUE_MARBLE = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8'
const NASA_LANDSAT_2000 = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/Landsat_WELD_CorrectedReflectance_TrueColor_Global_Annual/default/2000-12-01/GoogleMapsCompatible_Level12'
type MapLayer = 'street' | 'satellite' | 'blue-marble'

function satelliteTileAt(base: string, zoom: number, latitude: number, longitude: number): string {
  const size = 2 ** zoom
  const lat = Math.max(-85.0511, Math.min(85.0511, latitude)) * Math.PI / 180
  const x = Math.min(size - 1, Math.max(0, Math.floor((longitude + 180) / 360 * size)))
  const y = Math.min(size - 1, Math.max(0, Math.floor((1 - Math.asinh(Math.tan(lat)) / Math.PI) / 2 * size)))
  return `${base}/${zoom}/${y}/${x}.jpeg`
}

type Candidate = {
  rank: number
  latitude: number
  longitude: number
  location_name?: string
  geographic_label?: string
  geographic_label_source?: string
  earth_patch_id?: string
  profile_id?: string
  similarity_score?: number
  physical_feature_distance?: number
  neural_embedding_distance?: number
  physical_candidate_rank?: number
  dominant_landcover?: string
  quality_status?: string
  hem_coverage?: number
  original_source_fraction?: number
  landcover_status?: string
  caveats?: string
  metrics?: {
    slope_match?: number
    relief_match?: number
    roughness_match?: number
    steep_fraction_match?: number
  }
  source_ids?: string[]
  terrain_features?: TerrainFeatures
}

type TerrainFeatures = {
  mean_slope_deg: number
  p95_slope_deg: number
  roughness_m: number
  relief_m: number
  elevation_std_m: number
}

const featureLabels: [keyof TerrainFeatures, string, string][] = [
  ['mean_slope_deg', 'Mean slope', '°'],
  ['p95_slope_deg', '95th percentile slope', '°'],
  ['roughness_m', 'Roughness', 'm'],
  ['relief_m', 'Relief', 'm'],
  ['elevation_std_m', 'Elevation variability', 'm'],
]

type RegionalTarget = {
  target_id: string
  planet: string
  target_site: string
  candidate_count: number
}

type MarsPatch = {
  index: number
  patch_id: string
  candidate_count: number
}

type DiscoveryResponse = {
  top_analogs?: Candidate[]
  matches?: Candidate[]
  target_site?: string
  target_features?: TerrainFeatures
}

const fetchJSON = async <T,>(path: string): Promise<T> => {
  const response = await fetch(`${API}${path}`)
  if (!response.ok) throw new Error(`API error ${response.status}: ${path}`)
  return response.json()
}

function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null)
  const terrainViewer = useRef<HTMLDivElement | null>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const markers = useRef<maplibregl.Marker[]>([])
  const [mapLayer, setMapLayer] = useState<MapLayer>('street')
  const [mapNotice, setMapNotice] = useState('')

  const [mode, setMode] = useState<'regional' | 'detailed'>('regional')
  const [discoveryIndex, setDiscoveryIndex] =
    useState<'baseline' | 'expanded'>('baseline')
  const [detailedPlanet, setDetailedPlanet] =
    useState<'mars' | 'moon'>('mars')
  const [targets, setTargets] = useState<RegionalTarget[]>([])
  const [targetId, setTargetId] = useState('mars-jezero')
  const [patches, setPatches] = useState<MarsPatch[]>([])
  const [patchId, setPatchId] = useState('')
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [targetFeatures, setTargetFeatures] = useState<TerrainFeatures | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [coverage, setCoverage] = useState({
    earth_catalog_tiles: 0,
    earth_processed_tiles: 0,
    earth_indexed_patches: 0,
    expanded_processed_tiles: 0,
    expanded_tiles_with_qualifying_patches: 0,
    expanded_indexed_patches: 0,
    moon_indexed_patches: 0
  })

  useEffect(() => {
    Promise.all([
      fetchJSON<{ targets: RegionalTarget[] }>('/api/regional'),
      fetchJSON<typeof coverage>('/api/coverage')
    ])
      .then(([regional, scope]) => {
        setTargets(regional.targets)
        setCoverage(scope)
      })
      .catch(err => setError(String(err)))
  }, [])

  useEffect(() => {
    let cancelled = false

    fetchJSON<{ patches: MarsPatch[] }>(
      `/api/detailed/${detailedPlanet}`
    )
      .then(data => {
        if (cancelled) return
        setPatches(data.patches)
        setPatchId(data.patches[0]?.patch_id ?? '')
      })
      .catch(err => {
        if (!cancelled) setError(String(err))
      })

    return () => { cancelled = true }
  }, [detailedPlanet])

  useEffect(() => {
    if (mode === 'detailed' && !patchId) {
      return
    }

    let cancelled = false
    queueMicrotask(() => {
      if (!cancelled) {
        setLoading(true)
        setError('')
      }
    })

    const endpoint = mode === 'regional'
      ? `/api/regional/${targetId}`
      : detailedPlanet === 'moon'
        ? `/api/detailed/moon/${encodeURIComponent(patchId)}`
        : discoveryIndex === 'expanded'
          ? `/api/detailed-expanded/mars/${encodeURIComponent(patchId)}`
          : `/api/detailed/mars/${encodeURIComponent(patchId)}`

    fetchJSON<DiscoveryResponse>(endpoint)
      .then(data => {
        if (cancelled) return
        setCandidates(data.top_analogs ?? data.matches ?? [])
        setTargetFeatures(data.target_features ?? null)
        setSelectedIndex(0)
      })
      .catch(err => {
        if (!cancelled) {
          setCandidates([])
          setTargetFeatures(null)
          setError(String(err))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [mode, targetId, patchId, discoveryIndex, detailedPlanet])

  useEffect(() => {
    if (!mapContainer.current || map.current) return

    const instance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'osm': {
            type: 'raster',
            tiles: [
              'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
            ],
            tileSize: 256,
            attribution: '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a>'
          },
          'nasa-imagery': {
            type: 'raster',
            tiles: [`${NASA_BLUE_MARBLE}/{z}/{y}/{x}.jpeg`],
            tileSize: 256,
            maxzoom: 8,
            attribution: '<a href="https://nasa-gibs.github.io/gibs-api-docs/" target="_blank" rel="noopener noreferrer">NASA GIBS / Blue Marble</a>'
          },
          'landsat-imagery': {
            type: 'raster',
            tiles: [`${NASA_LANDSAT_2000}/{z}/{y}/{x}.jpeg`],
            tileSize: 256,
            maxzoom: 12,
            attribution: '<a href="https://lpdaac.usgs.gov/products/gweldyrv031/" target="_blank" rel="noopener noreferrer">NASA / USGS Landsat WELD · 2000 composite</a>'
          }
        },
        layers: [{
          id: 'osm-layer',
          type: 'raster',
          source: 'osm'
        }, {
          id: 'nasa-layer',
          type: 'raster',
          source: 'nasa-imagery',
          layout: { visibility: 'none' }
        }, {
          id: 'landsat-layer',
          type: 'raster',
          source: 'landsat-imagery',
          minzoom: 8.5,
          layout: { visibility: 'none' }
        }]
      },
      center: [10, 20],
      zoom: 1.4,
      attributionControl: false
    })

    instance.addControl(new maplibregl.NavigationControl(), 'top-right')
    instance.addControl(
      new maplibregl.AttributionControl({ compact: false }),
      'bottom-right'
    )

    map.current = instance
    instance.on('error', event => {
      if (!('sourceId' in event)) return
      if (event.sourceId === 'landsat-imagery' &&
          instance.getLayer('landsat-layer') &&
          instance.getLayoutProperty('landsat-layer', 'visibility') === 'visible') {
        setMapLayer('blue-marble')
        setMapNotice('Local Landsat imagery is unavailable here. Showing the NASA Blue Marble overview.')
      } else if (event.sourceId === 'nasa-imagery' &&
          instance.getLayer('nasa-layer') &&
          instance.getLayoutProperty('nasa-layer', 'visibility') === 'visible') {
        setMapLayer('street')
        setMapNotice('NASA imagery is unavailable. Showing the street map; street tiles also need a connection.')
      }
    })

    return () => {
      markers.current.forEach(marker => marker.remove())
      markers.current = []
      instance.remove()
      map.current = null
    }
  }, [])

  useEffect(() => {
    const instance = map.current
    if (!instance) return
    const applyLayer = () => {
      if (!instance.getLayer('nasa-layer') || !instance.getLayer('landsat-layer')) return
      instance.setLayoutProperty('osm-layer', 'visibility', mapLayer === 'street' ? 'visible' : 'none')
      instance.setLayoutProperty('nasa-layer', 'visibility', mapLayer === 'street' ? 'none' : 'visible')
      instance.setLayoutProperty('landsat-layer', 'visibility', mapLayer === 'satellite' ? 'visible' : 'none')
    }
    if (instance.getLayer('nasa-layer')) applyLayer()
    else instance.once('style.load', applyLayer)
    return () => { instance.off('style.load', applyLayer) }
  }, [mapLayer])

  useEffect(() => {
    if (!map.current) return

    markers.current.forEach(marker => marker.remove())
    markers.current = []

    candidates.forEach((candidate, index) => {
      if (!Number.isFinite(candidate.longitude) ||
          !Number.isFinite(candidate.latitude)) return

      const element = document.createElement('button')
      element.className = `map-marker ${index === 0 ? 'active' : ''}`
      element.textContent = String(index + 1)
      element.title = candidate.geographic_label ?? `Earth candidate ${index + 1}`
      element.setAttribute('aria-label', element.title)
      element.onclick = () => setSelectedIndex(index)

      const popupContent = document.createElement('div')
      const title = document.createElement('strong')
      title.textContent = candidate.geographic_label ?? `Earth candidate ${candidate.rank}`
      popupContent.append(title)
      const facts = [
        `${candidate.latitude.toFixed(5)}°, ${candidate.longitude.toFixed(5)}° · Rank ${candidate.rank}`,
        candidate.physical_feature_distance === undefined ? null : `Feature distance: ${candidate.physical_feature_distance.toFixed(4)}`,
        candidate.neural_embedding_distance === undefined ? null : `Neural distance: ${candidate.neural_embedding_distance.toFixed(4)}`,
        `Source quality: ${candidate.quality_status ?? 'not reported'}`,
      ]
      facts.forEach(fact => {
        if (!fact) return
        const line = document.createElement('div')
        line.textContent = fact
        popupContent.append(line)
      })

      const marker = new maplibregl.Marker({ element })
        .setLngLat([candidate.longitude, candidate.latitude])
        .setPopup(new maplibregl.Popup({ offset: 20 }).setDOMContent(popupContent))
        .addTo(map.current!)

      markers.current.push(marker)
    })

    if (candidates.length > 0) {
      const bounds = new maplibregl.LngLatBounds()

      candidates.forEach(candidate => {
        if (Number.isFinite(candidate.longitude) && Number.isFinite(candidate.latitude)) {
          bounds.extend([candidate.longitude, candidate.latitude])
        }
      })

      if (!bounds.isEmpty()) map.current.fitBounds(bounds, {
        padding: 75,
        maxZoom: 5,
        duration: 900
      })
    }
  }, [candidates])

  useEffect(() => {
    markers.current.forEach((marker, index) => {
      marker.getElement().classList.toggle('active', index === selectedIndex)
    })
    const candidate = candidates[selectedIndex]
    if (!candidate || !map.current || !Number.isFinite(candidate.latitude) ||
        !Number.isFinite(candidate.longitude)) return
    map.current.flyTo({
      center: [candidate.longitude, candidate.latitude],
      zoom: mapLayer === 'blue-marble'
        ? 8
        : Math.max(map.current.getZoom(), mapLayer === 'satellite' ? 12 : 10.5),
      duration: 1100,
      essential: true,
    })
  }, [selectedIndex, candidates, mapLayer])

  const resetMapView = () => {
    if (!map.current) return
    const bounds = new maplibregl.LngLatBounds()
    candidates.forEach(candidate => {
      if (Number.isFinite(candidate.longitude) && Number.isFinite(candidate.latitude)) {
        bounds.extend([candidate.longitude, candidate.latitude])
      }
    })
    if (bounds.isEmpty()) map.current.flyTo({ center: [10, 20], zoom: 1.4 })
    else map.current.fitBounds(bounds, { padding: 75, maxZoom: 5, duration: 900 })
  }

  const selected = candidates[selectedIndex]
  const terrainSummary = mode === 'detailed' && selected?.terrain_features && targetFeatures
    ? `Mean slope: ${targetFeatures.mean_slope_deg.toFixed(2)}° target vs ${selected.terrain_features.mean_slope_deg.toFixed(2)}° Earth (difference ${Math.abs(targetFeatures.mean_slope_deg - selected.terrain_features.mean_slope_deg).toFixed(2)}°). Relief: ${targetFeatures.relief_m.toFixed(2)} m vs ${selected.terrain_features.relief_m.toFixed(2)} m (difference ${Math.abs(targetFeatures.relief_m - selected.terrain_features.relief_m).toFixed(2)} m). Roughness: ${targetFeatures.roughness_m.toFixed(2)} m vs ${selected.terrain_features.roughness_m.toFixed(2)} m (difference ${Math.abs(targetFeatures.roughness_m - selected.terrain_features.roughness_m).toFixed(2)} m).`
    : null
  useEffect(() => {
    if (mapLayer === 'street') return
    const controller = new AbortController()
    let active = true
    const timeout = window.setTimeout(() => controller.abort(), 6000)
    const url = mapLayer === 'satellite'
      ? satelliteTileAt(NASA_LANDSAT_2000, 12, selected?.latitude ?? 0, selected?.longitude ?? 0)
      : satelliteTileAt(NASA_BLUE_MARBLE, 8, selected?.latitude ?? 0, selected?.longitude ?? 0)

    fetch(url, { method: 'HEAD', signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error(`Satellite tile HTTP ${response.status}`)
      })
      .catch(() => {
        if (!active) return
        if (mapLayer === 'satellite') {
          setMapLayer('blue-marble')
          setMapNotice('Local Landsat imagery is unavailable here. Showing the NASA Blue Marble overview.')
        } else {
          setMapLayer('street')
          setMapNotice('NASA imagery is unavailable. Showing the street map; street tiles also need a connection.')
        }
      })
      .finally(() => window.clearTimeout(timeout))

    return () => {
      active = false
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [mapLayer, selected?.latitude, selected?.longitude])
  const selectedTarget = targets.find(t => t.target_id === targetId)
  const currentPlanet = mode === 'detailed'
    ? detailedPlanet === 'moon' ? 'Moon' : 'Mars'
    : selectedTarget?.planet ?? 'Mars'

  const formatNumber = (value?: number, digits = 4) =>
    value === undefined ? 'N/A' : value.toFixed(digits)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Globe2 size={25} /></div>
          <div>
            <strong>TerraMirror</strong>
            <small>PLANETARY ANALOG DISCOVERY</small>
          </div>
        </div>

        <div className="nav-heading">EXPLORATION</div>
        <button
          className={`nav-button ${mode === 'regional' ? 'selected' : ''}`}
          onClick={() => setMode('regional')}
        >
          <Orbit size={18} /> Regional discovery
        </button>
        <button
          className={`nav-button ${mode === 'detailed' ? 'selected' : ''}`}
          onClick={() => { setCandidates([]); setSelectedIndex(0); setMode('detailed') }}
        >
          <Layers3 size={18} /> Detailed AI discovery
        </button>

        {mode === 'detailed' && (
          <div className="sidebar-section">
            <label htmlFor="detailed-planet">PLANETARY BODY</label>
            <select
              id="detailed-planet"
              value={detailedPlanet}
              onChange={event => {
                setSelectedIndex(0)
                setCandidates([])
                setPatchId('')
                setDetailedPlanet(
                  event.target.value as 'mars' | 'moon'
                )
              }}
            >
              <option value="mars">Mars — Jezero</option>
              <option value="moon">Moon — Site04 (experimental)</option>
            </select>
          </div>
        )}

        <div className="sidebar-section">
          <label htmlFor="target">
            {mode === 'regional'
              ? 'PLANETARY TARGET'
              : detailedPlanet === 'moon'
                ? 'LUNAR TERRAIN PATCH'
                : 'MARS TERRAIN PATCH'}
          </label>

          {mode === 'regional' ? (
            <select
              id="target"
              value={targetId}
              onChange={event => setTargetId(event.target.value)}
            >
              {targets.length === 0 && <option value="mars-jezero">Mars — Jezero</option>}
              {targets.map(target => (
                <option key={target.target_id} value={target.target_id}>
                  {target.planet} — {target.target_id.replace(/^(mars|moon)-/, '')}
                </option>
              ))}
            </select>
          ) : (
            <select
              id="target"
              value={patchId}
              onChange={event => setPatchId(event.target.value)}
            >
              {patches.map(patch => (
                <option key={patch.patch_id} value={patch.patch_id}>
                  Patch {patch.index} · {patch.patch_id}
                </option>
              ))}
            </select>
          )}
        </div>

        {mode === 'detailed' && detailedPlanet === 'mars' && (
          <div className="sidebar-section">
            <label htmlFor="discovery-index">
              EARTH DISCOVERY INDEX
            </label>
            <select
              id="discovery-index"
              value={discoveryIndex}
              onChange={event => {
                setSelectedIndex(0)
                setDiscoveryIndex(
                  event.target.value as 'baseline' | 'expanded'
                )
              }}
            >
              <option value="baseline">
                Baseline — {coverage.earth_indexed_patches.toLocaleString()} patches
              </option>
              <option value="expanded">
                Expanded — {coverage.expanded_indexed_patches.toLocaleString()} patches
              </option>
            </select>
            <p className="sidebar-note">
              {discoveryIndex === 'expanded'
                ? `Expanded sample: ${coverage.expanded_indexed_patches.toLocaleString()} indexed patches.`
                : 'Original pilot discovery results.'}
            </p>
          </div>
        )}

        {mode === 'detailed' && detailedPlanet === 'moon' && (
          <div className="sidebar-section">
            <p className="sidebar-note">
              Moon Site04: two low-clipping lunar targets,
              compared with {coverage.moon_indexed_patches.toLocaleString()} sampled Earth patches.
              Neural distances are not calibrated probabilities.
              Geological equivalence has not been validated.
            </p>
          </div>
        )}

        <div className="sidebar-section">
          <div className="nav-heading">SEARCH COVERAGE</div>
          <div className="coverage-box">
            <div><span>Catalogued tiles</span><strong>{coverage.earth_catalog_tiles.toLocaleString()}</strong></div>
            <div><span>Processed tiles</span><strong>{mode === 'detailed' && discoveryIndex === 'expanded'
              ? coverage.expanded_processed_tiles
              : coverage.earth_processed_tiles}</strong></div>
            <div><span>Indexed patches</span><strong>{(mode === 'detailed' && detailedPlanet === 'moon'
              ? coverage.moon_indexed_patches
              : mode === 'detailed' && discoveryIndex === 'expanded'
                ? coverage.expanded_indexed_patches
                : coverage.earth_indexed_patches
            ).toLocaleString()}</strong></div>
          </div>
          <p className="sidebar-note">Limited Earth pilot. Worldwide indexing is not yet complete.</p>
        </div>

        <div className="sidebar-footer">
          <ShieldAlert size={17} />
          <span>Experimental research prototype. Analog suitability has not been independently validated.</span>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <Globe2 size={16} /> Mission Control <span>/</span> Discovery
          </div>
          <div className="api-status"><span className="status-dot" /> API connected</div>
        </header>

        <div className="dashboard-body">
          <div className="page-intro">
            <div>
              <div className="eyebrow"><Satellite size={15} /> TERRAIN INTELLIGENCE</div>
              <h1>Discover Earth’s planetary analogs.</h1>
              <p>Explore automatically ranked Earth terrain candidates for {currentPlanet} using real elevation data.</p>
            </div>
            <div className="mode-tag">{mode === 'regional' ? '60 KM REGIONAL MODEL' : '5.76 KM HYBRID MODEL'}</div>
          </div>

          {error && <div className="error-message">{error} — ensure FastAPI is running on port 8000.</div>}

          <div className="stat-grid">
            <div className="stat-card"><Globe2 size={19} /><span>EARTH PATCH INDEX</span><strong>{(mode === 'detailed' && detailedPlanet === 'moon'
              ? coverage.moon_indexed_patches
              : mode === 'detailed' && discoveryIndex === 'expanded'
                ? coverage.expanded_indexed_patches
                : coverage.earth_indexed_patches
            ).toLocaleString()}</strong><small>Sampled terrain patches</small></div>
            <div className="stat-card"><Mountain size={19} /><span>ACTIVE TARGET</span><strong>{currentPlanet}</strong><small>{mode === 'regional'
              ? 'Regional terrain analysis'
              : detailedPlanet === 'moon'
                ? 'Lunar Site04'
                : 'Jezero crater'}</small></div>
            <div className="stat-card"><MapPin size={19} /><span>RANKED CANDIDATES</span><strong>{candidates.length}</strong><small>For selected target</small></div>
            <div className="stat-card"><Activity size={19} /><span>DISCOVERY MODE</span><strong>{mode === 'regional' ? 'Regional' : 'Hybrid AI'}</strong><small>Experimental retrieval</small></div>
          </div>

          <div className="workspace">
            <section className="map-panel">
              <div className="panel-heading">
                <div>
                  <h2><Globe2 size={18} /> Earth discovery map</h2>
                  <p>Click a candidate marker or select a result from the list.</p>
                </div>
                <div className="map-actions">
                  <label htmlFor="map-layer">Map layer</label>
                  <select id="map-layer" value={mapLayer} onChange={event => {
                    setMapNotice('')
                    setMapLayer(event.target.value as MapLayer)
                  }}>
                    <option value="street">Street · OpenStreetMap</option>
                    <option value="satellite">Satellite · Landsat WELD (2000)</option>
                    <option value="blue-marble">Global · NASA Blue Marble</option>
                  </select>
                  <button type="button" onClick={resetMapView}>Reset view</button>
                </div>
              </div>
              <div ref={mapContainer} className="map-container" />
              {mapNotice && <p className="map-notice" role="status">{mapNotice}</p>}
              {mapLayer === 'satellite' && <p className="map-notice">NASA / USGS Landsat WELD is a historical 2000 composite. Source detail is about 30 m; tiles stop at zoom 12. It is visual context, not the terrain DEM.</p>}
              {mapLayer === 'blue-marble' && <p className="map-notice">NASA Blue Marble is a coarse global overview; zooming in does not add local detail.</p>}
            </section>

            <section className="results-panel">
              <div className="panel-heading">
                <div>
                  <h2>Ranked Earth candidates</h2>
                  <p>{loading ? 'Loading discoveries…' : `${candidates.length} results for your selection`}</p>
                </div>
              </div>
              <div className="candidate-list">
                {candidates.map((candidate, index) => (
                  <button
                    key={`${candidate.earth_patch_id ?? candidate.location_name}-${index}`}
                    className={`candidate-item ${selectedIndex === index ? 'candidate-active' : ''}`}
                    aria-pressed={selectedIndex === index}
                    onClick={() => setSelectedIndex(index)}
                  >
                    <span className="rank-number">{candidate.rank}</span>
                    <span className="candidate-content">
                      <span className="candidate-title-row">
                        <strong>{candidate.geographic_label ?? `Earth terrain candidate ${candidate.rank}`}</strong>
                        {selectedIndex === index && <span className="candidate-select-label">Selected</span>}
                      </span>
                      <small className="candidate-coordinates">{candidate.latitude.toFixed(4)}°, {candidate.longitude.toFixed(4)}°</small>
                      <span className="candidate-metrics">
                        <span>{mode === 'regional' ? 'Similarity index' : 'Physical distance'} <b>{formatNumber(mode === 'regional' ? candidate.similarity_score : candidate.physical_feature_distance)}</b></span>
                        {mode === 'detailed' && <span>Neural distance <b>{formatNumber(candidate.neural_embedding_distance)}</b></span>}
                      </span>
                      {mode === 'detailed' && (
                        <small className="candidate-quality">
                          {candidate.quality_status === 'review'
                            ? '⚠ Source quality: review required'
                            : candidate.quality_status === 'measured'
                              ? '✓ Source quality: measured'
                              : 'Source quality: not reported'}
                          {candidate.hem_coverage !== undefined &&
                            ` · HEM ${ (candidate.hem_coverage * 100).toFixed(1)}%`}
                        </small>
                      )}
                    </span>
                    <MapPin size={17} aria-hidden="true" />
                  </button>
                ))}
                {!loading && candidates.length === 0 && (
                  <p className="empty-message">No results available for this selection.</p>
                )}
              </div>
            </section>
          </div>

          {selected && (
            <section className="details-panel">
              <div className="panel-heading">
                <div>
                  <h2><Mountain size={18} /> Selected terrain candidate</h2>
                  <p>Measured characteristics and retrieval evidence</p>
                </div>
                <div className="detail-actions">
                <button type="button" className="compare-action" onClick={() => terrainViewer.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
                  <Mountain size={15} /> Compare in 3D
                </button>
                <a
                  href={`https://www.openstreetmap.org/?mlat=${selected.latitude}&mlon=${selected.longitude}#map=9/${selected.latitude}/${selected.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="external-link"
                >
                  Open location <ExternalLink size={15} />
                </a>
                </div>
              </div>
              {selected.geographic_label && <p className="geographic-context">{selected.geographic_label} <small>Label from {selected.geographic_label_source === 'earth_acquisition_status.json' ? 'Earth acquisition metadata' : 'Copernicus tile catalog'}; coordinate shown below.</small></p>}
              <div className="detail-grid">
                <div><span>LATITUDE</span><strong>{selected.latitude.toFixed(5)}°</strong></div>
                <div><span>LONGITUDE</span><strong>{selected.longitude.toFixed(5)}°</strong></div>
                <div><span>{mode === 'regional' ? 'SIMILARITY INDEX' : 'FEATURE DISTANCE'}</span><strong>{formatNumber(mode === 'regional' ? selected.similarity_score : selected.physical_feature_distance)}</strong></div>
                <div><span>{mode === 'regional' ? 'RANK' : 'NEURAL DISTANCE'}</span><strong>{mode === 'regional' ? selected.rank : formatNumber(selected.neural_embedding_distance)}</strong></div>
                <div><span>LAND COVER</span><strong>{selected.dominant_landcover ?? 'Not reported'}</strong></div>
                <div>
                  <span>SOURCE QUALITY</span>
                  <strong>
                    {selected.quality_status === 'review'
                      ? 'Review required'
                      : selected.quality_status === 'measured'
                        ? 'Measured'
                        : 'Not reported'}
                  </strong>
                </div>
                {mode === 'detailed' && (
                  <>
                    <div>
                      <span>HEM COVERAGE</span>
                      <strong>
                        {selected.hem_coverage === undefined
                          ? 'Not reported'
                          : `${(selected.hem_coverage * 100).toFixed(2)}%`}
                      </strong>
                    </div>
                    <div>
                      <span>ORIGINAL SOURCE</span>
                      <strong>
                        {selected.original_source_fraction === undefined
                          ? 'Not reported'
                          : `${(selected.original_source_fraction * 100).toFixed(2)}%`}
                      </strong>
                    </div>
                    <div>
                      <span>LAND-COVER DATA</span>
                      <strong>
                        {selected.landcover_status ?? 'Not reported'}
                      </strong>
                    </div>
                  </>
                )}
              </div>
              <div className="scientific-note">
                <ShieldAlert size={17} />
                <span>
                  {mode === 'detailed' && selected.quality_status === 'review'
                    ? 'Elevation source quality requires review. This candidate remains ranked by terrain similarity; source quality has not been used to promote or demote it. '
                    : ''}
                  {selected.caveats ??
                    'Terrain-based experimental candidate, not verified as a geological or operational analog. Physical and neural distances are not probabilities.'}
                </span>
              </div>
              {terrainSummary && <div className="terrain-summary"><strong>Why this terrain is ranked</strong><p>{terrainSummary}</p><small>Measured DEM shape features; physical and neural distances are ranking distances, not probabilities or evidence of geological equivalence.</small></div>}
              {mode === 'detailed' && targetFeatures && selected.terrain_features && (
                <div className="feature-comparison">
                  <h3>Measured terrain features</h3>
                  <p>Same feature definitions; different planetary and Earth DEM sources. Values describe surface shape, not geology.</p>
                  <table>
                    <thead><tr><th>Feature</th><th>{currentPlanet} target</th><th>Earth candidate</th></tr></thead>
                    <tbody>{featureLabels.map(([key, label, unit]) => (
                      <tr key={key}>
                        <th>{label}</th>
                        <td>{targetFeatures[key].toFixed(2)} {unit}</td>
                        <td>{selected.terrain_features![key].toFixed(2)} {unit}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              )}
            </section>
          )}
          {mode === 'regional' && selected?.profile_id && (
            <MatchExplanation
              key={`${targetId}-${selected.profile_id}-evidence`}
              targetName={
                targets.find(target => target.target_id === targetId)
                  ?.target_site ?? targetId
              }
              candidateName={selected.geographic_label ?? `Earth candidate ${selected.rank}`}
              similarity={selected.similarity_score}
              metrics={selected.metrics}
              sourceIds={selected.source_ids}
            />
          )}

          <div ref={terrainViewer} id="terrain-comparison" className="terrain-viewer-anchor">
          {mode === 'regional' && selected?.profile_id && (
            <TerrainComparison
              key={`${targetId}-${selected.profile_id}`}
              mode="regional"
              regionalTargetProfileId={
                targetId === 'moon-shackleton'
                  ? 'moon_shackleton_60km_v1'
                  : targetId === 'moon-tranquillitatis'
                    ? 'moon_tranquillitatis_pit_60km_v1'
                    : 'mars_jezero_60km_v1'
              }
              regionalEarthProfileId={selected.profile_id}
            />
          )}

          {mode === 'detailed' && selected?.earth_patch_id && patchId && (
            <TerrainComparison
              key={`${detailedPlanet}-${patchId}-${selected.earth_patch_id}`}
              mode="detailed"
              targetBody={detailedPlanet}
              targetPatchId={patchId}
              earthPatchId={selected.earth_patch_id}
            />
          )}
          </div>

          <footer>TerraMirror · NASA Space Apps research prototype · Earth / Moon / Mars</footer>
        </div>
      </main>
    </div>
  )
}

export default App
