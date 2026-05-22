#!/usr/bin/env python3

# Core
import argparse
import concurrent.futures
import json
import logging
import os
import pathlib
import sys
import time
import typing
import copy
import fnmatch
import statistics
import subprocess
import warnings

# Each worker process re-imports `climatefind.main` (since we use `python -m
# climatefind.main`), which trips a benign runpy warning. Silence it in both
# the parent and any child interpreters via PYTHONWARNINGS (inherited by
# spawned workers) and warnings.filterwarnings (parent process).
warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")
os.environ.setdefault("PYTHONWARNINGS", "ignore::RuntimeWarning:runpy")

# Contrib
import branca
import folium
import folium.plugins

# from folium import plugins # TODO: needed or can we do folium.plugins?
import geojsoncontour
import matplotlib

matplotlib.use("Agg")  # headless: regenerate-maps must work without a display
import matplotlib.pyplot
import numpy
import pandas
import scipy
import scipy.interpolate

# from scipy.interpolate import griddata # TODO: or can we do scipy.interpolate?
import scipy.ndimage
import yaml

# This module
import climatefind

ENV: typing.Dict[typing.Any, typing.Any] = {}
LOG: logging.Logger = logging.getLogger(__name__)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
THIS_PARENT_DIR = os.path.dirname(THIS_DIR)
GHCN_DIR = os.path.dirname(THIS_PARENT_DIR)

US_STATES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

# MONTH_COMPLETENESS_REQ = 1.0  # 1.0 = require all days (except Feb 29)

CALENDAR = {
    1: {
        "name": "jan",
        "num_days": 31,
    },
    2: {
        "name": "feb",
        "num_days": 28,
    },
    3: {
        "name": "mar",
        "num_days": 31,
    },
    4: {
        "name": "apr",
        "num_days": 30,
    },
    5: {
        "name": "may",
        "num_days": 31,
    },
    6: {
        "name": "jun",
        "num_days": 30,
    },
    7: {
        "name": "jul",
        "num_days": 31,
    },
    8: {
        "name": "aug",
        "num_days": 31,
    },
    9: {
        "name": "sep",
        "num_days": 30,
    },
    10: {
        "name": "oct",
        "num_days": 31,
    },
    11: {
        "name": "nov",
        "num_days": 30,
    },
    12: {
        "name": "dec",
        "num_days": 31,
    },
}
for month, meta in CALENDAR.items():
    CALENDAR[month]["days"] = [i for i in range(1, (CALENDAR[month]["num_days"] + 1))]

MAP_COLORS = {
    "high_red": [
        "#00FFFF",
        "#00FFFF",
        "#00FFFF",
        "#00FFED",
        "#00FFB3",
        "#00FF7D",
        "#00FF49",
        "#00FF18",
        "#00FF00",
        "#00FF00",
        "#00FF00",
        "#19FF00",
        "#47FF00",
        "#72FF00",
        "#9AFF00",
        "#BFFF00",
        "#E1FF00",
        "#FFFF00",
        "#FFFC00",
        "#FFD700",
        "#FFB400",
        "#FF9B00",
        "#FF8200",
        "#FF6900",
        "#FF4F00",
        "#FF3400",
        "#FF1900",
        "#FF0000",
        "#FF000A",
        "#FF0024",
        "#FF003F",
        "#FF005A",
        "#FF0075",
        "#FF0091",
        "#FF00AE",
        "#FF00CB",
        "#FF00E8",
        "#FF00FF",
        "#FF00FF",
        "#EB00FF",
        "#CE00FF",
    ],
    "high_green": [
        "#CE00FF",
        "#EB00FF",
        "#FF00FF",
        "#FF00FF",
        "#FF00E8",
        "#FF00CB",
        "#FF00AE",
        "#FF0091",
        "#FF0075",
        "#FF005A",
        "#FF003F",
        "#FF0024",
        "#FF000A",
        "#FF0000",
        "#FF1900",
        "#FF3400",
        "#FF4F00",
        "#FF6900",
        "#FF8200",
        "#FF9B00",
        "#FFB400",
        "#FFD700",
        "#FFFC00",
        "#FFFF00",
        "#E1FF00",
        "#BFFF00",
        "#9AFF00",
        "#72FF00",
        "#47FF00",
        "#19FF00",
        "#00FF00",
        "#00FF00",
        "#00FF00",
        "#00FF18",
        "#00FF49",
        "#00FF7D",
        "#00FFB3",
        "#00FFED",
        "#00FFFF",
        "#00FFFF",
        "#00FFFF",
    ],
}


def _fmt_dur(seconds):
    if seconds is None or seconds == float("inf") or seconds != seconds:
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{sec:02d}s"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


# Module-level pipeline tracking so each stage's progress logger can also
# report overall elapsed + ETA across all four stages.
_PIPELINE_START_TIME = None
_PIPELINE_INPUT_COUNT = None  # set by check_all_files (stage 1 total)
_PIPELINE_QUALIFYING = None  # set after check_all_files (stage 1) completes

