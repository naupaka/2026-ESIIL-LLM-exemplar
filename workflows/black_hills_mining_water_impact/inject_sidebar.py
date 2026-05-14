#!/usr/bin/env python3
"""
Post-process harmonized_visualization.html to inject a fixed sidebar with:
- Layer list (draggable to reorder z-index)
- Toggle on/off checkbox
- Opacity slider
- Hover tooltips for vector layers

Layer identification is done by POSITION in the addTo() sequence, which is
deterministic and matches the DATASETS list in black_hills_harmonization.py.

Usage:
    python inject_sidebar.py
"""

import re
import sys
from pathlib import Path

HTML_PATH = Path(__file__).parent / "output" / "harmonized_visualization.html"

# Pull the DATASETS list straight from the harmonization module so layer order
# and labels stay in lockstep with what actually gets added to the map.
sys.path.insert(0, str(Path(__file__).parent))
from black_hills_harmonization import DATASETS  # noqa: E402

# ── Per-layer UI extras (presentation only) ────────────────────────────────
# Keyed by DatasetSpec.name. These don't belong on DatasetSpec because the
# harmonizer is UI-agnostic. Datasets without an entry fall back to defaults.
# tooltip_fields: property keys to show on mouseover (vector layers only).
LAYER_UI: dict[str, dict] = {
    "uranium_mine_locations":      {"icon": "☢️", "default_opacity": 0.8,
                                    "tooltip_fields": ["MINE_NAME", "COUNTY_NAM"]},
    "blm_mining_claims_not_closed":{"icon": "⛏️", "default_opacity": 0.6,
                                    "tooltip_fields": ["CSE_NAME", "BLM_PROD", "CSE_DISP"]},
    "danr_exni_applications":      {"icon": "📋", "default_opacity": 0.9,
                                    "tooltip_fields": ["name", "applicant", "county", "status"]},
    "watersheds_huc8":             {"icon": "💧", "default_opacity": 0.5,
                                    "tooltip_fields": ["Name", "HUC8", "States"]},
    "nhd_waterbodies":             {"icon": "🏞️", "default_opacity": 0.7,
                                    "tooltip_fields": ["GNIS_Name", "FType"]},
    "nhd_flowlines":               {"icon": "🌊", "default_opacity": 0.7,
                                    "tooltip_fields": ["GNIS_Name", "FType", "LengthKM"]},
    "watersheds_huc12":            {"icon": "💧", "default_opacity": 0.4,
                                    "tooltip_fields": ["Name", "HUC12", "States"]},
    "nlcd_2024":                   {"icon": "🌿", "default_opacity": 0.7},
    "hansen_forest_loss":          {"icon": "🌲", "default_opacity": 0.7},
    "hansen_tree_cover_2000":      {"icon": "🌳", "default_opacity": 0.7},
    "fbfm40_fuel_models":          {"icon": "🔥", "default_opacity": 0.7},
    "tribal_boundaries_aiannh":    {"icon": "🏛️", "default_opacity": 0.7,
                                    "tooltip_fields": ["NAMELSAD"]},
    "county_boundaries":           {"icon": "🗺️", "default_opacity": 0.6,
                                    "tooltip_fields": ["NAME", "STATEFP"]},
    "state_boundaries":            {"icon": "🗾", "default_opacity": 0.6,
                                    "tooltip_fields": ["NAME"]},
    "mtbs_burned_areas":           {"icon": "🔴", "default_opacity": 0.7,
                                    "tooltip_fields": ["incid_name", "ig_date", "burnbndac"]},
    "building_footprints_sd":      {"icon": "🏠", "default_opacity": 0.6},
    "building_footprints_wy":      {"icon": "🏠", "default_opacity": 0.6},
}

_UI_FALLBACK = {"icon": "📊", "default_opacity": 0.7, "tooltip_fields": []}


