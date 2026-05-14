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
from pathlib import Path

HTML_PATH = Path(__file__).parent / "output" / "harmonized_visualization.html"

# ── Layer metadata in DATASET ORDER ───────────────────────────────────────────
# Index 0 = first non-tile-layer addTo call (tile layer is always index 0 in addTo list)
# Matches the DATASETS list in black_hills_harmonization.py.
# tooltip_fields: property keys to show on mouseover (vector layers only).
LAYER_META = [
    {
        "label": "Uranium Mine Sites", "icon": "☢️", "default_opacity": 0.8,
        "tooltip_fields": ["MINE_NAME", "COUNTY_NAM"],
    },
    {
        "label": "BLM Mining Claims (Active)", "icon": "⛏️", "default_opacity": 0.6,
        "tooltip_fields": ["CSE_NAME", "BLM_PROD", "CSE_DISP"],
    },
    {
        "label": "EXNI & Uranium Exploration Permits", "icon": "📋", "default_opacity": 0.9,
        "tooltip_fields": ["name", "applicant", "county", "status"],
    },
    {"label": "Land Cover 2024 (NLCD)",        "icon": "🌿", "default_opacity": 0.7},
    {"label": "Forest Loss Year (Hansen)",      "icon": "🌲", "default_opacity": 0.7},
    {"label": "Tree Cover 2000 (Hansen)",       "icon": "🌳", "default_opacity": 0.7},
    {"label": "Fire Fuel Models (FBFM40)",      "icon": "🔥", "default_opacity": 0.7},
    {
        "label": "Tribal Area Boundaries", "icon": "🏛️", "default_opacity": 0.7,
        "tooltip_fields": ["NAMELSAD"],
    },
    {
        "label": "County Boundaries", "icon": "🗺️", "default_opacity": 0.6,
        "tooltip_fields": ["NAME", "STATEFP"],
    },
    {
        "label": "State Boundaries", "icon": "🗾", "default_opacity": 0.6,
        "tooltip_fields": ["NAME"],
    },
    {
        "label": "Fire Perimeters (MTBS)", "icon": "🔴", "default_opacity": 0.7,
        "tooltip_fields": ["incid_name", "ig_date", "burnbndac"],
    },
    {"label": "Building Footprints SD", "icon": "🏠", "default_opacity": 0.6},
]


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
"""

SIDEBAR_HTML = """
<div id="layer-sidebar">
  <div id="layer-sidebar-header" onclick="toggleSidebar()">
    <span>&#128194; Layers</span>
    <span class="toggle-icon" id="sidebar-toggle-icon">&#9650;</span>
  </div>
  <div id="layer-sidebar-body">
    <div id="layer-list"></div>
  </div>
</div><!-- /layer-sidebar -->
"""


def build_sidebar_js(layer_ids: list[str], map_var: str) -> str:
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

    return f"""
<script>
/* ── Layer Sidebar (injected by inject_sidebar.py) ── */
(function() {{
  var MAP_VAR = "{map_var}";
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
      cb.checked = true;
      cb.title = 'Toggle visibility';
      (function(id) {{
        cb.addEventListener('change', function() {{
          var map = getMap(), l = getLayer(id);
          if (!map || !l) return;
          if (this.checked) {{ l.addTo(map); }} else {{ map.removeLayer(l); }}
        }});
      }})(meta.id);

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
      slider.className = 'opacity-slider';
      (function(id, lbl) {{
        slider.addEventListener('input', function() {{
          lbl.textContent = Math.round(this.value * 100) + '%';
          var l = getLayer(id);
          if (!l) return;
          var v = parseFloat(this.value);
          if (typeof l.setOpacity === 'function') {{
            l.setOpacity(v);
          }} else if (typeof l.setStyle === 'function') {{
            l.setStyle({{ opacity: v, fillOpacity: v * 0.5 }});
          }}
        }});
      }})(meta.id, opLabel);

      opRow.appendChild(opLabel);
      opRow.appendChild(slider);

      item.appendChild(row);
      item.appendChild(opRow);
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
  function init() {{
    if (!getMap()) {{ setTimeout(init, 200); return; }}
    buildSidebar();
    bindTooltips();
    reorderLayers();
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

    # 5. Inject CSS into <head>
    css_block = f"<style>\n{SIDEBAR_CSS}\n</style>\n"
    html = html.replace("</head>", css_block + "</head>", 1)

    # 6. Inject sidebar HTML div before </body>
    html = html.replace("</body>", SIDEBAR_HTML + "\n</body>", 1)

    # 7. Inject sidebar JS at the VERY END of the file.
    # IMPORTANT: Folium places its large data <script> blocks AFTER </body>.
    # If we inject before </body>, our init() runs before those scripts execute
    # and window[layerVar] is still undefined. Appending to the end of the file
    # guarantees all layer globals exist when our code runs.
    sidebar_js = build_sidebar_js(layer_ids, map_var)
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