# Heuristic seconds-per-item used to estimate future-stage runtime before we
# have observed rates. Refined informally from smoke tests.
_STAGE_SEC_PER_ITEM = {
    1: 0.03,  # check_all_files: pandas.read_csv per input CSV
    2: 0.25,  # spool_tmax_tmin: per qualifying station
    3: 0.05,  # spool_year_summary_csv: per qualifying station
    4: 30.0,  # regenerate_all_maps: per map (15 maps)
}
_STAGE_FIXED_COUNT = {4: 15}


def _overall_eta(current_stage, stage_done, stage_total, stage_rate):
    """Return (overall_elapsed_sec, overall_remaining_sec) or (None, None)."""
    if _PIPELINE_START_TIME is None:
        return None, None
    elapsed = time.monotonic() - _PIPELINE_START_TIME
    remaining = 0.0

    # Current stage's remaining time, using observed rate if available.
    if stage_rate > 0:
        remaining += max(0.0, (stage_total - stage_done) / stage_rate)
    else:
        remaining += _STAGE_SEC_PER_ITEM.get(current_stage, 1.0) * max(
            0, stage_total - stage_done
        )

    # Future stages, using heuristics or known qualifying-station count.
    qual = _PIPELINE_QUALIFYING
    if qual is None and _PIPELINE_INPUT_COUNT:
        # Pre-stage-1: rough estimate that ~12% of input stations qualify.
        qual = int(_PIPELINE_INPUT_COUNT * 0.12)
    for s in range(current_stage + 1, 5):
        if s in _STAGE_FIXED_COUNT:
            remaining += _STAGE_SEC_PER_ITEM[s] * _STAGE_FIXED_COUNT[s]
        elif qual is not None:
            remaining += _STAGE_SEC_PER_ITEM[s] * qual

    return elapsed, remaining


class _Progress:
    """Log [stage i/N: name] pos/total (pct) rate eta at most every 10s."""

    def __init__(self, stage_name, total, stage_index, stage_count, log_every_sec=10):
        self.stage_name = stage_name
        self.total = total
        self.stage_index = stage_index
        self.stage_count = stage_count
        self.log_every_sec = log_every_sec
        self.start = time.monotonic()
        self.last_log = 0.0
        self.done = 0

    def tick(self, n=1, force=False):
        self.done += n
        now = time.monotonic()
        if not force and (now - self.last_log) < self.log_every_sec:
            return
        elapsed = now - self.start
        rate = (self.done / elapsed) if elapsed > 0 else 0
        remaining = ((self.total - self.done) / rate) if rate > 0 else float("inf")
        pct = (self.done * 100 / self.total) if self.total else 0
        overall_elapsed, overall_remaining = _overall_eta(
            self.stage_index, self.done, self.total, rate
        )
        overall_str = ""
        if overall_elapsed is not None:
            overall_str = (
                f" | overall elapsed={_fmt_dur(overall_elapsed)} "
                f"eta={_fmt_dur(overall_remaining)}"
            )
        LOG.info(
            f"[stage {self.stage_index}/{self.stage_count}: {self.stage_name}] "
            f"{self.done}/{self.total} ({pct:.1f}%) "
            f"rate={rate:.1f}/s elapsed={_fmt_dur(elapsed)} eta={_fmt_dur(remaining)}"
            f"{overall_str}"
        )
        self.last_log = now

    def done_now(self):
        self.tick(n=0, force=True)


def read_env(override=None) -> bool:
    """Read the global env from disk"""
    global ENV
    env_files_sorted = sorted(pathlib.Path(os.path.join(GHCN_DIR, "env")).glob("*.yml"))
    for file in env_files_sorted:
        LOG.debug(f"Opening {file.resolve()}")
        with open(file.resolve()) as env_file:
            ENV = climatefind.utils.deep_dict_merge(
                ENV, yaml.load(env_file, Loader=yaml.FullLoader)
            )
    if override:
        ENV = climatefind.utils.deep_dict_merge(ENV, override)
    return True


def setup_logger() -> None:
    """Create global logger"""
    log_levels = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    log_level = log_levels[ENV["log"]["level"]]

    global LOG
    LOG = logging.getLogger(__name__)
    LOG.propagate = False
    if LOG.hasHandlers():
        LOG.handlers.clear()
    LOG.setLevel(log_level)
    log_formatter = logging.Formatter(
        fmt=ENV["log"]["fmt"], style=ENV["log"]["style"], datefmt=ENV["log"]["datefmt"]
    )
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(log_formatter)
    LOG.addHandler(console_handler)
    LOG.info(f"""Logging enabled at {ENV["log"]["level"]} ({log_level}) level.""")


def setup_spool():
    dirs = [
        f"{GHCN_DIR}/spool",
        f"{GHCN_DIR}/spool/meta",
        f"{GHCN_DIR}/spool/tmin",
        f"{GHCN_DIR}/spool/tmax",
        f"{GHCN_DIR}/spool/year",
        f"{GHCN_DIR}/spool/comfy",
        f"{GHCN_DIR}/spool/rejected",
    ]
    for dir in dirs:
        if not os.path.isdir(dir):
            os.mkdir(dir)