def _build_layer_meta() -> list[dict]:
    """Build LAYER_META from DATASETS so order + labels stay synced."""
    metas: list[dict] = []
    missing: list[str] = []
    for ds in DATASETS:
        ui = LAYER_UI.get(ds.name)
        if ui is None:
            missing.append(ds.name)
            ui = {}
        metas.append({
            "label": ds.display_name or ds.name,
            "icon": ui.get("icon", _UI_FALLBACK["icon"]),
            "default_opacity": ui.get("default_opacity", _UI_FALLBACK["default_opacity"]),
            "tooltip_fields": ui.get("tooltip_fields", _UI_FALLBACK["tooltip_fields"]),
        })
    if missing:
        print(f"  Note: no LAYER_UI entry for {missing} — using defaults")
    return metas


LAYER_META = _build_layer_meta()


SIDEBAR_CSS = """
/* ── Sidebar styles ────────────────────────────────────── */
#layer-sidebar {
    position: fixed;
    top: 10px;
    right: 10px;
    z-index: 9999;
    width: 290px;
    max-height: calc(100vh - 20px);
    overflow-y: auto;
    background: rgba(255,255,255,0.97);
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 13px;
    color: #222;
    user-select: none;
}
#layer-sidebar-header {
    padding: 10px 14px 8px;
    background: #2c3e50;
    color: #fff;
    border-radius: 10px 10px 0 0;
    font-weight: 700;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
}
#layer-sidebar-header .toggle-icon {
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
}
#layer-sidebar-body { padding: 4px 0 6px; }
#basemap-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px 8px;
    border-bottom: 1px solid #eee;
    font-size: 11px;
    color: #666;
    background: #fafafa;
}
#basemap-row .basemap-label { flex-grow: 1; font-weight: 500; }
.basemap-btn {
    flex-shrink: 0;
    padding: 3px 8px;
    border: 1px solid #ccc;
    background: #fff;
    border-radius: 3px;
    font-size: 11px;
    cursor: pointer;
    color: #333;
}
.basemap-btn.active {
    background: #2980b9;
    color: #fff;
    border-color: #2471a3;
}
.layer-item {
    padding: 5px 10px 5px 6px;
    border-bottom: 1px solid #f0f0f0;
    cursor: grab;
    transition: background 0.12s;
}
.layer-item:last-child { border-bottom: none; }
.layer-item:hover { background: #f5f8fc; }
.layer-item.dragging { opacity: 0.35; cursor: grabbing; }
.layer-item.drag-over {
    background: #ddeeff;
    box-shadow: inset 0 2px 0 #3498db;
}
.layer-row {
    display: flex;
    align-items: center;
    gap: 5px;
}
.drag-handle { color: #bbb; font-size: 14px; flex-shrink: 0; line-height: 1; }
.layer-icon  { flex-shrink: 0; font-size: 14px; }
.layer-label { flex-grow: 1; font-size: 12px; line-height: 1.3; font-weight: 500; }
.layer-toggle {
    flex-shrink: 0;
    width: 15px; height: 15px;
    cursor: pointer;
    accent-color: #2980b9;
}
.opacity-row {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 0 0 24px;
}
.opacity-label { font-size: 10px; color: #999; width: 28px; text-align: right; }
.opacity-slider {
    flex-grow: 1;
    height: 3px;
    cursor: pointer;
    accent-color: #2980b9;
}
.color-row {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 2px 0 0 24px;
    font-size: 10px;
    color: #999;
}
.color-row .color-label { flex-grow: 1; }
.color-picker {
    width: 22px; height: 14px;
    border: 1px solid #ccc;
    border-radius: 2px;
    cursor: pointer;
    padding: 0;
    background: transparent;
}
"""

