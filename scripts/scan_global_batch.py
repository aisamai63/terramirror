import argparse
import csv
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("scripts").resolve()))

from scan_earth_v3 import process_tile, FIELDS, OUTPUT, CATALOG


def select_global_tiles(tiles):
    # Six latitude bands and twelve longitude bands.
    # Select one available tile nearest each cell center.
    cells = {}

    for tile in tiles:
        lat = (float(tile["south"]) + float(tile["north"])) / 2
        lon = (float(tile["west"]) + float(tile["east"])) / 2

        lat_band = min(5, max(0, int((lat + 90) // 30)))
        lon_band = min(11, max(0, int((lon + 180) // 30)))

        target_lat = -75 + 30 * lat_band
        target_lon = -165 + 30 * lon_band

        distance = (
            (lat - target_lat) ** 2
            + (
                (lon - target_lon)
                * np.cos(np.radians(target_lat))
            ) ** 2
        )

        key = (lat_band, lon_band)

        if key not in cells or distance < cells[key][0]:
            cells[key] = (distance, tile)

    selected = [item[1] for _, item in sorted(cells.items())]

    # Reproducible shuffled order so consecutive batches
    # sample multiple parts of the planet.
    rng = np.random.default_rng(20261114)
    rng.shuffle(selected)

    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    if args.limit < 1 or args.offset < 0:
        parser.error("limit must be positive; offset nonnegative")

    with CATALOG.open(newline="") as f:
        tiles = list(csv.DictReader(f))

    selected = select_global_tiles(tiles)
    batch = selected[args.offset:args.offset + args.limit]

    OUTPUT.mkdir(parents=True, exist_ok=True)

    print("Global catalog tiles:", len(tiles))
    print("Geographic candidate cells:", len(selected))
    print("Batch size:", len(batch), flush=True)

    failures = []
    completed = 0
    patches = 0

    for number, tile in enumerate(batch, 1):
        tile_id = tile["tile_id"]
        output = OUTPUT / f"{tile_id}.csv"

        if output.exists():
            print(f"[{number}] Already exists: {tile_id}", flush=True)
            completed += 1
            continue

        print(f"[{number}] Scanning {tile_id}", flush=True)

        try:
            records = process_tile(tile)
            temporary = output.with_suffix(".tmp")

            with temporary.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(records)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temporary, output)

            completed += 1
            patches += len(records)

            print(f"  Saved {len(records)} patches", flush=True)

        except Exception as exc:
            failures.append(tile_id)
            print(
                f"  FAILED: {type(exc).__name__}: {exc}",
                flush=True,
            )

    print("\n=== BATCH SUMMARY ===")
    print("Selected:", len(batch))
    print("Successful or already completed:", completed)
    print("New patches:", patches)
    print("Failures:", len(failures))

    for tile in failures:
        print("FAILED:", tile)


if __name__ == "__main__":
    main()
