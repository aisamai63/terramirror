"""Feature-based Earth analog retrieval; no labeled training set required."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler


class AnalogMatcher:
    """Fit on Earth reference patches, then rank them against a target.

    Records contain a ``features`` mapping. Earth records also require
    location_name, latitude and longitude. All feature units and patch scales
    must agree between Earth and planetary inputs.
    """

    def __init__(self, feature_names=("slope", "roughness"), metric="cosine"):
        self.feature_names = tuple(feature_names)
        if (not self.feature_names
                or any(not isinstance(name, str) or not name for name in self.feature_names)
                or len(set(self.feature_names)) != len(self.feature_names)):
            raise ValueError("feature_names must contain unique, nonempty strings")
        if metric not in ("cosine", "euclidean"):
            raise ValueError("metric must be cosine or euclidean")
        self.metric = metric
        self.scaler = None

    def _matrix(self, records):
        try:
            values = np.asarray([
                [record["features"][name] for name in self.feature_names]
                for record in records
            ], dtype=float)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Every record must supply every selected numeric feature") from exc
        if not np.isfinite(values).all():
            raise ValueError("Features must be finite; remove nodata/NaN/inf upstream")
        return values

    def fit(self, earth_patches):
        """Learn scaling only from the Earth reference catalog, never the query."""
        patches = deepcopy(list(earth_patches))
        if len(patches) < 2:
            raise ValueError("Provide at least two Earth reference patches")
        values = self._matrix(patches)
        for patch in patches:
            if not isinstance(patch.get("location_name"), str) or not patch["location_name"].strip():
                raise ValueError("Each Earth patch needs a location_name")
            for key, bound in (("latitude", 90), ("longitude", 180)):
                try:
                    coordinate = float(patch[key])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"Each Earth patch needs a valid {key}") from exc
                if not np.isfinite(coordinate) or abs(coordinate) > bound:
                    raise ValueError(f"Invalid {key}")
                patch[key] = coordinate
        scaler = StandardScaler().fit(values)
        if np.any(scaler.var_ == 0):
            raise ValueError("Selected features must vary across Earth reference patches")
        self.scaler = scaler
        self.earth_patches = patches
        self.reference = scaler.transform(values)
        return self

    def save(self, path):
        """Persist a portable JSON reference catalog and fitted scaling statistics."""
        if self.scaler is None:
            raise ValueError("Call fit before save")
        return save_results({
            "format_version": 1, "metric": self.metric,
            "feature_names": list(self.feature_names),
            "earth_patches": self.earth_patches,
            "scaler_mean": self.scaler.mean_.tolist(),
            "scaler_scale": self.scaler.scale_.tolist(),
        }, path)

    @classmethod
    def load(cls, path):
        """Rebuild from JSON and verify the stored scaling statistics."""
        artifact = json.loads(Path(path).read_text(encoding="utf-8"))
        if artifact.get("format_version") != 1:
            raise ValueError("Unsupported model artifact version")
        matcher = cls(artifact["feature_names"], artifact["metric"]).fit(artifact["earth_patches"])
        if not (np.allclose(matcher.scaler.mean_, artifact["scaler_mean"], rtol=1e-12, atol=1e-12)
                and np.allclose(matcher.scaler.scale_, artifact["scaler_scale"], rtol=1e-12, atol=1e-12)):
            raise ValueError("Model catalog and stored scaling statistics disagree")
        return matcher

    def rank(self, target, top_k=5, *, caveats):
        """Return the README output contract; scores are similarities, not probabilities.

        Cosine scores retain their native [-1, 1] range. Euclidean scores use
        1 / (1 + distance). Feature matches use 1 / (1 + absolute z difference).
        """
        if self.scaler is None:
            raise ValueError("Call fit before rank")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer")
        if not isinstance(target.get("target_site"), str) or not target["target_site"].strip():
            raise ValueError("Target needs a target_site name")
        if not isinstance(caveats, str) or not caveats.strip():
            raise ValueError("Supply target-specific physical caveats")
        query = self.scaler.transform(self._matrix([target]))
        differences = np.abs(self.reference - query[0])
        if self.metric == "cosine":
            # A mean-centered vector can be zero: its angle is undefined.
            if (np.linalg.norm(query[0]) < 1e-12
                    or np.any(np.linalg.norm(self.reference, axis=1) < 1e-12)):
                raise ValueError("Zero standardized vector: use metric='euclidean'")
            scores = np.clip(cosine_similarity(query, self.reference)[0], -1, 1)
        else:
            scores = 1 / (1 + np.linalg.norm(differences, axis=1))
        order = np.argsort(-scores, kind="stable")[:top_k]
        analogs = []
        for rank, index in enumerate(order, start=1):
            patch = self.earth_patches[index]
            analogs.append({
                "rank": rank,
                "location_name": patch["location_name"],
                **({"profile_id": patch["profile_id"]} if "profile_id" in patch else {}),
                "latitude": patch["latitude"],
                "longitude": patch["longitude"],
                "similarity_score": float(scores[index]),
                "metrics": {
                    f"{name}_match": float(1 / (1 + differences[index, column]))
                    for column, name in enumerate(self.feature_names)
                },
                "caveats": caveats,
            })
        return {"target_site": target["target_site"],
                "timestamp": date.today().isoformat(), "top_analogs": analogs}


def save_results(results, path="data/processed/analog_results.json"):
    """Write API/frontend results as strict JSON."""
    content = json.dumps(results, indent=2, allow_nan=False)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content + "\n", encoding="utf-8")
    return destination