SIDEBAR_HTML = """
<div id="layer-sidebar">
  <div id="layer-sidebar-header" onclick="toggleSidebar()">
    <span>&#128194; Layers</span>
    <span class="toggle-icon" id="sidebar-toggle-icon">&#9650;</span>
  </div>
  <div id="layer-sidebar-body">
    <div id="basemap-row">
      <span class="basemap-label">Basemap</span>
      <button type="button" class="basemap-btn active" data-basemap="light">Light</button>
      <button type="button" class="basemap-btn" data-basemap="sat">Satellite</button>
    </div>
    <div id="layer-list"></div>
  </div>
</div><!-- /layer-sidebar -->
"""


def tag_legend_swatches(html: str, vector_pairs: list[tuple[str, str]]) -> tuple[str, int]:
    """Tag the harmonizer's vector legend rows with data-legend-layer="<jsvar>".

    Lets the sidebar color picker locate and recolor the legend swatch when
    a user changes a vector layer's color, keeping the legend in sync.

    Returns (modified_html, count_of_tagged_rows).
    """
    # The harmonizer emits one row like:
    #   <div style="display:flex;align-items:center;margin:3px 0;">
    #     <i style="background:#XXXXXX;width:12px;height:12px;...">
    #     </i> Display Name
    #   </div>
    # We match each row by its trailing label text — that's the only signal
    # tying a legend row back to a specific layer.
    tagged = 0
    for js_var, label in vector_pairs:
        pattern = re.compile(
            r'<div(\s+style="display:flex;align-items:center;margin:3px 0;">'
            r'<i style="background:#[0-9a-fA-F]{3,6}[^"]*"></i>\s*'
            + re.escape(label)
            + r'</div>)'
        )
        new_html, n = pattern.subn(
            rf'<div data-legend-layer="{js_var}"\1',
            html, count=1,
        )
        if n:
            html = new_html
            tagged += 1
    return html, tagged


def find_positron_tile_var(html: str) -> str | None:
    """Find the JS var name of Folium's Positron base tile layer.

    The harmonizer emits exactly one CartoDB Positron L.tileLayer call; we
    grab its variable so the sidebar can hide/show it when the user picks
    the satellite basemap instead.
    """
    m = re.search(
        r"(tile_layer_[a-f0-9]+)\s*=\s*L\.tileLayer\(\s*\"https://\{s\}\.basemaps\.cartocdn\.com/light_all",
        html,
    )
    return m.group(1) if m else None


