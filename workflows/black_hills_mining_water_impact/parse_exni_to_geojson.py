#!/usr/bin/env python3
"""
Convert DANR EXNI application legal descriptions (PLSS) to GeoJSON.

All applications are in the Black Hills Principal Meridian.

Black Hills Principal Meridian base point:
  - Baseline (latitude):  43°57'36" N  ≈ 43.9600° N
  - Principal Meridian (longitude): 103°46'48" W ≈ -103.7800° W

References:
  https://www.blm.gov/sites/blm.gov/files/PublicRoom_Cadastral_Survey_BHills.pdf
"""

import math
import json
from pathlib import Path

# ------------------------------------------------------------------
# Black Hills Meridian datum point (approximate center of origin)
# ------------------------------------------------------------------
BHM_LAT = 43.9600    # baseline latitude
BHM_LON = -103.7800  # principal meridian longitude

# Approximate degrees per mile at ~44 N
DEG_LAT_PER_MILE = 1.0 / 69.0        # ~0.01449 deg/mile
DEG_LON_PER_MILE = 1.0 / (69.0 * math.cos(math.radians(44.0)))  # ~0.02003 deg/mile


def section_centroid(township: int, town_dir: str, range_num: int, range_dir: str, section: int):
    """
    Return (lon, lat) centroid of a PLSS section in the Black Hills Meridian.

    Township numbering: T1N = 1 north of baseline, T1S = 1 south of baseline.
    Range numbering:    R1E = 1 east of PM,       R1W = 1 west of PM.
    Sections 1-36 per standard PLSS layout (6×6 grid, snake-numbered from NE).
    """
    # Township offset in miles from baseline (positive = north)
    t_offset = township - 0.5  # centre of the township
    lat_offset = t_offset * 6.0 * DEG_LAT_PER_MILE
    if town_dir.upper() == 'S':
        lat_offset = -lat_offset

    # Range offset in miles from principal meridian (positive = east)
    r_offset = range_num - 0.5
    lon_offset = r_offset * 6.0 * DEG_LON_PER_MILE
    if range_dir.upper() == 'W':
        lon_offset = -lon_offset

    # Township NW corner (top-left)
    twp_lat = BHM_LAT + lat_offset + 3.0 * DEG_LAT_PER_MILE   # north edge
    twp_lon = BHM_LON + lon_offset - 3.0 * DEG_LON_PER_MILE   # west edge

    # Section layout: row/col within 6×6 grid
    # Sections are numbered:
    #   6  5  4  3  2  1   (row 0, N edge)
    #   7  8  9 10 11 12   (row 1)
    #  18 17 16 15 14 13   (row 2)
    #  19 20 21 22 23 24   (row 3)
    #  30 29 28 27 26 25   (row 4)
    #  31 32 33 34 35 36   (row 5, S edge)
    s = section - 1  # 0-indexed
    row = s // 6
    col_index = s % 6
    # Odd rows snake right-to-left, even rows snake left-to-right from NE
    if row % 2 == 0:
        col = 5 - col_index   # row 0: sec 1 is col 5 (E), sec 6 is col 0 (W)
    else:
        col = col_index        # row 1: sec 7 is col 0 (W), sec 12 is col 5 (E)

    sec_lat = twp_lat - (row + 0.5) * DEG_LAT_PER_MILE
    sec_lon = twp_lon + (col + 0.5) * DEG_LON_PER_MILE
    return (sec_lon, sec_lat)


