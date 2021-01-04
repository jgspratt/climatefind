#!/usr/bin/env python3

# Core
import argparse
import json
import logging
import os
import pathlib
import random
import sys
import time
import typing
import math
import copy
import fnmatch
import statistics
import pprint


# Contrib
import yaml
import pandas

# This module
import climatefind

ENV: typing.Dict[typing.Any, typing.Any] = {}
LOG: logging.Logger

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
THIS_PARENT_DIR = os.path.dirname(THIS_DIR)
GHCN_DIR = os.path.dirname(THIS_PARENT_DIR)

US_STATES = {
  'AL': 'Alabama',
  'AK': 'Alaska',
  'AZ': 'Arizona',
  'AR': 'Arkansas',
  'CA': 'California',
  'CO': 'Colorado',
  'CT': 'Connecticut',
  'DE': 'Delaware',
  'FL': 'Florida',
  'GA': 'Georgia',
  'HI': 'Hawaii',
  'ID': 'Idaho',
  'IL': 'Illinois',
  'IN': 'Indiana',
  'IA': 'Iowa',
  'KS': 'Kansas',
  'KY': 'Kentucky',
  'LA': 'Louisiana',
  'ME': 'Maine',
  'MD': 'Maryland',
  'MA': 'Massachusetts',
  'MI': 'Michigan',
  'MN': 'Minnesota',
  'MS': 'Mississippi',
  'MO': 'Missouri',
  'MT': 'Montana',
  'NE': 'Nebraska',
  'NV': 'Nevada',
  'NH': 'New Hampshire',
  'NJ': 'New Jersey',
  'NM': 'New Mexico',
  'NY': 'New York',
  'NC': 'North Carolina',
  'ND': 'North Dakota',
  'OH': 'Ohio',
  'OK': 'Oklahoma',
  'OR': 'Oregon',
  'PA': 'Pennsylvania',
  'RI': 'Rhode Island',
  'SC': 'South Carolina',
  'SD': 'South Dakota',
  'TN': 'Tennessee',
  'TX': 'Texas',
  'UT': 'Utah',
  'VT': 'Vermont',
  'VA': 'Virginia',
  'WA': 'Washington',
  'WV': 'West Virginia',
  'WI': 'Wisconsin',
  'WY': 'Wyoming',
}

# MONTH_COMPLETENESS_REQ = 1.0  # 1.0 = require all days (except Feb 29)

CALENDAR = {
  1: {
    'name': 'jan',
    'num_days': 31,
  },
  2: {
    'name': 'feb',
    'num_days': 28,
  },
  3: {
    'name': 'mar',
    'num_days': 31,
  },
  4: {
    'name': 'apr',
    'num_days': 30,
  },
  5: {
    'name': 'may',
    'num_days': 31,
  },
  6: {
    'name': 'jun',
    'num_days': 30,
  },
  7: {
    'name': 'jul',
    'num_days': 31,
  },
  8: {
    'name': 'aug',
    'num_days': 31,
  },
  9: {
    'name': 'sep',
    'num_days': 30,
  },
  10: {
    'name': 'oct',
    'num_days': 31,
  },
  11: {
    'name': 'nov',
    'num_days': 30,
  },
  12: {
    'name': 'dec',
    'num_days': 31,
  },
}
for month, meta in CALENDAR.items():
  CALENDAR[month]['days'] = [ i for i in range(1, (CALENDAR[month]['num_days'] + 1)) ]



def read_env(override=None) -> bool:
  """Read the global env from disk"""
  global ENV
  env_files_sorted = sorted(pathlib.Path(os.path.join(GHCN_DIR, 'env')).glob('*.yml'))
  for file in env_files_sorted:
    print(f'Opening {file.resolve()}')
    with open(file.resolve()) as env_file:
      ENV = climatefind.utils.deep_dict_merge(ENV, yaml.load(env_file, Loader=yaml.FullLoader))
  if override:
    ENV = climatefind.utils.deep_dict_merge(ENV, override)
  return True

def setup_logger() -> None:
  """Create global logger"""
  log_levels = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'NOTSET': logging.NOTSET,
  }
  log_level = log_levels[ENV['log']['level']]

  global LOG
  LOG = logging.getLogger(__name__)
  LOG.propagate = False
  if LOG.hasHandlers():
    LOG.handlers.clear()
  LOG.setLevel(log_level)
  log_formatter = logging.Formatter(fmt=ENV['log']['fmt'], style=ENV['log']['style'], datefmt=ENV['log']['datefmt'])
  console_handler = logging.StreamHandler(stream=sys.stdout)
  console_handler.setFormatter(log_formatter)
  LOG.addHandler(console_handler)
  LOG.info(f'''Logging enabled at {ENV['log']['level']} ({log_level}) level.''')