def build_sidebar_js(layer_ids: list[str], map_var: str, positron_var: str | None = None) -> str:
    """Build the sidebar JS, embedding the actual layer variable names from this HTML."""
    js_layers = []
    for i, var in enumerate(layer_ids):
        meta = LAYER_META[i]
        tooltip_fields = meta.get("tooltip_fields", [])
        js_layers.append(
            "  {{id:{id!r}, label:{label!r}, icon:{icon!r}, op:{op}, tip:{tip}}}".format(
                id=var,
                label=meta["label"],
                icon=meta["icon"],
                op=meta["default_opacity"],
                tip=str(tooltip_fields).replace("'", '"'),
            )
        )
    layers_js = "[\n" + ",\n".join(js_layers) + "\n]"

    positron_js = f'"{positron_var}"' if positron_var else "null"
    return f"""
<script>
/* ── Layer Sidebar (injected by inject_sidebar.py) ── */
(function() {{
  var MAP_VAR = "{map_var}";
  var POSITRON_VAR = {positron_js};
  var LAYERS  = {layers_js};
  var dragSrcEl = null;

  function getMap()      {{ return window[MAP_VAR]; }}
  function getLayer(id)  {{ return window[id]; }}

  function buildSidebar() {{
    var list = document.getElementById('layer-list');
    if (!list) return;
    list.innerHTML = '';

    LAYERS.forEach(function(meta) {{
      var lyr = getLayer(meta.id);
      if (!lyr) {{ console.warn('Sidebar: layer not found:', meta.id); return; }}

      var item = document.createElement('div');
      item.className = 'layer-item';
      item.draggable = true;
      item.dataset.id = meta.id;

      // drag & drop
      item.addEventListener('dragstart', function(e) {{
        dragSrcEl = this;
        setTimeout(function() {{ item.classList.add('dragging'); }}, 0);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', this.dataset.id);
      }});
      item.addEventListener('dragend', function() {{
        this.classList.remove('dragging');
        document.querySelectorAll('.layer-item').forEach(function(el) {{
          el.classList.remove('drag-over');
        }});
        reorderLayers();
      }});
      item.addEventListener('dragover', function(e) {{
        e.preventDefault();
        document.querySelectorAll('.layer-item').forEach(function(el) {{
          el.classList.remove('drag-over');
        }});
        this.classList.add('drag-over');
      }});
      item.addEventListener('dragleave', function() {{
        this.classList.remove('drag-over');
      }});
      item.addEventListener('drop', function(e) {{
        e.stopPropagation();
        this.classList.remove('drag-over');
        if (dragSrcEl && dragSrcEl !== this) {{
          var items = Array.from(list.querySelectorAll('.layer-item'));
          var fromIdx = items.indexOf(dragSrcEl);
          var toIdx   = items.indexOf(this);
          if (fromIdx < toIdx) {{ list.insertBefore(dragSrcEl, this.nextSibling); }}
          else                 {{ list.insertBefore(dragSrcEl, this); }}
        }}
      }});

      // label row
      var row = document.createElement('div');
      row.className = 'layer-row';

      var handle = document.createElement('span');
      handle.className = 'drag-handle';
      handle.innerHTML = '&#8942;&#8942;';
      handle.title = 'Drag to reorder';

      var iconEl = document.createElement('span');
      iconEl.className = 'layer-icon';
      iconEl.textContent = meta.icon;

      var labelEl = document.createElement('span');
      labelEl.className = 'layer-label';
      labelEl.textContent = meta.label;

      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'layer-toggle';
      cb.checked = false;
      cb.title = 'Toggle visibility';
      // Hide via opacity rather than removeLayer/addTo: re-adding a GeoJson
      // layer in Leaflet 1.x doesn't reliably re-attach its SVG paths, so
      // toggled layers would silently fail to render.
      function applyOpacity(l, op) {{
        if (!l) return;
        if (typeof l.setOpacity === 'function') {{
          l.setOpacity(op);
        }} else if (typeof l.setStyle === 'function') {{
          l.setStyle({{ opacity: op, fillOpacity: op * 0.5 }});
        }}
      }}
      (function(id, sliderId) {{
        cb.addEventListener('change', function() {{
          var l = getLayer(id);
          var sl = document.getElementById(sliderId);
          var v = sl ? parseFloat(sl.value) : 1;
          applyOpacity(l, this.checked ? v : 0);
        }});
      }})(meta.id, 'sl_' + meta.id);
      // Default to off — hide every layer once at init.
      applyOpacity(getLayer(meta.id), 0);

      row.appendChild(handle);
      row.appendChild(iconEl);
      row.appendChild(labelEl);
      row.appendChild(cb);

      // opacity row
      var opRow = document.createElement('div');
      opRow.className = 'opacity-row';

      var opLabel = document.createElement('span');
      opLabel.className = 'opacity-label';
      opLabel.textContent = Math.round(meta.op * 100) + '%';

      var slider = document.createElement('input');
      slider.type = 'range';
      slider.min = 0; slider.max = 1; slider.step = 0.05;
      slider.value = meta.op;
      slider.id = 'sl_' + meta.id;
      slider.className = 'opacity-slider';
      (function(id, lbl, chkbox) {{
        slider.addEventListener('input', function() {{
          lbl.textContent = Math.round(this.value * 100) + '%';
          // Slider only affects the map when the layer's checkbox is on.
          if (!chkbox.checked) return;
          applyOpacity(getLayer(id), parseFloat(this.value));
        }});
      }})(meta.id, opLabel, cb);

      opRow.appendChild(opLabel);
      opRow.appendChild(slider);

      item.appendChild(row);
      item.appendChild(opRow);

      // Color picker — only for vector layers (rasters don't support setStyle).
      if (typeof lyr.setStyle === 'function') {{
        var sampleFeat = (typeof lyr.getLayers === 'function') ? lyr.getLayers()[0] : null;
        var initialColor = (sampleFeat && sampleFeat.options && sampleFeat.options.color) || '#3186cc';
        var colorRow = document.createElement('div');
        colorRow.className = 'color-row';
        var colorLabel = document.createElement('span');
        colorLabel.className = 'color-label';
        colorLabel.textContent = 'Color';
        var colorPicker = document.createElement('input');
        colorPicker.type = 'color';
        colorPicker.className = 'color-picker';
        colorPicker.value = initialColor;
        colorPicker.title = 'Change layer color';
        (function(id) {{
          colorPicker.addEventListener('input', function() {{
            var l = getLayer(id);
            if (!l || typeof l.setStyle !== 'function') return;
            l.setStyle({{ color: this.value, fillColor: this.value }});
            // Keep the static legend swatch in sync.
            var swatch = document.querySelector(
              '[data-legend-layer="' + id + '"] i'
            );
            if (swatch) swatch.style.background = this.value;
          }});
        }})(meta.id);
        colorRow.appendChild(colorLabel);
        colorRow.appendChild(colorPicker);
        item.appendChild(colorRow);
      }}

      list.appendChild(item);
    }});
  }}

  function bindTooltips() {{
    LAYERS.forEach(function(meta) {{
      if (!meta.tip || !meta.tip.length) return;
      var lyr = getLayer(meta.id);
      if (!lyr || typeof lyr.eachLayer !== 'function') return;
      lyr.eachLayer(function(l) {{
        var p = l.feature && l.feature.properties;
        if (!p) return;
        var lines = meta.tip
          .filter(function(f) {{ return p[f] != null && p[f] !== 'None' && p[f] !== ''; }})
          .map(function(f) {{ return '<b>' + f + ':</b> ' + p[f]; }});
        if (lines.length) {{
          l.bindTooltip(lines.join('<br>'), {{ sticky: true, opacity: 0.92 }});
        }}
      }});
    }});
  }}

  function reorderLayers() {{
    var map = getMap();
    if (!map) return;
    var listEl = document.getElementById('layer-list');
    if (!listEl) return;
    var items = Array.from(listEl.querySelectorAll('.layer-item'));
    for (var i = items.length - 1; i >= 0; i--) {{
      var l = getLayer(items[i].dataset.id);
      if (l && map.hasLayer(l) && typeof l.bringToFront === 'function') {{
        l.bringToFront();
      }}
    }}
  }}

  window.toggleSidebar = function() {{
    var body = document.getElementById('layer-sidebar-body');
    var icon = document.getElementById('sidebar-toggle-icon');
    if (body.style.display === 'none') {{
      body.style.display = ''; icon.innerHTML = '&#9650;';
    }} else {{
      body.style.display = 'none'; icon.innerHTML = '&#9660;';
    }}
  }};

  // Because this script is placed AFTER all Folium data scripts at the end of
  // the HTML file, all layer globals are already defined by the time we run.
  // We still defer with setTimeout to let the browser finish layout.
  // Esri World Imagery — created lazily on first switch to satellite.
  var satLayer = null;
  function getSatLayer() {{
    if (!satLayer) {{
      satLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}",
        {{
          attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
          maxZoom: 19,
        }}
      );
    }}
    return satLayer;
  }}

  function setBasemap(which) {{
    var map = getMap();
    if (!map) return;
    var positron = POSITRON_VAR ? window[POSITRON_VAR] : null;
    var sat = getSatLayer();
    if (which === 'sat') {{
      if (positron && map.hasLayer(positron)) map.removeLayer(positron);
      if (!map.hasLayer(sat)) sat.addTo(map);
    }} else {{
      if (map.hasLayer(sat)) map.removeLayer(sat);
      if (positron && !map.hasLayer(positron)) positron.addTo(map);
    }}
    // Keep base map at the bottom of the stack.
    if (positron && positron.bringToBack) positron.bringToBack();
    if (sat.bringToBack) sat.bringToBack();
    // Toggle button active state.
    document.querySelectorAll('.basemap-btn').forEach(function(btn) {{
      btn.classList.toggle('active', btn.dataset.basemap === which);
    }});
  }}

  function wireBasemapButtons() {{
    document.querySelectorAll('.basemap-btn').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        setBasemap(this.dataset.basemap);
      }});
    }});
  }}

  function init() {{
    if (!getMap()) {{ setTimeout(init, 200); return; }}
    buildSidebar();
    bindTooltips();
    wireBasemapButtons();
    // No reorderLayers() on init — Folium's addTo order is already correct,
    // and bringToFront() on dense vector layers (NHD flowlines, HUC-12) is
    // slow enough to trigger the browser's slow-script dialog.
  }}

  // The script runs after </html>, so readyState is always 'complete'.
  // Use a small timeout to ensure Leaflet has fully initialized.
  setTimeout(init, 300);
}})();
</script>
"""