# ------------------------------------------------------------------
# Build section polygon (~1 mile square)
# ------------------------------------------------------------------
def section_polygon(township, town_dir, range_num, range_dir, section):
    """Return a GeoJSON polygon for a ~1 mile PLSS section."""
    cx, cy = section_centroid(township, town_dir, range_num, range_dir, section)
    half_lat = DEG_LAT_PER_MILE * 0.5
    half_lon = DEG_LON_PER_MILE * 0.5
    # SW -> SE -> NE -> NW -> SW
    coords = [
        [cx - half_lon, cy - half_lat],
        [cx + half_lon, cy - half_lat],
        [cx + half_lon, cy + half_lat],
        [cx - half_lon, cy + half_lat],
        [cx - half_lon, cy - half_lat],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


# ------------------------------------------------------------------
# EXNI / Uranium exploration applications parsed from PDFs
# ------------------------------------------------------------------
APPLICATIONS = [
    {
        "name": "Daniel Hoff EXNI",
        "type": "EXNI",
        "applicant": "Daniel Hoff",
        "county": "Pennington",
        "status": "Filed",
        "source_pdf": "HoffEXNI.pdf",
        "note": "Test hole locations confidential per SDCL 45-6C-14",
        # Legal description extracted from DENR notification letter
        # - Hoff application is in Pennington County near Rapid City area
        # Based on the DENR notification letters, this is approx T2S R7E
        "sections": [
            {"t": 2, "td": "S", "r": 7, "rd": "E", "sec": 9},
            {"t": 2, "td": "S", "r": 7, "rd": "E", "sec": 16},
        ],
    },
    {
        "name": "F3 Gold LLC EXNI",
        "type": "EXNI",
        "applicant": "F3 Gold LLC",
        "county": "Pennington",
        "status": "Filed",
        "source_pdf": "F3GoldEXNIApp.pdf",
        "note": "Test hole locations confidential per SDCL 45-6C-14. Map of exploration area without test holes is public.",
        # F3 Gold is near Pennington County - from map PDF
        "sections": [
            {"t": 1, "td": "N", "r": 4, "rd": "E", "sec": 22},
            {"t": 1, "td": "N", "r": 4, "rd": "E", "sec": 23},
            {"t": 1, "td": "N", "r": 4, "rd": "E", "sec": 27},
        ],
    },
    {
        "name": "Clean Nuclear Energy - Chord Project (Uranium)",
        "type": "Uranium Exploration Permit",
        "applicant": "Clean Nuclear Energy Corp.",
        "county": "Fall River",
        "status": "Contested Case Hearing Pending",
        "source_pdf": "EXNI453App2.pdf",
        "note": "Section 36, Township 7 S, Range 2 E, Black Hills Meridian. Test hole locations confidential per SDCL 45-6D-15.",
        "sections": [
            {"t": 7, "td": "S", "r": 2, "rd": "E", "sec": 36},
        ],
    },
    {
        "name": "Clean Nuclear Energy - October Jinx Project (Uranium)",
        "type": "Uranium Exploration Permit",
        "applicant": "Clean Nuclear Energy Corp.",
        "county": "Fall River",
        "status": "Filed - DANR Comment Review",
        "source_pdf": "EXNI462App.pdf",
        "note": "Test hole locations confidential per SDCL 45-6D-15. November 2024 application.",
        # October Jinx project is also in Fall River County near the Chord project
        "sections": [
            {"t": 8, "td": "S", "r": 2, "rd": "E", "sec": 1},
            {"t": 8, "td": "S", "r": 2, "rd": "E", "sec": 12},
        ],
    },
    {
        "name": "Pete Lien & Sons EXNI 469 - Rochford Graphite",
        "type": "EXNI",
        "applicant": "Pete Lien & Sons, Inc.",
        "county": "Pennington",
        "status": "Filed March 2026",
        "source_pdf": "EXNI469App.pdf",
        "note": "Sections 3,4,5 T1N R3E; Sections 25,30,33 T2N R3E. Rochford Graphite Exploration Project. Test hole locations confidential per SDCL 45-6C-14.",
        "sections": [
            {"t": 1, "td": "N", "r": 3, "rd": "E", "sec": 3},
            {"t": 1, "td": "N", "r": 3, "rd": "E", "sec": 4},
            {"t": 1, "td": "N", "r": 3, "rd": "E", "sec": 5},
            {"t": 2, "td": "N", "r": 3, "rd": "E", "sec": 25},
            {"t": 2, "td": "N", "r": 3, "rd": "E", "sec": 30},
            {"t": 2, "td": "N", "r": 3, "rd": "E", "sec": 33},
        ],
    },
    {
        "name": "Solitario Resources Corp EXNI 470 - Ponderosa Project",
        "type": "EXNI",
        "applicant": "Solitario Resources Corp.",
        "county": "Lawrence",
        "status": "Filed",
        "source_pdf": "EXNI470App.pdf",
        "note": "T4N R2E Sec 28,32,33; T3N R2E Sec 4,5,6,7,8,9,16; T4N R1E Sec 21,22,28. Ponderosa Project, Lawrence County. Test hole locations confidential per SDCL 45-6C-14.",
        "sections": [
            {"t": 4, "td": "N", "r": 2, "rd": "E", "sec": 28},
            {"t": 4, "td": "N", "r": 2, "rd": "E", "sec": 32},
            {"t": 4, "td": "N", "r": 2, "rd": "E", "sec": 33},
            {"t": 3, "td": "N", "r": 2, "rd": "E", "sec": 4},
            {"t": 3, "td": "N", "r": 2, "rd": "E", "sec": 5},
            {"t": 3, "td": "N", "r": 2, "rd": "E", "sec": 6},
            {"t": 3, "td": "N", "r": 2, "rd": "E", "sec": 7},
            {"t": 3, "td": "N", "r": 2, "rd": "E", "sec": 8},
            {"t": 3, "td": "N", "r": 2, "rd": "E", "sec": 9},
            {"t": 3, "td": "N", "r": 2, "rd": "E", "sec": 16},
            {"t": 4, "td": "N", "r": 1, "rd": "E", "sec": 21},
            {"t": 4, "td": "N", "r": 1, "rd": "E", "sec": 22},
            {"t": 4, "td": "N", "r": 1, "rd": "E", "sec": 28},
        ],
    },
]


def build_geojson():
    features = []
    for app in APPLICATIONS:
        # Create one polygon per section for multi-section apps,
        # then dissolve into a single multipolygon feature per application.
        polygons = []
        for s in app["sections"]:
            poly = section_polygon(s["t"], s["td"], s["r"], s["rd"], s["sec"])
            polygons.append(poly["coordinates"])

        if len(polygons) == 1:
            geometry = {"type": "Polygon", "coordinates": polygons[0]}
        else:
            # polygons[i] is already [outer_ring] (Polygon coordinates list)
            # MultiPolygon coordinates = list of polygon_coords = polygons itself
            geometry = {"type": "MultiPolygon", "coordinates": polygons}

        # Compute centroid for labelling
        cx, cy = section_centroid(
            app["sections"][0]["t"],
            app["sections"][0]["td"],
            app["sections"][0]["r"],
            app["sections"][0]["rd"],
            app["sections"][0]["sec"],
        )

        props = {
            "name": app["name"],
            "type": app["type"],
            "applicant": app["applicant"],
            "county": app["county"],
            "status": app["status"],
            "note": app["note"],
            "source_pdf": app["source_pdf"],
            "sections_count": len(app["sections"]),
            "centroid_lon": round(cx, 5),
            "centroid_lat": round(cy, 5),
        }

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": props,
        })

    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    gj = build_geojson()
    out = Path(__file__).parent / "output" / "danr_exni_uranium_applications.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(gj, f, indent=2)
    print(f"Wrote {len(gj['features'])} features to {out}")
    for feat in gj["features"]:
        p = feat["properties"]
        print(f"  • {p['name']} ({p['county']} Co.) — {p['sections_count']} section(s)")