def get_input_queue():
    input_queue = pathlib.Path(os.path.join(GHCN_DIR, "input", "queue")).glob(
        ENV["input"]["file_glob"]
    )
    return input_queue


def get_spool(empty=False):
    spool_dirs = [
        "meta",
        "tmax",
        "tmin",
        "year",
        "comfy",
        "rejected",
    ]

    if empty:
        return {spool_dir: set() for spool_dir in spool_dirs}

    return {
        spool_dir: set(
            [
                os.path.basename(file)
                for file in pathlib.Path(
                    os.path.join(GHCN_DIR, "spool", spool_dir)
                ).glob(ENV["input"]["file_glob"])
            ]
        )
        for spool_dir in spool_dirs
    }


def _worker_init():
    """ProcessPool initializer: each worker process needs ENV loaded."""
    read_env()


def _check_one_worker(filepath_str):
    """Stage-1 worker: read one input CSV; write spool/meta/<filename> if it qualifies.

    Non-qualifying files get an empty marker in spool/rejected/<filename> so
    future runs can skip them without re-reading the CSV.

    Returns 1 if the station qualified (any country with a complete temp
    year), else 0. The rejection criterion is the complete-temp-year check
    only — country filtering happens at render time per REGIONS.
    """
    filepath = filepath_str[len(GHCN_DIR) :]
    filename = os.path.basename(filepath_str)
    meta = read_ghcn_file_meta(filepath)
    if not meta or not meta.get("has_complete_temp_year"):
        # Touch a marker so the next run's filter skips this file.
        with open(f"{GHCN_DIR}/spool/rejected/{filename}", "w"):
            pass
        return 0
    with open(f"{GHCN_DIR}/spool/meta/{filename}", "w") as f:
        f.write(json.dumps(meta, indent=2))
    return 1


def _spool_tmax_tmin_one_worker(filename):
    """Stage-2 worker: build tmax/tmin/year JSON for one qualifying station."""
    meta = read_ghcn_file_meta(f"input/queue/{filename}")
    csv = csv_from_temp_ghcn_file(f"input/queue/{filename}")
    year = num_comfy_days_per_year_from_csv(csv)
    year["meta"] = meta
    tmaxs = {"months": {}, "meta": meta}
    tmins = {"months": {}, "meta": meta}
    for month in range(1, 13):
        tmaxs["months"][month] = {}
        tmins["months"][month] = {}
        for day in year[month]["days"]:
            tmaxs["months"][month][day] = year[month]["comfy_days"][day]["tmax_mean"]
            tmins["months"][month][day] = year[month]["comfy_days"][day]["tmin_mean"]
    with open(f"{GHCN_DIR}/spool/tmax/{filename}", "w") as f:
        f.write(climatefind.utils.compact_json_dumps(tmaxs, width=80, indent=2))
    with open(f"{GHCN_DIR}/spool/tmin/{filename}", "w") as f:
        f.write(climatefind.utils.compact_json_dumps(tmins, width=80, indent=2))
    with open(f"{GHCN_DIR}/spool/year/{filename}", "w") as f:
        f.write(climatefind.utils.compact_json_dumps(year, width=80, indent=2))
    return filename


def _render_one_map_worker(args):
    """Stage-4 worker: render one folium map.

    args = (region, column, output_name, color_scheme, units).
    """
    region, column, output_name, color_scheme, units = args
    return make_folium_elevation_map(
        elevation_column=column,
        output_name=output_name,
        color_scheme=color_scheme,
        units=units,
        region=region,
    )


def check_all_files(
    hash_start="*", overwrite=False, write_meta=False, spool=None, jobs=1
):
    global _PIPELINE_INPUT_COUNT, _PIPELINE_QUALIFYING
    queue = sorted(get_input_queue())
    _PIPELINE_INPUT_COUNT = len(queue)
    if overwrite:
        spool = get_spool(empty=True)
    else:
        if not spool:
            spool = get_spool()

    # Split the queue: files that need processing vs. already-cached. A file
    # is cached if it's in spool["meta"] (previously qualified) or in
    # spool["rejected"] (previously rejected, marker file only).
    cached = spool["meta"] | spool.get("rejected", set())
    to_process = []
    for file in queue:
        filename = os.path.basename(file)
        if (
            fnmatch.fnmatch(climatefind.utils.get_filename_hash(filename), hash_start)
            and filename not in cached
        ):
            to_process.append(str(file))
    already_done = len(queue) - len(to_process)

    progress = _Progress("check_all_files", len(queue), 1, 4)
    if already_done:
        progress.tick(n=already_done, force=True)

    num_qualifying_files = 0
    if jobs > 1 and len(to_process) > 1:
        LOG.info(
            f"check_all_files: dispatching {len(to_process)} files across {jobs} workers"
        )
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=jobs, initializer=_worker_init
        ) as ex:
            for qualified in ex.map(_check_one_worker, to_process, chunksize=64):
                num_qualifying_files += qualified
                progress.tick()
    else:
        for fp in to_process:
            num_qualifying_files += _check_one_worker(fp)
            progress.tick()

    progress.done_now()
    _PIPELINE_QUALIFYING = num_qualifying_files
    LOG.info(f"Found {num_qualifying_files} qualifying files")
    return num_qualifying_files


