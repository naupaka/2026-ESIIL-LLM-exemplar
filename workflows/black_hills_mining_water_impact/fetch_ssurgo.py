#!/usr/bin/env python3
"""Fetch SSURGO soil polygons + dominant-component attributes for the workflow bbox.

Two-step process:
  1. WFS GetFeature on NRCS SDM for mapunitpoly within the bbox → GeoJSON
     with `mukey` per polygon (via the harmonizer's download_wfs_features).
  2. POST SQL to NRCS SDA tabular endpoint to fetch attributes from each
     map unit's dominant component (highest comppct_r), and merge those
     attributes back into each GeoJSON feature's properties.

Output: output/ssurgo_with_attributes.geojson — used by the harmonizer
via a file:// DatasetSpec URL, same pattern as the EXNI parse output.

Attributes joined per feature (mukey):
  - muname, mukind, musym          (from mapunit)
  - compname, comppct_r            (from component, dominant)
  - taxorder, taxsuborder          (taxonomic class)
  - hydgrp                         (hydrologic soil group A/B/C/D)
  - drainagecl                     (drainage class)
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

# Walk up to repo root and import the harmonizer's WFS helper.
_repo_root = next(p for p in Path(__file__).resolve().parents
                  if (p / "src" / "geospatial_harmonizer.py").exists())
sys.path.insert(0, str(_repo_root))

from src.geospatial_harmonizer import download_wfs_features  # noqa: E402


# Bbox is duplicated from black_hills_harmonization.py rather than imported
# so this script can run independently and doesn't trigger the harmonizer's
# heavy imports.
BLACK_HILLS_EXTENT = (-104.6, 43.4, -103.3, 44.6)

WORKFLOW_DIR = Path(__file__).parent
OUTPUT_DIR = WORKFLOW_DIR / "output"
INTERMEDIATE_GEOJSON = OUTPUT_DIR / "ssurgo_mapunitpoly.geojson"
FINAL_GEOJSON = OUTPUT_DIR / "ssurgo_with_attributes.geojson"

WFS_URL = "https://sdmdataaccess.nrcs.usda.gov/Spatial/SDMWGS84Geographic.wfs"
SDA_URL = "https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest"

# NRCS WFS caps each GetFeature bbox to ~10.1 billion sq meters. Tiling the
# extent into an N×N grid keeps every request under the limit. For the
# Black Hills bbox (~13.9 billion sq m total), 2×2 is plenty (~3.5 billion
# per cell). Bumped to 3×3 for headroom + smaller per-tile payloads.
WFS_TILE_GRID = 3


def sda_query(sql: str) -> list[list]:
    """POST a SQL query to NRCS SDA, return the rows (without the column-name header).

    Response shape is {"Table": [[col1, col2, ...], [row1...], [row2...]]}.
    Returns the rows; the caller supplies column names via the SELECT list.
    """
    req = urllib.request.Request(
        SDA_URL,
        data=json.dumps({"format": "JSON+COLUMNNAME", "query": sql}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.load(resp)
    table = payload.get("Table") or []
    # First row is column names; subsequent rows are data.
    return table[1:] if len(table) > 1 else []


def fetch_dominant_component_attributes(mukeys: list[str]) -> dict[str, dict]:
    """Return {mukey: {muname, hydgrp, drainagecl, ...}} for each mukey.

    Joins mapunit + dominant component (highest comppct_r). Sends mukeys in
    a single IN clause — the SDA endpoint handles ~10k-key queries fine for
    the Black Hills bbox.
    """
    if not mukeys:
        return {}
    keys_csv = ",".join(f"'{k}'" for k in mukeys)
    # ROW_NUMBER picks the dominant component per mukey by comppct_r descending.
    sql = f"""
        WITH ranked AS (
            SELECT
                c.mukey,
                c.compname,
                c.comppct_r,
                c.taxorder,
                c.taxsuborder,
                c.hydgrp,
                c.drainagecl,
                ROW_NUMBER() OVER (
                    PARTITION BY c.mukey
                    ORDER BY c.comppct_r DESC, c.cokey
                ) AS rn
            FROM component c
            WHERE c.mukey IN ({keys_csv})
              AND c.majcompflag = 'Yes'
        )
        SELECT
            m.mukey, m.muname, m.mukind, m.musym,
            r.compname, r.comppct_r,
            r.taxorder, r.taxsuborder,
            r.hydgrp, r.drainagecl
        FROM mapunit m
        LEFT JOIN ranked r ON m.mukey = r.mukey AND r.rn = 1
        WHERE m.mukey IN ({keys_csv})
    """
    cols = [
        "mukey", "muname", "mukind", "musym",
        "compname", "comppct_r",
        "taxorder", "taxsuborder",
        "hydgrp", "drainagecl",
    ]
    rows = sda_query(sql)
    return {row[0]: dict(zip(cols, row)) for row in rows}


def fetch_tiled_mapunitpoly(bbox: tuple[float, float, float, float], n: int) -> list[dict]:
    """Fetch SSURGO mapunitpoly tiles to stay under NRCS's per-request bbox cap.

    Dedupes features by `properties.mupolygonkey` (unique per polygon) so
    polygons straddling tile boundaries are only counted once.
    """
    xmin, ymin, xmax, ymax = bbox
    dx, dy = (xmax - xmin) / n, (ymax - ymin) / n
    seen: dict[str, dict] = {}
    for iy in range(n):
        for ix in range(n):
            cell = (
                xmin + ix * dx,
                ymin + iy * dy,
                xmin + (ix + 1) * dx,
                ymin + (iy + 1) * dy,
            )
            tile_path = OUTPUT_DIR / f"_ssurgo_tile_{iy}_{ix}.geojson"
            tile_path.unlink(missing_ok=True)
            print(f"  tile ({iy+1}/{n},{ix+1}/{n})  bbox={cell}")
            download_wfs_features(
                wfs_url=WFS_URL,
                layer="mapunitpoly",
                bbox=cell,
                output_dir=OUTPUT_DIR,
                output_filename=tile_path.name,
                verbose=False,
            )
            with open(tile_path) as f:
                tile_fc = json.load(f)
            tile_path.unlink(missing_ok=True)
            (OUTPUT_DIR / (tile_path.stem + ".gml")).unlink(missing_ok=True)
            for feat in tile_fc.get("features", []):
                key = str(feat.get("properties", {}).get("mupolygonkey"))
                if key and key not in seen:
                    seen[key] = feat
            print(f"    cumulative unique features: {len(seen)}")
    return list(seen.values())


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] WFS GetFeature for mapunitpoly in {BLACK_HILLS_EXTENT} "
          f"({WFS_TILE_GRID}x{WFS_TILE_GRID} tiles)")
    features = fetch_tiled_mapunitpoly(BLACK_HILLS_EXTENT, WFS_TILE_GRID)
    fc = {"type": "FeatureCollection", "features": features}

    print(f"[2/3] Extracting mukeys from {len(features)} polygons")
    # The WFS layer's mukey attribute lives at properties.mukey (lower-case).
    mukeys = sorted({
        str(feat["properties"].get("mukey"))
        for feat in features
        if feat.get("properties", {}).get("mukey") is not None
    })
    print(f"  {len(features)} polygons, {len(mukeys)} distinct mukeys")

    print(f"[3/3] SDA query for dominant-component attributes")
    attrs = fetch_dominant_component_attributes(mukeys)
    print(f"  Got attributes for {len(attrs)} mukeys")

    merged = 0
    for feat in features:
        props = feat.setdefault("properties", {})
        mk = str(props.get("mukey")) if props.get("mukey") is not None else None
        if mk and mk in attrs:
            for k, v in attrs[mk].items():
                if k != "mukey":  # don't overwrite the geometric mukey
                    props[k] = v
            merged += 1
    print(f"  Merged attributes into {merged} features")

    with open(FINAL_GEOJSON, "w") as f:
        json.dump(fc, f)
    print(f"Wrote {FINAL_GEOJSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
