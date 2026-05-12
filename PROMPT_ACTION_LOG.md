# Prompt Action Log

---

## 2026-03-31

### Prompt
User asked: "Download these datasets, harmonize them to EPSG:4326 over Colorado, and generate a map:

- FBFM40 fuel models (raster, categorical, `resampling_method="nearest"`):
  `https://www.landfire.gov/data-downloads/CONUS_LF2024/LF2024_FBFM40_CONUS.zip`
  Use this CSV for both visualization colors (R, G, B columns) and legend labels:
  `https://landfire.gov/sites/default/files/CSV/2024/LF2024_FBFM40.csv`
- MACAv2 winter precipitation via OPeNDAP (raster, continuous, variable `precipitation`, months Dec–Mar):
  `https://thredds.northwestknowledge.net/thredds/dodsC/agg_macav2metdata_pr_CCSM4_r6i1p1_rcp85_2006_2099_CONUS_monthly.nc`
- MTBS burned area boundaries (vector, do not rasterize):
  `https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/MTBS_Fire/data/composite_data/burned_area_extent_shapefile/mtbs_perimeter_data.zip`
- Microsoft building footprints (vector, rasterize to presence/absence):
  `https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/Colorado.geojson.zip`"

### LLM
Claude Sonnet 4.5

### Files and folders inspected
- `src/geospatial_harmonizer.py`
- `data_catalog.yml`
- `AGENTS.md`

### Actions taken
- Created `examples/colorado_fire_risk/colorado_harmonization.py` defining four `DatasetSpec` entries and an `ExampleWorkflow` targeting EPSG:4326, Colorado extent (-109.05, 36.99, -102.04, 41.01), and ~270 m resolution (0.00243°).
- FBFM40 fuel models: downloaded CONUS ZIP, extracted GeoTIFF, resampled with `nearest` to preserve integer class codes; loaded Scott & Burgan color map and labels from Landfire CSV.
- MACAv2 precipitation: streamed via OPeNDAP, subsetted to Colorado before transfer to avoid downloading the full CONUS NetCDF; averaged Dec–Mar months; resampled from ~4 km to ~270 m using bilinear interpolation.
- MTBS burned areas: downloaded perimeter shapefile ZIP, reprojected to EPSG:4326, clipped to Colorado extent, kept as vector.
- Building footprints: downloaded Colorado GeoJSON ZIP, rasterized to presence/absence at ~270 m (burn value = 1); raw vector too large to embed in HTML at state scale.
- Generated `examples/colorado_fire_risk/output/harmonized_visualization.png` (per-layer static map) and `harmonized_visualization.html` (interactive Folium map with per-layer opacity controls).

### Verification
- Re-ran `python examples/colorado_fire_risk/colorado_harmonization.py` from repo root; all four layers harmonized and written to `examples/colorado_fire_risk/output/`.
- Confirmed OPeNDAP subset transferred only Colorado pixels (~19 MB vs. ~500 MB full CONUS).
- Confirmed `nearest` resampling preserved FBFM40 class codes (no interpolated values between integer codes).
- Visualization PNG and HTML map committed to git.

### Open questions and follow-up
- MTBS perimeters are kept as vector; if a future workflow needs them as a raster mask, set `rasterize=True` in the `DatasetSpec`.
- MACAv2 ensemble member used is CCSM4 r6i1p1; other models are available on the same THREDDS server if a multi-model comparison is needed.

---

## 2026-04-30

### Prompt
User asked: "recreate the colorado fire risk example but for utah in epsg:5070"

### LLM
glm-4.7

### Files and folders inspected
- `examples/colorado_fire_risk/colorado_harmonization.py`
- `scripts/region_extent.py`
- `src/geospatial_harmonizer.py`
- `data_catalog.yml`

### Actions taken
- Ran `python scripts/region_extent.py state Utah --crs EPSG:5070` to obtain Utah bounding box in EPSG:5070: (-1581748.3, 1629453.6, -1085516.0, 2250700.3)
- Created `workflows/utah_fire_risk/utah_harmonization.py` with the same four datasets as Colorado example, adapted for Utah:
  - FBFM40 fuel models: same CONUS source, resampled with `nearest` to preserve integer class codes
  - MACAv2 winter precipitation: same OPeNDAP source, subsetted to Utah before transfer, averaged Dec–Mar months, resampled using bilinear interpolation
  - MTBS burned areas: same perimeter shapefile, reprojected to EPSG:5070, clipped to Utah state boundary (using `clip_boundary="state:Utah"`), kept as vector
  - Building footprints: Utah-specific GeoJSON URL, rasterized to presence/absence at 270 m resolution
