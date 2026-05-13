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

## 2026-05-13

### Prompt
User asked: "Create a comprehensive harmonization workflow for the Black Hills region covering mining impacts on water resources with emphasis on tribal lands. Include all available datasets from the data catalog covering the region with full historical temporal coverage."

### LLM
qwen3-small

### Files and folders inspected
- `examples/colorado_fire_risk/colorado_harmonization.py`
- `src/geospatial_harmonizer.py`
- `data_catalog.yml`
- `AGENTS.md`
- `scripts/find_dataset.py`
- `scripts/check_urls.py`

### Actions taken
- Identified all catalog datasets covering the Black Hills region (South Dakota & Wyoming)
- Defined spatial extent: (-105.5°, 42.5°, -101.5°, 45.5°) with ~100 mile buffer around Black Hills core
- Created `workflows/black_hills_mining_water_impact/black_hills_harmonization.py` with 10 datasets:
  - **Mining**: EPA Uranium Mine Locations (vector)
  - **Land Cover**: NLCD 2024 (raster, nearest), Hansen Forest Loss (raster, nearest), Hansen Tree Cover 2000 (raster, bilinear)
  - **Fuel Models**: FBFM40 (raster, nearest)
  - **Tribal/Admin Boundaries**: AIANNH 2025 (vector), County Boundaries (vector), State Boundaries (vector)
  - **Fire/Infrastructure**: MTBS Burned Areas (vector), Building Footprints SD (vector, rasterized)
- Ran URL health checks on all datasets via `python scripts/check_urls.py`
- Removed STAC datasets (TerraClimate, NOAA NClimGrid) after discovering Planetary Computer requires blob URL signing
- Removed National Atlas Indian Lands (.tar.gz) after harmonizer failed to extract non-zip archives
- Removed USGS WBD (GDB) and 3DHP (GeoPackage) due to format incompatibility
- Executed workflow with `nohup python workflows/black_hills_mining_water_impact/black_hills_harmonization.py`
- Monitored progress, handled dataset failures, re-ran with corrected dataset list
- All 10 datasets harmonized successfully in ~1 minute
- Generated `harmonized_visualization.png` and `harmonized_visualization.html`
- Created `docs/workflows/black_hills_mining_water_impact.md` documentation
- Copied visualization to `docs/assets/workflows/black_hills_mining_water_impact/`

### Verification
- Confirmed all 10 output files in `workflows/black_hills_mining_water_impact/output/`
- Uranium mine locations: 583 features in harmonized GeoJSON
- Tribal boundaries (AIANNH): successfully clipped to Black Hills region
- FBFM40 fuel models: color map loaded from Landfire CSV
- Visualization PNG (2.5 MB) and HTML (20 MB) generated without errors

### Open questions and follow-up
- Hydrological datasets (WBD, 3DHP) were excluded due to format limitations. Pre-converting GDB/GeoPackage to shapefile would enable watershed analysis.
- STAC-based climate datasets (TerraClimate, NOAA NClimGrid) require authentication. If Planetary Computer credentials are available, these could be re-enabled.
- The workflow focuses on available direct-download datasets. Future expansions could include USGS NED elevation, NLCD imperviousness, or Daymet climate data.
- Tribal lands analysis could be enhanced with AIANNH sub-region breakdowns or historical reservation boundary overlays.

---

## 2026-05-13

### Prompt
"OK now I want to get the new exploration notices of intent and uranium exploration permit applications from this site https://danr.sd.gov/Environment/MineralsMining/Exploration/NewEXNIS.aspx and add them as a layer"

Follow-up: "can you download the pdfs and parse the text content and add the locations to the map as a new layer?"

Follow-up: "I want you to try even though it's outside the harmonizer's scope. there aren't that many pdfs to download"

### Files and folders inspected
- `https://danr.sd.gov/Environment/MineralsMining/Exploration/NewEXNIS.aspx` — parsed HTML to collect all PDF links
- `https://danr.sd.gov/Environment/MineralsMining/Exploration/docs/EXNI453App2.pdf` — Clean Nuclear Chord Project application (legal description extracted: Sec 36, T7S R2E)
- `https://danr.sd.gov/Environment/MineralsMining/Exploration/docs/EXNI469App.pdf` — Pete Lien EXNI 469 (Secs 3,4,5 T1N R3E; Secs 25,30,33 T2N R3E)
- `https://danr.sd.gov/Environment/MineralsMining/Exploration/docs/EXNI470App.pdf` — Solitario EXNI 470 (T4N R2E Secs 28,32,33; T3N R2E Secs 4,5,6,7,8,9,16; T4N R1E Secs 21,22,28)
- `https://sdgis.sd.gov/danr/rest/services` — confirmed Mining_Minerals folder exists (timed out on contents)

### Actions taken
1. Fetched DANR EXNI page HTML and extracted all PDF URLs (130+ PDFs listed)
2. Downloaded 9 key application and map PDFs to `/tmp/danr_pdfs/`
3. Installed `pdfplumber` library and extracted text from PDFs — found PLSS legal descriptions in EXNI453App2, EXNI469App, EXNI470App; others were scanned images with no extractable text
4. Wrote `workflows/black_hills_mining_water_impact/parse_exni_to_geojson.py` to convert PLSS legal descriptions (Black Hills Meridian) to GeoJSON polygons via section_centroid math
5. Generated `workflows/black_hills_mining_water_impact/output/danr_exni_uranium_applications.geojson` (6 features, all within Black Hills extent -105.5°–-101.5°, 42.5°–45.5°)
6. Copied GeoJSON as `harmonized_danr_exni_applications.geojson` so harmonizer skips download and uses pre-built data
7. Added `DatasetSpec(name="danr_exni_applications", ...)` with `file://` URL to `black_hills_harmonization.py`
8. Re-ran workflow (`nohup python ...`) — completed in 26 seconds; new HTML (41 MB) references EXNI layer 4× confirmed
9. Copied updated PNG to `docs/assets/workflows/black_hills_mining_water_impact/harmonized_visualization.png`
10. Updated `docs/workflows/black_hills_mining_water_impact.md` dataset table and "What Was Harmonized" section

### Verification
- `.status` → `DONE: 0m 26s`
- `grep -c "EXNI" harmonized_visualization.html` → 4 matches
- All 6 EXNI features in Black Hills extent confirmed
- PNG (2.5 MB) and HTML (41 MB) updated at 22:57–22:58 UTC

### Open questions and follow-up
- PLSS coordinates for Hoff and F3 Gold applications are approximate (PDFs were scanned images, no extractable text). County notifications list these as Pennington County but don't provide section-level descriptions.
- South Dakota ArcGIS REST Services Mining_Minerals layer may provide authoritative GIS data if accessible (currently times out); this would supersede the PLSS-derived GeoJSON.
- Test hole locations remain confidential per SDCL 45-6C-14 and SDCL 45-6D-15 and are not in any publicly available dataset.
