import './MatchExplanation.css'

type MatchMetrics = {
  slope_match?: number
  relief_match?: number
  roughness_match?: number
  steep_fraction_match?: number
}

type Props = {
  targetName: string
  candidateName: string
  similarity?: number
  metrics?: MatchMetrics
  sourceIds?: string[]
}

const FEATURES: {
  key: keyof MatchMetrics
  label: string
  explanation: string
}[] = [
  {
    key: 'slope_match',
    label: 'Terrain slope',
    explanation: 'Agreement in terrain steepness',
  },
  {
    key: 'relief_match',
    label: 'Terrain relief',
    explanation: 'Model-derived relief feature agreement',
  },
  {
    key: 'roughness_match',
    label: 'Surface roughness',
    explanation: 'Agreement in local elevation variability',
  },
  {
    key: 'steep_fraction_match',
    label: 'Steep terrain fraction',
    explanation: 'Agreement in the proportion of slopes above 15°',
  },
]

export default function MatchExplanation({
  targetName,
  candidateName,
  similarity,
  metrics,
  sourceIds,
}: Props) {
  const validMetrics = FEATURES
    .map(feature => ({
      ...feature,
      value: metrics?.[feature.key],
    }))
    .filter(
      (feature): feature is typeof feature & { value: number } =>
        typeof feature.value === 'number' &&
        Number.isFinite(feature.value)
    )

  const hasOutOfRangeScores = validMetrics.some(
    feature => feature.value < 0 || feature.value > 1
  )

  return (
    <section className="match-explanation">
      <div className="match-explanation-header">
        <div>
          <h2>Explain This Match</h2>
          <p>
            Regional terrain feature agreement for the selected
            Earth candidate
          </p>
        </div>
        <span className="match-method">
          Feature-based retrieval
        </span>
      </div>

      <div className="match-route">
        <strong>{targetName}</strong>
        <span>compared with</span>
        <strong>{candidateName}</strong>
      </div>

      <div className="match-summary">
        <span>Overall similarity index</span>
        <strong>
          {similarity === undefined
            ? 'Not available'
            : similarity.toFixed(4)}
        </strong>
      </div>

      <p className="match-disclaimer">
        Similarity is a model-derived ranking index, not a
        probability or a measure of geological suitability.
        Component scores are not raw terrain measurements.
      </p>

      <div className="match-feature-list">
        {validMetrics.map(feature => {
          const percentage = Math.max(
            0,
            Math.min(100, feature.value * 100)
          )

          return (
            <div className="match-feature" key={feature.key}>
              <div className="match-feature-top">
                <span>{feature.label}</span>
                <strong>{feature.value.toFixed(3)}</strong>
              </div>

              <div
                className="match-feature-track"
                role="progressbar"
                aria-label={feature.label}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={percentage}
              >
                <div
                  className="match-feature-fill"
                  style={{ width: `${percentage}%` }}
                />
              </div>

              <small>{feature.explanation}</small>
            </div>
          )
        })}
      </div>

      {validMetrics.length === 0 && (
        <p>No component matching metrics were reported.</p>
      )}

      {hasOutOfRangeScores && (
        <p className="match-data-alert">
          Some component scores fall outside the expected
          0–1 range. Their bars are visually bounded.
        </p>
      )}

      {similarity !== undefined && similarity < 0.1 && (
        <p className="match-data-alert">
          Very low similarity index. This candidate is
          primarily a ranked comparison within the available
          Earth catalog, not evidence of a close analog.
        </p>
      )}

      {sourceIds && sourceIds.length > 0 && (
        <div className="match-sources">
          <strong>Earth data source IDs</strong>
          <div>
            {sourceIds.map(id => (
              <code key={id}>{id}</code>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
