"""Contract checks for saved discovery outputs and measured terrain grids."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi import HTTPException

from src import discovery_api as api


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name,sha256", [
    ("outputs/neural/hybrid_matches.json", "2a9d66c40f0a73aaf719fb540a9bbaf1d0ffe9b6a67b56d04059da92feb9bd07"),
    ("outputs/neural_candidate/hybrid_matches.json", "0dca4c1f85a4383b44a6945ef3ffb2d4ef630d5b3e6b6e8195ef5f8e893fbce7"),
    ("outputs/moon_site04_experimental/hybrid_matches.json", "e670d7005918b3521a716b62c8b491ca2c3eca19773e0dd5e56a8387578ce745"),
])
def test_saved_result_integrity(name, sha256):
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha256


def test_expanded_only_coordinates_remain_retrievable():
    baseline = json.loads((ROOT / "outputs/neural/hybrid_matches.json").read_text())
    expanded = json.loads((ROOT / "outputs/neural_candidate/hybrid_matches.json").read_text())
    coordinates = lambda result: {
        (match["latitude"], match["longitude"])
        for row in result["results"] for match in row["matches"]
    }
    expanded_only = coordinates(expanded) - coordinates(baseline)
    assert len(expanded_only) == 74
    returned = set()
    for row in expanded["results"]:
        response = api.get_expanded_mars_matches(row["mars_patch_id"])
        returned.update(
            (match["latitude"], match["longitude"])
            for match in response["matches"]
        )
    assert expanded_only <= returned


def test_discovery_routes_and_candidate_coordinates():
    assert api.health()["status"] == "ok"
    assert api.regional_targets()["count"] == 3
    coverage = api.coverage()
    assert coverage["earth_catalog_tiles"] == 26450
    assert coverage["earth_indexed_patches"] == 3505
    assert coverage["expanded_indexed_patches"] == 3736
    assert coverage["moon_indexed_patches"] == 3762
    mars = api.detailed_mars()
    moon = api.detailed_moon()
    assert mars["count"] == 255
    assert moon["count"] == 2
    for result in (
        api.detailed_mars_matches(mars["patches"][0]["patch_id"]),
        api.get_expanded_mars_matches(mars["patches"][0]["patch_id"]),
        api.detailed_moon_matches(moon["patches"][0]["patch_id"]),
    ):
        assert len(result["matches"]) == 5
        assert all(np.isfinite(value) for value in result["target_features"].values())
        for rank, candidate in enumerate(result["matches"], 1):
            assert candidate["rank"] == rank
            assert -90 <= candidate["latitude"] <= 90
            assert -180 <= candidate["longitude"] <= 180
            assert candidate["earth_patch_id"] in api.terrain_index()["earth"]
            assert candidate["quality_status"]
            assert all(np.isfinite(value) for value in candidate["terrain_features"].values())


def test_geographic_labels_require_matching_local_metadata():
    regional = api.get_regional("mars-jezero")["top_analogs"]
    assert regional[0]["geographic_label"] == (
        "Mojave-area exploratory ROI · United States"
    )
    assert regional[0]["geographic_label_source"] == "earth_acquisition_status.json"
    assert "geographic_label" not in regional[1]
    detailed = api.detailed_mars_matches("jezero_0_0")["matches"][0]
    assert detailed["geographic_label"] == "Copernicus DEM tile 57°N, 105°E"
    assert detailed["geographic_label_source"] == "earth_tile_catalog.csv"
    misplaced = {**detailed, "latitude": -57.5}
    assert api.detailed_geographic_label(misplaced) == {}


def test_terrain_grid_uses_archive_elevations_and_mask():
    patch_id = api.detailed_mars()["patches"][0]["patch_id"]
    full = api.terrain_elevation("mars", patch_id, 64)
    light = api.terrain_elevation("mars", patch_id, 32)
    path, position = api.terrain_index()["mars"][patch_id]
    with np.load(path, allow_pickle=False) as archive:
        original = archive["elevation"][position]
        valid = archive["valid_mask"][position].astype(bool)
    assert full["grid_size"] == [64, 64]
    assert light["grid_size"] == [32, 32]
    assert full["sampling"] == "native_patch_grid"
    assert light["sampling"] == "every_second_cell"
    np.testing.assert_array_equal(full["valid_mask"], valid.astype(int))
    np.testing.assert_allclose(np.array(full["elevation"])[valid], original[valid])
    np.testing.assert_allclose(light["elevation"], np.array(full["elevation"])[::2, ::2])
    assert light["resolution_m"] == 2 * full["resolution_m"]


def test_real_earth_nodata_remains_masked():
    patch_id = "Copernicus_DSM_COG_10_S45_00_W072_00_DEM_0_0"
    full = api.terrain_elevation("earth", patch_id, 64)
    light = api.terrain_elevation("earth", patch_id, 32)
    mask = np.array(full["valid_mask"], dtype=bool)
    elevations = np.array(full["elevation"])
    assert full["valid_fraction"] == pytest.approx(mask.mean())
    assert full["valid_fraction"] < 1
    assert not mask.all()
    assert np.all(elevations[~mask] == 0)
    assert full["minimum_m"] == pytest.approx(elevations[mask].min())
    assert full["maximum_m"] == pytest.approx(elevations[mask].max())
    np.testing.assert_array_equal(light["valid_mask"], mask[::2, ::2].astype(int))


def test_terrain_grid_query_contract():
    parameters = api.app.openapi()["paths"]["/api/terrain/{body}/{patch_id}"]["get"]["parameters"]
    grid = next(item for item in parameters if item["name"] == "grid")
    assert grid["schema"]["type"] == "integer"
    with pytest.raises(HTTPException) as exc:
        api.terrain_elevation("mars", "jezero_0_0", 48)
    assert exc.value.status_code == 422


def test_missing_terrain_is_404():
    with pytest.raises(HTTPException) as exc:
        api.terrain_elevation("moon", "missing-patch", 64)
    assert exc.value.status_code == 404


def test_corrupt_terrain_archive_is_503(monkeypatch, tmp_path):
    bad = tmp_path / "bad.npz"
    bad.write_bytes(b"not an npz archive")
    monkeypatch.setattr(api, "terrain_index", lambda: {
        "mars": {"bad": (bad, 0)}, "earth": {}, "moon": {},
    })
    with pytest.raises(HTTPException) as exc:
        api.terrain_elevation("mars", "bad", 64)
    assert exc.value.status_code == 503


def test_corrupt_archive_during_indexing_is_503(monkeypatch, tmp_path):
    archive = tmp_path / "data/processed/ml_patches/mars_jezero.npz"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"invalid")
    monkeypatch.setattr(api, "ROOT", tmp_path)
    with pytest.raises(HTTPException) as exc:
        api.terrain_index.__wrapped__()
    assert exc.value.status_code == 503
