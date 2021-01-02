# Core
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

MONTH_COMPLETENESS_REQ = 1.0  # 1.0 = require all days (except Feb 29)

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

def get_input_queue():
  input_queue = pathlib.Path(os.path.join(GHCN_DIR, 'input', 'queue')).glob(ENV['input']['file_glob'])
  return input_queue

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
      cvs_from_temp_ghcn_file(filepath)
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
    if not year[month_found]['day_found'][day_found]:
      year[month_found]['day_found'][day_found] = True
      # LOG.debug(f'found {month_found}/{day_found} present in {year_found}')
      num_found_days += 1
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

def cvs_from_temp_ghcn_file(filepath):
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
