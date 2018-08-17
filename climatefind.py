import os
import sys
import csv
from pprint import pprint
from tqdm import tqdm
import logging
import time
import yaml
import re
import pandas
import collections
import calendar
import comfort_models
import glob
import ntpath
import colorama
import datetime
from time import strftime
import numbers



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


def comfy(dry_bulb_c, dew_point_c, rhum_percent, wspd_m_s, lprecip_depth_mm, hour):
  if config['LATEST_HOUR'] < hour or hour < config['EARLIEST_HOUR']:
    return False
  
  # if wspd_m_s == 0:
  #   wspd_m_s = 0.1  # comfPMVElevatedAirspeed can't handle zero wind.  You'll get this error:
  #     # X = X_OLD - DELTA * ERR1 / (ERR2 - ERR1)
  #     # ZeroDivisionError: float division by zero

  
  if config['SPEED'] == 'FAST':
    if config['MIN_DRY_BULB_C'] < dry_bulb_c < config['MAX_DRY_BULB_C'] and \
      dew_point_c < config['MAX_DEW_POINT'] and \
      wspd_m_s < config['MAX_WINDSPEED_MS'] and \
      lprecip_depth_mm == config['MAX_LIQUID_PRECIP_MM'] and \
      config['EARLIEST_HOUR'] <= hour <= config['LATEST_HOUR']:
      return True
    else:
      return False
  else:
    try:
      how_you_would_feel_dressed_cool_walking_slow=comfort_models.comfPMVElevatedAirspeed(
        ta=dry_bulb_c,
        tr=dry_bulb_c,
        vel=wspd_m_s,
        rh=rhum_percent,
        met=config['MIN_METABOLIC_RATE'],
        clo=config['MIN_CLOTHING_RATING'],
        wme=0  # This is like the heat generated (in MET units) by rubbing sandpaper against wood.  In practice, assume zero.
      )[2]
    except ArithmeticError:
      log.warning(f'could not calculate this data: ta={dry_bulb_c}, tr={dry_bulb_c}, vel={wspd_m_s}, rh={rhum_percent},met={config["MAX_METABOLIC_RATE"]},clo={config["MAX_CLOTHING_RATING"]},wme=0)')
      return False
      
    try:
      how_you_would_feel_dressed_warm_walking_fast=comfort_models.comfPMVElevatedAirspeed(
        ta=dry_bulb_c,
        tr=dry_bulb_c,
        vel=wspd_m_s,
        rh=rhum_percent,
        met=config['MAX_METABOLIC_RATE'],
        clo=config['MAX_CLOTHING_RATING'],
        wme=0
      )[2]
    except ArithmeticError:
      log.warning(f'could not calculate this data: ta={dry_bulb_c}, tr={dry_bulb_c}, vel={wspd_m_s}, rh={rhum_percent},met={config["MAX_METABOLIC_RATE"]},clo={config["MAX_CLOTHING_RATING"]},wme=0)')
      return False
    
    
    if how_you_would_feel_dressed_cool_walking_slow <= config['DESIRED_STANDARD_EFFECTIVE_TEMPERATURE'] <= how_you_would_feel_dressed_warm_walking_fast and \
      dew_point_c <= config['MAX_DEW_POINT'] and \
      lprecip_depth_mm <= config['MAX_RAIN_DEPTH'] and \
      wspd_m_s <= config['MAX_WIND_SPEED']:
      return True
    else:
      return False


## Setup logging
################
log = logging.getLogger('main')
log.setLevel(logging.WARNING)
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


print('it works')

## Format columns
#################
files_list = glob.glob(config[config['MODE']])

# print(files_list)

# sys.exit()

comfyness_report = {}

progress_bar_files = tqdm(total=len(files_list), position=0, unit='station')

