"""
TerraMirror Earth discovery pipeline.

Phase 1: controlled geographic scanning.
Existing indexes and discovery outputs remain unchanged.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scan_global_batch import select_global_tiles
from scan_earth_v3 import CATALOG, OUTPUT, FIELDS, process_tile


def validate_records(tile_id, records):
    seen = set()

    for row in records:
        patch_id = row["patch_id"]

        if row["tile_id"] != tile_id:
            raise ValueError("Unexpected tile ID")

        if patch_id in seen:
            raise ValueError("Duplicate patch ID")

        seen.add(patch_id)

    return len(seen)


def save_atomic(tile_id, records):
    OUTPUT.mkdir(parents=True, exist_ok=True)

    destination = OUTPUT / f"{tile_id}.csv"
    temporary = OUTPUT / f"{tile_id}.tmp"

    if destination.exists():
        raise FileExistsError(destination)

    try:
        with temporary.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=FIELDS,
            )
            writer.writeheader()
            writer.writerows(records)
            f.flush()
            os.fsync(f.fileno())

        if destination.exists():
            raise FileExistsError(destination)

        os.replace(temporary, destination)

    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--new-tiles", type=int, default=1
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )
    mode.add_argument(
        "--dry-run", action="store_true"
    )
    mode.add_argument(
        "--execute-scans", action="store_true"
    )

    parser.add_argument(
        "--include-polar", action="store_true"
    )

    args = parser.parse_args()

    if args.new_tiles < 1:
        parser.error("--new-tiles must be positive")

    with CATALOG.open(newline="") as f:
        catalog = list(csv.DictReader(f))

    representatives = select_global_tiles(catalog)

    eligible = []

    for tile in representatives:
        latitude = (
            float(tile["south"]) + float(tile["north"])
        ) / 2

        if not args.include_polar and abs(latitude) >= 60:
            continue

        destination = (
            OUTPUT / f"{tile['tile_id']}.csv"
        )

        if not destination.exists():
            eligible.append(tile)

    batch = eligible[:args.new_tiles]

    print("=== TERRAMIRROR GLOBAL DISCOVERY ===")
    print(
        "Mode:",
        "EXECUTE SCANS"
        if args.execute_scans else "DRY RUN"
    )
    print("Catalog tiles:", len(catalog))
    print("Representatives:", len(representatives))
    print("Eligible unprocessed:", len(eligible))
    print("Selected batch:", len(batch))

    failures = []
    completed = 0
    total_patches = 0

    for index, tile in enumerate(batch, 1):
        tile_id = tile["tile_id"]

        print(
            f"\\n[{index}/{len(batch)}] {tile_id}",
            flush=True,
        )

        if args.dry_run:
            print("  Planned scan only")
            continue

        try:
            records = process_tile(tile)

            count = validate_records(
                tile_id, records
            )

            if count == 0:
                print(
                    "  EMPTY: no qualifying terrain patches; "
                    "not saved",
                    flush=True,
                )
                continue

            save_atomic(tile_id, records)

            completed += 1
            total_patches += count

            print(
                f"  SAVED: {count} patches",
                flush=True,
            )

        except Exception as exc:
            failures.append(tile_id)
            print(
                f"  FAILED: {type(exc).__name__}: "
                f"{exc}",
                flush=True,
            )

    print("\\n=== SUMMARY ===")
    print("Successful new tiles:", completed)
    print("New terrain patches:", total_patches)
    print("Failures:", len(failures))

    for tile_id in failures:
        print("FAILED:", tile_id)

    print(
        "Existing neural and hybrid indexes "
        "remain unchanged."
    )

    if failures:
        raise SystemExit(1)

    print("RESULT: PASS")


if __name__ == "__main__":
    main()
