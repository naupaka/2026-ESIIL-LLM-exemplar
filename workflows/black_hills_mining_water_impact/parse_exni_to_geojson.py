#!/usr/bin/env python3
"""
Crawl DANR EXNI / uranium exploration permit applications, parse the PDFs,
and emit a GeoJSON of the application footprints.

Pipeline per application:
  1. Fetch the DANR listing page and extract PDF links + row metadata.
  2. Download each PDF into a local cache directory (skip if already present).
  3. Extract text with pdfplumber (fast path for text-based PDFs).
  4. Fall back to OCR via pdf2image + pytesseract for scanned/image PDFs.
  5. Parse PLSS legal descriptions (Township / Range / Section) from the text.
  6. Build Polygon / MultiPolygon geometry from parsed sections using the
     Black Hills Principal Meridian.
  7. If no PLSS description can be parsed, place the application at a
     county-level fallback polygon and flag it as approximate.

Dependencies:
  pip install pdfplumber pdf2image pytesseract beautifulsoup4 requests
  apt install tesseract-ocr poppler-utils

Black Hills Principal Meridian base point:
  Baseline (latitude):  43°57'36" N  ≈ 43.9600° N
  Principal Meridian (longitude): 103°46'48" W ≈ -103.7800° W
Reference: https://www.blm.gov/sites/blm.gov/files/PublicRoom_Cadastral_Survey_BHills.pdf
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

LISTING_URL = "https://danr.sd.gov/Environment/MineralsMining/Exploration/NewEXNIS.aspx"
PDF_BASE_URL = "https://danr.sd.gov/Environment/MineralsMining/Exploration/docs/"

WORKFLOW_DIR = Path(__file__).parent
# PDFs are archived under pdfs/YYYY-MM-DD/ so each run's snapshot of the DANR
# site is preserved alongside the code. These files are intentionally tracked
# in git as archival documents.
PDF_ARCHIVE_ROOT = WORKFLOW_DIR / "pdfs"
TODAY_STAMP = date.today().isoformat()
PDF_CACHE_DIR = PDF_ARCHIVE_ROOT / TODAY_STAMP
OUTPUT_DIR = WORKFLOW_DIR / "output"
OUTPUT_GEOJSON = OUTPUT_DIR / "danr_exni_uranium_applications.geojson"

# ── Black Hills Meridian datum ────────────────────────────────────────────────
BHM_LAT = 43.9600
BHM_LON = -103.7800
DEG_LAT_PER_MILE = 1.0 / 69.0
DEG_LON_PER_MILE = 1.0 / (69.0 * math.cos(math.radians(44.0)))

# Approximate centroids for SD counties in/near the Black Hills.
# Used only as fallback geometry when PLSS parsing fails.
SD_COUNTY_CENTROIDS = {
    "Fall River": (-103.50, 43.25),
    "Custer":     (-103.60, 43.70),
    "Pennington": (-102.80, 44.00),
    "Lawrence":   (-103.80, 44.40),
    "Meade":      (-102.50, 44.50),
    "Butte":      (-103.50, 44.90),
    "Harding":    (-103.50, 45.55),
    "Perkins":    (-102.50, 45.50),
    "Ziebach":    (-101.70, 44.95),
    "Haakon":     (-101.60, 44.30),
    "Jackson":    (-101.60, 43.70),
}

COUNTY_FALLBACK_HALF_SIZE_MI = 5.0  # rough 10-mile square


# ── PLSS section math ─────────────────────────────────────────────────────────
def section_centroid(township: int, town_dir: str, range_num: int, range_dir: str, section: int):
    """Return (lon, lat) centroid of a PLSS section in the Black Hills Meridian."""
    t_offset = township - 0.5
    lat_offset = t_offset * 6.0 * DEG_LAT_PER_MILE
    if town_dir.upper() == "S":
        lat_offset = -lat_offset

    r_offset = range_num - 0.5
    lon_offset = r_offset * 6.0 * DEG_LON_PER_MILE
    if range_dir.upper() == "W":
        lon_offset = -lon_offset

    twp_lat = BHM_LAT + lat_offset + 3.0 * DEG_LAT_PER_MILE
    twp_lon = BHM_LON + lon_offset - 3.0 * DEG_LON_PER_MILE

    s = section - 1
    row = s // 6
    col_index = s % 6
    col = 5 - col_index if row % 2 == 0 else col_index

    sec_lat = twp_lat - (row + 0.5) * DEG_LAT_PER_MILE
    sec_lon = twp_lon + (col + 0.5) * DEG_LON_PER_MILE
    return (sec_lon, sec_lat)


def section_polygon(township, town_dir, range_num, range_dir, section):
    """Return a GeoJSON Polygon geometry for a ~1 mile PLSS section."""
    cx, cy = section_centroid(township, town_dir, range_num, range_dir, section)
    half_lat = DEG_LAT_PER_MILE * 0.5
    half_lon = DEG_LON_PER_MILE * 0.5
    coords = [
        [cx - half_lon, cy - half_lat],
        [cx + half_lon, cy - half_lat],
        [cx + half_lon, cy + half_lat],
        [cx - half_lon, cy + half_lat],
        [cx - half_lon, cy - half_lat],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


def county_fallback_polygon(county: str):
    """Return an approximate square polygon for a county centroid, or None."""
    centroid = SD_COUNTY_CENTROIDS.get(county)
    if centroid is None:
        return None
    cx, cy = centroid
    half_lat = DEG_LAT_PER_MILE * COUNTY_FALLBACK_HALF_SIZE_MI
    half_lon = DEG_LON_PER_MILE * COUNTY_FALLBACK_HALF_SIZE_MI
    coords = [
        [cx - half_lon, cy - half_lat],
        [cx + half_lon, cy - half_lat],
        [cx + half_lon, cy + half_lat],
        [cx - half_lon, cy + half_lat],
        [cx - half_lon, cy - half_lat],
    ]
    return {"type": "Polygon", "coordinates": [coords]}


# ── DANR listing crawl ────────────────────────────────────────────────────────
def fetch_listing(url: str = LISTING_URL) -> list[dict]:
    """Fetch the DANR EXNI page and extract application rows.

    Returns one dict per detected PDF application link:
        {"filename": str, "url": str, "row_text": str}

    Row metadata (applicant, county, status) is captured as raw row_text;
    structured fields are extracted later in build_application_record().
    """
    import requests
    from bs4 import BeautifulSoup

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    apps: list[dict] = []
    seen_filenames: set[str] = set()

    # Look for every anchor pointing at a PDF in the EXNI docs directory.
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.lower().endswith(".pdf"):
            continue
        pdf_url = urljoin(url, href)
        if "/Exploration/docs/" not in pdf_url:
            continue

        filename = pdf_url.rsplit("/", 1)[-1]
        # Only keep "application" PDFs (skip notice letters, decisions, maps).
        if not re.search(r"app|exni", filename, re.IGNORECASE):
            continue
        if filename in seen_filenames:
            continue
        seen_filenames.add(filename)

        # Capture surrounding row text (containing applicant/county/status) if
        # this anchor lives inside a <tr>; otherwise fall back to its parent.
        container = a.find_parent("tr") or a.parent
        row_text = " ".join(container.get_text(" ", strip=True).split()) if container else ""

        apps.append({
            "filename": filename,
            "url": pdf_url,
            "row_text": row_text,
        })

    return apps


# ── PDF download + text extraction ────────────────────────────────────────────
def download_pdf(url: str, cache_dir: Path = PDF_CACHE_DIR) -> Path:
    """Download a PDF to cache_dir, reusing any prior dated snapshot.

    PDF files are archived under pdfs/YYYY-MM-DD/. To avoid re-downloading
    every PDF on every run, we first look for the same filename in any
    existing dated subdirectory and reuse it. Only PDFs not seen before are
    downloaded into today's directory.
    """
    import requests
    filename = url.rsplit("/", 1)[-1]

    # Reuse the most recent existing copy if one is on disk already.
    if PDF_ARCHIVE_ROOT.exists():
        for prior_dir in sorted(PDF_ARCHIVE_ROOT.iterdir(), reverse=True):
            if not prior_dir.is_dir():
                continue
            existing = prior_dir / filename
            if existing.exists() and existing.stat().st_size > 0:
                return existing

    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / filename
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(out, "wb") as f:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if chunk:
                f.write(chunk)
    return out


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Extract text from a text-based PDF. Returns empty string on failure."""
    try:
        import pdfplumber
    except ImportError:
        return ""
    pages: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                pages.append(t)
    except Exception as exc:
        print(f"    pdfplumber failed on {pdf_path.name}: {exc}", file=sys.stderr)
    return "\n".join(pages)


