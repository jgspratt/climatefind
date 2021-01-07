# climatefind

A project to help find the right climate.

Green is better.

![GHCN Average Comfy Days](img/ghcn_average_comfy_days.png)

## Typical Meteorological Year v3 (TMY3) Version

The original version of this application used the TMY3 data which was available from [nsrdb.nrel.gov](https://nsrdb.nrel.gov/about/tmy.html) in CSV format.
Unfortunately, this version does not seem to be publicly available anymore, however, I have an archived copy.
The zipped version of the file was only 226 MB and contained detailed hourly weather data from 1,020 US locations.

The main advantage of this version was it's use of very high quality hourly data including humidity.
The main disadvantages of this version were (1) its computational complexity (due to the comfort model calculations) and (2) the low geographic density (essentially, only airports and high tech installations). 

The main configurable parameters were set in `config.yml` which allows the user to specify their personal preferences.
The resulting output graphs were generated and stored in the `output/` directory.

## Global Historical Climatology Network (GHCN) Version

The next generation software was based on the [GHCN data set](https://www.ncei.noaa.gov/data/daily-summaries/archive/daily-summaries-latest.tar.gz).
As of 2021-01-01, this project is starting.

The main advanatage of this version is the geographic density of locations (approximately 60,000 US locations in total over the entire data set).
The main disadvantage of this version is the lack of hourly granularity and humidity data.