filecount = 0
for sample_file in files_list:
  filecount += 1
  if filecount > config['MAX_FILES']:
    break
  
  # meta header
  meta_header = {}
  station_meta = []
  meta_header_file = pandas.read_csv(sample_file, nrows=1, header=None, names=config['META_HEADER_ROWS'])
  for column in config['META_HEADER_ROWS']:
    meta_header[column] = str(meta_header_file.at[0,column])
    try:
      station_meta.append(round(float(meta_header[column]),3))
    except ValueError:
      station_meta.append(meta_header[column])
  
  file_code = str(ntpath.basename(sample_file)[:-4])
  
  # pprint(meta_header)
  # pprint(station_meta)
  # sys.exit()
  
  # column header on line 1 (after line 0)
  # date + time in column 0,1
  header_read = pandas.read_csv(sample_file, header=1, nrows=1, parse_dates=[[0,1]])
  
  regex_replace_dict = dict((re.escape(k), v) for k, v in config['COLUMS_REPLACEMENT_DICTIONARY'].items())
  regex_pattern_string = re.compile("|".join(regex_replace_dict.keys()))
  simplified_column_names = ['date']
  for column in header_read.columns:
    column_name = (regex_pattern_string.sub(lambda m: regex_replace_dict[re.escape(m.group(0))], column)).lower()
    # print(f'column_name: {column_name}')
    # print(f'{column_name}')
    simplified_column_names.append(column_name)
  
  # pprint(simplified_column_names)
  
  # move hour back one to avoid this error:
  #   ValueError: time data '01/01/1985 24:00' does not match format '%m/%d/%Y %H:%M'
  # Also, because the records all **end** at the time listed (they are for the previous hour)
  dateparse = lambda date, hour: pandas.datetime.strptime(f'{date} {int(hour[0:2])-1:02}:00', '%m/%d/%Y %H:%M')
  
  
  datafile = pandas.read_csv(sample_file, header=1, parse_dates=[[0,1]], keep_date_col=True, date_parser=dateparse, names=simplified_column_names)
  # datafile = pandas.read_csv(config['DATA_SMALL_SAMPLE'], header=1, nrows=48, parse_dates=[[0,1]], keep_date_col=True, date_parser=dateparse, names=simplified_column_names)
  
  # print(datafile.columns)
  log.debug(str(datafile.size))
  
  # print(datafile)
  
  year = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict( int ))))
  comfy_year = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict()))
  
  log.info(f'make hash for {file_code}: {meta_header["station_name"]}, {meta_header["station_state"]} - start')
  
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
  
  log.info(f'make hash for {file_code}: {meta_header["station_name"]}, {meta_header["station_state"]} - done')
  
  log.info(f'calculate comfyness for {file_code}: {meta_header["station_name"]}, {meta_header["station_state"]} - start')
  
  progress_bar_months = tqdm(total=12, position=1, unit='month')
  for month, days in year.items():
    # sys.stdout.write(f'month {month:02} ({calendar.month_abbr[month]})')
    # sys.stdout.flush()
    progress_bar_days = tqdm(total=len(days.items()), position=2, unit='day')
    for day, hours in days.items():
      for hour, cols in hours.items():
        # print(f'{month}-{day} {hour}')  # Use this if you need to find some bad data
        year[month][day][hour]['comfy'] = comfy(
          dry_bulb_c=cols['dry_bulb_c'],
          dew_point_c=cols['dew_point_c'],
          rhum_percent=cols['rhum_percent'],
          wspd_m_s=cols['wspd_m_s'],
          lprecip_depth_mm=cols['lprecip_depth_mm'],
          hour=hour
        )
      progress_bar_days.update(1)
    progress_bar_months.update(1)
    # sys.stdout.write('.')
    # sys.stdout.flush()
  
  log.info(f'\n\nReport for {file_code}: {meta_header["station_name"]}, {meta_header["station_state"]}:\n')
  
  progress_bar_days.close()
  progress_bar_months.close()
  
  comfy_days_in_year = 0
  comfy_months_in_year_count = 0
  comfy_days_in_months_percent = []
  for month, days in year.items():
    comfy_days_in_month = 0
    total_days_in_month = len(days.items())
    for day, hours in days.items():
      comfy_hours = 0
      for hour, cols in hours.items():
        # print(f'{month:02}{day:02} {hour:02}: temp:{cols["dry_bulb_c"]}, dp:{cols["dew_point_c"]}  {cols["comfy"]}')
        if cols['comfy']: comfy_hours += 1
        comfy_year[month][day]['comfy'] = comfy_hours >= 6
      if comfy_hours >= config['MIN_COMFY_HOURS']:
        # print(f'{month:02}-{day:02}: comfy!')
        comfy_days_in_month += 1
        comfy_days_in_year += 1
      else:
        # print(f'{month:02}-{day:02}')
        pass
    comfy_days_in_month_percent = round((comfy_days_in_month/total_days_in_month)*100)
    comfy_days_in_months_percent.append(comfy_days_in_month_percent)
    if comfy_days_in_month_percent >= config['MIN_COMFY_DAYS_PER_MONTH_PERCENT']:
      comfy_months_in_year_count += 1
    log.info(f'  month {month:02} ({calendar.month_abbr[month]}): {comfy_days_in_month: >2} comfy days')
  
  comfy_days_in_year_percent = round((comfy_days_in_year/365)*100)
  comfy_months_in_year_percent = round((comfy_months_in_year_count/12)*100)
  
  log.info(f'\n  Typical year: {comfy_days_in_year} comfy days   ({comfy_days_in_year_percent: >3}%)')
  log.info(f'                  {comfy_months_in_year_count} comfy months ({comfy_months_in_year_percent: >3}%)\n\n')
  
  log.info(f'calculate comfyness for {file_code}: {meta_header["station_name"]}, {meta_header["station_state"]} - done')
  
  comfyness_report[file_code] = (station_meta + [comfy_days_in_year, comfy_months_in_year_count, comfy_days_in_year_percent, comfy_months_in_year_percent] + comfy_days_in_months_percent)
  
  progress_bar_files.update(1)

progress_bar_files.close()

time.sleep(2)

# print(comfyness_report)

write_out_this = pandas.DataFrame.from_dict(
  data=comfyness_report,
  orient='index', 
  columns=(
    config['META_HEADER_ROWS'] + 
    ['comfy_days_in_year', 'comfy_months_in_year', 'comfy_days_in_year_percent', 'comfy_months_in_year_percent'] + 
    [f'month_{x}_%' for x in range(1,13)]
  )
)

# print(write_out_this)

output_file_folder = f'export/{strftime("%Y-%m-%d")}'
os.mkdir(output_file_folder)
output_file_path = f'{output_file_folder}/{config["MODE"]}_{config["SPEED"]}_{strftime("%Y-%m-%d_%H%M%S")}_{config["OUTPUT_FILENAME"]}.{config["OUTPUT_EXT"]}'

write_out_this.to_csv(
  output_file_path,
  header=(
    config['META_HEADER_ROWS'] + 
    ['comfy_days_in_year', 'comfy_months_in_year', 'comfy_days_in_year_percent', 'comfy_months_in_year_percent'] + 
    [f'month_{x}_%' for x in range(1,13)]
  )
)

# with open('comfyness_report.csv', 'w') as csv_file:
#     writer = csv.writer(csv_file)
#     for key, value in comfyness_report.items():
#        writer.writerow([key, value])