def setup_spool():
  dirs = [
    f'{GHCN_DIR}/spool',
    f'{GHCN_DIR}/spool/meta',
    f'{GHCN_DIR}/spool/tmin',
    f'{GHCN_DIR}/spool/tmax',
    f'{GHCN_DIR}/spool/year',
  ]
  for dir in dirs:
    if not os.path.isdir(dir):
      os.mkdir(dir)

def get_input_queue():
  input_queue = pathlib.Path(os.path.join(GHCN_DIR, 'input', 'queue')).glob(ENV['input']['file_glob'])
  return input_queue

def check_all_files(hash_start='*', write_meta=False):
  queue = get_input_queue()
  num_qualifying_files = 0
  num_files_checked = 0
  for file in queue:
    filepath = str(file)[len(GHCN_DIR):]
    filename = os.path.basename(file)
    if fnmatch.fnmatch(climatefind.utils.get_filename_hash(filename), hash_start):
      LOG.debug(f'checking {filepath}')
      meta = read_usa_ghcn_file_meta(filepath)
      num_files_checked += 1
      if not meta:
        LOG.debug(f'{filepath} is a non-US file')
      elif meta['has_complete_temp_year']:
        LOG.info(f'''{filepath} from {meta['state']} at {meta['lat']},{meta['lon']} {meta['elev_m']}m is complete ({num_qualifying_files}/{num_files_checked} = {int((num_qualifying_files*100/num_files_checked))}%)''')
        if write_meta:
          with open(f'{GHCN_DIR}/spool/meta/{filename}', 'w') as f:
            f.write(json.dumps(meta, indent=2))
        num_qualifying_files += 1
      else:
        LOG.debug(f'{filepath} is a US file without a complete year of temp records')

  LOG.info(f'Found {num_qualifying_files} qualifying files')
  return num_qualifying_files

def spool_tmax_tmin(hash_start='*'):
  queue = pathlib.Path(os.path.join(GHCN_DIR, 'spool', 'meta')).glob(ENV['input']['file_glob'])
  for file in queue:
    filename = os.path.basename((file.resolve()))
    if fnmatch.fnmatch(climatefind.utils.get_filename_hash(filename), hash_start):
      meta = read_usa_ghcn_file_meta(f'input/queue/{filename}')
      tmaxs = {
        'months': {},
        'meta': meta,
      }
      tmins = {
        'months': {},
        'meta': meta,
      }
      csv = csv_from_temp_ghcn_file(f'input/queue/{filename}')
      year = num_comfy_days_per_year_from_csv(csv)
      for month in range(1,13):
        tmaxs['months'][month] = {}
        tmins['months'][month] = {}
        for day in year[month]['days']:
          tmaxs['months'][month][day] = year[month]['comfy_days'][day]['tmax_mean']
          tmins['months'][month][day] = year[month]['comfy_days'][day]['tmin_mean']
      with open(f'{GHCN_DIR}/spool/tmax/{filename}', 'w') as f:
        f.write(json.dumps(tmaxs, indent=2))
      with open(f'{GHCN_DIR}/spool/tmin/{filename}', 'w') as f:
        f.write(json.dumps(tmins, indent=2))

def num_comfy_days_per_year_from_csv(csv):
  year = copy.deepcopy(CALENDAR)
  for month, meta in year.items():
    year[month]['comfy_days'] = {}
    for day in year[month]['days']:
      year[month]['comfy_days'][day] = {
        'comfy': 0,
        'uncomfy': 0,
        'tmax': [],
        'tmin': [],
      }

  for index, row in csv.iterrows():
    date = get_date_dict(row['DATE'])
    year_found = date['year']
    month_found = date['month']
    day_found = date['day']
    if month_found == 2 and day_found == 29:  # Simply ignore Feb 29
      continue
    tmax_found = row['TMAX']
    tmin_found = row['TMIN']
    try:
      normalized_tmax = normalize_temperature(int(tmax_found))
      normalized_tmin = normalize_temperature(int(tmin_found))
      year[month_found]['comfy_days'][day_found]['tmax'].append(normalized_tmax)
      year[month_found]['comfy_days'][day_found]['tmin'].append(normalized_tmin)
      if is_comfy_day(
        tmax=normalize_temperature(tmax_found),
        tmin=normalize_temperature(tmin_found)
      ):
        year[month_found]['comfy_days'][day_found]['comfy'] += 1
      else:
        year[month_found]['comfy_days'][day_found]['uncomfy'] += 1
    except ValueError:
      continue

  for month, meta in year.items():
    for day in year[month]['days']:
      year[month]['comfy_days'][day]['tmax_mean'] = statistics.mean(year[month]['comfy_days'][day]['tmax'])
      year[month]['comfy_days'][day]['tmin_mean'] = statistics.mean(year[month]['comfy_days'][day]['tmin'])

  year = summarize_year(year)

  return year

