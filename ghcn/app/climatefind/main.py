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
import timeit
import subprocess

# Contrib
import branca
import folium
import folium.plugins
# from folium import plugins # TODO: needed or can we do folium.plugins?
import geojsoncontour
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

MAP_COLORS = {
  'high_red': [
    '#00FFFF',
    '#00FFFF',
    '#00FFFF',
    '#00FFED',
    '#00FFB3',
    '#00FF7D',
    '#00FF49',
    '#00FF18',
    '#00FF00',
    '#00FF00',
    '#00FF00',
    '#19FF00',
    '#47FF00',
    '#72FF00',
    '#9AFF00',
    '#BFFF00',
    '#E1FF00',
    '#FFFF00',
    '#FFFC00',
    '#FFD700',
    '#FFB400',
    '#FF9B00',
    '#FF8200',
    '#FF6900',
    '#FF4F00',
    '#FF3400',
    '#FF1900',
    '#FF0000',
    '#FF000A',
    '#FF0024',
    '#FF003F',
    '#FF005A',
    '#FF0075',
    '#FF0091',
    '#FF00AE',
    '#FF00CB',
    '#FF00E8',
    '#FF00FF',
    '#FF00FF',
    '#EB00FF',
    '#CE00FF',
  ],
  'high_green': [
    '#CE00FF',
    '#EB00FF',
    '#FF00FF',
    '#FF00FF',
    '#FF00E8',
    '#FF00CB',
    '#FF00AE',
    '#FF0091',
    '#FF0075',
    '#FF005A',
    '#FF003F',
    '#FF0024',
    '#FF000A',
    '#FF0000',
    '#FF1900',
    '#FF3400',
    '#FF4F00',
    '#FF6900',
    '#FF8200',
    '#FF9B00',
    '#FFB400',
    '#FFD700',
    '#FFFC00',
    '#FFFF00',
    '#E1FF00',
    '#BFFF00',
    '#9AFF00',
    '#72FF00',
    '#47FF00',
    '#19FF00',
    '#00FF00',
    '#00FF00',
    '#00FF00',
    '#00FF18',
    '#00FF49',
    '#00FF7D',
    '#00FFB3',
    '#00FFED',
    '#00FFFF',
    '#00FFFF',
    '#00FFFF',
  ]
}

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
    f'{GHCN_DIR}/spool/comfy',
  ]
  for dir in dirs:
    if not os.path.isdir(dir):
      os.mkdir(dir)

def get_input_queue():
  input_queue = pathlib.Path(os.path.join(GHCN_DIR, 'input', 'queue')).glob(ENV['input']['file_glob'])
  return input_queue

def get_spool(empty=False):
  spool_dirs = [
    'meta',
    'tmax',
    'tmin',
    'year',
    'comfy',
  ]

  if empty:
    return { spool_dir: set() for spool_dir in spool_dirs }

  return {
    spool_dir: set([
       os.path.basename(file)
       for file in pathlib.Path(os.path.join(GHCN_DIR, 'spool', spool_dir)).glob(ENV['input']['file_glob'])
     ])
    for spool_dir in spool_dirs
  }

def check_all_files(hash_start='*', overwrite=False, write_meta=False, spool=None):
  queue = get_input_queue()
  if overwrite:
    spool = get_spool(empty=True)
  else:
    if not spool:
      spool = get_spool()
  num_qualifying_files = 0
  num_files_checked = 0
  for file in queue:
    filepath = str(file)[len(GHCN_DIR):]
    filename = os.path.basename(file)
    if (
      fnmatch.fnmatch(climatefind.utils.get_filename_hash(filename), hash_start)
      and
      filename not in spool['meta']
    ):
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

def spool_year_summary_csv(overwrite=False, spool=None):
  queue = pathlib.Path(os.path.join(GHCN_DIR, 'spool', 'year')).glob(ENV['input']['file_glob'])
  if overwrite:
    spool = get_spool(empty=True)
  else:
    if not spool:
      spool = get_spool()

  if 'year.csv' in spool['comfy'] and not overwrite:
    return True

  comfy = {}
  file_num = 0
  for file in queue:
    file_num += 1
    if file_num % 100 == 0:
      LOG.info(f'Loading file {file_num}')
    with open(file.resolve()) as f:
      year = json.load(f)
      comfy[file_num] = {
        'id': year['meta']['id'],
        'state': year['meta']['state'],
        'start_date': year['meta']['start_date'],
        'end_date': year['meta']['end_date'],
        'lat': year['meta']['lat'],
        'lon': year['meta']['lon'],
        'elev_m': year['meta']['elev_m'],
        'total_comfy_days': year['total_comfy_days'],
        'average_comfy_days': year['average_comfy_days'],
        'aug_1_tmin': year["8"]['comfy_days']["1"]['tmin_mean'],
        'aug_1_tmax': year["8"]['comfy_days']["1"]['tmax_mean'],
        'name': year['meta']['name'],
      }

  comfy_df = pandas.DataFrame.from_dict(comfy, orient="index")
  comfy_df.sort_values(['state', 'average_comfy_days'], inplace=True)
  comfy_df.to_csv(f'{GHCN_DIR}/spool/comfy/year.csv')
  return True