def inject_sidebar(html: str) -> str:
    # 1. Remove the old inline "Data Layers" control panel generated by the harmonizer.
    # The new sidebar replaces it; strip it every time so re-runs stay clean.
    html = _remove_element(html, '<div style="position:fixed; top:80px; right:10px;')

    # 2. Strip Folium's layer-level bindTooltip calls (generic label-only tooltips).
    # These conflict with the per-feature tooltips bound by bindTooltips() below.
    html = re.sub(
        r'\s+geo_json_[a-f0-9]+\.bindTooltip\(\s*`<div>.*?</div>`.*?\);',
        '',
        html,
        flags=re.DOTALL,
    )

    # 3. Find the map variable name
    map_match = re.search(r'var (map_[a-f0-9]+) = L\.map\(', html)
    if not map_match:
        raise RuntimeError("Could not find Leaflet map variable in HTML")
    map_var = map_match.group(1)
    print(f"  Map variable: {map_var}")

    # 4. Get ALL layer vars in addTo order (skip tile_layer which is the base)
    all_adds = re.findall(
        rf'((?:geo_json|image_overlay|tile_layer)_[a-f0-9]+)\.addTo\({re.escape(map_var)}\)',
        html,
    )
    # Drop tile_layer (base map tile)
    layer_ids = [v for v in all_adds if not v.startswith("tile_layer")]
    print(f"  Found {len(layer_ids)} data layers (expected {len(LAYER_META)})")

    if len(layer_ids) != len(LAYER_META):
        print(f"  WARNING: layer count mismatch — found {len(layer_ids)}, expected {len(LAYER_META)}")
        n = min(len(layer_ids), len(LAYER_META))
        layer_ids = layer_ids[:n]

    for i, var in enumerate(layer_ids):
        print(f"    {i:2d}. {var[:50]}  →  {LAYER_META[i]['label']}")

    # 5. Tag the legend's vector swatches so the color picker can keep them in sync.
    vector_pairs = [
        (var, LAYER_META[i]["label"])
        for i, var in enumerate(layer_ids)
        if var.startswith("geo_json_")
    ]
    html, tagged = tag_legend_swatches(html, vector_pairs)
    print(f"  Tagged {tagged}/{len(vector_pairs)} legend swatches for color sync")

    # 6. Inject CSS into <head>
    css_block = f"<style>\n{SIDEBAR_CSS}\n</style>\n"
    html = html.replace("</head>", css_block + "</head>", 1)

    # 6. Inject sidebar HTML div before </body>
    html = html.replace("</body>", SIDEBAR_HTML + "\n</body>", 1)

    # 7. Inject sidebar JS at the VERY END of the file.
    # IMPORTANT: Folium places its large data <script> blocks AFTER </body>.
    # If we inject before </body>, our init() runs before those scripts execute
    # and window[layerVar] is still undefined. Appending to the end of the file
    # guarantees all layer globals exist when our code runs.
    positron_var = find_positron_tile_var(html)
    if positron_var:
        print(f"  Positron base layer: {positron_var}")
    else:
        print("  WARNING: could not find Positron tile var; basemap toggle will skip the light layer")
    sidebar_js = build_sidebar_js(layer_ids, map_var, positron_var)
    html = html.rstrip() + "\n" + sidebar_js + "\n"

    return html


