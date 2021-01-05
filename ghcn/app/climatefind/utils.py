# Core
import collections
import typing
import copy
import hashlib
import json
import re

def deep_dict_merge(
  default: typing.Any,
  override: typing.Any,
) -> typing.Dict[typing.Any, typing.Any]:
  """
  :param default: First dict to merge
  :param override: Second dict to merge
  :return: The merge dictionary
  """
  merged = copy.deepcopy(default)
  for k, val2 in override.items():
    if k in merged:
      val1 = merged[k]
      if isinstance(val1, dict) and isinstance(val2, collections.abc.Mapping):  # type: ignore
        merged[k] = deep_dict_merge(val1, val2)
      elif isinstance(val1, list) and isinstance(val2, list):
        merged[k] = val1 + val2
      else:
        merged[k] = copy.deepcopy(val2)
    else:
      merged[k] = copy.deepcopy(val2)
  return merged

def get_filename_hash(filename: str):
  return hashlib.sha256(filename.encode('ascii')).hexdigest()

def compact_json_dumps(obj, width=None, indent=None):
  """
  Better docs needed
  """
  non_space_pattern = re.compile('[^ ]')
  r = json.dumps(obj, indent=indent)
  if indent and width:
    lines = r.split('\n')
    result_lines = [lines[0]]
    prev_space_count = None
    for line in lines[1:]:
      splitted = non_space_pattern.split(line)
      space_count = len(splitted[0])
      if space_count and prev_space_count:
        if (
          space_count == prev_space_count
          or (
            space_count > prev_space_count and
            space_count - prev_space_count <= indent
          )
        ):
          if (
            len(line) + len(result_lines[-1]) - space_count <= width
            and not result_lines[-1].rstrip().endswith(('],', '},'))
          ):
            result_lines[-1] = result_lines[-1] + line[space_count:]
            continue
      result_lines.append(line)
      prev_space_count = space_count
    r = '\n'.join(result_lines)

  return r
