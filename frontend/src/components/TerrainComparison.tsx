import { useEffect, useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

type TerrainData = {
  body: string
  patch_id: string
  grid_size: number[]
  resolution_m: number
  elevation: number[][]
  valid_mask: number[][]
  minimum_m: number
  maximum_m: number
  relief_m: number
  source_attribution?: string
  source_liability_notice?: string
}

type Props =
  | {
      mode: 'detailed'
      targetBody: 'mars' | 'moon'
      targetPatchId: string
      earthPatchId: string
    }
  | {
      mode: 'regional'
      regionalTargetProfileId: string
      regionalEarthProfileId: string
    }

const API = ''

function validCoverage(terrain: TerrainData): number {
  const cells = terrain.valid_mask.flat()
  if (cells.length === 0) return 0

  const valid = cells.filter(value => value !== 0).length
  return (valid / cells.length) * 100
}

function Surface({
  terrain,
  offset,
  exaggeration,
  colorMin,
  colorMax,
}: {
  terrain: TerrainData
  offset: number
  exaggeration: number
  colorMin: number
  colorMax: number
}) {
  const geometry = useMemo(() => {
    const rows = terrain.elevation.length
    const cols = terrain.elevation[0].length
    const spacing = terrain.resolution_m / 1000

    const positions: number[] = []
    const colors: number[] = []
    const indices: number[] = []

    const range = Math.max(colorMax - colorMin, 0.001)

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const height = terrain.elevation[row][col]

        const x = (col - (cols - 1) / 2) * spacing
        const z = (row - (rows - 1) / 2) * spacing

        // Horizontal and vertical units are kilometres.
        const y = height / 1000 * exaggeration

        positions.push(x, y, z)

        const t = THREE.MathUtils.clamp(
          (height - colorMin) / range, 0, 1
        )

        const color = new THREE.Color()
        color.setHSL(0.65 - t * 0.62, 0.75, 0.48)

        colors.push(color.r, color.g, color.b)
      }
    }

    for (let row = 0; row < rows - 1; row++) {
      for (let col = 0; col < cols - 1; col++) {
        const a = row * cols + col
        const b = a + 1
        const c = (row + 1) * cols + col
        const d = c + 1

        const valid = [
          terrain.valid_mask[row][col],
          terrain.valid_mask[row][col + 1],
          terrain.valid_mask[row + 1][col],
          terrain.valid_mask[row + 1][col + 1],
        ]

        // Never render triangles containing invalid terrain cells.
        if (valid[0] && valid[2] && valid[1]) {
          indices.push(a, c, b)
        }
        if (valid[1] && valid[2] && valid[3]) {
          indices.push(b, c, d)
        }
      }
    }

    const mesh = new THREE.BufferGeometry()

    mesh.setAttribute(
      'position',
      new THREE.Float32BufferAttribute(positions, 3)
    )

    mesh.setAttribute(
      'color',
      new THREE.Float32BufferAttribute(colors, 3)
    )

    mesh.setIndex(indices)
    mesh.computeVertexNormals()

    return mesh
  }, [terrain, exaggeration, colorMin, colorMax])

  const boundary = useMemo(() => {
    const rows = terrain.elevation.length
    const cols = terrain.elevation[0].length
    const spacing = terrain.resolution_m / 1000
    const points: number[] = []
    const addEdge = (r1: number, c1: number, r2: number, c2: number) => {
      if (!terrain.valid_mask[r1][c1] || !terrain.valid_mask[r2][c2]) return
      for (const [row, col] of [[r1, c1], [r2, c2]]) {
        points.push(
          (col - (cols - 1) / 2) * spacing,
          terrain.elevation[row][col] / 1000 * exaggeration + 0.006,
          (row - (rows - 1) / 2) * spacing
        )
      }
    }
    for (let col = 0; col < cols - 1; col++) {
      addEdge(0, col, 0, col + 1)
      addEdge(rows - 1, col, rows - 1, col + 1)
    }
    for (let row = 0; row < rows - 1; row++) {
      addEdge(row, 0, row + 1, 0)
      addEdge(row, cols - 1, row + 1, cols - 1)
    }
    const outline = new THREE.BufferGeometry()
    outline.setAttribute('position', new THREE.Float32BufferAttribute(points, 3))
    return outline
  }, [terrain, exaggeration])

  useEffect(() => () => {
    geometry.dispose()
    boundary.dispose()
  }, [geometry, boundary])

  return (
    <group position={[offset, 0, 0]}>
      <mesh geometry={geometry}>
        <meshStandardMaterial
          vertexColors
          side={THREE.DoubleSide}
          roughness={0.94}
          metalness={0}
        />
      </mesh>
      <lineSegments geometry={boundary}>
        <lineBasicMaterial color="#d6ecf2" transparent opacity={0.8} depthWrite={false} />
      </lineSegments>
    </group>
  )
}