def extract_text_ocr(pdf_path: Path, dpi: int = 200) -> str:
    """OCR a scanned PDF using pdf2image + pytesseract.

    Streams one page at a time to bound peak memory — converting an entire PDF
    at 200 DPI in one call can hold hundreds of MB of decoded pixels in RAM
    simultaneously and trigger the OOM killer on small machines.
    """
    try:
        from pdf2image import convert_from_path, pdfinfo_from_path
        import pytesseract
    except ImportError as exc:
        print(f"    OCR deps missing ({exc}); skipping OCR for {pdf_path.name}", file=sys.stderr)
        return ""
    try:
        info = pdfinfo_from_path(str(pdf_path))
        n_pages = int(info.get("Pages", 0))
    except Exception as exc:
        print(f"    pdfinfo failed on {pdf_path.name}: {exc}", file=sys.stderr)
        return ""
    pages: list[str] = []
    for i in range(1, n_pages + 1):
        try:
            imgs = convert_from_path(str(pdf_path), dpi=dpi, first_page=i, last_page=i)
        except Exception as exc:
            print(f"    pdf2image failed on page {i} of {pdf_path.name}: {exc}", file=sys.stderr)
            continue
        for img in imgs:
            try:
                pages.append(pytesseract.image_to_string(img))
            except Exception as exc:
                print(f"    tesseract failed on page {i} of {pdf_path.name}: {exc}", file=sys.stderr)
            finally:
                img.close()
    return "\n".join(pages)


