"""Validate processed terrain profiles, fit the model and export reproducible rankings.

Run from the project root: python -m src.prepare_model
"""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from .model import AnalogMatcher, save_results


FEATURES = ("slope_median_deg", "relief_p90_p10_m", "roughness_local_std_m", "steep_fraction_15deg")
CONTRACT = {"roi_size_km": 60, "common_grid_m": 1000, "roughness_kernel_cells": 3,
            "processing_version": "terrain_v1", "features_version": "features_v1"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_profiles(frame, planetary=False):
    """Reject incompatible schemas; return eligible rows and exclusion reasons."""
    required = set(FEATURES) | set(CONTRACT) | {
        "profile_id", "body", "qa_pass", "synthetic", "valid_cell_fraction",
        "region_name", "source_ids", "data_warning",
    }
    if not planetary:
        required |= {"site_name", "centroid_lat", "centroid_lon"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing profile columns: {sorted(missing)}")
    if frame.empty or frame.profile_id.isna().any() or frame.profile_id.duplicated().any():
        raise ValueError("Profile IDs must be present and unique in a nonempty catalog")
    accepted, excluded = [], []
    for _, row in frame.iterrows():
        reasons = []
        if pd.isna(row.qa_pass) or row.qa_pass != True:
            reasons.append("qa_failed")
        if pd.isna(row.synthetic) or row.synthetic != False:
            reasons.append("synthetic_or_unspecified")
        if row.body not in (("Mars", "Moon") if planetary else ("Earth",)):
            reasons.append("wrong_body")
        coverage = pd.to_numeric(row.valid_cell_fraction, errors="coerce")
        if not np.isfinite(coverage) or not 0.9 <= coverage <= 1:
            reasons.append("valid_cell_fraction_below_0.90_or_invalid")
        for key, value in CONTRACT.items():
            if pd.isna(row[key]) or row[key] != value:
                reasons.append(f"incompatible_{key}")
        values = pd.to_numeric(row[list(FEATURES)], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all() or np.any(values < 0):
            reasons.append("missing_or_invalid_features")
        elif values[0] > 90 or values[3] > 1:
            reasons.append("features_out_of_physical_range")
        if not planetary:
            coordinates = pd.to_numeric(row[["centroid_lat", "centroid_lon"]], errors="coerce").to_numpy(dtype=float)
            if (not np.isfinite(coordinates).all()
                    or abs(coordinates[0]) > 90 or abs(coordinates[1]) > 180):
                reasons.append("invalid_earth_coordinates")
            if not isinstance(row.site_name, str) or not row.site_name.strip():
                reasons.append("missing_site_name")
        if reasons:
            excluded.append({"profile_id": row.profile_id, "reasons": reasons})
        else:
            accepted.append(row.to_dict())
    return accepted, excluded


def record(row):
    result = {"profile_id": row["profile_id"],
              "features": {key: float(row[key]) for key in FEATURES}}
    if row["body"] == "Earth":
        result.update(location_name=row["site_name"], latitude=float(row["centroid_lat"]),
                      longitude=float(row["centroid_lon"]))
    else:
        result["target_site"] = row["region_name"]
    return result


def verify_evidence(data_dir, frames):
    """Cross-check supplied numerical verification and processed raster manifests.

    This checks consistency with supplied evidence, not scientific suitability
    or an independent re-extraction of features from raw elevation products.
    """
    checks = {}
    validation_path = data_dir / "real_validation.json"
    manifest_path = data_dir / "processing_manifest.json"
    profiles = {row["profile_id"]: row for frame in frames for row in frame.to_dict("records")}
    if validation_path.exists():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        verified = validation["profiles"]
        if {p["profile_id"] for p in verified} != set(profiles) or len(verified) != len(profiles):
            raise ValueError("Numerical validation does not cover the profile catalog exactly")
        for item in verified:
            row = profiles[item["profile_id"]]
            for key in FEATURES:
                if not np.isclose(row[key], item["independent_features"][key], rtol=1e-10, atol=1e-10):
                    raise ValueError(f"Numerical evidence mismatch: {row['profile_id']} {key}")
        checks["numerical_evidence"] = {"sha256": digest(validation_path), "matched_profiles": len(verified)}
    else:
        checks["numerical_evidence"] = {"status": "not_supplied"}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = manifest["profiles"]
        if {p["profile_id"] for p in items} != set(profiles) or len(items) != len(profiles):
            raise ValueError("Processing manifest does not cover the profile catalog exactly")
        for item in items:
            raster = (data_dir / item["analysis_raster"]).resolve()
            if not raster.is_relative_to(data_dir.resolve()):
                raise ValueError("Manifest raster must stay inside the processed data directory")
            if digest(raster) != item["analysis_raster_sha256"]:
                raise ValueError(f"Processed raster checksum mismatch: {item['profile_id']}")
        checks["processed_rasters"] = {"manifest_sha256": digest(manifest_path), "matched_checksums": len(items)}
    else:
        checks["processed_rasters"] = {"status": "not_supplied"}
    return checks


def prepare(data_dir="data/processed", output_dir=None, metric="euclidean", top_k=5):
    data_dir = Path(data_dir)
    shared_output = data_dir / "analog_results.json" if output_dir is None else Path(output_dir) / "analog_results.json"
    output_dir = Path(output_dir) if output_dir else data_dir / "ml"
    paths = {name: data_dir / name for name in (
        "earth_profiles.parquet", "planetary_profiles.parquet")}
    earth_frame = pd.read_parquet(paths["earth_profiles.parquet"])
    target_frame = pd.read_parquet(paths["planetary_profiles.parquet"])
    evidence_checks = verify_evidence(data_dir, [earth_frame, target_frame])
    earth, excluded_earth = validate_profiles(earth_frame)
    targets, excluded_targets = validate_profiles(target_frame, planetary=True)
    if not targets:
        raise ValueError("No valid planetary targets")
    # Sort IDs for stable tie ordering independent of Parquet row order.
    earth.sort(key=lambda row: row["profile_id"])
    patches = [record(row) for row in earth]
    matcher = AnalogMatcher(FEATURES, metric).fit(patches)
    provenance = {name: digest(path) for name, path in paths.items()}
    audit = {"input_sha256": provenance, "contract": CONTRACT,
             "evidence_checks": evidence_checks,
             "features": list(FEATURES), "selected_metric": metric,
             "selection_reason": "Euclidean preserves standardized magnitudes; cosine retained as README baseline. No supervised quality comparison is available.",
             "scientific_suitability_validated": False,
             "earth_input_count": len(earth_frame), "earth_eligible_count": len(earth),
             "excluded_earth": excluded_earth, "excluded_targets": excluded_targets,
             "packages": {"python": platform.python_version(), "numpy": np.__version__,
                          "pandas": pd.__version__, "scikit-learn": sklearn.__version__},
             "feature_correlation": pd.DataFrame([p["features"] for p in patches]).corr().to_dict(),
             "limitations": ["No independent relevance labels; no accuracy, precision@k or recall@k claim.",
                             "Slope and roughness are highly correlated; equal feature weighting is provisional.",
                             "60 km regional morphology does not resolve landing hazards or pit interiors.",
                             "Thermal, geology, resources and atmosphere are not scored."],
             "targets": []}
    default_result = None
    for row in targets:
        target = record(row)
        caveats = (f"{row['body']} gravity and atmosphere differ from Earth. Regional terrain comparison only; "
                   "scientific analog suitability unvalidated. " + str(row["data_warning"]))
        result = matcher.rank(target, top_k=top_k, caveats=caveats)
        result["model_metadata"] = {"metric": metric, "features": list(FEATURES),
                                    "input_sha256": provenance, "target_profile_id": row["profile_id"],
                                    "target_source_ids": list(row["source_ids"]),
                                    "scientific_suitability_validated": False}
        by_id = {patch["profile_id"]: patch for patch in earth}
        for analog in result["top_analogs"]:
            original = by_id[analog["profile_id"]]
            analog["source_ids"] = list(original["source_ids"])
            analog["caveats"] += " " + str(original["data_warning"])
            # Preserve the README's metric names while retaining exact feature definitions in metadata.
            metrics = analog["metrics"]
            analog["metrics"] = dict(zip(
                ("slope_match", "relief_match", "roughness_match", "steep_fraction_match"),
                (metrics[f"{key}_match"] for key in FEATURES)))
        comparison = {}
        for comparison_metric in ("cosine", "euclidean"):
            other = AnalogMatcher(FEATURES, comparison_metric).fit(patches)
            try:
                ranked = other.rank(target, top_k=len(patches), caveats=caveats)
                comparison[comparison_metric] = [
                    {"profile_id": a["profile_id"], "score": a["similarity_score"]}
                    for a in ranked["top_analogs"]]
            except ValueError as exc:
                comparison[comparison_metric] = {"error": str(exc)}
        values = np.array([target["features"][key] for key in FEATURES])
        training = np.array([[patch["features"][key] for key in FEATURES] for patch in patches])
        outside = [key for i, key in enumerate(FEATURES)
                   if values[i] < training[:, i].min() or values[i] > training[:, i].max()]
        result["model_metadata"]["features_outside_earth_range"] = outside
        if outside:
            for analog in result["top_analogs"]:
                analog["caveats"] += " Target exceeds Earth catalog range: " + ", ".join(outside) + "."
        save_results(result, output_dir / f"{row['profile_id']}_results.json")
        audit["targets"].append({"profile_id": row["profile_id"],
                                  "features_outside_earth_range": outside,
                                  "comparison": comparison})
        if row["profile_id"] == "mars_jezero_60km_v1":
            default_result = result
    artifact = output_dir / "analog_model.json"
    matcher.save(artifact)
    reloaded = AnalogMatcher.load(artifact)
    sample = record(targets[0])
    if matcher.rank(sample, caveats="reload check") != reloaded.rank(sample, caveats="reload check"):
        raise ValueError("Saved model does not reproduce rankings")
    audit["artifact_sha256"] = digest(artifact)
    audit["model_code_sha256"] = digest(Path(__file__).with_name("model.py"))
    audit["preparation_code_sha256"] = digest(__file__)
    audit["artifact_reload_verified"] = True
    save_results(audit, output_dir / "validation_report.json")
    if default_result is not None:
        save_results(default_result, shared_output)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/processed")
    parser.add_argument("--output-dir")
    parser.add_argument("--metric", choices=("cosine", "euclidean"), default="euclidean")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    report = prepare(args.data_dir, args.output_dir, args.metric, args.top_k)
    print(f"Prepared {report['earth_eligible_count']} Earth profiles for {len(report['targets'])} targets; "
          f"excluded {len(report['excluded_earth'])} Earth profiles. Reload verified.")


if __name__ == "__main__":
    main()
