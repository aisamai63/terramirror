from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

FEATURE_COLUMNS = [
    "median_slope_deg",
    "roughness_m",
    "relief_m",
    "steep_fraction",
]


def _to_float_array(data: Any, *, name: str) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim == 0:
        raise ValueError(f"{name} must not be scalar.")
    return arr


def _validate_numeric_series(series: pd.Series, column_name: str) -> None:
    if series.empty:
        raise ValueError(f"Column '{column_name}' is empty.")
    for idx, value in series.items():
        if pd.isna(value):
            raise ValueError(f"Missing or NaN value found in '{column_name}' at row {idx}.")
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating, np.number)):
            raise ValueError(
                f"Column '{column_name}' contains a nonnumeric value at row {idx}: {value!r}. "
                "Only numeric feature values are allowed."
            )
        numeric = float(value)
        if not np.isfinite(numeric):
            raise ValueError(f"Column '{column_name}' contains an infinite or NaN value at row {idx}.")


def validate_features(data: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a terrain feature DataFrame with required columns and ranges."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Feature data must be provided as a pandas DataFrame.")
    if data.empty:
        raise ValueError("Feature data is empty; at least one terrain record is required.")

    missing = [column for column in FEATURE_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")

    validated = data.loc[:, FEATURE_COLUMNS].copy()
    for column in FEATURE_COLUMNS:
        _validate_numeric_series(validated[column], column)

        values = validated[column].to_numpy(dtype=float, copy=True)
        if column == "median_slope_deg":
            if np.any((values < 0.0) | (values > 90.0)):
                raise ValueError(f"'{column}' values must be between 0 and 90 degrees.")
        elif column == "roughness_m":
            if np.any(values < 0.0):
                raise ValueError(f"'{column}' values must be nonnegative.")
        elif column == "relief_m":
            if np.any(values < 0.0):
                raise ValueError(f"'{column}' values must be nonnegative.")
        elif column == "steep_fraction":
            if np.any((values < 0.0) | (values > 1.0)):
                raise ValueError(f"'{column}' values must be between 0 and 1.")

    return validated.copy()


def select_features(data: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame containing only the required terrain feature columns in order."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Input data must be a pandas DataFrame.")
    if data.empty:
        raise ValueError("Feature data is empty; at least one terrain record is required.")

    missing = [column for column in FEATURE_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")

    selected = data.loc[:, FEATURE_COLUMNS].copy()
    return validate_features(selected)


class TerrainFeatureScaler:
    """Fit and transform terrain features using a RobustScaler trained only on Earth data."""

    def __init__(self):
        self.scaler_: RobustScaler | None = None
        self.feature_names_in_: list[str] | None = None

    def fit(self, earth_features: pd.DataFrame):
        if not isinstance(earth_features, pd.DataFrame):
            raise TypeError("Earth feature data must be provided as a pandas DataFrame.")
        if earth_features.empty:
            raise ValueError("Earth feature dataset is empty; at least one Earth record is required.")

        earth = select_features(earth_features)
        self.feature_names_in_ = list(earth.columns)
        self.scaler_ = RobustScaler()
        self.scaler_.fit(earth.to_numpy(dtype=float, copy=True))
        return self

    def transform(self, features: pd.DataFrame) -> np.ndarray:
        if self.scaler_ is None or self.feature_names_in_ is None:
            raise ValueError("TerrainFeatureScaler has not been fitted yet.")
        if not isinstance(features, pd.DataFrame):
            raise TypeError("Feature data must be provided as a pandas DataFrame.")
        if features.empty:
            raise ValueError("Feature data is empty; at least one terrain record is required.")

        incoming = list(features.columns)
        expected = list(self.feature_names_in_)
        missing = [column for column in expected if column not in incoming]
        extra = [column for column in incoming if column not in expected]
        duplicates = [column for column in incoming if incoming.count(column) > 1]
        if duplicates:
            raise ValueError(f"Feature data contains duplicate columns: {sorted(set(duplicates))}.")
        if missing:
            raise ValueError(f"Missing required feature columns for transformation: {missing}")
        if extra:
            raise ValueError(f"Unexpected extra feature columns for transformation: {extra}")
        if incoming != expected:
            raise ValueError(
                "Feature column order is incorrect for transformation. "
                f"Expected {expected}, got {incoming}."
            )

        validated = validate_features(features.loc[:, expected].copy())
        return self.scaler_.transform(validated.to_numpy(dtype=float, copy=True))

    def fit_transform(self, earth_features: pd.DataFrame) -> np.ndarray:
        self.fit(earth_features)
        return self.transform(earth_features)


def _validate_compatibility_dict(metadata: dict, name: str) -> dict:
    if not isinstance(metadata, dict):
        raise TypeError(f"{name} metadata must be a dictionary of feature compatibility settings.")
    required = {
        "feature_version",
        "grid_m",
        "roi_size_km",
        "roughness_window_m",
        "slope_method",
        "relief_method",
        "steep_threshold_deg",
    }
    missing = sorted(required - set(metadata.keys()))
    if missing:
        raise ValueError(f"Missing required compatibility metadata in {name}: {missing}")
    return metadata


def validate_compatibility(earth_metadata: dict, planetary_metadata: dict) -> None:
    """Validate that Earth and planetary terrain definitions are scientifically compatible."""
    earth = _validate_compatibility_dict(earth_metadata, "earth_metadata")
    planet = _validate_compatibility_dict(planetary_metadata, "planetary_metadata")

    for field in ("feature_version", "slope_method", "relief_method"):
        if earth[field] != planet[field]:
            raise ValueError(
                f"Incompatible '{field}': Earth='{earth[field]}', Planetary='{planet[field]}'."
            )

    float_fields = ["grid_m", "roi_size_km", "roughness_window_m", "steep_threshold_deg"]
    for field in float_fields:
        try:
            earth_value = float(earth[field])
            planet_value = float(planet[field])
        except (TypeError, ValueError):
            raise ValueError(f"Compatibility field '{field}' must be numeric.")
        if not math.isclose(earth_value, planet_value, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(
                f"Incompatible '{field}': Earth={earth_value}, Planetary={planet_value}."
            )


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    if not isinstance(weights, dict):
        raise TypeError("Weights must be provided as a dict keyed by FEATURE_COLUMNS.")
    if list(weights.keys()) != FEATURE_COLUMNS:
        raise ValueError(
            f"Weight keys must exactly match FEATURE_COLUMNS: {FEATURE_COLUMNS}. "
            f"Received {list(weights.keys())}."
        )

    normalized: dict[str, float] = {}
    total = 0.0
    for column in FEATURE_COLUMNS:
        if column not in weights:
            raise ValueError(f"Missing weight for '{column}'.")
        value = weights[column]
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating, np.number)):
            raise ValueError(f"Weight for '{column}' must be numeric.")
        weight = float(value)
        if not np.isfinite(weight):
            raise ValueError(f"Weight for '{column}' is NaN or infinite.")
        if weight < 0.0:
            raise ValueError(f"Weight for '{column}' must be nonnegative.")
        normalized[column] = weight
        total += weight

    if total <= 0.0:
        raise ValueError("All feature weights are zero; at least one positive weight is required.")

    return {column: normalized[column] / total for column in FEATURE_COLUMNS}


def apply_feature_weights(scaled_features: np.ndarray, weights: dict[str, float]) -> np.ndarray:
    """Apply mission weighting to scaled features while preserving the original Euclidean distance semantics."""
    normalized = _normalize_weights(weights)
    scaled = np.array(scaled_features, dtype=float, copy=True)

    if scaled.ndim == 1:
        if scaled.shape[0] != len(FEATURE_COLUMNS):
            raise ValueError(
                f"Single feature vector must have shape ({len(FEATURE_COLUMNS)},); got {scaled.shape}."
            )
        weight_vector = np.sqrt(np.array([normalized[column] for column in FEATURE_COLUMNS], dtype=float))
        return scaled * weight_vector

    if scaled.ndim == 2:
        if scaled.shape[1] != len(FEATURE_COLUMNS):
            raise ValueError(
                f"Feature matrices must have {len(FEATURE_COLUMNS)} columns; got shape {scaled.shape}."
            )
        weight_vector = np.sqrt(np.array([normalized[column] for column in FEATURE_COLUMNS], dtype=float))
        return scaled * weight_vector

    raise ValueError(
        "scaled_features must be either a 1D vector or a 2D array with exactly "
        f"{len(FEATURE_COLUMNS)} feature columns; got shape {scaled.shape}."
    )


def calculate_feature_contributions(
    earth_scaled: np.ndarray,
    planet_scaled: np.ndarray,
    weights: dict[str, float],
) -> dict:
    """Compute per-feature squared contributions and the weighted Euclidean distance."""
    earth = np.asarray(earth_scaled, dtype=float)
    planet = np.asarray(planet_scaled, dtype=float)

    if earth.ndim == 2 and earth.shape[0] == 1:
        earth = earth[0]
    if planet.ndim == 2 and planet.shape[0] == 1:
        planet = planet[0]

    if earth.shape != planet.shape:
        raise ValueError(
            "Earth and planetary scaled feature arrays must have the same shape. "
            f"Got earth={earth.shape} and planet={planet.shape}."
        )
    if earth.shape != (len(FEATURE_COLUMNS),):
        raise ValueError(
            "earth_scaled and planet_scaled must each have shape "
            f"({len(FEATURE_COLUMNS)},) for a single Earth candidate and planetary reference."
        )

    normalized = _normalize_weights(weights)
    diff = earth - planet
    absolute_diff = np.abs(diff)

    contributions = []
    for index, column in enumerate(FEATURE_COLUMNS):
        weighted_contribution = normalized[column] * diff[index] ** 2
        contributions.append(
            {
                "feature_name": column,
                "normalized_weight": normalized[column],
                "scaled_earth_value": float(earth[index]),
                "scaled_planet_value": float(planet[index]),
                "absolute_scaled_difference": float(absolute_diff[index]),
                "squared_weighted_contribution": float(weighted_contribution),
            }
        )

    total_squared_distance = float(sum(item["squared_weighted_contribution"] for item in contributions))
    weighted_euclidean_distance = float(np.sqrt(total_squared_distance))
    largest_mismatch_feature = max(
        contributions, key=lambda item: item["squared_weighted_contribution"]
    )["feature_name"]
    smallest_mismatch_feature = min(
        contributions, key=lambda item: item["squared_weighted_contribution"]
    )["feature_name"]

    if not math.isclose(
        total_squared_distance,
        sum(normalized[column] * (earth[index] - planet[index]) ** 2 for index, column in enumerate(FEATURE_COLUMNS)),
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("The weighted feature contributions do not sum to the total squared distance.")

    return {
        "feature_contributions": contributions,
        "total_squared_distance": total_squared_distance,
        "weighted_euclidean_distance": weighted_euclidean_distance,
        "largest_mismatch_feature": largest_mismatch_feature,
        "smallest_mismatch_feature": smallest_mismatch_feature,
    }


__all__ = [
    "FEATURE_COLUMNS",
    "TerrainFeatureScaler",
    "apply_feature_weights",
    "calculate_feature_contributions",
    "select_features",
    "validate_compatibility",
    "validate_features",
]