def spool_year_summary_csv(overwrite=False, spool=None):
    queue = sorted(
        pathlib.Path(os.path.join(GHCN_DIR, "spool", "year")).glob(
            ENV["input"]["file_glob"]
        )
    )
    if overwrite:
        spool = get_spool(empty=True)
    else:
        if not spool:
            spool = get_spool()

    if "year.csv" in spool["comfy"] and not overwrite:
        return True

    progress = _Progress("spool_year_summary_csv", len(queue), 3, 4)
    comfy = {}
    file_num = 0
    for file in queue:
        file_num += 1
        progress.tick()
        with open(file.resolve()) as f:
            year = json.load(f)
            comfy[file_num] = {
                "id": year["meta"]["id"],
                "country": year["meta"].get("country", ""),
                "state": year["meta"]["state"],
                "start_date": year["meta"]["start_date"],
                "end_date": year["meta"]["end_date"],
                "lat": year["meta"]["lat"],
                "lon": year["meta"]["lon"],
                "elev_m": year["meta"]["elev_m"],
                "total_comfy_days": year["total_comfy_days"],
                "average_comfy_days": year["average_comfy_days"],
                "aug_1_tmin": year["8"]["comfy_days"]["1"]["tmin_mean"],
                "aug_1_tmax": year["8"]["comfy_days"]["1"]["tmax_mean"],
                "name": year["meta"]["name"],
            }
            for month_num in CALENDAR:
                comfy[file_num][f"""{CALENDAR[month_num]["name"]}_percent_comfy"""] = (
                    round(
                        (
                            (
                                sum(
                                    [
                                        (day["comfy"] / (day["uncomfy"] + day["comfy"]))
                                        for day_num, day in year[str(month_num)][
                                            "comfy_days"
                                        ].items()
                                    ]
                                )
                                / CALENDAR[month_num]["num_days"]
                            )
                            * 100  # Convert to percent
                        ),
                        2,
                    )
                )

    progress.done_now()
    comfy_df = pandas.DataFrame.from_dict(comfy, orient="index")
    comfy_df.sort_values(["country", "state", "average_comfy_days"], inplace=True)
    comfy_df.to_csv(f"{GHCN_DIR}/spool/comfy/year.csv")
    return True


def spool_tmax_tmin(hash_start="*", overwrite=False, spool=None, jobs=1):
    queue = sorted(
        pathlib.Path(os.path.join(GHCN_DIR, "spool", "meta")).glob(
            ENV["input"]["file_glob"]
        )
    )
    if overwrite:
        spool = get_spool(empty=True)
    else:
        if not spool:
            spool = get_spool()

    to_process = []
    for file in queue:
        filename = os.path.basename((file.resolve()))
        if fnmatch.fnmatch(
            climatefind.utils.get_filename_hash(filename), hash_start
        ) and (
            filename not in spool["tmax"]
            or filename not in spool["tmin"]
            or filename not in spool["year"]
        ):
            to_process.append(filename)
    already_done = len(queue) - len(to_process)

    progress = _Progress("spool_tmax_tmin", len(queue), 2, 4)
    if already_done:
        progress.tick(n=already_done, force=True)

    if jobs > 1 and len(to_process) > 1:
        LOG.info(
            f"spool_tmax_tmin: dispatching {len(to_process)} stations across {jobs} workers"
        )
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=jobs, initializer=_worker_init
        ) as ex:
            for _ in ex.map(_spool_tmax_tmin_one_worker, to_process, chunksize=16):
                progress.tick()
    else:
        for filename in to_process:
            _spool_tmax_tmin_one_worker(filename)
            progress.tick()

    progress.done_now()


