# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Read SIM 3464 GeoUnits_v1 straight out of the remote zip (GDAL /vsizip//vsicurl) and count units in the Jezero AOI.
Usage: python sim3464_units.py OUT.gpkg"""
import os, sys, time
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import pyogrio, numpy as np
from pyproj import Transformer
from shapely import box, wkb
G = "/vsizip//vsicurl/https://pubs.usgs.gov/sim/3464/sim3464_database.zip/sim3464_JezeroNili_FINAL/Geodatabase/Nili.gdb"
t = time.time()
print("layers:", [l[0] for l in pyogrio.list_layers(G)]); info = pyogrio.read_info(G, layer="GeoUnits_v1")
print("GeoUnits_v1:", info["features"], "features; fields", list(info["fields"]), "|", round(time.time()-t, 1), "s")
meta, _, geoms, fields = pyogrio.raw.read(G, layer="GeoUnits_v1")
print("read", round(time.time()-t, 1), "s; crs:", meta["crs"][:120])
names = list(meta["fields"]); unit_col = "symbol"
units = [f"{a} ({b})" for a, b in zip(fields[names.index("symbol")], fields[names.index("name")])]
# Jezero AOI from waypoints spike (base-origin metres): x[-1700,700] y[-1000,1400]; base lon 77.45088572 lat 18.44462715
import math
R = 3389500.0; blon, blat = 77.45088572, 18.44462715
def ll(x, y): return blon + math.degrees(x / (R * math.cos(math.radians(blat)))), blat + math.degrees(y / R)
corners = [ll(x, y) for x, y in ((-1700, -1000), (700, -1000), (700, 1400), (-1700, 1400))]
tr = Transformer.from_crs("+proj=longlat +R=3396190 +no_defs", meta["crs"], always_xy=True)
xs, ys = zip(*[tr.transform(*c) for c in corners]); aoi = box(min(xs), min(ys), max(xs), max(ys))
area = {}
for g, u in zip(geoms, units):
    s = wkb.loads(g)
    if s.intersects(aoi): area[u] = area.get(u, 0) + s.intersection(aoi).area
tot = aoi.area
print(f"unit field '{unit_col}'; AOI units (share of AOI area):", {k: round(v / tot, 3) for k, v in sorted(area.items(), key=lambda kv: -kv[1])})
