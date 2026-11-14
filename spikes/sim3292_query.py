# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Query USGS SIM 3292 (Tanaka 2014) Global_Geology feature service for units at given sites,
and units within a lon/lat box (counts). Usage: python sim3292_query.py"""
import json, urllib.parse, urllib.request
from pyproj import Transformer
S = "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Tanaka_et_al_2014_Mars_Global_Map_Features/FeatureServer/3/query"
ROB = "+proj=robin +lon_0=0 +R=3396190 +units=m +no_defs"
tr = Transformer.from_crs("+proj=longlat +R=3396190 +no_defs", ROB, always_xy=True)
SITES = {"Starship 060706": (189.80, 39.09), "Starship 060719": (195.62, 39.81), "Starship 061075": (195.61, 39.18),
         "Starship 060363": (192.06, 39.82), "Starship 061128": (190.16, 38.64), "Jezero base": (77.45, 18.44)}
def q(params):
    url = S + "?" + urllib.parse.urlencode({**params, "f": "json"})
    return json.load(urllib.request.urlopen(url, timeout=120))
for n, (lon, lat) in SITES.items():
    x, y = tr.transform(lon - 360 if lon > 180 else lon, lat)
    d = q({"geometry": f"{x},{y}", "geometryType": "esriGeometryPoint", "spatialRel": "esriSpatialRelIntersects",
           "outFields": "*", "returnGeometry": "false"})
    print(n, [(f["attributes"].get("FIRST_Unit") or f["attributes"].get("Unit"), f["attributes"].get("FIRST_UnitDesc") or f["attributes"].get("UnitDesc")) for f in d.get("features", [])], d.get("error"))
# fields once
d = q({"where": "1=1", "outFields": "*", "returnGeometry": "false", "resultRecordCount": 1})
print("fields:", list(d["features"][0]["attributes"].keys()) if d.get("features") else d)
