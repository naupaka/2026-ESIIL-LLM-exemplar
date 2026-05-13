# AGENTS.md

## Repository Purpose

Template for scientists learning how AI can harmonize environmental datasets.
See **TASKS.md** for a plain-English description of the harmonization pipeline.

---

## Step 1: Read the Example

Read `examples/colorado_fire_risk/colorado_harmonization.py` before writing
a new workflow. Follow the same pattern: construct `DatasetSpec` objects,
build an `ExampleWorkflow`, call `run_harmonization_example()`.

---

## Core Steps

1. **Validate URLs** — `python scripts/check_urls.py <url1> <url2> ...`. Stop if any fail.
2. **Search the data catalog when the user asks by topic** — `python scripts/find_dataset.py <keyword>`.
3. **Get region bounds** — `python scripts/region_extent.py state Colorado`. Always set `clip_boundary` (e.g. `clip_boundary="state:Colorado"`).
4. **Write a Python script** in `workflows/<project_name>/` using the bootstrap header below.
5. **Set `output_dir=Path(__file__).parent / "output"`**.
6. **Run with nohup** — create the output directory first, then run:
   ```bash
   mkdir -p workflows/<name>/output
   nohup python workflows/<name>/<script>.py > workflows/<name>/output/run.log 2>&1 &
   ```
   Poll `.status` every 10 seconds. Wait for completion before re-running.

## After It Runs

1. **Append to `PROMPT_ACTION_LOG.md`** — date, user's exact prompt, model name, actions taken.
2. **Create `docs/workflows/<project_name>.md`** — follow the format in `docs/workflows/utah_fire_risk.md`.
3. **Add new datasets to `data_catalog.yml`** — only if URLs pass health check.
4. **Visualization filename must be exactly `harmonized_visualization.png`**.

---

## Directory Structure

```
src/                              Core harmonization library (read-only)
scripts/                          Helper scripts (URL check, catalog search, region lookup)
examples/colorado_fire_risk/      Reference example (read-only)
workflows/<project_name>/         Each user analysis gets its own folder
  <script>.py
  output/                         Generated outputs
docs/                             Website source (mkdocs)
```

---

## Region Boundaries

For US states, counties, or places, get coordinates from the lookup tool:

```bash
python scripts/region_extent.py state Colorado
python scripts/region_extent.py county Larimer Colorado --crs EPSG:5070
python scripts/region_extent.py place Boulder CO
```

Pass `--crs` when target CRS ≠ EPSG:4326. Always set `clip_boundary` on `ExampleWorkflow`.

For non-US regions: ask the user for a boundary file or bounding box.

---

## Required Script Header

Every workflow script must include this before importing from `src/`:

```python
import sys
from pathlib import Path

_repo_root = next(p for p in Path(__file__).resolve().parents
                  if (p / "src" / "geospatial_harmonizer.py").exists())
sys.path.insert(0, str(_repo_root))

from src.geospatial_harmonizer import (
    DatasetSpec,
    ExampleWorkflow,
    run_harmonization_example,
)
```

---

## Output Requirements

- Rasters: `harmonized_<name>.tif`
- Vectors: `harmonized_<name>.geojson`
- Static visualization: `harmonized_visualization.png` (exact filename)
- Interactive map: `harmonized_visualization.html`
- All outputs in `workflows/<project_name>/output/`

---

## Failure Handling

- Download fails → stop and tell the user which URL failed.
- URL returns HTML → tell the user it's a portal link and ask for a direct download URL.
- No valid geospatial files found → stop and ask the user.

---

## Resampling Rules

- Categorical data (land cover, fuel models) → `resampling_method="nearest"`
- Continuous data (temperature, precipitation) → `resampling_method="bilinear"`
- If unsure → ask the user

---

## Ad-Hoc Preprocessing

GDAL CLI tools (`gdalwarp`, `ogr2ogr`, `gdal_translate`) are available for
format conversion or preprocessing before running the harmonizer.