def num_comfy_days_per_year_from_csv(csv):
    year = copy.deepcopy(CALENDAR)
    for month_num, month in year.items():
        year[month_num]["comfy_days"] = {}
        for day in year[month_num]["days"]:
            year[month_num]["comfy_days"][day] = {
                "comfy": 0,
                "uncomfy": 0,
                "tmax": [],
                "tmin": [],
            }

    for index, row in csv.iterrows():
        date = get_date_dict(row["DATE"])
        year_found = date["year"]
        month_found = date["month"]
        day_found = date["day"]
        if month_found == 2 and day_found == 29:  # Simply ignore Feb 29
            continue
        tmax_found = row["TMAX"]
        tmin_found = row["TMIN"]
        try:
            normalized_tmax = normalize_temperature(int(tmax_found))
            normalized_tmin = normalize_temperature(int(tmin_found))
            year[month_found]["comfy_days"][day_found]["tmax"].append(normalized_tmax)
            year[month_found]["comfy_days"][day_found]["tmin"].append(normalized_tmin)
            if is_comfy_day(
                tmax=normalize_temperature(tmax_found),
                tmin=normalize_temperature(tmin_found),
            ):
                year[month_found]["comfy_days"][day_found]["comfy"] += 1
            else:
                year[month_found]["comfy_days"][day_found]["uncomfy"] += 1
        except ValueError:
            continue

    for month, meta in year.items():
        for day in year[month]["days"]:
            year[month]["comfy_days"][day]["tmax_mean"] = round(
                statistics.mean(year[month]["comfy_days"][day]["tmax"]), 2
            )
            year[month]["comfy_days"][day]["tmin_mean"] = round(
                statistics.mean(year[month]["comfy_days"][day]["tmin"]), 2
            )

    year = summarize_year(year)

    return year


def summarize_year(year):
    for month_num, month in year.items():
        month_summary = summarize_month(year[month_num])
        year[month_num]["total_comfy_days"] = month_summary["total_comfy_days"]
        year[month_num]["average_comfy_days"] = month_summary["average_comfy_days"]

    year["total_comfy_days"] = 0
    year["average_comfy_days"] = 0
    for month_num in range(1, 13):
        # print('\n'*3)
        # print(f'month: {month}')
        # pprint.pprint(year[month], compact=True)
        year["total_comfy_days"] += year[month_num]["total_comfy_days"]
        year["average_comfy_days"] += year[month_num]["average_comfy_days"]

    year["average_comfy_days"] = round(year["average_comfy_days"], 2)
    return year


def summarize_month(month):
    total_comfy_days = 0
    average_comfy_days = 0
    for day_num, day in month["comfy_days"].items():
        if day["comfy"] >= day["uncomfy"]:
            total_comfy_days += 1
        average_comfy_days += day["comfy"] / (day["comfy"] + day["uncomfy"])
    return {
        "total_comfy_days": total_comfy_days,
        "average_comfy_days": round(average_comfy_days, 2),
    }


def is_comfy_day(tmax, tmin):
    return (
        ENV["comfy"]["tmax_solo"]["min"] <= tmax <= ENV["comfy"]["tmax_solo"]["max"]
    ) or (
        tmax > ENV["comfy"]["tmax_solo"]["max"]
        and tmin <= ENV["comfy"]["tmin_if_tmax_above_max"]
    )


def read_ghcn_file_meta(filepath):
    """
    :return: The following
    {
      'id': <station id>,
      'name': <station name>,
      'start_date': <date>,
      'end_date': <date>,
      'lat': <latitude>,
      'lon': <longitude>,
      'elev_m': <station elevation in meters>,
      'state': <station state>,
      'has_temps': True | False
      'has_complete_temp_year': True | False
    }
    """
    csv = pandas.read_csv(
        f"{GHCN_DIR}/{filepath}",
        usecols=[
            "STATION",
            "DATE",
            "LATITUDE",
            "LONGITUDE",
            "ELEVATION",
            "NAME",
        ],
    )
    meta = {}
    attributes_map = {
        "STATION": "id",
        "NAME": "name",
        "LATITUDE": "lat",
        "LONGITUDE": "lon",
        "ELEVATION": "elev_m",
    }
    first_data_row = csv.iloc[0]
    for csv_key, meta_key in attributes_map.items():
        meta[meta_key] = first_data_row[csv_key]

    # GHCN station IDs are an 11-character FIPS-prefixed code; the first two
    # characters identify the country (e.g. "US", "CA", "FR"). See
    # ghcn/doc/readme.txt.
    meta["country"] = str(meta["id"])[:2]
    meta["state"] = get_state_from_csv(csv)
    meta["start_date"] = get_start_date_from_csv(csv)
    meta["end_date"] = get_end_date_from_csv(csv)
    meta["has_temps"] = is_temperature_file(filepath)
    if meta["has_temps"]:
        meta["has_complete_temp_year"] = has_complete_year_from_csv(
            csv_from_temp_ghcn_file(filepath)
        )
    else:
        meta["has_complete_temp_year"] = False

    return meta


def get_start_date_from_csv(csv):
    return csv.iloc[0]["DATE"]


def get_end_date_from_csv(csv):
    return csv.iloc[-1]["DATE"]


def get_state_from_csv(csv):
    """Return the US state postal code for US stations, empty string otherwise.

    Non-US stations are not ignored — they just have no state.
    """
    station_name = csv.iloc[0]["NAME"]
    try:
        country = station_name[-2:]
        if country == "US":
            state = station_name[-5:-3]
            if US_STATES.get(state):
                return state
    except IndexError:
        pass
    return ""


def normalize_temperature(temperature_tenths_c):
    return temperature_tenths_c / 10


