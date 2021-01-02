import collections
import typing
import copy
import hashlib

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
