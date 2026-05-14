"""Thin wrappers around GDAL/OGR command-line tools.

These functions call ``ogr2ogr``, ``ogrinfo``, and ``gdal_rasterize`` via
:mod:`subprocess`, keeping the rest of the codebase free from ad-hoc
command construction.  All functions raise :class:`subprocess.CalledProcessError`
on failure with stderr in the error message.

Requires the ``gdal-bin`` system package (``apt install gdal-bin``).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from shapely.geometry import mapping as _shapely_mapping, shape as _shapely_shape


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def _check_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(
            f"{name!r} not found on PATH. Install it with: apt install gdal-bin"
        )
    return path


_OGR2OGR = _check_tool("ogr2ogr")
_OGRINFO = _check_tool("ogrinfo")
_GDAL_RASTERIZE = _check_tool("gdal_rasterize")


# ---------------------------------------------------------------------------
# ogr2ogr
# ---------------------------------------------------------------------------

def ogr2ogr(
    input_path: str | Path,
    output_path: str | Path,
    *,
    t_srs: str | None = None,
    s_srs: str | None = None,
    clipsrc: str | Path | None = None,
    spat: tuple[float, float, float, float] | None = None,
    where: str | None = None,
    sql: str | None = None,
    output_format: str = "GeoJSON",
    simplify: float | None = None,
    layer: str | None = None,
    extra_args: list[str] | None = None,
) -> Path:
    """Run ``ogr2ogr`` to reproject, clip, filter, or convert a vector file.

    Returns *output_path* as a :class:`Path`.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [_OGR2OGR, "-f", output_format]

    if t_srs is not None:
        cmd += ["-t_srs", t_srs]
    if s_srs is not None:
        cmd += ["-s_srs", s_srs]
    if clipsrc is not None:
        cmd += ["-clipsrc", str(clipsrc)]
    if spat is not None:
        cmd += ["-spat", str(spat[0]), str(spat[1]), str(spat[2]), str(spat[3])]
    if where is not None:
        cmd += ["-where", where]
    if sql is not None:
        cmd += ["-sql", sql]
    if simplify is not None:
        cmd += ["-simplify", str(simplify)]
    if extra_args:
        cmd += extra_args

    # ogr2ogr fails if the output file already exists — remove it first
    if out.exists():
        out.unlink()

    cmd += [str(out), str(input_path)]
    # When input is a multi-layer datasource (.gdb / .gpkg), a trailing positional
    # arg selects which layer to read.
    if layer is not None:
        cmd.append(layer)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ogr2ogr failed (exit {result.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return out


# ---------------------------------------------------------------------------
# ogrinfo helpers
# ---------------------------------------------------------------------------

def ogrinfo_bounds(
    input_path: str | Path,
    *,
    layer: str | None = None,
    where: str | None = None,
) -> tuple[float, float, float, float]:
    """Return ``(xmin, ymin, xmax, ymax)`` for a vector layer via ``ogrinfo -so``."""
    cmd: list[str] = [_OGRINFO, "-so", "-ro"]
    if where is not None:
        cmd += ["-where", where]
    cmd.append(str(input_path))
    if layer is not None:
        cmd.append(layer)

    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    # Parse "Extent: (xmin, ymin) - (xmax, ymax)" from ogrinfo output
    m = re.search(
        r"Extent:\s*\(([^,]+),\s*([^)]+)\)\s*-\s*\(([^,]+),\s*([^)]+)\)",
        result.stdout,
    )
    if m is None:
        raise ValueError(f"Could not parse extent from ogrinfo output:\n{result.stdout}")
    return float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))


def ogrinfo_layers(input_path: str | Path) -> list[str]:
    """Return the list of layer names in a multi-layer datasource (.gdb / .gpkg).

    Parses ``ogrinfo -ro -q``, which emits one ``Layer: <name> (<geomtype>)``
    line per layer (optionally nested under ``Group <name>:`` headers in
    FileGDB output). Older GDAL builds use ``N: <name>`` instead — handled too.
    """
    result = subprocess.run(
        [_OGRINFO, "-ro", "-q", str(input_path)],
        check=True, capture_output=True, text=True,
    )
    layers: list[str] = []
    for line in result.stdout.splitlines():
        m = re.match(r"\s*Layer:\s+(\S+)", line) or re.match(r"\s*\d+:\s*(\S+)", line)
        if m:
            layers.append(m.group(1))
    return layers


def ogrinfo_feature_count(
    input_path: str | Path,
    *,
    layer: str | None = None,
) -> int:
    """Return the feature count for a vector layer."""
    cmd: list[str] = [_OGRINFO, "-so", "-ro", str(input_path)]
    if layer is not None:
        cmd.append(layer)
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    m = re.search(r"Feature Count:\s*(\d+)", result.stdout)
    if m is None:
        raise ValueError(f"Could not parse feature count from ogrinfo output:\n{result.stdout}")
    return int(m.group(1))


# ---------------------------------------------------------------------------
# gdal_rasterize
# ---------------------------------------------------------------------------

def gdal_rasterize(
    input_path: str | Path,
    output_path: str | Path,
    *,
    burn_value: int = 1,
    te: tuple[float, float, float, float] | None = None,
    ts: tuple[int, int] | None = None,
    tr: tuple[float, float] | None = None,
    ot: str = "Byte",
    a_srs: str | None = None,
    a_nodata: float | int | None = None,
    all_touched: bool = True,
) -> Path:
    """Run ``gdal_rasterize`` to burn vector features into a raster.

    Returns *output_path* as a :class:`Path`.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [_GDAL_RASTERIZE, "-burn", str(burn_value), "-ot", ot]

    if te is not None:
        cmd += ["-te", str(te[0]), str(te[1]), str(te[2]), str(te[3])]
    if ts is not None:
        cmd += ["-ts", str(ts[0]), str(ts[1])]
    if tr is not None:
        cmd += ["-tr", str(tr[0]), str(tr[1])]
    if a_srs is not None:
        cmd += ["-a_srs", a_srs]
    if a_nodata is not None:
        cmd += ["-a_nodata", str(a_nodata)]
    if all_touched:
        cmd.append("-at")

    cmd += [str(input_path), str(out)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"gdal_rasterize failed (exit {result.returncode}):\n"
            f"  cmd: {' '.join(cmd)}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return out


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def write_geometry_to_geojson(geom, crs: str, path: str | Path) -> Path:
    """Write a Shapely geometry to a minimal GeoJSON file for use with GDAL.

    Useful for creating temporary clip boundaries for ``ogr2ogr -clipsrc``.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": _shapely_mapping(geom),
            "properties": {},
        }],
    }
    with open(out, "w") as f:
        json.dump(fc, f)
    return out


def read_geometries_from_file(path: str | Path):
    """Yield Shapely geometries from a vector file using fiona (streaming).

    This reads features one at a time without loading the entire file into RAM.
    """
    import fiona
    with fiona.open(str(path)) as src:
        for feat in src:
            yield _shapely_shape(feat["geometry"])


def read_bounds_from_file(path: str | Path) -> tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) of a vector file using fiona."""
    import fiona
    with fiona.open(str(path)) as src:
        return src.bounds


def read_crs_from_file(path: str | Path) -> str:
    """Return the CRS of a vector file as a string."""
    import fiona
    with fiona.open(str(path)) as src:
        return src.crs_wkt or "EPSG:4326"
