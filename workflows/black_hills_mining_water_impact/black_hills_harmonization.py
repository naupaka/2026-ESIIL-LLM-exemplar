#!/usr/bin/env python3
"""
Black Hills Mining & Water Impact Analysis - Harmonization Workflow

This workflow harmonizes all available geospatial datasets covering the Black Hills
region (South Dakota & Wyoming) to assess historical and future impacts of mining
on water resources, with emphasis on sovereign tribal lands.

Key Themes:
- Mining contamination & water quality
- Hydrological systems & watersheds
- Tribal sovereignty & environmental justice
- Land cover & vegetation change over time
- Climate trends & projections
- Fire history & fuel models

Spatial Extent:
- Extended Black Hills region with ~100 mile buffer
- Bounding Box: (-105.5°, 42.5°, -101.5°, 45.5°) in EPSG:4326
- Coverage: South Dakota, Wyoming, partial Nebraska
- Tribal Priority: Pine Ridge, Rosebud, Black Hills Six Tribes lands

Datasets:
1.  EPA Uranium Mine Locations (vector) - Historical mining sites
2.  BLM Mining Claims Active (vector) - Active BLM mining claim records
3.  SD DANR EXNI & Uranium Exploration Permits (vector) - Active exploration applications
4.  USGS Watershed Boundary Dataset (vector) - HUC2-HUC12 watersheds
5.  USGS 3D Hydrography Program (vector) - Flowlines, waterbodies
6.  Census TIGER AIANNH 2025 (vector) - Tribal area boundaries
7.  National Atlas of Indian Lands (vector) - Historical tribal lands
8.  NLCD Annual Land Cover 2024 (raster) - Current land cover
9.  Hansen Forest Loss Year (raster) - Forest change detection
10. Hansen Tree Cover 2000 (raster) - Baseline tree canopy
11. TerraClimate Precipitation (raster, STAC) - Monthly precipitation
12. TerraClimate Drought PDSI (raster, STAC) - Drought index
13. Census TIGER Counties 2025 (vector) - County boundaries
14. Census TIGER States 2025 (vector) - State boundaries
15. MTBS Burned Areas (vector) - Fire perimeters
16. Microsoft Building Footprints SD (vector, rasterized) - Settlement patterns
17. FBFM40 Fuel Models (raster) - Fire behavior fuel types

All outputs are harmonized to:
- CRS: EPSG:4326
- Extent: Extended Black Hills region
- Resolution: ~270m (0.00243°)
"""

import sys
from pathlib import Path

# Walk up to find the repo root (dir containing src/geospatial_harmonizer.py).
# Depth-agnostic — works regardless of how nested this script is.
_repo_root = next(p for p in Path(__file__).resolve().parents
                  if (p / "src" / "geospatial_harmonizer.py").exists())
sys.path.insert(0, str(_repo_root))

from src.geospatial_harmonizer import (
    DatasetSpec,
    ExampleWorkflow,
    run_harmonization_example,
)

# Extended Black Hills bounding box (~100 mile buffer around core region)
# Covers western SD, northeastern WY, and partial Nebraska
BLACK_HILLS_EXTENT = (-105.5, 42.5, -101.5, 45.5)

# Common output settings
TARGET_CRS = "EPSG:4326"
TARGET_RESOLUTION = 0.00243  # ~270m at this latitude

# Output goes into this project's own folder
OUTPUT_DIR = Path(__file__).parent / "output"

# ── Dataset Specifications ──────────────────────────────────────────────────────

