import os
import sys
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.colors import BoundaryNorm
import matplotlib.pyplot as plt
import numpy as np
from pprint import pprint
from time import strftime
from tqdm import tqdm

from metpy.cbook import get_test_data
from metpy.gridding.gridding_functions import (interpolate, remove_nan_observations, remove_repeat_coordinates)
from metpy.plots import add_metpy_logo

this_script_dir_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_script_dir_path)

np.seterr(divide='ignore', invalid='ignore')

print('it works')

col_map = {
  10: 'days_in_year',
  11: 'months_in_year',
  12: '01_jan',
  13: '02_feb',
  14: '03_mar',
  15: '04_apr',
  16: '05_may',
  17: '06_jun',
  18: '07_jul',
  19: '08_aug',
  20: '09_sep',
  21: '10_oct',
  22: '11_nov',
  23: '12_dec',
}

run_day = f'{strftime("%Y-%m-%d")}'
run_time = f'{strftime("%H%M%S")}'

def basic_map(proj):
  """Make our basic default map for plotting"""
  fig = plt.figure(figsize=(15, 10))
  add_metpy_logo(fig, 0, 80, size='large')
  view = fig.add_axes([0, 0, 1, 1], projection=proj)
  view.set_extent([-120, -70, 20, 50])
  view.add_feature(cfeature.STATES.with_scale('50m'))
  view.add_feature(cfeature.OCEAN)
  view.add_feature(cfeature.COASTLINE)
  view.add_feature(cfeature.BORDERS, linestyle=':')
  return fig, view


def station_test_data(variable_names, col_num, proj_from=None, proj_to=None):
  all_data = np.loadtxt(
    './data/comfy_data_monthly.csv',
    skiprows=1,
    delimiter=',',
    usecols=(1, 5, 6, col_num),
    dtype=np.dtype([
      ('stid', '6S'), 
      ('lat', 'f'),
      ('lon', 'f'),
      ('comfy_days', 'f')
    ])
  )
  
  # pprint(len(all_data))
  
  # for row in all_data:
  #   print(row)
  
  all_stids = [s.decode('ascii') for s in all_data['stid']]
  
  # pprint(len(all_stids))

  data = np.concatenate([all_data[all_stids.index(site)].reshape(1, ) for site in all_stids])

  value = data[variable_names]
  lon = data['lon']
  lat = data['lat']

  if proj_from is not None and proj_to is not None:
    try:
      proj_points = proj_to.transform_points(proj_from, lon, lat)
      return proj_points[:, 0], proj_points[:, 1], value
    except Exception as e:
      print(e)
      return None
  return lon, lat, value


from_proj = ccrs.Geodetic()
to_proj = ccrs.AlbersEqualArea(central_longitude=-97.0000, central_latitude=38.0000)

levels = list(range(0, 100, 5))
cmap = plt.get_cmap('viridis')
norm = BoundaryNorm(levels, ncolors=cmap.N, clip=True)

progress_bar_files = tqdm(total=len(col_map.items()), position=0, unit='file')

for col_num, col_name in col_map.items():
  
  x, y, comfy_days = station_test_data('comfy_days', col_num, from_proj, to_proj)
  
  x, y, comfy_days = remove_nan_observations(x, y, comfy_days)
  
  # for i in range(len(comfy_days)):
  #   print(f'{x[i]}, {y[i]}: {comfy_days[i]}')
  
  x, y, comfy_days = remove_repeat_coordinates(x, y, comfy_days)
  
  
  gx, gy, img = interpolate(x, y, comfy_days, interp_type='linear', hres=10000)
  img = np.ma.masked_where(np.isnan(img), img)
  fig, view = basic_map(to_proj)
  mmb = view.pcolormesh(gx, gy, img, cmap=cmap, norm=norm)
  fig.colorbar(mmb, shrink=.4, pad=0, boundaries=levels)
  
  # https://unidata.github.io/MetPy/latest/examples/gridding/Point_Interpolation.html#sphx-glr-examples-gridding-point-interpolation-py
  
  ## RFB
  #########
  # gx, gy, img = interpolate(x, y, comfy_days, interp_type='rbf', hres=75000, rbf_func='linear', rbf_smooth=1)
  # img = np.ma.masked_where(np.isnan(img), img)
  # fig, view = basic_map(to_proj)
  # mmb = view.pcolormesh(gx, gy, img, cmap=cmap, norm=norm)
  # fig.colorbar(mmb, shrink=.4, pad=0, boundaries=levels)
  
  
  ## Natural Neighbor
  ###################
  # gx, gy, img = interpolate(x, y, comfy_days, interp_type='natural_neighbor', hres=25000)
  # img = np.ma.masked_where(np.isnan(img), img)
  # fig, view = basic_map(to_proj)
  # mmb = view.pcolormesh(gx, gy, img, cmap=cmap, norm=norm)
  # fig.colorbar(mmb, shrink=.4, pad=0, boundaries=levels)
  
  ## Cressman
  ###########
  # gx, gy, img = interpolate(x, y, comfy_days, interp_type='cressman', minimum_neighbors=1, hres=25000,
  #                           search_radius=100000)
  # img = np.ma.masked_where(np.isnan(img), img)
  # fig, view = basic_map(to_proj)
  # mmb = view.pcolormesh(gx, gy, img, cmap=cmap, norm=norm)
  # fig.colorbar(mmb, shrink=.4, pad=0, boundaries=levels)
  
  ## Barnes
  #########
  # gx, gy, img1 = interpolate(x, y, comfy_days, interp_type='barnes', hres=75000, search_radius=100000)
  # img1 = np.ma.masked_where(np.isnan(img1), img1)
  # fig, view = basic_map(to_proj)
  # mmb = view.pcolormesh(gx, gy, img1, cmap=cmap, norm=norm)
  # fig.colorbar(mmb, shrink=.4, pad=0, boundaries=levels)
  
  
  ## Radial basis
  ###############
  # gx, gy, img = interpolate(x, y, comfy_days, interp_type='rbf', hres=25000, rbf_func='linear', rbf_smooth=0)
  # img = np.ma.masked_where(np.isnan(img), img)
  # fig, view = basic_map(to_proj)
  # mmb = view.pcolormesh(gx, gy, img, cmap=cmap, norm=norm)
  # fig.colorbar(mmb, shrink=.4, pad=0, boundaries=levels)
  
  plt.savefig(fname=f'export/{run_day}/{run_time}_{col_name}.png')
  progress_bar_files.update(1)

# plt.show()
