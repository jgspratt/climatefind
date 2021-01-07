```python
d = {
  'row1': {
    'station': 1234,
    'comfy': 333,
    'lat': 333,
    'lon': 333,
  },
  'row2': {
    'station': 1234,
    'comfy': 333,
    'lat': 333,
    'lon': 333,
  }
}

# >>> df = pd.DataFrame.from_dict(d, orient="index")
# >>> df
#       station  comfy  lat  lon
# row1     1234    333  333  333
# row2     1234    333  333  333

# >>> df.to_csv("data3.csv", header=True)

# cat data3.csv
# ,station,comfy,lat,lon
# row1,1234,333,333,333
# row2,1234,333,333,333
```
