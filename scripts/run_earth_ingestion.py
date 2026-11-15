"""
TerraMirror controlled Earth ingestion.

Select representative tiles, scan missing terrain,
and resume quality/land-cover/ML processing.

Sequential execution only. No neural index publication.
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scan_global_batch import select_global_tiles

CATALOG = ROOT / "data/metadata/earth_tile_catalog.csv"
BASE = ROOT / "data/processed/global"
ARCHIVES = ROOT / "data/processed/ml_patches/earth"


def stage_paths(tile_id):
    return {
        "scan": BASE / "v3" / f"{tile_id}.csv",
        "quality": BASE / "v3_quality" / f"{tile_id}.csv",
        "landcover": BASE / "v3_landcover" / f"{tile_id}.csv",
        "complete": BASE / "v3_complete" / f"{tile_id}.csv",
        "archive": ARCHIVES / f"{tile_id}.npz",
    }


def execute(command):
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiles", type=int, default=1)

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")

    args = parser.parse_args()

    if args.tiles < 1:
        parser.error("--tiles must be positive")

    with CATALOG.open(newline="") as file:
        catalog = list(csv.DictReader(file))

    selected = select_global_tiles(catalog)

    candidates = []

    for tile in selected:
        latitude = (
            float(tile["south"]) + float(tile["north"])
        ) / 2

        if abs(latitude) >= 60:
            continue

        tile_id = tile["tile_id"]
        paths = stage_paths(tile_id)

        if paths["scan"].exists():
            with paths["scan"].open(newline="") as f:
                scanned = list(csv.DictReader(f))

            # A successful scan can legitimately have no
            # qualifying land patches.
            if not scanned:
                print(
                    f"SKIP EMPTY: {tile_id} "
                    "(zero qualifying terrain patches)"
                )
                continue

            # WorldCover is optional when final metadata
            # explicitly records unavailable classifications.
            required = (
                paths["quality"],
                paths["complete"],
                paths["archive"],
            )

            if all(p.exists() for p in required):
                continue

            priority = 0
        else:
            priority = 1

        candidates.append((priority, tile_id, paths))

    candidates.sort(key=lambda item: item[0])
    batch = candidates[:args.tiles]

    print("=== TERRAMIRROR EARTH INGESTION ===")
    print("Mode:", "EXECUTE" if args.execute else "DRY RUN")
    print("Catalog tiles:", len(catalog))
    print("Selected tiles:", len(batch))

    failures = []

    for index, (_, tile_id, paths) in enumerate(batch, 1):
        print(f"\n[{index}/{len(batch)}] {tile_id}", flush=True)

        needs_scan = not paths["scan"].exists()

        if args.dry_run:
            print("Scan:", "RUN" if needs_scan else "SKIP")
            for stage, path in paths.items():
                if stage != "scan":
                    print(
                        stage + ":",
                        "SKIP" if path.exists() else "RUN"
                    )
            continue

        try:
            if needs_scan:
                # Scanner's representative ordering can change
                # after a tile is processed. Resolve the current
                # tile's offset from its stable selection list.
                offset = next(
                    i for i, item in enumerate(selected)
                    if item["tile_id"] == tile_id
                )

                execute([
                    sys.executable,
                    "-u",
                    "scripts/scan_global_batch.py",
                    "--offset",
                    str(offset),
                    "--limit",
                    "1",
                ])

            if not paths["scan"].exists():
                raise RuntimeError(
                    "Scan did not produce a CSV output"
                )

            # An empty, header-only CSV is a valid scan
            # result, not a failed processing stage.
            with paths["scan"].open(newline="") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames or "patch_id" not in reader.fieldnames:
                    raise ValueError("Invalid scan CSV header")

                scanned_rows = list(reader)

            if not scanned_rows:
                print(
                    "EMPTY: No qualifying terrain patches. "
                    "Skipping downstream processing.",
                    flush=True,
                )
                continue

            execute([
                sys.executable,
                "-u",
                "scripts/complete_earth_tile.py",
                "--tile",
                tile_id,
                "--execute",
            ])

            print("PASS: Tile processing complete", flush=True)

        except Exception as exc:
            failures.append((tile_id, str(exc)))
            print(f"FAILED: {exc}", flush=True)

    print("\n=== INGESTION SUMMARY ===")
    print("Tiles attempted:", len(batch))
    print("Failures:", len(failures))

    for tile_id, reason in failures:
        print("FAILED:", tile_id, reason)

    print("Neural and hybrid discovery outputs unchanged.")

    if failures:
        raise SystemExit(1)

    print("RESULT: PASS")


if __name__ == "__main__":
    main()
