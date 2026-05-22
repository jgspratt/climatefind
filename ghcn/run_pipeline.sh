#!/usr/bin/env bash
# Run the full GHCN pipeline end-to-end.
#
# Default (no --overwrite): idempotent resume. Existing per-station spool
# entries are kept and skipped by the python side; spool/comfy/year.csv is
# removed before the run so stage 3 always rebuilds the summary CSV from the
# current spool (otherwise spool_year_summary_csv short-circuits on an
# existing year.csv and stage 4 renders stale maps).
#
# --overwrite: wipe the entire spool first, then run the pipeline from
# scratch. The flag is also forwarded to python so its in-memory caches
# match what's on disk.
#
# Any other args forward straight to `python3 -m climatefind.main`.
#
# NOTE: schema-changing pipeline updates (e.g. adding a `country` column,
# or changing the stage-1 rejection criteria) require a one-time
# `--overwrite` so spool/rejected/ is wiped and every CSV is re-checked
# under the new rules. After that, idempotent resume is fine again.
#
# Usage:
#   ./run_pipeline.sh                       # resume / finish a partial run
#   ./run_pipeline.sh --overwrite           # wipe everything, start over
#   ./run_pipeline.sh --jobs 8              # cap workers
#   ./run_pipeline.sh --hash-start "0*"     # just a 1/16 slice

set -euo pipefail

GHCN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPOOL="${GHCN_DIR}/spool"

OVERWRITE=0
for arg in "$@"; do
  case "${arg}" in
    -h|--help)
      cd "${GHCN_DIR}/app"
      exec python3 -m climatefind.main "$@"
      ;;
    --overwrite)
      OVERWRITE=1
      ;;
  esac
done

if [[ "${OVERWRITE}" -eq 1 ]]; then
  for sub in meta tmax tmin year rejected; do
    target="${SPOOL}/${sub}"
    if [[ -d "${target}" ]]; then
      echo "wiping ${target}"
      rm -rf "${target}"
    fi
  done
fi

# Always reset the summary CSV so stage 3 actually rebuilds it; otherwise
# spool_year_summary_csv returns early and stage 4 renders stale maps.
if [[ -f "${SPOOL}/comfy/year.csv" ]]; then
  echo "wiping ${SPOOL}/comfy/year.csv"
  rm -f "${SPOOL}/comfy/year.csv"
fi

mkdir -p "${SPOOL}"/{meta,tmax,tmin,year,comfy,rejected}

cd "${GHCN_DIR}/app"
exec python3 -m climatefind.main --full-pipeline "$@"
