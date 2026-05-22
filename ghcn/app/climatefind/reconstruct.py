#!/usr/bin/env python3
"""Rebuild ghcn/spool/comfy/year.csv from the checked-in output HTML files.

The original CSV was gitignored and is no longer on disk, but every per-metric
folium map embeds one CircleMarker per weather station whose bindTooltip text
carries the station id/name/state/lat/lon/elev_m plus that metric's value.
Joining all 15 metric files on station id reconstructs the columns needed by
``make_folium_elevation_map``.

Run from the climatefind app dir::

  python -m climatefind.reconstruct
"""

import argparse
import pathlib
import re
import sys

import pandas

THIS_DIR = pathlib.Path(__file__).resolve().parent
GHCN_DIR = THIS_DIR.parent.parent
OUTPUT_DIR = GHCN_DIR / "output"
SPOOL_CSV = GHCN_DIR / "spool" / "comfy" / "year.csv"

# {metric column in year.csv: source HTML basename}
METRIC_FILES = {
    "average_comfy_days": "average_comfy_days.Stamen_Terrain.html",
    "aug_1_tmax": "aug_1_tmax.Stamen_Terrain.html",
    "aug_1_tmin": "aug_1_tmin.Stamen_Terrain.html",
    "jan_percent_comfy": "jan_percent_comfy.Stamen_Terrain.html",
    "feb_percent_comfy": "feb_percent_comfy.Stamen_Terrain.html",
    "mar_percent_comfy": "mar_percent_comfy.Stamen_Terrain.html",
    "apr_percent_comfy": "apr_percent_comfy.Stamen_Terrain.html",
    "may_percent_comfy": "may_percent_comfy.Stamen_Terrain.html",
    "jun_percent_comfy": "jun_percent_comfy.Stamen_Terrain.html",
    "jul_percent_comfy": "jul_percent_comfy.Stamen_Terrain.html",
    "aug_percent_comfy": "aug_percent_comfy.Stamen_Terrain.html",
    "sep_percent_comfy": "sep_percent_comfy.Stamen_Terrain.html",
    "oct_percent_comfy": "oct_percent_comfy.Stamen_Terrain.html",
    "nov_percent_comfy": "nov_percent_comfy.Stamen_Terrain.html",
    "dec_percent_comfy": "dec_percent_comfy.Stamen_Terrain.html",
}

# Tooltip body inside `<div>...</div>` looks like:
#   USW00027516 UTQIA VIK FORMERLY BARROW 4 ENE, AK US 71.3213,-156.611 @ 4.6m @ 17.28 days/year
# The station name may contain commas, so anchor on the trailing
# `, <STATE> US <LAT>,<LON> @ <ELEV>m @ <VALUE> <UNIT>` portion.
TOOLTIP_RE = re.compile(
    r"(?P<id>\S+)\s+"
    r"(?P<name>.+?), "
    r"(?P<state>[A-Z]{2}) US\s+"
    r"(?P<lat>-?\d+(?:\.\d+)?),"
    r"(?P<lon>-?\d+(?:\.\d+)?)\s+@\s+"
    r"(?P<elev_m>-?\d+(?:\.\d+)?)m\s+@\s+"
    r"(?P<value>-?\d+(?:\.\d+)?)"
    r"(?:\s+\S.*)?"
)

# Capture the bindTooltip(`<div>...</div>`) body. Tooltips span multiple lines
# in the rendered HTML, so use DOTALL.
BIND_RE = re.compile(
    r"\.bindTooltip\(\s*`<div>\s*(?P<body>.+?)\s*</div>`",
    re.DOTALL,
)


def parse_html(path):
    """Yield (id, name, state, lat, lon, elev_m, value) for each marker in *path*."""
    with open(path, encoding="utf-8") as f:
        html = f.read()
    for bind_match in BIND_RE.finditer(html):
        body = re.sub(r"\s+", " ", bind_match.group("body")).strip()
        m = TOOLTIP_RE.match(body)
        if not m:
            continue
        # Keep ``name`` byte-identical to the upstream GHCN station name
        # (``<NAME>, <STATE> US``) so regenerated tooltips match the originals.
        yield {
            "id": m.group("id"),
            "name": f"{m.group('name')}, {m.group('state')} US",
            "state": m.group("state"),
            "lat": float(m.group("lat")),
            "lon": float(m.group("lon")),
            "elev_m": float(m.group("elev_m")),
            "value": float(m.group("value")),
        }


def build_frame(metric_files, output_dir):
    master_metric, master_basename = next(iter(metric_files.items()))
    master_rows = list(parse_html(output_dir / master_basename))
    if not master_rows:
        raise RuntimeError(f"No markers parsed from {master_basename}")
    df = pandas.DataFrame(master_rows).rename(columns={"value": master_metric})
    df = df.drop_duplicates(subset="id", keep="first")

    for metric, basename in list(metric_files.items())[1:]:
        path = output_dir / basename
        if not path.exists():
            print(f"  skip {metric}: {basename} missing", file=sys.stderr)
            continue
        rows = list(parse_html(path))
        if not rows:
            print(f"  skip {metric}: no markers in {basename}", file=sys.stderr)
            continue
        metric_df = (
            pandas.DataFrame(rows)[["id", "value"]]
            .rename(columns={"value": metric})
            .drop_duplicates(subset="id", keep="first")
        )
        df = df.merge(metric_df, on="id", how="left")
        print(f"  merged {metric} ({len(rows)} markers)")

    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Directory containing the .Stamen_Terrain.html source files.",
    )
    parser.add_argument(
        "--out",
        default=str(SPOOL_CSV),
        help="Path to write the reconstructed year.csv.",
    )
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    out_path = pathlib.Path(args.out)

    print(f"Reconstructing {out_path} from {output_dir}")
    df = build_frame(METRIC_FILES, output_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # spool_year_summary_csv writes with the default index (an integer file_num).
    # Preserve that shape so downstream readers don't have to change.
    df.to_csv(out_path)
    print(f"Wrote {len(df)} rows, {len(df.columns)} columns -> {out_path}")


if __name__ == "__main__":
    main()
