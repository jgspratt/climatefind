import climatefind

climatefind.read_env()
climatefind.setup_logger()

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
  }
}

def test_version():
  assert climatefind.__version__ == '0.1.0'

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
  assert bool(climatefind.read_usa_ghcn_file_meta(samples[4]['filepath'])) == samples[4]['is_usa_location']
