import os
import sys
from pprint import pprint
import logging
import time
import yaml
import re
import pandas
import collections
import calendar

## YAML Configuration
#####################
this_script_dir_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_script_dir_path)
CONFIG_YAML_FILE_DEFAULT_PATH = os.path.join(this_script_dir_path, 'config.yml')

try:
  with open(CONFIG_YAML_FILE_DEFAULT_PATH,'r') as config_yaml_default_file:
    config_yaml_default = yaml.load(config_yaml_default_file)
except FileNotFoundError:
  raise FileNotFoundError(str('could not load file: {path}'.format(path=CONFIG_YAML_FILE_DEFAULT_PATH)))
config = config_yaml_default


class JsonLog(object):
  def __init__(self, **kwargs):
    self.kwargs = kwargs
    self.kwargs['@timestamp'] = datetime.now().isoformat()
  
  def __str__(self):
    return '{json_string}'.format(json_string=json.dumps(self.kwargs, sort_keys=True))
jl = JsonLog


## Setup logging
################
log = logging.getLogger('main')
log.setLevel(logging.INFO)
logFormatter = logging.Formatter(fmt=config['LOG_FORMAT'], style='{', datefmt=config['LOG_DATE_FORMAT'])

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
log.addHandler(consoleHandler)

fileHandler = logging.FileHandler(config['LOG_FILENAME'])
fileHandler.setFormatter(logFormatter)
log.addHandler(fileHandler)


json_log = logging.getLogger('json')
json_log.setLevel(logging.INFO)
logFormatterJson = logging.Formatter(config['LOG_FORMAT_JSON'], style='{')
fileHandlerJson = logging.FileHandler(config['LOG_FILENAME_JSON'])
fileHandlerJson.setFormatter(logFormatterJson)
json_log.addHandler(fileHandlerJson)


log.info('it works')

## Format columns
#################

# column header on line 1 (after line 0)
# date + time in column 0,1
header_read = pandas.read_csv(config['DATA_SMALL_SAMPLE'], header=1, nrows=1, parse_dates=[[0,1]])

regex_replace_dict = dict((re.escape(k), v) for k, v in config['COLUMS_REPLACEMENT_DICTIONARY'].items())
regex_pattern_string = re.compile("|".join(regex_replace_dict.keys()))
simplified_column_names = ['date']
for column in header_read.columns:
  column_name = (regex_pattern_string.sub(lambda m: regex_replace_dict[re.escape(m.group(0))], column)).lower()
  # print(f'column_name: {column_name}')
  # print(f'{column_name}')
  simplified_column_names.append(column_name)

pprint(simplified_column_names)

# move hour back one to avoid this error:
#   ValueError: time data '01/01/1985 24:00' does not match format '%m/%d/%Y %H:%M'
# Also, because the records all **end** at the time listed (they are for the previous hour)
dateparse = lambda date, hour: pandas.datetime.strptime(f'{date} {int(hour[0:2])-1:02}:00', '%m/%d/%Y %H:%M')


datafile = pandas.read_csv(config['DATA_SMALL_SAMPLE'], header=1, parse_dates=[[0,1]], keep_date_col=True, date_parser=dateparse, names=simplified_column_names)
# datafile = pandas.read_csv(config['DATA_SMALL_SAMPLE'], header=1, nrows=48, parse_dates=[[0,1]], keep_date_col=True, date_parser=dateparse, names=simplified_column_names)

print(datafile.columns)
print(str(datafile.size))

# print(datafile)

year = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict( int ))))
comfy_year = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict()))

log.info('make array - start')

for index, row in datafile.iterrows():
  important_cols = [
    'dry_bulb_c',
    'dew_point_c',
    'rhum_percent',
    'wspd_m_s',
    'lprecip_depth_mm',
  ]
  
  for col in important_cols:
    year[row['date_time'].month][row['date_time'].day][row['date_time'].hour][col] = row[col]

log.info('make array - done')

def comfy(dry_bulb_c, dew_point_c):
  if 15 < dry_bulb_c < 25 and dew_point_c < 15:
    return True
  else:
    return False

for month, days in year.items():
  for day, hours in days.items():
    for hour, cols in hours.items():
      year[month][day][hour]['comfy'] = comfy(dry_bulb_c=cols['dry_bulb_c'], dew_point_c=cols['dew_point_c'])

comfy_days_in_year = 0
for month, days in year.items():
  comfy_days_in_month = 0
  for day, hours in days.items():
    comfy_hours = 0
    for hour, cols in hours.items():
      # print(f'{month:02}{day:02} {hour:02}: temp:{cols["dry_bulb_c"]}, dp:{cols["dew_point_c"]}  {cols["comfy"]}')
      if cols['comfy']: comfy_hours += 1
      comfy_year[month][day]['comfy'] = comfy_hours >= 6
    if comfy_hours >= 6:
      # print(f'{month:02}-{day:02}: comfy!')
      comfy_days_in_month += 1
      comfy_days_in_year += 1
    else:
      # print(f'{month:02}-{day:02}')
      pass
  print(f'month {month:02} ({calendar.month_abbr[month]}): {comfy_days_in_month} comfy days')


