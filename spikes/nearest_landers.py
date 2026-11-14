# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Fetch lander sites from SIM 3292 feature service layer 0 and compute great-circle distance to Arcadia AOI.
Usage: python nearest_landers.py"""
import json, math, urllib.parse, urllib.request
S = "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Tanaka_et_al_2014_Mars_Global_Map_Features/FeatureServer/0/query"
d = json.load(urllib.request.urlopen(S + "?" + urllib.parse.urlencode({"where": "1=1", "outFields": "*", "returnGeometry": "false", "f": "json"}), timeout=60))
R = 3389.5
def gc(lon1, lat1, lon2, lat2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    return R * math.acos(min(1, math.sin(p1)*math.sin(p2) + math.cos(p1)*math.cos(p2)*math.cos(dl)))
A = (189.80, 39.09)
rows = []
for f in d["features"]:
    a = f["attributes"]
    try: lon, lat = float(a["X_COORD"]), float(a["Y_COORD"])
    except (TypeError, ValueError): continue
    rows.append((gc(A[0], A[1], lon % 360, lat), a["NAME"], a.get("FULL_NAME"), a.get("YEAR"), lat, lon))
for r in sorted(rows): print(f"{r[0]:7.0f} km | {r[1]} | {r[2]} | {r[3]} | lat {r[4]} lon {r[5]}")