# Heuristic: a PDF whose extracted text is mostly whitespace, or shorter than
# this many non-whitespace chars, is treated as a scanned image needing OCR.
MIN_TEXT_CHARS = 200


def extract_text(pdf_path: Path) -> tuple[str, str]:
    """Extract text from a PDF. Returns (text, source) where source is 'pdfplumber' or 'ocr'."""
    text = extract_text_pdfplumber(pdf_path)
    if len(re.sub(r"\s+", "", text)) >= MIN_TEXT_CHARS:
        return text, "pdfplumber"
    ocr_text = extract_text_ocr(pdf_path)
    if len(re.sub(r"\s+", "", ocr_text)) > len(re.sub(r"\s+", "", text)):
        return ocr_text, "ocr"
    return text, "pdfplumber"


# ── PLSS legal description parsing ────────────────────────────────────────────
_TR_RE = re.compile(
    r"T(?:ownship|wp)?\.?\s*(\d{1,3})\s*(N|S|North|South)\b"
    r".{0,40}?"
    r"R(?:ange|g)?\.?\s*(\d{1,3})\s*(E|W|East|West)\b",
    re.IGNORECASE,
)

# Capture a section block — "Sec(tion)(s) NUM[, NUM, NUM-NUM, ...]"
# Matches an explicit list of section numbers (and ranges) joined by ',', '&',
# or the word 'and'. The first number is required; subsequent numbers are optional.
_SEC_RE = re.compile(
    r"Sec(?:tion)?s?\.?\s*"
    r"("
    r"\d{1,2}(?:\s*-\s*\d{1,2})?"                              # first number or range
    r"(?:\s*(?:,|&|\band\b)\s*\d{1,2}(?:\s*-\s*\d{1,2})?)*"   # additional numbers
    r")",
    re.IGNORECASE,
)


def _parse_section_numbers(s: str) -> list[int]:
    """Parse a section-number string like '3, 4, 5' or '3-5' or '1 and 12'."""
    nums: list[int] = []
    for part in re.split(r"[,&]|\band\b", s, flags=re.IGNORECASE):
        part = part.strip().rstrip(".")
        if not part:
            continue
        m = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 1 <= a <= 36 and 1 <= b <= 36 and a <= b:
                nums.extend(range(a, b + 1))
            continue
        m = re.match(r"\d{1,2}$", part)
        if m:
            n = int(part)
            if 1 <= n <= 36:
                nums.append(n)
    return nums


def parse_plss(text: str) -> list[dict]:
    """Parse a PLSS legal description blob into [{t, td, r, rd, sec}, ...]."""
    sections: list[dict] = []
    norm = re.sub(r"\s+", " ", text)
    # Split into clauses on strong separators so a T/R block stays with its sections.
    # Note: don't split on "and" — in PLSS descriptions "and" typically joins
    # sections within the same T/R block, not separate clauses.
    clauses = re.split(r"[;.\n]", norm)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        tr_match = _TR_RE.search(clause)
        if not tr_match:
            continue
        t = int(tr_match.group(1))
        td = tr_match.group(2)[0].upper()
        r = int(tr_match.group(3))
        rd = tr_match.group(4)[0].upper()

        # A single clause can contain multiple "Sec ..." blocks bound to one T/R
        # (e.g. "Sec 9 and Sec 16, T2S R7E"), so collect them all.
        sec_matches = list(_SEC_RE.finditer(clause))
        if not sec_matches:
            continue
        for m in sec_matches:
            for sec in _parse_section_numbers(m.group(1)):
                sections.append({"t": t, "td": td, "r": r, "rd": rd, "sec": sec})

    # De-duplicate while preserving order
    seen = set()
    unique: list[dict] = []
    for s in sections:
        key = (s["t"], s["td"], s["r"], s["rd"], s["sec"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


# ── Metadata extraction from listing row + PDF text ───────────────────────────
COUNTY_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in SD_COUNTY_CENTROIDS) + r")\b",
    re.IGNORECASE,
)


