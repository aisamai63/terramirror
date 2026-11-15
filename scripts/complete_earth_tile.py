"""
TerraMirror resumable Earth tile processing.

Processes an already-scanned tile through:
quality -> landcover -> finalization -> ML archive.

Existing files are validated, never silently overwritten.
No neural outputs or dashboard results are modified.
"""

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def csv_ids(path):
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "patch_id" not in reader.fieldnames:
            raise ValueError(f"Invalid CSV header: {path}")
        rows = list(reader)

    ids = [r["patch_id"] for r in rows]

    if not ids or len(ids) != len(set(ids)):
        raise ValueError(f"Empty or duplicate patch IDs: {path}")

    return set(ids)


def check_archive(path, expected):
    with np.load(path, allow_pickle=False) as data:
        elevation = data["elevation"]
        mask = data["valid_mask"]
        ids = data["patch_ids"].tolist()

        if elevation.shape != mask.shape:
            raise ValueError("Elevation/mask shape mismatch")

        if elevation.shape != (len(expected), 64, 64):
            raise ValueError("Unexpected elevation shape")

        if len(ids) != len(set(ids)) or set(ids) != expected:
            raise ValueError("Archive patch IDs mismatch")

        if not np.isfinite(elevation).all():
            raise ValueError("Nonfinite elevation values")

        if not np.all(mask.mean(axis=(1, 2)) >= 0.95):
            raise ValueError("Insufficient valid coverage")


def run_stage(name, command, output, expected, env):
    if output.exists():
        if output.suffix == ".npz":
            check_archive(output, expected)
        elif csv_ids(output) != expected:
            raise ValueError(f"{name}: existing IDs mismatch")

        print(f"SKIP (validated): {name}", flush=True)
        return

    print(f"RUN: {name}", flush=True)

    try:
        subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            check=True,
        )

        if output.suffix == ".npz":
            check_archive(output, expected)
        elif csv_ids(output) != expected:
            raise ValueError(f"{name}: output IDs mismatch")

    except BaseException:
        # Only remove a new output from this failed stage.
        # Pre-existing validated outputs are never touched.
        output.unlink(missing_ok=True)
        raise

    print(f"PASS: {name}", flush=True)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--tile", required=True)

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")

    args = parser.parse_args()

    tile = args.tile

    # Accept only a canonical Copernicus tile identifier.
    import re
    if not re.fullmatch(
        r"Copernicus_DSM_COG_10_[NS]\d{2}_00_[EW]\d{3}_00_DEM",
        tile,
    ):
        parser.error("Invalid Copernicus tile ID")

    base = ROOT / "data/processed/global"

    scan = base / "v3" / f"{tile}.csv"
    quality = base / "v3_quality" / f"{tile}.csv"
    landcover = base / "v3_landcover" / f"{tile}.csv"
    complete = base / "v3_complete" / f"{tile}.csv"
    archive = (
        ROOT / "data/processed/ml_patches/earth"
        / f"{tile}.npz"
    )

    expected = csv_ids(scan)

    env = os.environ.copy()
    env["TERRAMIRROR_TILE"] = tile

    stages = [
        (
            "Elevation quality",
            [sys.executable, "-u", "scripts/audit_earth_quality.py"],
            quality,
        ),
        (
            "WorldCover",
            [sys.executable, "-u", "scripts/add_worldcover.py"],
            landcover,
        ),
        (
            "Finalized metadata",
            [sys.executable, "-u", "scripts/finalize_worldcover.py"],
            complete,
        ),
        (
            "ML archive",
            [
                sys.executable,
                "-u",
                "scripts/build_ml_patches.py",
                "--earth-tile",
                tile,
            ],
            archive,
        ),
    ]

    print("=== TERRAMIRROR TILE PROCESSOR ===")
    print("Tile:", tile)
    print("Scanned patches:", len(expected))
    print("Mode:", "EXECUTE" if args.execute else "DRY RUN")

    for name, command, output in stages:
        if args.dry_run:
            if output.exists():
                if output.suffix == ".npz":
                    check_archive(output, expected)
                elif csv_ids(output) != expected:
                    raise ValueError(f"{name}: IDs mismatch")
                print(f"SKIP (validated): {name}")
            else:
                print(f"WOULD RUN: {name}")
        else:
            run_stage(name, command, output, expected, env)

    print("\nNeural and hybrid outputs unchanged.")
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
