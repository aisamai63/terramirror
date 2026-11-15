import csv
import math
import os
from pathlib import Path

TILE_FILTER = os.environ.get("TERRAMIRROR_TILE")

SOURCE = Path("data/processed/global/v3_quality")
ENRICHED = Path("data/processed/global/v3_landcover")
OUTPUT = Path("data/processed/global/v3_complete")

LANDCOVER_FIELDS = [
    "dominant_landcover",
    "bare_fraction",
    "vegetation_fraction",
    "snow_ice_fraction",
    "built_fraction",
    "landcover_coverage",
]

OUTPUT.mkdir(parents=True, exist_ok=True)

total = 0
classified = 0
missing = 0
seen_ids = set()
statuses = {}

source_files = (
    [SOURCE / f"{TILE_FILTER}.csv"]
    if TILE_FILTER
    else sorted(SOURCE.glob("*.csv"))
)

for source_file in source_files:
    if not source_file.is_file():
        raise FileNotFoundError(source_file)

    tile = source_file.stem
    enriched_file = ENRICHED / source_file.name
    output_file = OUTPUT / source_file.name

    with source_file.open(newline="") as f:
        reader = csv.DictReader(f)
        source_fields = reader.fieldnames
        source_rows = list(reader)

    if not source_fields:
        raise ValueError(f"Missing header: {source_file}")

    enriched = {}

    if enriched_file.exists():
        with enriched_file.open(newline="") as f:
            for row in csv.DictReader(f):
                patch_id = row["patch_id"]
                if patch_id in enriched:
                    raise ValueError(
                        f"Duplicate enriched ID: {patch_id}"
                    )
                enriched[patch_id] = row

    source_ids = {r["patch_id"] for r in source_rows}

    if len(source_ids) != len(source_rows):
        raise ValueError(f"Duplicate source IDs: {tile}")

    unexpected = set(enriched) - source_ids
    if unexpected:
        raise ValueError(
            f"Unexpected enriched IDs in {tile}"
        )

    fields = (
        source_fields
        + LANDCOVER_FIELDS
        + ["landcover_status"]
    )

    results = []

    for row in source_rows:
        patch_id = row["patch_id"]

        if patch_id in seen_ids:
            raise ValueError(
                f"Global duplicate ID: {patch_id}"
            )

        seen_ids.add(patch_id)

        if patch_id in enriched:
            extra = enriched[patch_id]

            for field in LANDCOVER_FIELDS:
                row[field] = extra[field]

            coverage = float(row["landcover_coverage"])

            if not math.isfinite(coverage):
                raise ValueError("Invalid land-cover coverage")

            if not 0 <= coverage <= 1:
                raise ValueError("Coverage outside [0, 1]")

            row["landcover_status"] = "available"
            classified += 1
        else:
            row["dominant_landcover"] = "unknown"

            for field in LANDCOVER_FIELDS[1:-1]:
                row[field] = ""

            row["landcover_coverage"] = 0
            row["landcover_status"] = "unavailable"
            missing += 1

        status = row["landcover_status"]
        statuses[status] = statuses.get(status, 0) + 1

        results.append(row)
        total += 1

    temporary = output_file.with_suffix(".tmp")

    with temporary.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temporary, output_file)

print("=== COMPLETE EARTH DATASET ===")
print("Tiles:", len(list(OUTPUT.glob("*.csv"))))
print("Total patches:", total)
print("Classified:", classified)
print("Unavailable classifications:", missing)
print("Unique patch IDs:", len(seen_ids))
print("Statuses:", statuses)
print("Output:", OUTPUT)

# Dataset totals are dynamic as new Earth tiles are processed.
# Validate internal consistency rather than fixed pilot counts.
if total != classified + missing:
    raise ValueError(
        "Classification totals do not equal the patch count"
    )

if total != len(seen_ids):
    raise ValueError("Patch IDs are not globally unique")

if sum(statuses.values()) != total:
    raise ValueError("Land-cover status totals are inconsistent")

print("\nRESULT: PASS")