def has_complete_year_from_csv(csv):
    year = copy.deepcopy(CALENDAR)
    for month, meta in year.items():
        year[month]["day_found"] = {}
        for day in year[month]["days"]:
            year[month]["day_found"][day] = False

    num_found_days = 0
    records_checked = 0
    station = csv.iloc[0]["STATION"]

    for index, row in csv.iterrows():
        records_checked += 1
        date = get_date_dict(row["DATE"])
        year_found = date["year"]
        month_found = date["month"]
        day_found = date["day"]
        if month_found == 2 and day_found == 29:  # Simply ignore Feb 29
            continue
        if not year[month_found]["day_found"][day_found]:
            try:
                if int(row["TMAX"]) and int(row["TMIN"]):
                    year[month_found]["day_found"][day_found] = True
                    LOG.debug(
                        f"found {month_found}/{day_found} present in {year_found}"
                    )
                    num_found_days += 1
            except ValueError:
                continue
        if num_found_days >= 365:
            LOG.info(
                f"Found 365 days in {station} after searching {records_checked} records"
            )
            return True

    LOG.info(f"Found only {num_found_days} days")
    return False


def get_date_dict(date_string):
    return {
        "year": int(date_string[0:4]),
        "month": int(date_string[5:7]),
        "day": int(date_string[8:10]),
    }


def csv_from_temp_ghcn_file(filepath):
    return pandas.read_csv(
        f"{GHCN_DIR}/{filepath}",
        usecols=[
            "STATION",
            "DATE",
            "LATITUDE",
            "LONGITUDE",
            "ELEVATION",
            "NAME",
            "TMAX",
            "TMIN",
        ],
    )


def read_ghcn_file(filepath):
    """
    :param filepath: Path relative to `ghcn/` dir
    :return: Nicely formatted dict of file like this:

    <DATE>: {
      "STATION":
      "DATE"
      "LATITUDE"
      "LONGITUDE"
      "ELEVATION"
      "NAME":
      <ATTRIB>: <VAL>
      ...
    }

    "STATION","DATE","LATITUDE","LONGITUDE","ELEVATION","NAME","PRCP","PRCP_ATTRIBUTES","SNWD","SNWD_ATTRIBUTES","TMAX","TMAX_ATTRIBUTES","TMIN","TMIN_ATTRIBUTES","TAVG","TAVG_ATTRIBUTES","TOBS","TOBS_ATTRIBUTES","WESD","WESD_ATTRIBUTES"
    """
    pass


def is_temperature_file(filepath):
    """Checks headers for presence of temperature data"""
    try:
        csv = pandas.read_csv(
            f"{GHCN_DIR}/{filepath}",
            usecols=[
                "TMAX",
                "TMIN",
            ],
        )
        return True
    except ValueError:
        return False


def scale_onto_array(vmin, vmax, val, arr):
    arr_len = len(arr)
    this_range = vmax - vmin
    step = this_range / arr_len
    val_steps = min(round(val / step), (arr_len - 1))
    return arr[val_steps]


def get_elevation_df_from_summary_csv(elevation_column="elev_m", no_negatives=True):
    """
    Elevation may or may not be an actual elevation.
    """
    usecols = [
        "lat",
        "lon",
        elevation_column,
        "name",
        "id",
        "country",
        "state",
    ]
    if elevation_column != "elev_m":
        usecols += ["elev_m"]

    df = pandas.read_csv(f"{GHCN_DIR}/spool/comfy/year.csv", usecols=usecols)
    df["country"] = df["country"].fillna("").astype(str)
    df["state"] = df["state"].fillna("").astype(str)
    df.rename(columns={elevation_column: "elev"}, inplace=True)
    # Some stations are only present in a subset of metric files (the
    # reconstructed year.csv left those cells as NaN); drop them so the
    # contour/marker math doesn't choke on NaN.
    df = df.dropna(subset=["elev"])
    if no_negatives:
        # Clamp negative elevations to 0 in the elev column only. The bare
        # `df[mask] = 0` form assigns 0 to every column of matching rows,
        # which pandas 2.x rejects for string columns like `name`/`id`.
        df.loc[df["elev"] < 0, "elev"] = 0
    return df


