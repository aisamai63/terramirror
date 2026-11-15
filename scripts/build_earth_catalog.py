from pathlib import Path
import csv
import re

SOURCE = Path("data/metadata/copernicus_glo30_tiles.txt")
OUTPUT = Path("data/metadata/earth_tile_catalog.csv")

pattern = re.compile(
    r"^Copernicus_DSM_COG_10_"
    r"([NS])(\d{2})_00_"
    r"([EW])(\d{3})_00_DEM$"
)

base_url = (
    "https://copernicus-dem-30m."
    "s3.eu-central-1.amazonaws.com"
)

records = []

for line in SOURCE.read_text().splitlines():
    tile = line.strip()

    if not tile:
        continue

    match = pattern.fullmatch(tile)

    if not match:
        raise ValueError(f"Unexpected tile name: {tile}")

    ns, lat_text, ew, lon_text = match.groups()

    south = int(lat_text) * (1 if ns == "N" else -1)
    west = int(lon_text) * (1 if ew == "E" else -1)

    records.append({
        "tile_id": tile,
        "west": west,
        "south": south,
        "east": west + 1,
        "north": south + 1,
        "resolution": "GLO-30",
        "source": "Copernicus DEM",
        "url": f"{base_url}/{tile}/{tile}.tif",
    })

fields = [
    "tile_id", "west", "south", "east", "north",
    "resolution", "source", "url",
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)

print("Catalog created:", OUTPUT)
print("Total tiles:", len(records))
print("Unique tiles:", len(set(r["tile_id"] for r in records)))

if len(records) != 26450:
    print("Note: Tile count differs from the current inventory.")

print("\nFirst three records:")
for record in records[:3]:
    print(record["tile_id"], record["south"], record["west"])
