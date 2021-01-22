#!/usr/bin/env python3

# Core
import json
import pprint
import subprocess
import os
import time

# Contrib
import yaml
import folium

# Custom
import climatefind

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
THIS_PARENT_DIR = os.path.dirname(THIS_DIR)
GHCN_DIR = os.path.dirname(THIS_PARENT_DIR)


climatefind.read_env()
climatefind.setup_logger()
climatefind.setup_spool()

samples = {
  1: {
    'filename': 'USS0005M08S.csv', # TRINCHERA, CO US
    'filepath': 'app/tests/input/queue/USS0005M08S.csv',
    'filename_hash': 'f18d3ca82f31e31aa09826de832c9881f7d291626ffbae2e1a524b9713d46f93',
    'is_usa_location': True,
    'is_temperature_file': True,
    'state': 'CO',
    'meta': {
      'id': 'USS0005M08S',
      'start_date': '1989-09-19',
      'end_date': '2020-12-29',
      'name': 'TRINCHERA, CO US',
      'lat': 37.35,
      'lon': -105.23,
      'elev_m': 3310.1,
      'state': 'CO',
      'has_temps': True,
      'has_complete_temp_year': True,
    }
  },
  2: {
    'filename': 'US1WVBB0001.csv', # PHILIPPI 0.7 W, WV US
    'filepath': 'app/tests/input/queue/US1WVBB0001.csv',
    'is_usa_location': True,
    'is_temperature_file': False,
    'state': 'WV',
  },
  3: {
    'filename': 'USC00300023.csv',
    'filepath': 'app/tests/input/queue/USC00300023.csv',
    'meta': {
      'id': 'USC00300023',
      'start_date': '1893-02-01',
      'end_date': '2020-06-04',
      'name': 'ADDISON, NY US',
      'lat': 42.1013,
      'lon': -77.2344,
      'elev_m': 304.5,
      'state': 'NY',
      'has_temps': True,
      'has_complete_temp_year': True,
    }
  },
  4: {
    'filename': 'ZI000067991.csv',
    'filepath': 'app/tests/input/queue/ZI000067991.csv',
    'is_usa_location': False,
    'is_temperature_file': True,
  },
  5: {
    'filename': 'USW00014758.csv',
    'filepath': 'app/tests/input/queue/USW00014758.csv',
    'meta': {
      'id': 'USW00014758',
      'start_date': '1948-01-01',
      'end_date': '2020-12-27',
      'name': 'NEW HAVEN TWEED AIRPORT, CT US',
      'lat': 41.26389,
      'lon': -72.88722,
      'elev_m': 0.9,
      'state': 'CT',
      'has_temps': True,
      'has_complete_temp_year': True,
    }
  },
  6: {
    'filename': 'USC00449215.csv',
    'filepath': 'input/queue/USC00449215.csv',
    "meta": {
      "id": "USC00449215",
      "name": "WISE 1 SE, VA US",
      "lat": 36.9725,
      "lon": -82.5579,
      "elev_m": 781.5,
      "state": "VA",
      "start_date": "1955-05-12",
      "end_date": "2020-12-25",
      "has_temps": True,
      "has_complete_temp_year": True,
    }
  },
}

def test_compact_json_dumps():
  dict_for_compact_printing = {
    'foo': [ i for i in range(0,256) ],
    'bar': [ i for i in range(0,256) ],
    'baz': [ i for i in range(0,256) ],
  }
  ret = climatefind.utils.compact_json_dumps(dict_for_compact_printing, indent=2, width=80)
  assert ret
  # print(ret)

def test_get_input_queue():
  assert climatefind.get_input_queue()

def test_get_filename_hash():
  assert climatefind.utils.get_filename_hash(samples[1]['filename']) == samples[1]['filename_hash']

def test_is_temperature_file():
  assert climatefind.is_temperature_file(samples[1]['filepath']) == samples[1]['is_temperature_file']
  assert climatefind.is_temperature_file(samples[2]['filepath']) == samples[2]['is_temperature_file']

def test_read_usa_ghcn_file_meta():
  print()
  assert climatefind.read_usa_ghcn_file_meta(samples[1]['filepath']) == samples[1]['meta']
  assert climatefind.read_usa_ghcn_file_meta(samples[3]['filepath']) == samples[3]['meta']
  assert climatefind.read_usa_ghcn_file_meta(samples[5]['filepath']) == samples[5]['meta']
  assert bool(climatefind.read_usa_ghcn_file_meta(samples[4]['filepath'])) == samples[4]['is_usa_location']

