import numpy as np
import pandas as pd
import pytest

from src.features import (
    FEATURE_COLUMNS,
    TerrainFeatureScaler,
    apply_feature_weights,
    calculate_feature_contributions,
    select_features,
    validate_compatibility,
    validate_features,
)


@pytest.fixture
def valid_feature_frame():
    return pd.DataFrame(
        {
            "median_slope_deg": [10.0, 18.5, 6.0],
            "roughness_m": [1.0, 2.5, 0.75],
            "relief_m": [30.0, 44.0, 20.0],
            "steep_fraction": [0.12, 0.25, 0.08],
        }
    )


@pytest.fixture
def valid_metadata():
    return {
        "feature_version": "1.0",
        "grid_m": 90.0,
        "roi_size_km": 25.0,
        "roughness_window_m": 9.0,
        "slope_method": "median_slope_deg",
        "relief_method": "p10_p90",
        "steep_threshold_deg": 15.0,
    }


@pytest.fixture
def valid_weights():
    return {col: 1.0 / len(FEATURE_COLUMNS) for col in FEATURE_COLUMNS}


def test_valid_feature_input(valid_feature_frame):
    result = validate_features(valid_feature_frame)
    assert list(result.columns) == FEATURE_COLUMNS
    assert result.shape == valid_feature_frame.shape
    assert result.equals(valid_feature_frame[FEATURE_COLUMNS])


def test_missing_required_columns(valid_feature_frame):
    missing = valid_feature_frame.drop(columns=["roughness_m"])
    with pytest.raises(ValueError, match="Missing required feature columns"):
        validate_features(missing)


def test_invalid_feature_ranges(valid_feature_frame):
    bad = valid_feature_frame.copy()
    bad.loc[0, "median_slope_deg"] = 95.0
    with pytest.raises(ValueError, match="median_slope_deg"):
        validate_features(bad)

    bad = valid_feature_frame.copy()
    bad.loc[0, "roughness_m"] = -0.5
    with pytest.raises(ValueError, match="roughness_m"):
        validate_features(bad)

    bad = valid_feature_frame.copy()
    bad.loc[0, "relief_m"] = -1.0
    with pytest.raises(ValueError, match="relief_m"):
        validate_features(bad)

    bad = valid_feature_frame.copy()
    bad.loc[0, "steep_fraction"] = 1.5
    with pytest.raises(ValueError, match="steep_fraction"):
        validate_features(bad)


def test_nan_and_infinity_rejection(valid_feature_frame):
    bad = valid_feature_frame.copy()
    bad.loc[0, "roughness_m"] = np.nan
    with pytest.raises(ValueError, match="NaN|infinite|missing"):
        validate_features(bad)

    bad = valid_feature_frame.copy()
    bad.loc[0, "relief_m"] = np.inf
    with pytest.raises(ValueError, match="infinite|finite"):
        validate_features(bad)


def test_feature_order_preservation(valid_feature_frame):
    reordered = valid_feature_frame[["steep_fraction", "roughness_m", "relief_m", "median_slope_deg"]]
    selected = select_features(reordered)
    assert list(selected.columns) == FEATURE_COLUMNS
    assert reordered.columns.tolist() == ["steep_fraction", "roughness_m", "relief_m", "median_slope_deg"]


def test_input_immutability(valid_feature_frame):
    original = valid_feature_frame.copy(deep=True)
    validated = validate_features(valid_feature_frame)
    assert valid_feature_frame.equals(original)
    assert validated is not valid_feature_frame

    selected = select_features(valid_feature_frame)
    assert valid_feature_frame.equals(original)
    assert selected is not valid_feature_frame


def test_robust_scaler_fitting_and_transform(valid_feature_frame):
    scaler = TerrainFeatureScaler()
    fitted = scaler.fit(valid_feature_frame)
    transformed = scaler.transform(valid_feature_frame)

    assert fitted is scaler
    assert transformed.shape == (len(valid_feature_frame), len(FEATURE_COLUMNS))
    assert transformed.dtype.kind == "f"