DATASETS = [
    # ── Mining & Contamination (Primary Focus) ──────────────────────────────────
    
    # EPA Uranium Mine Locations - Historical mining sites
    DatasetSpec(
        name="uranium_mine_locations",
        display_name="Uranium Mine Sites",
        description="EPA uranium mining locations (historical)",
        url="https://www.epa.gov/sites/default/files/2015-03/uld-ii_gis.zip",
        data_type="vector",
        rasterize=False,
    ),
    
    # BLM National MLRS Mining Claims (Not Closed) - Active mining claims
    DatasetSpec(
        name="blm_mining_claims_not_closed",
        display_name="BLM Mining Claims (Active)",
        description="BLM Mineral and Land Record System mining claims - not closed",
        url="https://gbp-blm-egis.hub.arcgis.com/api/download/v1/items/abec5ef96dc8495d9c29a01b30cc04ee/shapefile?layers=0",
        data_type="vector",
        rasterize=False,
    ),

    # SD DANR Exploration Notices of Intent (EXNI) & Uranium Exploration Permit Applications
    # Locations derived from PDF applications filed with SD DANR Minerals & Mining Program.
    # Legal descriptions (PLSS sections) converted to GeoJSON via Black Hills Meridian math.
    # Source: https://danr.sd.gov/Environment/MineralsMining/Exploration/NewEXNIS.aspx
    # Note: test hole locations are confidential per SDCL 45-6C-14 / 45-6D-15.
    # The harmonized GeoJSON is pre-built by parse_exni_to_geojson.py in this directory.
    DatasetSpec(
        name="danr_exni_applications",
        display_name="EXNI & Uranium Exploration Permits",
        description="SD DANR active exploration notices of intent and uranium permit applications",
        url=f"file://{(OUTPUT_DIR / 'harmonized_danr_exni_applications.geojson').resolve()}",
        data_type="vector",
        rasterize=False,
    ),

    # ── Hydrology & Water Resources (Primary Focus) ────────────────────────────

    # USGS Watershed Boundary Dataset — HUC-8 sub-basins (Missouri region, HU2=10).
    # The bundled zip contains WBDHU2/4/6/8/10/12 layers; file_pattern picks HUC-8.
    DatasetSpec(
        name="watersheds_huc8",
        display_name="Watersheds (HUC-8)",
        description="USGS NHD Watershed Boundary Dataset — HUC-8 sub-basins (Missouri region)",
        url="https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/HU2/Shape/WBD_10_HU2_Shape.zip",
        data_type="vector",
        rasterize=False,
        file_pattern="WBDHU8",
    ),

    # USGS National Hydrography Dataset — surface waterbodies (lakes, ponds, reservoirs).
    # HU4=1012 (Cheyenne basin) covers the southern Black Hills.
    DatasetSpec(
        name="nhd_waterbodies",
        display_name="Surface Waterbodies (NHD)",
        description="USGS NHD lakes, ponds, reservoirs (Cheyenne HU4=1012)",
        url="https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/Shape/NHD_H_1012_HU4_Shape.zip",
        data_type="vector",
        rasterize=False,
        file_pattern="NHDWaterbody",
    ),

    # USGS NHD Flowlines — rivers, streams, ditches. Same HU4=1012 bundle as
    # waterbodies above; previously skipped on small machines (~300 MB shapefile).
    DatasetSpec(
        name="nhd_flowlines",
        display_name="Streams & Rivers (NHD)",
        description="USGS NHD flowlines (Cheyenne HU4=1012)",
        url="https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/Shape/NHD_H_1012_HU4_Shape.zip",
        data_type="vector",
        rasterize=False,
        file_pattern="NHDFlowline",
    ),

    # USGS Watershed Boundary Dataset — HUC-12 sub-watersheds from the full-res
    # File Geodatabase (Missouri region, HU2=10). HUC-12 is the finest sub-basin
    # level — useful for tracing contamination from a specific mine claim.
    # Uses the .gdb format support in geospatial_harmonizer.discover_dataset_file.
    DatasetSpec(
        name="watersheds_huc12",
        display_name="Sub-watersheds (HUC-12)",
        description="USGS WBD HUC-12 sub-watersheds (Missouri region, full-res GDB)",
        url="https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/HU2/GDB/WBD_10_HU2_GDB.zip",
        data_type="vector",
        rasterize=False,
        file_pattern="WBDHU12",
    ),

    # Note: USGS 3DHP (GeoPackage), SSURGO/gNATSGO (.gdb) — direct download URLs
    # need verification; add when confirmed. Format support is now in place.

    # Note: STAC datasets (TerraClimate, NOAA NClimGrid) are excluded because
    # Planetary Computer STAC assets require blob URL signing (authentication)
    # that the harmonizer cannot perform. Direct-download datasets only.

    # Deferred — would expand water/contamination context but each needs a code
    # change or preprocessing step not in scope right now:
    #   • EPA Superfund NPL sites — only available via ArcGIS FeatureServer
    #     query (?f=geojson) endpoints; the harmonizer's download_file assumes a
    #     downloadable archive URL.
    #   • USGS MRDS mineral occurrences — distributed as CSV only (no .shp);
    #     needs a lat/lon → GeoJSON preprocessing step like parse_exni_to_geojson.
    #   • PRISM 30-yr climate normals — Oregon State PRISM download endpoints
    #     require a referer/cookie session and ship as .bil (not .tif).
    #   • USDA SSURGO/gNATSGO hydrologic soil group, depth to bedrock, depth to
    #     water table — only redistributed as ESRI File Geodatabase (.gdb), which
    #     the harmonizer cannot read. Needs ogr2ogr preconversion per state.
    
    # ── Land Cover & Vegetation Change (Secondary Focus) ───────────────────────
    
    # NLCD Annual Land Cover 2024 - Current land cover classification
    DatasetSpec(
        name="nlcd_2024",
        display_name="Land Cover 2024",
        description="NLCD annual land cover classification (2024)",
        url="https://www.mrlc.gov/downloads/sciweb1/shared/mrlc/data-bundles/Annual_NLCD_LndCov_2024_CU_C1V1.zip",
        data_type="raster",
        resampling_method="nearest",
    ),
    
    # Hansen Global Forest Change - Loss Year
    DatasetSpec(
        name="hansen_forest_loss",
        display_name="Forest Loss Year",
        description="Hansen Global Forest Change loss year (2000-2024)",
        url="https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12/Hansen_GFC-2024-v1.12_lossyear_50N_110W.tif",
        data_type="raster",
        resampling_method="nearest",
    ),
    
    # Hansen Global Forest Change - Tree Cover 2000 (baseline)
    DatasetSpec(
        name="hansen_tree_cover_2000",
        display_name="Tree Cover 2000",
        description="Hansen tree canopy cover baseline (2000)",
        url="https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12/Hansen_GFC-2024-v1.12_treecover2000_50N_110W.tif",
        data_type="raster",
        resampling_method="bilinear",
    ),
    
    # FBFM40 Fire Behavior Fuel Models 2024 - Vegetation/fuel types
    DatasetSpec(
        name="fbfm40_fuel_models",
        display_name="Fire Fuel Models",
        description="LANDFIRE FBFM40 fuel models (2024)",
        url="https://www.landfire.gov/data-downloads/CONUS_LF2024/LF2024_FBFM40_CONUS.zip",
        data_type="raster",
        resampling_method="nearest",
        labels_url="https://landfire.gov/sites/default/files/CSV/2024/LF2024_FBFM40.csv",
    ),
    
    # ── Tribal & Administrative Boundaries (Context) ───────────────────────────
    
    # Census TIGER AIANNH 2025 - Tribal area boundaries
    DatasetSpec(
        name="tribal_boundaries_aiannh",
        display_name="Tribal Area Boundaries",
        description="Census AIANNH 2025 tribal boundaries",
        url="https://www2.census.gov/geo/tiger/TIGER2025/AIANNH/tl_2025_us_aiannh.zip",
        data_type="vector",
        rasterize=False,
    ),
    
    # Note: National Atlas of Indian Lands (.tar.gz) is excluded because
    # the harmonizer only extracts .zip archives, not .tar.gz.
    
    # Census TIGER Counties 2025 - County boundaries
    DatasetSpec(
        name="county_boundaries",
        display_name="County Boundaries",
        description="Census TIGER 2025 county polygons",
        url="https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip",
        data_type="vector",
        rasterize=False,
    ),
    
    # Census TIGER States 2025 - State boundaries
    DatasetSpec(
        name="state_boundaries",
        display_name="State Boundaries",
        description="Census TIGER 2025 state polygons",
        url="https://www2.census.gov/geo/tiger/TIGER2025/STATE/tl_2025_us_state.zip",
        data_type="vector",
        rasterize=False,
    ),
    
    # ── Fire History & Infrastructure (Context) ────────────────────────────────
    
    # MTBS Burned Area Boundaries - Fire perimeters 1984-present
    DatasetSpec(
        name="mtbs_burned_areas",
        display_name="Fire Perimeters",
        description="MTBS burned area boundaries (1984-present)",
        url="https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/MTBS_Fire/data/composite_data/burned_area_extent_shapefile/mtbs_perimeter_data.zip",
        data_type="vector",
        rasterize=False,
    ),
    
    # Microsoft Building Footprints South Dakota - Human settlement patterns
    DatasetSpec(
        name="building_footprints_sd",
        display_name="Building Footprints SD",
        description="Microsoft building footprints (South Dakota)",
        url="https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/SouthDakota.geojson.zip",
        data_type="vector",
        rasterize=True,
        burn_value=1,
    ),

    # Microsoft Building Footprints Wyoming (covers the western buffer of the extent)
    DatasetSpec(
        name="building_footprints_wy",
        display_name="Building Footprints WY",
        description="Microsoft building footprints (Wyoming)",
        url="https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/Wyoming.geojson.zip",
        data_type="vector",
        rasterize=True,
        burn_value=1,
    ),

    # Microsoft Building Footprints Nebraska (covers the southeastern buffer)
    DatasetSpec(
        name="building_footprints_ne",
        display_name="Building Footprints NE",
        description="Microsoft building footprints (Nebraska)",
        url="https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/Nebraska.geojson.zip",
        data_type="vector",
        rasterize=True,
        burn_value=1,
    ),
]