def make_folium_elevation_map(
    elevation_column="elev_m",
    output_name=None,
    color_scheme="high_green",
    units="m",
    region="conus",
):
    region_cfg = REGIONS[region]
    df = get_elevation_df_from_summary_csv(elevation_column)
    df = df[df.apply(region_cfg["filter"], axis=1)]
    if df.empty:
        LOG.warning(
            f"make_folium_elevation_map: no stations match region={region!r}, skipping"
        )
        return None
    colors = MAP_COLORS[color_scheme]
    num_colors = len(colors)

    # Setup minimum and maximum values for the contour lines
    elevation_min = df["elev"].min()
    elevation_max = df["elev"].max()

    # Setup colormap
    color_map = branca.colormap.LinearColormap(
        colors, vmin=elevation_min, vmax=elevation_max
    ).to_step(num_colors)

    # Convertion from dataframe to array
    x = numpy.asarray(df.lon.tolist())  # note: 'lon'
    y = numpy.asarray(df.lat.tolist())  # note: 'lat'
    z = numpy.asarray(df.elev.tolist())

    # Make a grid
    x_arr = numpy.linspace(numpy.min(x), numpy.max(x), 500)
    y_arr = numpy.linspace(numpy.min(y), numpy.max(y), 500)
    x_mesh, y_mesh = numpy.meshgrid(x_arr, y_arr)

    # Grid the elevation (Edited on March 30th, 2020)
    z_mesh = scipy.interpolate.griddata((x, y), z, (x_mesh, y_mesh), method="linear")

    # Use Gaussian filter to smoothen the contour
    sigma = [1, 1]
    z_mesh = scipy.ndimage.gaussian_filter(z_mesh, sigma, mode="constant")

    # Create the contour
    contourf = matplotlib.pyplot.contourf(
        x_mesh,
        y_mesh,
        z_mesh,
        num_colors,
        alpha=0.5,
        colors=colors,
        linestyles="None",
        vmin=elevation_min,
        vmax=elevation_max,
    )

    # Convert matplotlib contourf to geojson
    geojson = geojsoncontour.contourf_to_geojson(
        contourf=contourf,
        min_angle_deg=3.0,
        ndigits=5,
        stroke_width=2,
        fill_opacity=0.1,
    )

    # Set up the map placeholdder
    center_lat, center_lon = region_cfg["center"]
    geomap1 = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=region_cfg["zoom"],
        tiles=ENV["map"]["url"],
        attr=ENV["map"]["attr"],
        max_zoom=ENV["map"].get("max_zoom", 18),
    )

    # Plot the contour on Folium map
    folium.GeoJson(
        geojson,
        style_function=lambda x: {
            "color": x["properties"]["stroke"],
            "weight": x["properties"]["stroke-width"],
            "fillColor": x["properties"]["fill"],
            "opacity": 0.9,
            "fillOpacity": 0.5,
        },
    ).add_to(geomap1)

    # Add the colormap to the folium map for legend
    color_map.caption = "Elevation"
    geomap1.add_child(color_map)

    # Add all stations to map
    for lat, lon, elev, name, id, elev_m in zip(
        df["lat"],
        df["lon"],
        df["elev"],
        df["name"],
        df["id"],
        df["elev_m"],
    ):
        this_color = scale_onto_array(
            vmin=elevation_min, vmax=elevation_max, val=elev, arr=colors
        )
        if elevation_column == "elev_m":
            tooltip = f"{id} {name} {lat},{lon} @ {elev}{units}"
        else:
            tooltip = f"{id} {name} {lat},{lon} @ {elev_m}m @ {elev} {units}"
        folium.CircleMarker(
            [lat, lon],
            radius=4,  # pixels
            tooltip=tooltip,
            popup=tooltip,
            color=this_color,
            fill=True,
            fillColor=this_color,
            fillOpacity=1.0,
        ).add_to(geomap1)

    # Add the legend to the map
    folium.plugins.Fullscreen(position="topright", force_separate_button=True).add_to(
        geomap1
    )

    tile_name = ENV["map"]["name"].replace(" ", "_")
    name = output_name or elevation_column
    test_html_filepath = f"""{GHCN_DIR}/output/{region}/{name}.{tile_name}.html"""
    os.makedirs(os.path.dirname(test_html_filepath), exist_ok=True)
    geomap1.save(test_html_filepath)
    matplotlib.pyplot.close("all")
    if ENV.get("map", {}).get("open_in_browser"):
        subprocess.Popen(["open", "-a", "Google Chrome", test_html_filepath])

    return test_html_filepath


# Regions are the unit of "one set of maps". Each region is rendered as its
# own subdir under ghcn/output/<region>/ and img/<region>/. Adding a region
# is a one-entry config change: `filter` is a row predicate over year.csv
# (gets a pandas row, returns bool); `center`/`zoom` frame the folium map;
# `viewport` is consumed by render_pngs.py for the matching PNG.
#
# `state` empty means the station isn't US; non-US data ingests fine but
# only renders for regions whose filter accepts it.
REGIONS = {
    "conus": {
        "filter": lambda r: r["country"] == "US",
        "center": (38.4, -96.05),
        "zoom": 6,
        "viewport": (2640, 1430),
    },
    "world": {
        "filter": lambda r: True,
        "center": (20.0, 0.0),
        "zoom": 3,
        "viewport": (2640, 1430),
    },
}