def test_scaler_rejects_unfitted_transform(valid_feature_frame):
    scaler = TerrainFeatureScaler()
    with pytest.raises(ValueError, match="fitted"):
        scaler.transform(valid_feature_frame)


def test_single_row_planetary_transformation(valid_feature_frame):
    scaler = TerrainFeatureScaler().fit(valid_feature_frame)
    planet = valid_feature_frame.iloc[[0]].copy()
    transformed = scaler.transform(planet)
    assert transformed.shape == (1, len(FEATURE_COLUMNS))


def test_scaling_reproducibility(valid_feature_frame):
    scaler1 = TerrainFeatureScaler().fit(valid_feature_frame)
    arr1 = scaler1.transform(valid_feature_frame)
    scaler2 = TerrainFeatureScaler().fit(valid_feature_frame)
    arr2 = scaler2.transform(valid_feature_frame)
    np.testing.assert_allclose(arr1, arr2, rtol=1e-12, atol=1e-12)


def test_scientific_metadata_compatibility(valid_metadata):
    validate_compatibility(valid_metadata, valid_metadata)


def test_metadata_mismatch_rejection(valid_metadata):
    mismatched = dict(valid_metadata)
    mismatched["grid_m"] = 45.0
    with pytest.raises(ValueError, match="grid_m"):
        validate_compatibility(valid_metadata, mismatched)

    mismatched = dict(valid_metadata)
    mismatched["slope_method"] = "different_method"
    with pytest.raises(ValueError, match="slope_method"):
        validate_compatibility(valid_metadata, mismatched)


def test_valid_mission_weights(valid_weights):
    arr = np.array([[1.0, 2.0, 3.0, 4.0]], dtype=float)
    result = apply_feature_weights(arr, valid_weights)
    expected = arr * np.sqrt(1.0 / len(FEATURE_COLUMNS))
    np.testing.assert_allclose(result, expected)


def test_all_zero_weight_rejection(valid_weights):
    weights = {key: 0.0 for key in valid_weights}
    arr = np.ones((2, 4), dtype=float)
    with pytest.raises(ValueError, match="zero"):
        apply_feature_weights(arr, weights)


def test_negative_weight_rejection(valid_weights):
    weights = dict(valid_weights)
    weights["median_slope_deg"] = -0.25
    arr = np.ones((2, 4), dtype=float)
    with pytest.raises(ValueError, match="negative|nonnegative"):
        apply_feature_weights(arr, weights)


def test_weighted_euclidean_distance_correctness(valid_weights):
    earth = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
    planet = np.array([0.0, 1.0, 2.5, 5.0], dtype=float)
    weighted = apply_feature_weights(np.vstack([earth, planet]), valid_weights)
    diff = weighted[0] - weighted[1]
    expected_dist = np.linalg.norm(diff)
    weight_vector = np.array([valid_weights[col] for col in FEATURE_COLUMNS], dtype=float)
    np.testing.assert_allclose(expected_dist, np.sqrt(np.sum(weight_vector * (earth - planet) ** 2)))


def test_feature_contributions_sum_to_total_squared_distance(valid_weights):
    earth = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)
    planet = np.array([0.0, 1.0, 2.5, 5.0], dtype=float)
    result = calculate_feature_contributions(earth, planet, valid_weights)
    contribution_total = sum(item["squared_weighted_contribution"] for item in result["feature_contributions"])
    np.testing.assert_allclose(contribution_total, result["total_squared_distance"], rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(result["weighted_euclidean_distance"] ** 2, result["total_squared_distance"], rtol=1e-12, atol=1e-12)


def test_invalid_input_shapes(valid_weights):
    with pytest.raises(ValueError, match="shape|dimensions"):
        calculate_feature_contributions(np.ones((2, 4)), np.ones((4,)), valid_weights)

    with pytest.raises(ValueError, match="shape|dimensions"):
        apply_feature_weights(np.ones((2, 3)), valid_weights)


def test_empty_dataset_rejection(valid_feature_frame):
    empty = valid_feature_frame.iloc[0:0]
    with pytest.raises(ValueError, match="empty"):
        validate_features(empty)

    with pytest.raises(ValueError, match="empty"):
        select_features(empty)
