import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.model import AnalogMatcher
from src.prepare_model import CONTRACT, FEATURES, prepare, validate_profiles


DATA = Path(__file__).resolve().parents[1] / "data" / "processed"


class ProfileContractTests(unittest.TestCase):
    def profile(self):
        return {**CONTRACT, **dict(zip(FEATURES, [2, 500, 30, 0.1])),
                "profile_id": "earth_test", "body": "Earth", "qa_pass": True,
                "synthetic": False, "valid_cell_fraction": 1.0,
                "region_name": "test", "source_ids": ["test"], "data_warning": "test",
                "site_name": "test", "centroid_lat": 20, "centroid_lon": 10}

    def test_exclusions(self):
        for field, value in (("qa_pass", False), ("synthetic", True),
                             ("valid_cell_fraction", 0.89), ("common_grid_m", 30),
                             ("slope_median_deg", float("nan")), ("centroid_lat", 95)):
            with self.subTest(field=field):
                row = self.profile()
                row[field] = value
                accepted, rejected = validate_profiles(pd.DataFrame([row]))
                self.assertEqual(accepted, [])
                self.assertEqual(len(rejected), 1)

    def test_duplicate_ids_and_missing_columns_rejected(self):
        row = self.profile()
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_profiles(pd.DataFrame([row, row]))
        del row["synthetic"]
        with self.assertRaisesRegex(ValueError, "Missing profile columns"):
            validate_profiles(pd.DataFrame([row]))


@unittest.skipUnless((DATA / "earth_profiles.parquet").exists(), "Project data not present")
class RealDataTests(unittest.TestCase):
    def test_end_to_end_and_independent_distances(self):
        with tempfile.TemporaryDirectory() as directory:
            report = prepare(DATA, directory)
            artifact = Path(directory) / "analog_model.json"
            matcher = AnalogMatcher.load(artifact)
            self.assertEqual(report["earth_eligible_count"], 15)
            self.assertEqual(report["excluded_earth"][0]["profile_id"], "earth_arctic_26_29_60km_v1")
            self.assertEqual(len(report["targets"]), 3)
            self.assertFalse(report["scientific_suitability_validated"])
            self.assertTrue(report["artifact_reload_verified"])
            training = np.array([[p["features"][key] for key in FEATURES] for p in matcher.earth_patches])
            means, scales = training.mean(axis=0), training.std(axis=0)
            for _, target in pd.read_parquet(DATA / "planetary_profiles.parquet").iterrows():
                result = json.loads((Path(directory) / f"{target.profile_id}_results.json").read_text())
                query = np.array([target[key] for key in FEATURES])
                distance = np.sqrt(np.sum(((training - query) / scales) ** 2, axis=1))
                expected_order = np.argsort(distance, kind="stable")[:5]
                self.assertEqual([a["profile_id"] for a in result["top_analogs"]],
                                 [matcher.earth_patches[i]["profile_id"] for i in expected_order])
                np.testing.assert_allclose([a["similarity_score"] for a in result["top_analogs"]],
                                           1 / (1 + distance[expected_order]))
                self.assertIn("roughness_match", result["top_analogs"][0]["metrics"])
                self.assertNotIn("thermal_match", result["top_analogs"][0]["metrics"])
            np.testing.assert_allclose(matcher.scaler.mean_, means)
            default = json.loads((Path(directory) / "analog_results.json").read_text())
            self.assertEqual(default["model_metadata"]["target_profile_id"], "mars_jezero_60km_v1")
            polar = next(t for t in report["targets"] if "shackleton" in t["profile_id"])
            self.assertEqual(set(polar["features_outside_earth_range"]), set(FEATURES))
            content = json.loads(artifact.read_text())
            content["scaler_mean"][0] += 1
            artifact.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "disagree"):
                AnalogMatcher.load(artifact)


if __name__ == "__main__":
    unittest.main()