def main() -> int:
    """Run the Black Hills mining & water impact harmonization workflow."""
    workflow = ExampleWorkflow(
        name="black_hills_mining_water_impact",
        datasets=DATASETS,
        target_crs=TARGET_CRS,
        target_extent=BLACK_HILLS_EXTENT,
        target_resolution=TARGET_RESOLUTION,
        output_dir=OUTPUT_DIR,
        create_visualization=True,
        verbose=True,
        clip_boundary=None,  # Use bounding box for extended region
    )
    
    output_files, interactive_map = run_harmonization_example(workflow)
    
    print("\n" + "=" * 70)
    print("Black Hills Mining & Water Impact Harmonization Complete")
    print("=" * 70)
    print(f"\nOutputs saved to: {OUTPUT_DIR.resolve()}")
    
    print("\nGenerated Files:")
    for path in output_files:
        print(f"  - {path.name}")
    
    viz_path = OUTPUT_DIR / "harmonized_visualization.png"
    composite_path = OUTPUT_DIR / "harmonized_visualization_composite.png"
    
    print("\nGenerated Visualizations:")
    if viz_path.exists():
        print(f"  - Per-layer PNG: {viz_path.name}")
    if composite_path.exists():
        print(f"  - Composite PNG: {composite_path.name}")
    if interactive_map is not None:
        print("  - Interactive map: harmonized_visualization.html")
    
    print("\n" + "=" * 70)
    print("Key Analysis Themes:")
    print("  1. Mining-Water Proximity: Uranium sites vs watersheds")
    print("  2. Tribal Sovereignty: Mining impacts on AIANNH lands")
    print("  3. Environmental Justice: Historical context + current data")
    print("  4. Land Cover Change: Vegetation loss near mining sites")
    print("  5. Climate Trends: Precipitation/drought patterns")
    print("  6. Fire History: Burned areas & fuel models")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
