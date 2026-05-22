#!/usr/bin/env bash
# Wipe the per-station spool dirs and run the full GHCN pipeline end-to-end.
# Preserves spool/comfy/year.csv until stage 3 rewrites it. Any args passed
# to this script forward to `python3 -m climatefind.main`.
#
# Usage:
#   ./run_pipeline.sh                # default --full-pipeline run on all cores - 1
#   ./run_pipeline.sh --jobs 8       # cap workers
#   ./run_pipeline.sh --hash-start "0*"   # just a slice

set -euo pipefail

GHCN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPOOL="${GHCN_DIR}/spool"

# Forward --help / -h to argparse without wiping anything.
for arg in "$@"; do
  case "${arg}" in
    -h|--help)
      cd "${GHCN_DIR}/app"
      exec python3 -m climatefind.main "$@"
      ;;
  esac
done

for sub in meta tmax tmin year; do
  target="${SPOOL}/${sub}"
  if [[ -d "${target}" ]]; then
    echo "wiping ${target}"
    rm -rf "${target}"
  fi
  mkdir -p "${target}"
done

cd "${GHCN_DIR}/app"
exec python3 -m climatefind.main --full-pipeline "$@"