def summarize_year(year):
  for month, meta in year.items():
    year[month]['total_comfy_days'] = summarize_month(year[month])

  year['total_comfy_days'] = 0
  for month in range (1, 13):
    # print('\n'*3)
    # print(f'month: {month}')
    # pprint.pprint(year[month], compact=True)
    year['total_comfy_days'] += year[month]['total_comfy_days']

  return year

def summarize_month(month):
  num_comfy_days = 0
  for day, val in month['comfy_days'].items():
    if is_comfy_day_on_average(val):
      num_comfy_days += 1
  return num_comfy_days

def is_comfy_day_on_average(day):
 return day['comfy'] >= day['uncomfy']

def is_comfy_day(tmax, tmin):
  return (
    (
      ENV['comfy']['tmax_solo']['min'] <= tmax <= ENV['comfy']['tmax_solo']['max']
    ) or (
      tmax > ENV['comfy']['tmax_solo']['max']
      and
      tmin <= ENV['comfy']['tmin_if_tmax_above_max']
    )
  )

def read_usa_ghcn_file_meta(filepath):
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
    f'{GHCN_DIR}/{filepath}',
    usecols=[
      'STATION',
      'DATE',
      'LATITUDE',
      'LONGITUDE',
      'ELEVATION',
      'NAME',
    ]
  )
  meta = {}
  if not get_state_from_csv(csv): # Non-US loation
    return meta

  attributes_map = {
    'STATION': 'id',
    'NAME': 'name',
    'LATITUDE': 'lat',
    'LONGITUDE': 'lon',
    'ELEVATION': 'elev_m',
  }
  first_data_row = csv.iloc[0]
  for csv_key, meta_key in attributes_map.items():
    meta[meta_key] = first_data_row[csv_key]

  meta['state'] = get_state_from_csv(csv)
  meta['start_date'] = get_start_date_from_csv(csv)
  meta['end_date'] = get_end_date_from_csv(csv)
  meta['has_temps'] = is_temperature_file(filepath)
  if meta['has_temps']:
    meta['has_complete_temp_year'] = has_complete_year_from_csv(
      csv_from_temp_ghcn_file(filepath)
    )
  else:
    meta['has_complete_temp_year'] = False

  return meta

def get_start_date_from_csv(csv):
  return csv.iloc[0]['DATE']

def get_end_date_from_csv(csv):
  return csv.iloc[-1]['DATE']

def get_state_from_csv(csv):
  station_name = csv.iloc[0]['NAME']
  try:
    country = station_name[-2:]
    if country == 'US':
      state = station_name[-5:-3]
      if US_STATES.get(state):
        return state
  except IndexError:
    return ''

def normalize_temperature(temperature_tenths_c):
  return (temperature_tenths_c/10)

def has_complete_year_from_csv(csv):
  year = copy.deepcopy(CALENDAR)
  for month, meta in year.items():
    year[month]['day_found'] = {}
    for day in year[month]['days']:
      year[month]['day_found'][day] = False

  num_found_days = 0
  records_checked = 0
  for index, row in csv.iterrows():
    records_checked += 1
    date = get_date_dict(row['DATE'])
    year_found = date['year']
    month_found = date['month']
    day_found = date['day']
    if month_found == 2 and day_found == 29:  # Simply ignore Feb 29
      continue
    if not year[month_found]['day_found'][day_found]:
      try:
        if int(row['TMAX']) and int(row['TMIN']):
          year[month_found]['day_found'][day_found] = True
          LOG.debug(f'found {month_found}/{day_found} present in {year_found}')
          num_found_days += 1
      except ValueError:
        continue
    if num_found_days >= 365:
      LOG.info(f'Found 365 days after searching {records_checked} records')
      return True

  LOG.info(f'Found only {num_found_days} days')
  return False

def get_date_dict(date_string):
  return {
    'year': int(date_string[0:4]),
    'month': int(date_string[5:7]),
    'day': int(date_string[8:10]),
  }

def csv_from_temp_ghcn_file(filepath):
  return pandas.read_csv(
    f'{GHCN_DIR}/{filepath}',
    usecols=[
      'STATION',
      'DATE',
      'LATITUDE',
      'LONGITUDE',
      'ELEVATION',
      'NAME',
      'TMAX',
      'TMIN',
    ]
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
      f'{GHCN_DIR}/{filepath}',
      usecols=[
        'TMAX',
        'TMIN',
      ]
    )
    return True
  except ValueError:
    return False

def is_usa_location_from_csv(csv):
  return bool(get_state_from_csv())


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--hash-start', dest='hash_start', default='*', required=False)
  args = parser.parse_args()

  read_env()
  setup_logger()
  setup_spool()

  check_all_files(hash_start=args.hash_start, write_meta=True)
  spool_tmax_tmin(hash_start=args.hash_start)

if __name__ == "__main__":
    main()
