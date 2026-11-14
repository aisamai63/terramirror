# ML model preparation

Use **StandardScaler + cosine similarity** as the README's baseline. This is
unsupervised analog retrieval: no classifier labels or pretrained weights are
required. `src/model.py` implements fitting on Earth reference patches and ranking
them against a planetary target. The ingestion module remains a placeholder;
the latest team feature-engineering and API implementations are preserved.
The supplied processed data now supports an operational regional terrain model.

Cosine compares direction and ignores magnitude, so a high score does not guarantee
close absolute terrain measurements. `metric="euclidean"` is also available for
comparison using standardized feature distance. **The prepared demo model uses
standardized Euclidean distance**, because absolute terrain differences matter.
Cosine remains available as the original baseline. This is an engineering choice,
not a claim of superior accuracy: no independently labeled analog pairs are supplied.

## Finalized real-data workflow

From the project root in PowerShell:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-ml.lock
.venv\Scripts\python.exe -m src.prepare_model
.venv\Scripts\python.exe -m pytest tests -q
```

`requirements-ml.txt` lists direct ML dependencies; `requirements-ml.lock` captures
the tested Python 3.11 environment. The original GIS/API requirements are unchanged.

`src.prepare_model` loads `data/processed/earth_profiles.parquet` and
`planetary_profiles.parquet`. It uses four measured features in this order:
`slope_median_deg`, `relief_p90_p10_m`, `roughness_local_std_m`,
`steep_fraction_15deg`. All features receive equal weight after Earth-only
standardization. Slope and roughness are strongly correlated, so this weighting
remains a documented modeling limitation to revisit with expert labels.

Of 16 Earth profiles, **15 are eligible**. `earth_arctic_26_29_60km_v1` is excluded
because `qa_pass` is false and valid-cell coverage is 0.8247, below 0.90. Synthetic,
missing, incompatible-scale and invalid-feature records are also excluded with
reasons. All three planetary targets pass the input contract. Profiles share a
60 km ROI, 1000 m grid and 3-cell roughness kernel (`terrain_v1`, `features_v1`).

The runner checks all 19 supplied feature profiles against `real_validation.json`
and all 19 processed-raster hashes against `processing_manifest.json`. These are
consistency checks against supplied evidence, not a new raw-raster extraction or
independent scientific validation. It never uses existing ranking CSVs as labels.

Generated outputs:

- `data/processed/ml/analog_model.json`: reference records, feature order, metric,
  and verified scaling statistics. Load with `AnalogMatcher.load(path)`.
- `data/processed/ml/<profile_id>_results.json`: top five matches for each target,
  including source warnings, provenance, and out-of-range indicators.
- `data/processed/ml/validation_report.json`: input/code hashes, environment,
  exclusions, evidence checks, feature correlations, and full cosine/Euclidean rankings.
- `data/processed/analog_results.json`: Jezero results in the shared frontend contract.
  Jezero is the explicit default; target-specific files contain both lunar results.

Use `--metric cosine` to reproduce the README baseline, `--top-k 15` to export all
eligible matches, or `--output-dir <directory>` for an isolated experiment. Custom
output directories receive their own `analog_results.json` without overwriting
the shared default. Planetary coordinates are never treated as Earth coordinates.

The prepared model's leading regional candidates are Mojave for Jezero, the REMA
Antarctic region for Shackleton, and ArcticDEM 29_25 for Tranquillitatis. Shackleton
exceeds the eligible Earth range on **all four features** and gets a low distance
similarity; it has no close match demonstrated by this catalog. The 60 km lunar
pit ROI does not describe pit interiors, caves, or local landing hazards.

## Input contract with feature engineering

Earth records require `location_name`, WGS84 patch-center `latitude` and `longitude`,
and a `features` mapping. A target requires `target_site` and `features`.
Default feature names are `slope` and `roughness`. Agree with Member 2 on slope
units, the exact roughness definition and units, raster resolution, physical patch
size, and nodata handling. These must be comparable across Earth and planetary
inputs. Exclude invalid patches upstream; missing and nonfinite values are rejected.
At least two reference patches are required, and every selected feature must vary.

The scaler is fitted only on the Earth reference catalog. Queries use that same
scaler. Scaling Earth and planetary features independently would erase the shared
comparison basis. The model does not read raster files or generate features.

Thermal data is optional: the README's example includes it, but the feature
workstream specifies only slope and roughness. Include `thermal` in `feature_names`
only when comparable thermal measurements exist on every reference and query.
Otherwise `thermal_match` is omitted; the backend needs to accept that omission.

## Run the model

Install `requirements.txt` in a compatible Python environment (Python 3.11 is a
reasonable starting point for the existing older pins). Model-only experiments
need NumPy and scikit-learn; no GPU is required.

```python
from src.model import AnalogMatcher, save_results

# Synthetic interface example, not measured Earth analogs.
earth = [
    {"location_name": "Demo A", "latitude": 37.2, "longitude": 94.3,
     "features": {"slope": 5.0, "roughness": 0.3}},
    {"location_name": "Demo B", "latitude": 64.0, "longitude": -19.0,
     "features": {"slope": 20.0, "roughness": 1.5}},
    {"location_name": "Demo C", "latitude": 24.0, "longitude": -69.0,
     "features": {"slope": 10.0, "roughness": 0.9}},
]
target = {"target_site": "Synthetic Mars target",
          "features": {"slope": 5.5, "roughness": 0.35}}
matcher = AnalogMatcher().fit(earth)
results = matcher.rank(
    target, top_k=3,
    caveats="Terrain comparison only; gravity and atmosphere differ from Earth.",
)
save_results(results)  # data/processed/analog_results.json
```

Retain the fitted matcher in the API process. Refit deliberately when the reference
catalog changes. For thermal features use
`AnalogMatcher(feature_names=("slope", "roughness", "thermal"))`.

## Scores and limitations

- Cosine scores retain their native **[-1, 1]** range, higher first.
- Euclidean scores are `1 / (1 + standardized_distance)`, in **(0, 1]**.
- Feature `_match` values are `1 / (1 + absolute_standardized_difference)`.
  These are explanatory heuristics, not independently measured scientific agreement.
- Scores are not probabilities or proof of geological equivalence, and cannot be
  compared directly across different catalogs, features, or metric choices.
- Mean-centered zero vectors have undefined cosine angles. The model raises an
  error directing the caller to Euclidean distance in that case.
- Ties preserve input order. Nearby patches can repeat a geographic location;
  geographic deduplication is not implemented.
- Supply target-specific physical caveats. A terrain score does not account for
  gravity, atmosphere, chemistry, or unmeasured geology.

`save_results` emits the README's top-level contract as strict JSON. The timestamp
is the execution environment's current date. GeoJSON conversion belongs to the API.

## Validation before final model selection

Assemble independently reviewed target–Earth analog pairs and hard negatives.
Separate geographic regions between reference and validation sets to prevent
overlapping-window leakage. Compare cosine and Euclidean precision@k, recall@k,
and ranking quality where relevance judgments exist. Inspect outliers, resolution
sensitivity, and feature contributions. Record catalog version, feature names and
order, definitions, units, patch scales, and chosen metric with every experiment.
Do not choose a CNN or other learned embedding model without suitable data and
evidence that it improves on these baselines.

References: [StandardScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html),
[cosine similarity](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html).

Run all checks with `python -m pytest tests -q` (26 tests in this integrated snapshot).
