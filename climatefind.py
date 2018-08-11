import os
import logging
import time
import yaml
import re
import pandas

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

# column header on line 1 (after line 0)
# date + time in column 0,1
rows = pandas.read_csv(config['DATA_SMALL_SAMPLE'], header=1, nrows=1, parse_dates=[[0,1]])

regex_replace_dict = dict((re.escape(k), v) for k, v in config['COLUMS_REPLACEMENT_DICTIONARY'].items())
regex_pattern_string = re.compile("|".join(regex_replace_dict.keys()))
simplified_column_names = []
for column in rows.columns:
  column_name = (regex_pattern_string.sub(lambda m: regex_replace_dict[re.escape(m.group(0))], column)).lower()
  log.info(f'column_name: {column_name}')
  simplified_column_names += column_name