export default function TerrainComparison(props: Props) {
  const isRegional = props.mode === 'regional'
  const targetBody = isRegional
    ? props.regionalTargetProfileId.startsWith('moon_')
      ? 'moon'
      : 'mars'
    : props.targetBody

  const marsPatchId = isRegional
    ? props.regionalTargetProfileId
    : props.targetPatchId
  const earthPatchId = isRegional
    ? props.regionalEarthProfileId
    : props.earthPatchId
  const [mars, setMars] = useState<TerrainData | null>(null)
  const [earth, setEarth] = useState<TerrainData | null>(null)
  const [exaggeration, setExaggeration] = useState(3)
  const [grid, setGrid] = useState<32 | 64>(64)
  const [cameraPreset, setCameraPreset] = useState<'oblique' | 'top' | 'side'>('oblique')
  const [cameraReset, setCameraReset] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()

    async function fetchTerrain(body: string, id: string) {
      const url = isRegional
        ? `${API}/api/regional-terrain/${encodeURIComponent(id)}`
        : `${API}/api/terrain/${body}/${encodeURIComponent(id)}?grid=${grid}`

      const response = await fetch(url, {
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`${body} terrain request failed: ${response.status}`)
      }

      return response.json() as Promise<TerrainData>
    }

    Promise.all([
      fetchTerrain(targetBody, marsPatchId),
      fetchTerrain('earth', earthPatchId),
    ])
      .then(([marsData, earthData]) => {
        if (controller.signal.aborted) return
        setMars(marsData)
        setEarth(earthData)
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(String(err))
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [marsPatchId, earthPatchId, isRegional, targetBody, grid])

  const colorMin = mars && earth
    ? Math.min(mars.minimum_m, earth.minimum_m)
    : 0

  const colorMax = mars && earth
    ? Math.max(mars.maximum_m, earth.maximum_m)
    : 1

  const halfOffset = mars
    ? (
        (mars.grid_size[1] - 1) * mars.resolution_m / 1000
        + (isRegional ? 12 : 1.4)
      ) / 2
    : 3.5

  const cameraPosition: [number, number, number] = isRegional
    ? cameraPreset === 'top' ? [0, 115, 0.01]
      : cameraPreset === 'side' ? [0, 25, 110] : [45, 52, 92]
    : cameraPreset === 'top' ? [0, 14, 0.01]
      : cameraPreset === 'side' ? [0, 2.4, 10.5]
        : targetBody === 'moon' ? [4.2, 6, 11.5] : [3.2, 4.4, 8.6]

  const baseY = colorMin / 1000 * exaggeration - (isRegional ? 0.7 : 0.22)
  const targetWidth = mars ? (mars.grid_size[1] - 1) * mars.resolution_m / 1000 : 6
  const referenceGridWidth = targetWidth + halfOffset * 2 + (isRegional ? 8 : 1)

  return (
    <section className="terrain-panel">
      <div className="terrain-heading">
        <div>
          <h2>Interactive 3D Terrain Comparison</h2>
          <p>{isRegional
              ? 'Regional planetary and Earth DEMs · 1 km resolution'
              : `Detailed ${targetBody === 'moon' ? 'Moon' : 'Mars'} and Earth DEMs · measured grid elevations`}</p>
        </div>
        <div className="terrain-view-controls">
          {!isRegional && <label>Grid resolution
            <select value={grid} onChange={event => {
              setLoading(true)
              setError('')
              setMars(null)
              setEarth(null)
              setGrid(Number(event.target.value) as 32 | 64)
            }}>
              <option value={64}>64 × 64 (full)</option>
              <option value={32}>32 × 32 (lighter)</option>
            </select>
          </label>}
          <div className="terrain-preset-group" role="group" aria-label="Camera views">
            {(['top', 'oblique', 'side'] as const).map(preset => (
              <button key={preset} type="button" aria-pressed={cameraPreset === preset}
                onClick={() => { setCameraPreset(preset); setCameraReset(value => value + 1) }}>
                {preset[0].toUpperCase() + preset.slice(1)}
              </button>
            ))}
            <button type="button" onClick={() => { setCameraPreset('oblique'); setCameraReset(value => value + 1) }}>
              Reset
            </button>
          </div>
        </div>
        <label className="exaggeration-control">
          Vertical exaggeration: <strong>{exaggeration}×</strong>
          <input
            type="range"
            min="1"
            max="10"
            step="1"
            value={exaggeration}
            onChange={event =>
              setExaggeration(Number(event.target.value))
            }
          />
        </label>
      </div>

      {error && <p className="terrain-error">{error}</p>}
      {loading && <p className="terrain-loading">Loading terrain elevation data…</p>}

      {mars && earth && !loading && (
        <>
          <div className="terrain-labels">
            <div>
              <strong>{mars.body.toUpperCase()} — {isRegional
                  ? 'REGIONAL TARGET'
                  : targetBody === 'moon' ? 'SITE04' : 'JEZERO'}</strong>
              <span>Relief: {mars.relief_m.toFixed(1)} m</span>
              <span>Valid terrain: {validCoverage(mars).toFixed(1)}%</span>
            </div>
            <div>
              <strong>EARTH — SELECTED ANALOG</strong>
              <span>Relief: {earth.relief_m.toFixed(1)} m</span>
              <span>Valid terrain: {validCoverage(earth).toFixed(1)}%</span>
            </div>
          </div>

          <div className="terrain-canvas">
            <Canvas
              key={`${isRegional ? 'regional' : `detailed-${targetBody}`}-${cameraPreset}-${cameraReset}`}
              camera={{
                position: cameraPosition,
                fov: 48,
                near: 0.1,
                far: 1000,
              }}
              gl={{ antialias: true }}
            >
              <color attach="background" args={['#101c2a']} />

              <ambientLight intensity={0.48} />
              <hemisphereLight args={['#d6f1ff', '#203344', 0.58]} />
              <directionalLight
                position={[-6, 11, 5]}
                intensity={2.5}
              />
              <directionalLight position={[7, 3, -6]} intensity={0.35} />
              <gridHelper args={[referenceGridWidth, 12, '#45657a', '#294354']} position={[0, baseY, 0]} />

              <Surface
                terrain={mars}
                offset={-halfOffset}
                exaggeration={exaggeration}
                colorMin={colorMin}
                colorMax={colorMax}
              />

              <Surface
                terrain={earth}
                offset={halfOffset}
                exaggeration={exaggeration}
                colorMin={colorMin}
                colorMax={colorMax}
              />

              <OrbitControls
                makeDefault
                enableDamping
                enablePan
                minDistance={isRegional ? 45 : 5}
                maxDistance={isRegional ? 400 : 35}
              />
            </Canvas>
          </div>

          <div className="terrain-science-bar">
            <div className="terrain-scale-info">
              <strong>Terrain orientation</strong>
              <span>North: −Z · East: +X</span>
              <small>Directions are relative to the terrain grid, not the rotated screen.</small>
            </div>

            <div className="terrain-scale-info">
              <strong>Horizontal scale</strong>
              <span>{((mars.grid_size[1] - 1) * mars.resolution_m / 1000).toFixed(2)} km</span>
              <small>Displayed sample-centre span per side</small>
            </div>

            <div className="terrain-legend">
              <strong>Relative elevation (m)</strong>
              <div className="terrain-color-gradient" />
              <div className="terrain-legend-values">
                <span>{colorMin.toFixed(1)} m</span>
                <span>{colorMax.toFixed(1)} m</span>
              </div>
            </div>
          </div>

          <div className="terrain-footer">
            <span>Drag to rotate · Scroll to zoom · Right-drag to pan</span>
            <span>Reference grid is a visual guide, not measured terrain.</span>
          </div>

          {(validCoverage(mars) < 99.95 ||
            validCoverage(earth) < 99.95) && (
            <p className="terrain-data-warning">
              Missing elevation cells are excluded from the 3D mesh.
              Dark gaps represent unavailable data, not confirmed
              terrain holes or craters.
            </p>
          )}

          <p className="terrain-caveat">
            Terrain coverage represents valid raster cells, not
            independently verified measurement coverage.
            Terrain is displayed at {mars.resolution_m} m grid spacing.
            The 32 × 32 option samples every second measured grid cell;
            it does not add detail.
            Elevations are patch-relative. Vertical exaggeration changes
            appearance, not measurements. This visualization does not
            establish geological equivalence.
          </p>
          {earth.source_attribution && (
            <p className="terrain-source-credit">
              {earth.source_attribution}. {earth.source_liability_notice}. Independent research prototype; not endorsed by Copernicus, ESA, DLR or Airbus.
              {' '}<a href="https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM" target="_blank" rel="noopener noreferrer">Copernicus DEM terms</a>
            </p>
          )}
        </>
      )}
    </section>
  )
}
