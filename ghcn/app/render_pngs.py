#!/usr/bin/env python3
"""Render per-region PNGs from the folium HTML maps in ghcn/output/<region>/.

Drives a headless Chromium via Playwright: load each HTML, center the
Leaflet map for the region, wait for tiles + markers, screenshot.

Install once::

  pip3 install --user playwright
  python3 -m playwright install chromium

Usage::

  python3 render_pngs.py                  # render all regions x metrics
  python3 render_pngs.py --only world     # only the world region
  python3 render_pngs.py --only months_01 # only Jan maps (both regions)
  python3 render_pngs.py --no-headless    # show the browser (debugging)
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

# Mirror of REGIONS in climatefind/main.py — render-side only needs the
# viewport + center + zoom. Keep these in sync when adding a region.
REGIONS = {
    "conus": {"center": (38.4, -96.05), "zoom": 6, "viewport": (2640, 1430)},
    "world": {"center": (20.0, 0.0), "zoom": 4, "viewport": (2640, 1430)},
}

# Metric paths under ghcn/output/<region>/ and img/<region>/, without the
# `.OpenTopoMap.html` / `.png` suffix. Months live in their own subdir.
METRICS = [
    "average_comfy_days",
    "aug_1_tmax",
    "aug_1_tmin",
    "months/01_jan_percent_comfy",
    "months/02_feb_percent_comfy",
    "months/03_mar_percent_comfy",
    "months/04_apr_percent_comfy",
    "months/05_may_percent_comfy",
    "months/06_jun_percent_comfy",
    "months/07_jul_percent_comfy",
    "months/08_aug_percent_comfy",
    "months/09_sep_percent_comfy",
    "months/10_oct_percent_comfy",
    "months/11_nov_percent_comfy",
    "months/12_dec_percent_comfy",
]


def build_renders():
    """(region, html_path_under_output, png_path_under_img) for every render."""
    return [
        (
            region,
            f"{region}/{metric}.OpenTopoMap.html",
            f"{region}/{metric}.png",
        )
        for region in REGIONS
        for metric in METRICS
    ]


def build_set_view_js(center_lat, center_lon, zoom):
    """Build the JS that targets the folium-generated map var and reframes it."""
    return f"""
() => {{
  const mapKey = Object.keys(window).find(k => k.startsWith('map_'));
  if (!mapKey) {{ throw new Error('no map_<hash> global found'); }}
  const m = window[mapKey];
  m.setView([{center_lat}, {center_lon}], {zoom});
  // Hide the zoom controls + attribution so they don't sit in the corner of
  // the README hero shot.
  document.querySelectorAll(
    '.leaflet-control-zoom, .leaflet-control-attribution, .leaflet-control-fullscreen'
  ).forEach(el => el.style.display = 'none');
  return mapKey;
}}
"""


# Wait for at least most of the visible tiles to load. Leaflet sets a class
# `leaflet-tile-loaded` on each tile <img> once it's done.
TILES_READY_JS = """
() => {
  const tiles = document.querySelectorAll('.leaflet-tile');
  const loaded = document.querySelectorAll('.leaflet-tile-loaded');
  return tiles.length > 0 && loaded.length >= tiles.length;
}
"""


def render_one(page, html_path, png_path, set_view_js, settle_seconds):
    print(f"  loading {html_path.name}")
    page.goto(html_path.as_uri(), wait_until="domcontentloaded")
    # Folium injects the map var via a deferred script; give it a beat.
    page.wait_for_function(
        "Object.keys(window).some(k => k.startsWith('map_'))", timeout=15000
    )
    map_key = page.evaluate(set_view_js)
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
        "--no-headless",
        action="store_true",
        help="Show the browser for debugging.",
    )
    parser.add_argument(
        "--only",
        default=None,
        help=(
            "Substring filter: matches against region+metric path "
            "(e.g. 'world', 'conus/months_01', 'jun_percent')."
        ),
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=2.0,
        help="Extra wait after tiles report loaded, for markers/contour paint.",
    )
    args = parser.parse_args()

    renders = build_renders()
    if args.only:
        renders = [r for r in renders if args.only in r[1]]
        if not renders:
            print(f"no matches for --only={args.only!r}", file=sys.stderr)
            return 1

    missing = [h for (_, h, _) in renders if not (GHCN_OUTPUT / h).exists()]
    if missing:
        print("missing source HTMLs:", missing, file=sys.stderr)
        return 1

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.no_headless)
        # One context per region — viewport may differ region-to-region.
        for region, cfg in REGIONS.items():
            region_renders = [r for r in renders if r[0] == region]
            if not region_renders:
                continue
            w, h = cfg["viewport"]
            center_lat, center_lon = cfg["center"]
            set_view_js = build_set_view_js(center_lat, center_lon, cfg["zoom"])
            context = browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=1,
            )
            page = context.new_page()
            print(f"region {region} (viewport={w}x{h}, zoom={cfg['zoom']})")
            for _, html_name, png_name in region_renders:
                render_one(
                    page,
                    GHCN_OUTPUT / html_name,
                    IMG_DIR / png_name,
                    set_view_js,
                    settle_seconds=args.settle_seconds,
                )
            context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
