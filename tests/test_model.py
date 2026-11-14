import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.model import AnalogMatcher, save_results


def catalog():
    return [
        {"location_name": str(i), "latitude": i, "longitude": i,
         "features": {"slope": slope, "roughness": roughness}}
        for i, (slope, roughness) in enumerate([(1, 2), (3, 7), (8, 9)])
    ]


class ModelTests(unittest.TestCase):
    def test_exact_match_and_output(self):
        matcher = AnalogMatcher().fit(catalog())
        target = {"target_site": "test", "features": catalog()[0]["features"]}
        means = matcher.scaler.mean_.copy()
        result = matcher.rank(target, caveats="Synthetic test only")
        self.assertEqual(result["top_analogs"][0]["location_name"], "0")
        self.assertAlmostEqual(result["top_analogs"][0]["similarity_score"], 1)
        self.assertEqual(result["top_analogs"][0]["metrics"]["slope_match"], 1)
        self.assertNotIn("thermal_match", result["top_analogs"][0]["metrics"])
        np.testing.assert_array_equal(means, matcher.scaler.mean_)
        with tempfile.TemporaryDirectory() as directory:
            path = save_results(result, Path(directory) / "nested/results.json")
            self.assertEqual(json.loads(path.read_text()), result)

    def test_distance_ranks_nearest_patch(self):
        target = {"target_site": "test", "features": {"slope": 7.9, "roughness": 8.9}}
        result = AnalogMatcher(metric="euclidean").fit(catalog()).rank(target, caveats="test")
        self.assertEqual(result["top_analogs"][0]["location_name"], "2")

    def test_mean_query_requires_distance(self):
        matcher = AnalogMatcher().fit(catalog())
        target = {"target_site": "test", "features": dict(zip(
            matcher.feature_names, matcher.scaler.mean_))}
        with self.assertRaisesRegex(ValueError, "Zero standardized"):
            matcher.rank(target, caveats="test")
        result = AnalogMatcher(metric="euclidean").fit(catalog()).rank(target, caveats="test")
        self.assertEqual(len(result["top_analogs"]), 3)

    def test_bad_inputs(self):
        for value in [None, float("nan"), float("inf")]:
            patches = catalog()
            patches[0]["features"]["slope"] = value
            with self.assertRaises(ValueError):
                AnalogMatcher().fit(patches)
        patches = catalog()
        del patches[0]["features"]["slope"]
        with self.assertRaises(ValueError):
            AnalogMatcher().fit(patches)
        patches = catalog()
        patches[0]["latitude"] = 91
        with self.assertRaises(ValueError):
            AnalogMatcher().fit(patches)
        with self.assertRaises(ValueError):
            AnalogMatcher().fit([catalog()[0]] * 2)


if __name__ == "__main__":
    unittest.main()