def spool_tmax_tmin(hash_start='*', overwrite=False, spool=None):
  queue = pathlib.Path(os.path.join(GHCN_DIR, 'spool', 'meta')).glob(ENV['input']['file_glob'])
  if overwrite:
    spool = get_spool(empty=True)
  else:
    if not spool:
      spool = get_spool()
  for file in queue:
    filename = os.path.basename((file.resolve()))
    if (
      fnmatch.fnmatch(climatefind.utils.get_filename_hash(filename), hash_start)
      and
      (
        filename not in spool['tmax']
        or
        filename not in spool['tmin']
        or
        filename not in spool['year']
      )
    ):
      start_time = timeit.default_timer()
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
      year['meta'] = meta
      for month in range(1,13):
        tmaxs['months'][month] = {}
        tmins['months'][month] = {}
        for day in year[month]['days']:
          tmaxs['months'][month][day] = year[month]['comfy_days'][day]['tmax_mean']
          tmins['months'][month][day] = year[month]['comfy_days'][day]['tmin_mean']
      with open(f'{GHCN_DIR}/spool/tmax/{filename}', 'w') as f:
        f.write(climatefind.utils.compact_json_dumps(tmaxs, width=80, indent=2))
      with open(f'{GHCN_DIR}/spool/tmin/{filename}', 'w') as f:
        f.write(climatefind.utils.compact_json_dumps(tmins, width=80, indent=2))
      with open(f'{GHCN_DIR}/spool/year/{filename}', 'w') as f:
        f.write(climatefind.utils.compact_json_dumps(year, width=80, indent=2))
      LOG.info(f'Wrote tmin and tmax for {filename} in {round((timeit.default_timer() - start_time), 1)}s')