def _detect_county(row_text: str, pdf_text: str) -> str | None:
    for source in (row_text, pdf_text):
        m = COUNTY_RE.search(source)
        if m:
            # Normalize capitalization to match SD_COUNTY_CENTROIDS keys
            for k in SD_COUNTY_CENTROIDS:
                if k.lower() == m.group(1).lower():
                    return k
    return None


def _detect_applicant(row_text: str) -> str:
    # Drop the filename and obvious DANR words from the row text.
    cleaned = re.sub(r"\S*\.pdf", "", row_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|,;")
    return cleaned[:120]


def _detect_status(row_text: str) -> str:
    for kw in (
        "Contested Case Hearing",
        "Decision Pending",
        "Approved",
        "Denied",
        "Withdrawn",
        "Pending",
        "Filed",
    ):
        if re.search(kw, row_text, re.IGNORECASE):
            return kw
    return "Unknown"


def _detect_type(filename: str, pdf_text: str) -> str:
    if re.search(r"uranium", pdf_text, re.IGNORECASE):
        return "Uranium Exploration Permit"
    return "EXNI"


# ── Build one feature per application ─────────────────────────────────────────
def build_features(applications: Iterable[dict]) -> list[dict]:
    features: list[dict] = []
    for app in applications:
        sections = app.get("plss_sections") or []
        county = app.get("county")

        approximate = False
        if sections:
            polygons = [section_polygon(s["t"], s["td"], s["r"], s["rd"], s["sec"])["coordinates"]
                        for s in sections]
            geometry = (
                {"type": "Polygon", "coordinates": polygons[0]} if len(polygons) == 1
                else {"type": "MultiPolygon", "coordinates": polygons}
            )
            cx, cy = section_centroid(sections[0]["t"], sections[0]["td"],
                                      sections[0]["r"], sections[0]["rd"],
                                      sections[0]["sec"])
        else:
            fallback = county_fallback_polygon(county) if county else None
            if fallback is None:
                print(f"  ! skipping {app['filename']}: no PLSS parsed and no county fallback")
                continue
            geometry = fallback
            cx, cy = SD_COUNTY_CENTROIDS[county]
            approximate = True

        props = {
            "name": app.get("name", app["filename"]),
            "type": app.get("type", "EXNI"),
            "applicant": app.get("applicant", ""),
            "county": county or "",
            "status": app.get("status", "Unknown"),
            "source_pdf": app["filename"],
            "source_url": app["url"],
            "extraction_method": app.get("extraction_method", ""),
            "sections_count": len(sections),
            "geometry_source": "plss_section" if sections else "county_fallback",
            "approximate_location": approximate,
            "centroid_lon": round(cx, 5),
            "centroid_lat": round(cy, 5),
        }
        features.append({"type": "Feature", "geometry": geometry, "properties": props})
    return features


# ── Orchestrator ──────────────────────────────────────────────────────────────
def process_application(app: dict) -> dict:
    """Download, OCR-if-needed, parse PLSS, enrich metadata. Returns enriched dict."""
    print(f"  • {app['filename']}", flush=True)
    pdf_path = download_pdf(app["url"])
    text, method = extract_text(pdf_path)
    sections = parse_plss(text)

    county = _detect_county(app.get("row_text", ""), text)
    enriched = dict(app)
    enriched.update({
        "pdf_path": str(pdf_path),
        "text_chars": len(text),
        "extraction_method": method,
        "plss_sections": sections,
        "county": county,
        "applicant": _detect_applicant(app.get("row_text", "")),
        "status": _detect_status(app.get("row_text", "")),
        "type": _detect_type(app["filename"], text),
        "name": app["filename"].replace(".pdf", ""),
    })
    print(f"    text={len(text):>6} chars via {method:10}  sections={len(sections):>2}  county={county or '-'}", flush=True)
    return enriched


def main(argv: list[str] | None = None) -> int:
    print(f"Fetching listing: {LISTING_URL}")
    listing = fetch_listing(LISTING_URL)
    print(f"  Found {len(listing)} candidate application PDFs")

    enriched: list[dict] = []
    for app in listing:
        try:
            enriched.append(process_application(app))
        except Exception as exc:
            print(f"    ! failed {app['filename']}: {exc}", file=sys.stderr)

    features = build_features(enriched)
    gj = {"type": "FeatureCollection", "features": features}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_GEOJSON, "w") as f:
        json.dump(gj, f, indent=2)

    plss_count = sum(1 for f in features if not f["properties"]["approximate_location"])
    fallback_count = len(features) - plss_count
    print(f"\nWrote {len(features)} features to {OUTPUT_GEOJSON}")
    print(f"  • {plss_count} with PLSS-derived geometry")
    print(f"  • {fallback_count} using county fallback (approximate)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
