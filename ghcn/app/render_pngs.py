#!/usr/bin/env python3
"""Render CONUS-zoomed PNGs from the folium HTML maps in ghcn/output/.

Drives a headless Chromium via Playwright: load each HTML, center the
Leaflet map on the continental US, wait for tiles + markers, screenshot.

Install once::

  pip3 install --user playwright
  python3 -m playwright install chromium

Usage::

  python3 render_pngs.py             # render all 13 maps to img/
  python3 render_pngs.py --no-headless   # show the browser (debugging)
"""

import argparse
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

THIS_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent
GHCN_OUTPUT = REPO_ROOT / "ghcn" / "output"
IMG_DIR = REPO_ROOT / "img"

# (path under ghcn/output/, path under img/)
RENDERS = [
    ("average_comfy_days.OpenTopoMap.html", "ghcn_average_comfy_days.png"),
    ("months/01_jan_percent_comfy.OpenTopoMap.html", "months/01_jan_percent_comfy.png"),
    ("months/02_feb_percent_comfy.OpenTopoMap.html", "months/02_feb_percent_comfy.png"),
    ("months/03_mar_percent_comfy.OpenTopoMap.html", "months/03_mar_percent_comfy.png"),
    ("months/04_apr_percent_comfy.OpenTopoMap.html", "months/04_apr_percent_comfy.png"),
    ("months/05_may_percent_comfy.OpenTopoMap.html", "months/05_may_percent_comfy.png"),
    ("months/06_jun_percent_comfy.OpenTopoMap.html", "months/06_jun_percent_comfy.png"),
    ("months/07_jul_percent_comfy.OpenTopoMap.html", "months/07_jul_percent_comfy.png"),
    ("months/08_aug_percent_comfy.OpenTopoMap.html", "months/08_aug_percent_comfy.png"),
    ("months/09_sep_percent_comfy.OpenTopoMap.html", "months/09_sep_percent_comfy.png"),
    ("months/10_oct_percent_comfy.OpenTopoMap.html", "months/10_oct_percent_comfy.png"),
    ("months/11_nov_percent_comfy.OpenTopoMap.html", "months/11_nov_percent_comfy.png"),
    ("months/12_dec_percent_comfy.OpenTopoMap.html", "months/12_dec_percent_comfy.png"),
]

# Viewport ratio matches the existing PNGs (~1.83:1) at 2x density for sharp
# README rendering. CONUS center/zoom chosen to fit the lower 48.
VIEWPORT_W = 2400
VIEWPORT_H = 1300
CONUS_CENTER_LAT = 39.5
CONUS_CENTER_LON = -97.5
CONUS_ZOOM = 5

# Folium auto-generates a global `map_<hash>` for each map. Find it and set
# the view, then wait for tile + contour layers to settle.
SET_VIEW_JS = f"""
() => {{
  const mapKey = Object.keys(window).find(k => k.startsWith('map_'));
  if (!mapKey) {{ throw new Error('no map_<hash> global found'); }}
  const m = window[mapKey];
  m.setView([{CONUS_CENTER_LAT}, {CONUS_CENTER_LON}], {CONUS_ZOOM});
  // Hide the zoom controls + attribution so they don't sit in the corner of
  // the README hero shot.
  document.querySelectorAll(
    '.leaflet-control-zoom, .leaflet-control-attribution, .leaflet-control-fullscreen'
  ).forEach(el => el.style.display = 'none');
  return mapKey;
}}
"""

# Wait for at least most of the visible tiles to load. Leaflet sets a class
# `leaflet-tile-loaded` on each tile <img> once it's done. We poll for a
# stable count.
TILES_READY_JS = """
() => {
  const tiles = document.querySelectorAll('.leaflet-tile');
  const loaded = document.querySelectorAll('.leaflet-tile-loaded');
  return tiles.length > 0 && loaded.length >= tiles.length;
}
"""


def render_one(page, html_path, png_path, settle_seconds):
    print(f"  loading {html_path.name}")
    page.goto(html_path.as_uri(), wait_until="domcontentloaded")
    # Folium injects the map var via a deferred script; give it a beat.
    page.wait_for_function(
        "Object.keys(window).some(k => k.startsWith('map_'))", timeout=15000
    )
    map_key = page.evaluate(SET_VIEW_JS)
    print(f"    set view via {map_key}; waiting for tiles")
    try:
        page.wait_for_function(TILES_READY_JS, timeout=60000)
    except Exception:
        print("    warning: tile-loaded check timed out; screenshotting anyway")
    # Even after tiles report loaded, give CircleMarkers + contour overlay a
    # moment to finish painting.
    time.sleep(settle_seconds)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(png_path), full_page=False, omit_background=False)
    print(f"    wrote {png_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-headless", action="store_true", help="Show the browser for debugging."
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Render only the HTMLs whose basename contains this substring (e.g. 'months_01').",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=2.0,
        help="Extra wait after tiles report loaded, for markers/contour paint.",
    )
    args = parser.parse_args()

    renders = RENDERS
    if args.only:
        renders = [r for r in RENDERS if args.only in r[0]]
        if not renders:
            print(f"no matches for --only={args.only!r}", file=sys.stderr)
            return 1

    missing = [h for (h, _) in renders if not (GHCN_OUTPUT / h).exists()]
    if missing:
        print("missing source HTMLs:", missing, file=sys.stderr)
        return 1

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.no_headless)
        context = browser.new_context(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            device_scale_factor=1,
        )
        page = context.new_page()
        for html_name, png_name in renders:
            render_one(
                page,
                GHCN_OUTPUT / html_name,
                IMG_DIR / png_name,
                settle_seconds=args.settle_seconds,
            )
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