def num_comfy_days_per_year_from_csv(csv):
  year = copy.deepcopy(CALENDAR)
  for month_num, month in year.items():
    year[month_num]['comfy_days'] = {}
    for day in year[month_num]['days']:
      year[month_num]['comfy_days'][day] = {
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
      year[month]['comfy_days'][day]['tmax_mean'] = round(statistics.mean(year[month]['comfy_days'][day]['tmax']), 2)
      year[month]['comfy_days'][day]['tmin_mean'] = round(statistics.mean(year[month]['comfy_days'][day]['tmin']), 2)

  year = summarize_year(year)

  return year

def summarize_year(year):
  for month_num, month in year.items():
    month_summary = summarize_month(year[month_num])
    year[month_num]['total_comfy_days'] = month_summary['total_comfy_days']
    year[month_num]['average_comfy_days'] = month_summary['average_comfy_days']

  year['total_comfy_days'] = 0
  year['average_comfy_days'] = 0
  for month_num in range (1, 13):
    # print('\n'*3)
    # print(f'month: {month}')
    # pprint.pprint(year[month], compact=True)
    year['total_comfy_days'] += year[month_num]['total_comfy_days']
    year['average_comfy_days'] += year[month_num]['average_comfy_days']

  year['average_comfy_days'] = round(year['average_comfy_days'], 2)
  return year

def summarize_month(month):
  total_comfy_days = 0
  average_comfy_days = 0
  for day_num, day in month['comfy_days'].items():
    if day['comfy'] >= day['uncomfy']:
      total_comfy_days += 1
    average_comfy_days += (day['comfy'] / ( day['comfy'] + day['uncomfy'] ))
  return {
    'total_comfy_days': total_comfy_days,
    'average_comfy_days': round(average_comfy_days, 2),
  }

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
  station = csv.iloc[0]['STATION']

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
      LOG.info(f'Found 365 days in {station} after searching {records_checked} records')
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

def scale_onto_array(vmin, vmax, val, arr):
  arr_len = len(arr)
  this_range = vmax - vmin
  step = (this_range/arr_len)
  val_steps = min(round(val/step), (arr_len-1))
  return arr[val_steps]

def get_elevation_df_from_summary_csv(elevation_column='elev_m', no_negatives=True):
  """
  Elevation may or may not be an actual elevation.
  """
  usecols=[
    'lat',
    'lon',
    elevation_column,
    'name',
    'id',
  ]
  if elevation_column != 'elev_m':
    usecols += ['elev_m']

  df = pandas.read_csv(
    f'{GHCN_DIR}/spool/comfy/year.csv',
    usecols=usecols
  )
  df.rename(columns={elevation_column: 'elev'}, inplace=True)
  if no_negatives:
    df[df['elev'] < 0] = 0
    return df
  else:
    return df

def make_folium_elevation_map(elevation_column='elev_m', color_scheme='high_green', units='m'):
  df = get_elevation_df_from_summary_csv(elevation_column)
  colors = MAP_COLORS[color_scheme]
  num_colors = len(colors)

  # Setup minimum and maximum values for the contour lines
  elevation_min = df['elev'].min()
  elevation_max = df['elev'].max()

  # Setup colormap
  color_map = branca.colormap.LinearColormap(
    colors,
    vmin=elevation_min,
    vmax=elevation_max
  ).to_step(
    num_colors
  )

  # Convertion from dataframe to array
  x = numpy.asarray(df.lon.tolist()) # note: 'lon'
  y = numpy.asarray(df.lat.tolist()) # note: 'lat'
  z = numpy.asarray(df.elev.tolist())

  # Make a grid
  x_arr          = numpy.linspace(numpy.min(x), numpy.max(x), 500)
  y_arr          = numpy.linspace(numpy.min(y), numpy.max(y), 500)
  x_mesh, y_mesh = numpy.meshgrid(x_arr, y_arr)

  # Grid the elevation (Edited on March 30th, 2020)
  z_mesh = scipy.interpolate.griddata(
    (x, y),
    z,
    (x_mesh, y_mesh),
    method='linear'
  )

  # Use Gaussian filter to smoothen the contour
  sigma = [1, 1]
  z_mesh = scipy.ndimage.filters.gaussian_filter(
    z_mesh,
    sigma,
    mode='constant'
  )

  # Create the contour
  contourf = matplotlib.pyplot.contourf(
    x_mesh,
    y_mesh,
    z_mesh,
    num_colors,
    alpha=0.5,
    colors=colors,
    linestyles='None',
    vmin=elevation_min,
    vmax=elevation_max
  )

  # Convert matplotlib contourf to geojson
  geojson = geojsoncontour.contourf_to_geojson(
    contourf=contourf,
    min_angle_deg=3.0,
    ndigits=5,
    stroke_width=2,
    fill_opacity=0.1
  )

  # Set up the map placeholdder
  geomap1 = folium.Map(
    location=[42.0573, -102.8017],
    zoom_start=6,
    tiles=ENV['map']['tiles']
  )

  # Plot the contour on Folium map
  folium.GeoJson(
    geojson,
    style_function=lambda x: {
      'color':     x['properties']['stroke'],
      'weight':    x['properties']['stroke-width'],
      'fillColor': x['properties']['fill'],
      'opacity':   0.9,
      'fillOpacity': 0.5,
    }).add_to(geomap1)

  # Add the colormap to the folium map for legend
  color_map.caption = 'Elevation'
  geomap1.add_child(color_map)

  # Add all stations to map
  for lat, lon, elev, name, id, elev_m in zip(
    df['lat'],
    df['lon'],
    df['elev'],
    df['name'],
    df['id'],
    df['elev_m'],
  ):
    this_color = scale_onto_array(
      vmin=elevation_min,
      vmax=elevation_max,
      val=elev,
      arr=colors
    )
    if elevation_column == 'elev_m':
      tooltip = f'{id} {name} {lat},{lon} @ {elev}{units}'
    else:
      tooltip = f'{id} {name} {lat},{lon} @ {elev_m}m @ {elev} {units}'
    folium.CircleMarker(
      [lat, lon],
      radius=4, # pixels
      tooltip=tooltip,
      popup=tooltip,
      color=this_color,
      fill=True,
      fillColor=this_color,
      fillOpacity=1.0
    ).add_to(geomap1)

  # Add the legend to the map
  folium.plugins.Fullscreen(
    position='topright',
    force_separate_button=True
  ).add_to(geomap1)

  test_html_filepath = f'''{GHCN_DIR}/output/{elevation_column}.{(ENV['map']['tiles']).replace(' ', '_')}.html'''
  geomap1.save(test_html_filepath)
  subprocess.Popen(['open', '-a', 'Google Chrome', test_html_filepath])

  return True

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--hash-start', dest='hash_start', default='*', required=False)
  parser.add_argument('--overwrite', dest='overwrite', action='store_true')
  parser.add_argument('--no-overwrite', dest='overwrite', action='store_false')
  parser.set_defaults(overwrite=False)
  args = parser.parse_args()

  read_env()
  setup_logger()
  setup_spool()

  time.sleep(300)

  spool = get_spool()
  check_all_files(hash_start=args.hash_start, overwrite=args.overwrite, write_meta=True, spool=spool)
  spool_tmax_tmin(hash_start=args.hash_start, overwrite=args.overwrite, spool=spool)

if __name__ == "__main__":
    main()