- Target CRS changed to EPSG:5070 (CONUS Albers Equal Area) with 270 m resolution (meters, not degrees)
- Used `clip_boundary="state:Utah"` to clip outputs to actual state polygon instead of just bounding box
- Generated `workflows/utah_fire_risk/output/harmonized_visualization.png` and `harmonized_visualization.html`
- Created `docs/workflows/utah_fire_risk.md` documentation following the template

### Verification
- Ran `python workflows/utah_fire_risk/utah_harmonization.py` successfully
- Confirmed all four layers harmonized and written to `workflows/utah_fire_risk/output/`
- Confirmed OPeNDAP subset transferred only Utah pixels
- Confirmed `nearest` resampling preserved FBFM40 class codes
- Confirmed boundary clipping applied to all outputs (rasters clipped to state polygon, vectors clipped to boundary)
- Documentation created with no placeholder text

### Open questions and follow-up
- MTBS perimeters are kept as vector; if a future workflow needs them as a raster mask, set `rasterize=True` in the `DatasetSpec`.
- MACAv2 ensemble member used is CCSM4 r6i1p1; other models are available on the same THREDDS server if a multi-model comparison is needed.
- The Utah building footprints layer was rasterized to presence/absence at 270 m; if individual building analysis is needed, work with the raw vector data directly.
- EPSG:5070 (CONUS Albers Equal Area) provides equal-area representation suitable for area-based analysis across CONUS; for local Utah analysis, a UTM zone (e.g., EPSG:32612 for northern Utah) might be more appropriate.

---

## 2026-05-12

### Prompt
User asked: "can you do this over for kansas"

### LLM
gpt-5.3-codex

### Files and folders inspected
- `examples/colorado_fire_risk/colorado_harmonization.py`
- `workflows/utah_fire_risk/utah_harmonization.py`
- `scripts/region_extent.py`
- `data_catalog.yml`

### Actions taken
- Ran `python scripts/region_extent.py state Kansas` and set workflow target extent to `(-102.0518, 36.993, -94.5884, 40.0032)` in EPSG:4326.
- Created `workflows/kansas_fire_risk/kansas_harmonization.py` using the required script bootstrap header and the same four-dataset pattern used by the Colorado/Utah examples.
- Set `output_dir=Path(__file__).parent / "output"` and `clip_boundary="state:Kansas"`.
- Validated all dataset URLs with `python scripts/check_urls.py ...` before running.
- Executed workflow via `nohup python workflows/kansas_fire_risk/kansas_harmonization.py > workflows/kansas_fire_risk/output/run.log 2>&1 &` and polled `.status` and log output until completion.
- Confirmed harmonized outputs were created for all four datasets.
- The built-in static PNG visualization step failed with `cannot convert float NaN to integer`; created required `workflows/kansas_fire_risk/output/harmonized_visualization.png` as a fallback static map from harmonized rasters and copied it to `docs/assets/workflows/kansas_fire_risk/harmonized_visualization.png`.
- Created `docs/workflows/kansas_fire_risk.md` documentation page following the Utah workflow format.
- Checked `data_catalog.yml`; no new entries were needed because all URLs already exist (including Microsoft building footprint `url_template` with `Kansas` variant).

### Verification
- `workflows/kansas_fire_risk/output/.status` reported `DONE: 66m 4s`.
- Confirmed output files:
  - `harmonized_fbfm40_fuel_models.tif`
  - `harmonized_pr_winter_rcp85_ccsm4.tif`
  - `harmonized_mtbs_burned_areas.geojson`
  - `harmonized_building_footprints.tif`
  - `harmonized_visualization.html`
  - `harmonized_visualization.png`

### Open questions and follow-up
- The NaN handling issue in the built-in static visualization routine should be fixed in `src/geospatial_harmonizer.py` so future workflows consistently produce `harmonized_visualization.png` without fallback generation.
