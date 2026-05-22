# Running the GHCN pipeline from scratch

Recipe for taking the raw NOAA GHCN daily-summaries archive and producing the
15 interactive `*.OpenTopoMap.html` maps under `ghcn/output/`.

> Status: **work in progress.** Steps marked "unverified" haven't been
> end-to-end tested yet in this environment. Update this doc as we go.

## Prerequisites

- ~200 GB free disk (extracted archive is ~144 GB; tarball adds another 7.4 GB)
- Python 3 with `pandas`, `folium`, `scipy`, `matplotlib`, `geojsoncontour`, `branca`, `PyYAML`
- Linux/macOS shell (instructions assume bash, paths assume the repo lives at `/home/dev/git/cf`)

## Happy path

1. **Download the GHCN daily-summaries archive.** ~7.4 GB compressed.

   ```bash
   mkdir -p ghcn/input/queue
   cd ghcn/input/queue
   curl -fL --retry 5 --retry-delay 10 \
     -O https://www.ncei.noaa.gov/data/daily-summaries/archive/daily-summaries-latest.tar.gz
   ```

2. **Extract.** Produces ~125k per-station CSVs (`<STATION_ID>.csv`). Slow on WSL2 — single-threaded gzip + many small files.

   ```bash
   tar xzf daily-summaries-latest.tar.gz
   rm daily-summaries-latest.tar.gz   # optional, frees 7.4 GB
   cd -
   ```

3. **Run the pipeline.** From the repo root:

   ```bash
   cd ghcn/app
   python3 -m climatefind.main --full-pipeline
   ```

   This walks `ghcn/input/queue/*.csv`, writes per-station intermediates to
   `ghcn/spool/{meta,tmin,tmax,year}/`, then a summary `ghcn/spool/comfy/year.csv`,
   then renders 15 `*.OpenTopoMap.html` files into `ghcn/output/`.

   Without `--full-pipeline`, `main()` stops after the spool stage (no
   `year.csv`, no maps). With `--regenerate-maps`, it only re-renders maps
   from an existing `year.csv` and skips ingest entirely.

   **Parallelism:** `--jobs N` controls the worker pool (default
   `cpu_count - 1`). Stages 1, 2, and 4 are CPU-parallel via
   `concurrent.futures.ProcessPoolExecutor`. On a 16-core WSL2 box this
   typically cuts the full pipeline from ~2-3 h to ~15-20 min.

4. **Verify the outputs.** Open `ghcn/output/average_comfy_days.OpenTopoMap.html`
   in a browser — should show terrain tiles with a contour overlay and ~16k
   station markers across the US.

## Caveats

- **`spool/` is mostly gitignored** (~500 MB of per-station JSON). Only
  `spool/comfy/year.csv` is committed (see `ghcn/.gitignore`). Losing the
  spool is recoverable; losing `year.csv` is recoverable from the rendered
  HTMLs via `climatefind/reconstruct.py`.
- **Non-US stations are silently dropped** — `get_state_from_csv` returns
  empty for stations whose `NAME` doesn't end in `, XX US`.
- **WSL2 tar extraction is slow** — expect 30–90 min for the extract step.
  CPU sits at ~100% on one core (gzip) and iowait climbs.
- **Map regen alone** (skipping ingest) is `python -m climatefind.main --regenerate-maps`,
  which requires only `ghcn/spool/comfy/year.csv` to be present.
- ~~**`time.sleep(300)` at the top of `main()`** — legacy throttle; remove or
  comment out for interactive runs.~~ Removed.

## Verification checkpoints

| After step | Expected state                                                                 |
|------------|--------------------------------------------------------------------------------|
| 1          | `ghcn/input/queue/daily-summaries-latest.tar.gz` exists, ~7.4 GB              |
| 2          | `ghcn/input/queue/` has ~132k `*.csv` files, ~144 GB                           |
| 3 (ingest) | `ghcn/spool/comfy/year.csv` regenerated with ~16k rows                         |
| 3 (render) | 15 `*.OpenTopoMap.html` files in `ghcn/output/`, each ~22 MB                   |
| 4          | Average-comfy-days map renders with OpenTopoMap tiles + contours + markers     |

## Extra info

### What's in the archive

Each station CSV in `daily-summaries-latest.tar.gz` has columns:
`STATION, DATE, LATITUDE, LONGITUDE, ELEVATION, NAME, TMAX, TMIN, ...`.
`main.py` only reads the first six in `read_usa_ghcn_file_meta` (line 593) and
adds `TMAX`/`TMIN` for the year-completion check (line 678).

### Reference files in `ghcn/doc/`

`ghcnd-stations.txt`, `ghcnd-inventory.txt`, `readme.txt`, and
`GHCND_documentation.pdf` are upstream NOAA reference files. **None are read by
the pipeline** — they're checked in for human reference only. State is parsed
from each per-station CSV's `NAME` field suffix.

### Map config

Tile provider is configured in `ghcn/env/env.yml` under `map:`. OpenTopoMap is
the current default (Stamen Terrain went dark in 2023 when Stamen moved to
Stadia Maps). The commented OpenStreetMap block is a drop-in alternative.

### Pipeline revival TODOs (deferred work)

- Python version pin — the old code was written against Python 3.8 / pandas 1.2
  / folium 0.11 / scipy 1.6. The `scipy.ndimage.filters` → `scipy.ndimage`
  rename was patched but other compat issues may surface.
- The `time.sleep(300)` at the start of `main()` is dead weight for non-cron runs.
- No driver/CLI subcommands beyond the new `--regenerate-maps` flag — ingestion,
  spool building, and rendering all run in one shot.