# (column, output_name, color_scheme, units) for each map regenerated from
# year.csv. `column` is read from the CSV; `output_name` is the path
# (relative to ghcn/output/<region>/, without the .{tile_name}.html suffix)
# where the HTML lands. Months live in their own subdir so the region root
# stays tidy.
ALL_MAPS = [
    ("average_comfy_days", "average_comfy_days", "high_green", "days/year"),
    ("aug_1_tmax", "aug_1_tmax", "high_red", "C"),
    ("aug_1_tmin", "aug_1_tmin", "high_red", "C"),
    ("jan_percent_comfy", "months/01_jan_percent_comfy", "high_green", "% comfy"),
    ("feb_percent_comfy", "months/02_feb_percent_comfy", "high_green", "% comfy"),
    ("mar_percent_comfy", "months/03_mar_percent_comfy", "high_green", "% comfy"),
    ("apr_percent_comfy", "months/04_apr_percent_comfy", "high_green", "% comfy"),
    ("may_percent_comfy", "months/05_may_percent_comfy", "high_green", "% comfy"),
    ("jun_percent_comfy", "months/06_jun_percent_comfy", "high_green", "% comfy"),
    ("jul_percent_comfy", "months/07_jul_percent_comfy", "high_green", "% comfy"),
    ("aug_percent_comfy", "months/08_aug_percent_comfy", "high_green", "% comfy"),
    ("sep_percent_comfy", "months/09_sep_percent_comfy", "high_green", "% comfy"),
    ("oct_percent_comfy", "months/10_oct_percent_comfy", "high_green", "% comfy"),
    ("nov_percent_comfy", "months/11_nov_percent_comfy", "high_green", "% comfy"),
    ("dec_percent_comfy", "months/12_dec_percent_comfy", "high_green", "% comfy"),
]


def regenerate_all_maps(jobs=1):
    """Regenerate every output HTML map from spool/comfy/year.csv.

    Walks REGIONS x ALL_MAPS; each (region, metric) pair becomes one HTML
    under ghcn/output/<region>/.
    """
    work = [
        (region, column, output_name, color_scheme, units)
        for region in REGIONS
        for (column, output_name, color_scheme, units) in ALL_MAPS
    ]
    progress = _Progress("regenerate_all_maps", len(work), 4, 4)
    # Cap at len(work) — extra workers buy nothing.
    pool_jobs = min(jobs, len(work))
    if pool_jobs > 1:
        LOG.info(
            f"regenerate_all_maps: rendering {len(work)} maps "
            f"({len(REGIONS)} regions x {len(ALL_MAPS)} metrics) "
            f"across {pool_jobs} workers"
        )
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=pool_jobs, initializer=_worker_init
        ) as ex:
            for out in ex.map(_render_one_map_worker, work):
                LOG.info(f"  wrote {out}")
                progress.tick(force=True)
    else:
        for region, column, output_name, color_scheme, units in work:
            LOG.info(f"rendering {region}/{output_name} ({color_scheme}, {units})")
            out = make_folium_elevation_map(
                elevation_column=column,
                output_name=output_name,
                color_scheme=color_scheme,
                units=units,
                region=region,
            )
            LOG.info(f"  wrote {out}")
            progress.tick(force=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hash-start", dest="hash_start", default="*", required=False)
    parser.add_argument("--overwrite", dest="overwrite", action="store_true")
    parser.add_argument("--no-overwrite", dest="overwrite", action="store_false")
    parser.add_argument(
        "--regenerate-maps",
        dest="regenerate_maps",
        action="store_true",
        help="Skip GHCN ingestion and just (re)render the output HTML maps from spool/comfy/year.csv.",
    )
    parser.add_argument(
        "--full-pipeline",
        dest="full_pipeline",
        action="store_true",
        help="Run the complete ingest + summarize + render pipeline from raw input/queue/*.csv.",
    )
    parser.add_argument(
        "--from-summary",
        dest="from_summary",
        action="store_true",
        help="Skip stages 1+2; assume spool/year/ is populated and run only spool_year_summary_csv + regenerate_all_maps.",
    )
    parser.add_argument(
        "--jobs",
        dest="jobs",
        type=int,
        default=max(1, (os.cpu_count() or 2) - 1),
        help="Number of worker processes for the per-station and per-map stages. Default: cpu_count - 1.",
    )
    parser.set_defaults(
        overwrite=False, regenerate_maps=False, full_pipeline=False, from_summary=False
    )
    args = parser.parse_args()

    read_env()
    setup_logger()
    setup_spool()

    global _PIPELINE_START_TIME
    _PIPELINE_START_TIME = time.monotonic()
    LOG.info(f"Pipeline starting with jobs={args.jobs} (cpu_count={os.cpu_count()})")

    if args.regenerate_maps:
        regenerate_all_maps(jobs=args.jobs)
        return

    if args.from_summary:
        spool_year_summary_csv(overwrite=args.overwrite)
        regenerate_all_maps(jobs=args.jobs)
        return

    spool = get_spool()
    check_all_files(
        hash_start=args.hash_start,
        overwrite=args.overwrite,
        write_meta=True,
        spool=spool,
        jobs=args.jobs,
    )
    spool_tmax_tmin(
        hash_start=args.hash_start,
        overwrite=args.overwrite,
        spool=spool,
        jobs=args.jobs,
    )

    if args.full_pipeline:
        spool_year_summary_csv(overwrite=args.overwrite)
        regenerate_all_maps(jobs=args.jobs)


if __name__ == "__main__":
    main()
