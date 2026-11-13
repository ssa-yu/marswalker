"""Scratch demo: build the small derived files used by scratch.html (interactive demo only, not the analysis).

Run from app/:  .conda-env/bin/python web/scratch/build_data.py
Reads (unchanged): data_work/jezero/terrain_2m.npz, data_work/jezero/waypoints_all.json,
                   data_raw/jezero/step2/supercam/supercam_libs_moc.csv, web/data/jezero/photos.json
Writes: web/scratch/data/terrain.bin   1200 x 1200 uint8, row 0 = north (y = 1400 m), col 0 = west (x = -1700 m),
                                       2 m cells; low 4 bits = HiRISE reference class, high 4 bits = CTX prior class
                                       (0 firm, 1 rough, 2 sand, 3 blocked; sand classes heuristic, not yet reviewed)
        web/scratch/data/supercam.json SuperCam LIBS sites in the AOI (placed on the rover's last waypoint
                                       at or before the sol, same rule as spikes/s3_report.py), mean oxides
        web/scratch/data/views.json    hand-picked Perseverance images per terrain class of the 22 m window
                                       around the waypoint where they were taken (illustrative only)
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

APP = Path(__file__).resolve().parents[2]
OUT = APP / "web/scratch/data"
OUT.mkdir(parents=True, exist_ok=True)
AOI = (-1700, -1000, 700, 1400)
RES = 2.0

T = np.load(APP / "data_work/jezero/terrain_2m.npz")
ref, pri = T["class_ref"].astype(np.uint8), T["class_prior"].astype(np.uint8)
assert ref.shape == (1200, 1200)
(ref | (pri << 4)).tofile(OUT / "terrain.bin")

# ---- SuperCam LIBS sites
W = json.loads((APP / "data_work/jezero/waypoints_all.json").read_text())
W.sort(key=lambda w: (w["sol"], w["site"], w["drive"]))
wsol = np.array([w["sol"] for w in W])
lines = (APP / "data_raw/jezero/step2/supercam/supercam_libs_moc.csv").read_text().splitlines()
hi = next(i for i, l in enumerate(lines) if l.startswith("cdr_fname"))
head = lines[hi].split(",")
OX = ["SiO2", "TiO2", "Al2O3", "FeOT", "MgO", "CaO", "Na2O", "K2O"]
sites = defaultdict(lambda: {"targets": set(), "sols": set(), "n": 0, "sum": np.zeros(len(OX)), "cnt": np.zeros(len(OX))})
for l in lines[hi + 1:]:
    f = l.split(",")
    m = re.match(r"scam_(\d{4})_\d+_\d+_\w{3}_scam\d+_(.+?)_*(\d{2})p$", f[0])
    if not m or m.group(2).strip("_").lower().startswith("scct"):
        continue
    sol = int(m.group(1))
    i = int(np.searchsorted(wsol, sol, side="right")) - 1
    if i < 0:
        continue
    w = W[i]
    if not (AOI[0] <= w["x"] <= AOI[2] and AOI[1] <= w["y"] <= AOI[3]):
        continue
    s = sites[w["id"]]
    s.update(id=w["id"], x=round(w["x"], 1), y=round(w["y"], 1), lon=w["lon"], lat=w["lat"])
    s["targets"].add(m.group(2).strip("_")); s["sols"].add(sol); s["n"] += 1
    for j, ox in enumerate(OX):
        try:
            v = float(f[head.index(ox)])
            s["sum"][j] += v; s["cnt"][j] += 1
        except (ValueError, IndexError):
            pass
out = []
for s in sites.values():
    mean = {ox: (round(float(s["sum"][j] / s["cnt"][j]), 2) if s["cnt"][j] else None) for j, ox in enumerate(OX)}
    out.append({"id": s["id"], "x": s["x"], "y": s["y"], "lon": s["lon"], "lat": s["lat"], "n_shots": s["n"],
                "targets": sorted(s["targets"]), "sols": sorted(s["sols"]), "mean_wt_pct": mean})
out.sort(key=lambda s: s["sols"][0])
json.dump({"label": "measured (oxides); location derived",
           "location_rule": "rover's last waypoint at or before the sol of the shot (site/drive not used); precision = waypoint, LIBS standoff median ~3 m",
           "source": "Mars 2020 SuperCam LIBS major-oxide table (supercam_libs_moc.csv), PDS Geosciences; calibration targets excluded",
           "oxides": OX, "sites": out}, open(OUT / "supercam.json", "w"), indent=0)

# ---- representative ground images per terrain class (hand-picked from contact sheets, see header)
P = json.loads((APP / "web/data/jezero/photos.json").read_text())
CLS = ["firm", "rough", "sand", "blocked"]
cand = {k: [] for k in CLS[:3]}
for w in P["waypoints"]:
    r, c = int((AOI[3] - w["y"]) / RES), int((w["x"] - AOI[0]) / RES)
    if not (0 <= r < 1200 and 0 <= c < 1200):
        continue
    win = ref[max(0, r - 5):r + 6, max(0, c - 5):c + 6]
    fr = [float((win == i).mean()) for i in range(4)]
    k = int(np.argmax(fr))
    if k > 2:
        continue
    for im in w["images"]:
        if im["camera"] == "MCZ_LEFT" or fr[k] < 0.5:
            continue
        cand[CLS[k]].append((fr[k], im, w))
for k in cand:
    cand[k].sort(key=lambda t: -t[0])
# indices into the purity-sorted candidate lists (same order as the contact sheets used for picking)
CHOSEN = {"firm": [35, 38, 25, 29], "rough": [0, 1, 32, 35], "sand": [9, 7, 12, 13]}
views = {}
for k, idx in CHOSEN.items():
    views[k] = []
    for i in idx:
        fr, im, w = cand[k][i]
        views[k].append({"src": "../data/jezero/" + im["local"], "imageid": im["imageid"], "camera": im["camera"],
                         "sol": im["sol"], "waypoint": w["id"], "x": w["x"], "y": w["y"],
                         "class_share_22m": round(fr, 2), "credit": im.get("credit") or P["credit_default"],
                         "page": im.get("page"), "heading_deg": (im.get("view") or {}).get("heading_deg")})
json.dump({"label": "measured images; class assignment derived; use illustrative",
           "rule": "terrain class = majority HiRISE reference class in the 22 m window around the waypoint; Navcam/Front Hazcam only; picked by eye for a forward view",
           "views": views}, open(OUT / "views.json", "w"), indent=1)
print({k: len(v) for k, v in views.items()}, "supercam sites", len(out))
