# climatefind

A project to help find the right climate.

## Global Historical Climatology Network (GHCN) Version

Green is better.  Red is worse.

![GHCN Average Comfy Days](img/ghcn_average_comfy_days.png)

To zoom in, you will need to [download the 22MB+ HTML file](https://github.com/jgspratt/climatefind/blob/master/ghcn/output/average_comfy_days.Stamen_Terrain.html?raw=true) (right-click, "download" or "save link as").

See also the [OpenStreetMap version](https://github.com/jgspratt/climatefind/blob/master/ghcn/output/average_comfy_days.OpenStreetMap.html?raw=true) with more street-level detail but less terrain detail.

You will have to do this on a computer with a desktop operating system.
Save the file somewhere and then open it up with your browser.
Github can't seem to serve it directly to your browser.
Be patient when opening it: it can take 10+ seconds to render: there are 16,000 weather stations to render and a 20-layer contour to render on top of that.

The next generation software was based on the [GHCN data set](https://www.ncei.noaa.gov/data/daily-summaries/archive/daily-summaries-latest.tar.gz).
As of 2021-01-01, this project is starting.

The main advanatage of this version is the geographic density of locations (approximately 60,000 US locations in total over the entire data set with approximately 16,000 with at least one complete year of temperature records).
The main disadvantage of this version is the lack of hourly granularity and humidity data.

## Typical Meteorological Year v3 (TMY3) Version

Yellow is better.  Blue is worse.

![TMY3 Days In Year Natural Neighbor Interpolation](tmy3/output/natural_neighbor_days_in_year.png)

The original version of this application used the TMY3 data which was available from [nsrdb.nrel.gov](https://nsrdb.nrel.gov/about/tmy.html) in CSV format.
Unfortunately, this version does not seem to be publicly available anymore, however, I have an archived copy.
The zipped version of the file was only 226 MB and contained detailed hourly weather data from 1,020 US locations.

The main advantage of this version was it's use of very high quality hourly data including humidity.
The main disadvantages of this version were (1) its computational complexity (due to the comfort model calculations) and (2) the low geographic density (essentially, only airports and high tech installations). 

The main configurable parameters were set in `config.yml` which allows the user to specify their personal preferences.
The resulting output graphs were generated and stored in the `output/` directory.