def _remove_element(html: str, tag_prefix: str) -> str:
    """Remove all <div ...>...</div> whose opening tag starts with tag_prefix, depth-aware."""
    result = html
    while True:
        idx = result.find(tag_prefix)
        if idx == -1:
            break
        tag_end = result.find('>', idx)
        if tag_end == -1:
            break
        pos = tag_end + 1
        depth = 1
        while pos < len(result) and depth > 0:
            open_pos = result.find('<div', pos)
            close_pos = result.find('</div>', pos)
            if close_pos == -1:
                break
            if open_pos != -1 and open_pos < close_pos:
                depth += 1
                pos = open_pos + 4
            else:
                depth -= 1
                if depth == 0:
                    end_pos = close_pos + 6
                    trim_start = idx
                    while trim_start > 0 and result[trim_start - 1] in ' \t\r\n':
                        trim_start -= 1
                    result = result[:trim_start] + result[end_pos:]
                    break
                pos = close_pos + 6
    return result


def _remove_div_by_id(html: str, div_id: str) -> str:
    """Remove all <div id="div_id">...</div> occurrences, correctly handling nested divs."""
    return _remove_element(html, f'<div id="{div_id}">')


def strip_old_injection(html: str) -> str:
    """Remove a previous sidebar injection so we don't double-inject."""
    # 1. Remove injected CSS block
    html = re.sub(r'<style>\s*/\* ── Sidebar styles.*?</style>\s*', '', html, flags=re.DOTALL)

    # 2. Remove sidebar div — new format (sentinel comment at end)
    html = re.sub(r'\s*<div id="layer-sidebar">.*?</div><!-- /layer-sidebar -->\s*', '', html, flags=re.DOTALL)

    # 3. Remove sidebar div — old format (no sentinel); use depth-aware removal
    html = _remove_div_by_id(html, 'layer-sidebar')

    # 4. Remove any orphaned layer-sidebar-body / layer-list fragments left by bad prior strips
    html = _remove_div_by_id(html, 'layer-sidebar-body')
    html = _remove_div_by_id(html, 'layer-list')

    # 5. Remove sidebar JS — new format
    html = re.sub(
        r'\s*<script>\s*/\* ── Layer Sidebar \(injected.*?</script>\s*',
        '', html, flags=re.DOTALL,
    )

    # 6. Remove sidebar JS — old format (uses var _mapVar)
    html = re.sub(
        r'\s*<script>\s*\(function\(\)\s*\{[\s\S]*?var _mapVar\s*=[\s\S]*?</script>\s*',
        '', html, flags=re.DOTALL,
    )

    # 7. Strip any prior legend-row tags so they can be re-applied cleanly.
    html = re.sub(r' data-legend-layer="[^"]*"', '', html)

    return html


def main():
    print(f"Reading {HTML_PATH}")
    html = HTML_PATH.read_text(encoding="utf-8")

    if 'id="layer-sidebar"' in html:
        print("  Stripping previous sidebar injection...")
        html = strip_old_injection(html)

    original_size = len(html)
    html_out = inject_sidebar(html)
    new_size = len(html_out)

    HTML_PATH.write_text(html_out, encoding="utf-8")
    print(f"Wrote {HTML_PATH}")
    print(f"  Size: {original_size:,} → {new_size:,} bytes (+{new_size-original_size:,})")
    print("Done.")


if __name__ == "__main__":
    main()