# def test_check_all_files():
#   print()
#   assert climatefind.check_all_files(hash_start='00*', write_meta=True)

def test_num_comfy_days_per_year_from_csv():
  csv = climatefind.csv_from_temp_ghcn_file(samples[6]['filepath'])
  year = climatefind.num_comfy_days_per_year_from_csv(csv)
  print()
  # pprint.pprint(year, compact=True, width=80, indent=1, depth=2)
  # print(climatefind.utils.compact_json_dumps(year, width=80, indent=2))

  csv = climatefind.csv_from_temp_ghcn_file(samples[5]['filepath'])
  year = climatefind.num_comfy_days_per_year_from_csv(csv)
  print()
  # pprint.pprint(year, compact=True, width=80, indent=1, depth=2)
  # print(climatefind.utils.compact_json_dumps(year, width=80, indent=2))

# def test_spool_tmax_tmin():
#   climatefind.spool_tmax_tmin(hash_start='00*')

def test_spool_year_summary_csv():
  assert climatefind.spool_year_summary_csv(overwrite=True)

def test_get_elevation_df_from_summary_csv():
  assert not climatefind.get_elevation_df_from_summary_csv().empty
  # print(climatefind.get_elevation_df_from_summary_csv(elevation_column='average_comfy_days'))

def test_scale_onto_array():
  assert climatefind.scale_onto_array(
    vmin=0,
    vmax=365,
    val=1,
    arr=[ i for i in range(0,20) ]
  ) == 0

  assert climatefind.scale_onto_array(
    vmin=0,
    vmax=365,
    val=364,
    arr=[ i for i in range(0,20) ]
  ) == 19

  assert climatefind.scale_onto_array(
    vmin=0,
    vmax=365,
    val=182,
    arr=[ i for i in range(0,20) ]
  ) == 10

def test_make_folium_elevation_map():
  pass
  # assert climatefind.make_folium_elevation_map(elevation_column='average_comfy_days', color_scheme='high_green', units='days/year')
  # assert climatefind.make_folium_elevation_map(elevation_column='total_comfy_days', color_scheme='high_green', units='days/year')
  assert climatefind.make_folium_elevation_map(elevation_column='aug_1_tmin', color_scheme='high_red', units='C')
  assert climatefind.make_folium_elevation_map(elevation_column='aug_1_tmax', color_scheme='high_red', units='C')
  # for month_num, month in climatefind.CALENDAR.items():
  #   assert climatefind.make_folium_elevation_map(elevation_column=f'''{month['name']}_percent_comfy''', color_scheme='high_green', units='% comfy')

## 256 batches
# def test_main_fast():
#   procs = []
#   # for i in range(0,16):
#   for i in range(0,16):
#     print()
#     for j in range (0,16):
#       hash_start = f'''{str(hex(i))[2:]}{str(hex(j))[2:]}*'''
#       print(hash_start)
#       procs.append(
#         subprocess.Popen(
#           [
#             'poetry',
#             'run',
#             'python3',
#             f'{GHCN_DIR}/app/climatefind/main.py',
#             '--hash-start',
#             hash_start,
#             '--overwrite'
#           ]
#         )
#       )
#
#     for proc in procs:
#       proc.communicate()

## 4096 batches
# def test_main():
#   procs = []
#   # for i in range(0,16):
#   for i in range(0,16):
#     for j in range (0,16):
#       print()
#       for k in range (0,16):
#         hash_start = f'''{str(hex(i))[2:]}{str(hex(j))[2:]}{str(hex(k))[2:]}*'''
#         print(hash_start)
#         procs.append(
#           subprocess.Popen(
#             [
#               'poetry',
#               'run',
#               'python3',
#               f'{GHCN_DIR}/app/climatefind/main.py',
#               '--hash-start',
#               hash_start,
#               '--overwrite'
#             ]
#           )
#         )
#
#       for proc in procs:
#         proc.communicate()

# def test_folium():
#   m = folium.Map(
#     location=[42.0573, -102.8017],
#     tiles='Stamen Terrain',
#     zoom_start=4
#   )
#   folium.Marker(
#     location=[40.9698895,-74.3118416],
#     popup='Pompton Plains',
#     icon=folium.Icon(
#       color='green',
#       icon_color='#FF0000',
#       icon='info-sign'
#     )
#   ).add_to(m)
#
#
#   test_html_filepath = f'{climatefind.GHCN_DIR}/output/test.html'
#   m.save(test_html_filepath)
#   subprocess.Popen(['open', '-a', 'Google Chrome', test_html_filepath])
