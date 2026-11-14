# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""S3 report (evaluation only, NOT used by the planner): coverage by direction/band, unlocked SuperCam
sites (15 m), their SIM 3464 unit, and how many of the AOI sites a single loop could reach at all.
python -m spikes.s3_report  -> qa/jezero/S3_rover_v2_report.json + S3_coverage_v1_v2.png
"""
import json, re, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from collections import Counter
from scipy.spatial import cKDTree
from skimage.graph import MCP_Geometric
from shapely.geometry import Point, shape
from pipeline.common import APP, LocalGrid
from pipeline.rover_sim import cell_cost_array, PARAMS
G = LocalGrid(77.45088572, 18.44462715); AOI = (-1700, -1000, 700, 1400); res = 2.0
W = json.loads((APP / "data_work/jezero/waypoints_all.json").read_text()); W.sort(key=lambda w: (w["sol"], w["site"], w["drive"]))
wsol = np.array([w["sol"] for w in W])
lines = (APP / "data_raw/jezero/step2/supercam/supercam_libs_moc.csv").read_text().splitlines()
hi = next(i for i, l in enumerate(lines) if l.startswith("cdr_fname"))
locs = set()
for l in lines[hi + 1:]:
    m = re.match(r"scam_(\d{4})_\d+_\d+_\w{3}_scam\d+_(.+?)_*(\d{2})p$", l.split(",")[0])
    if not m or m.group(2).strip("_").lower().startswith("scct"):
        continue
    i = int(np.searchsorted(wsol, int(m.group(1)), side="right")) - 1
    if i < 0: continue
    w = W[i]
    if AOI[0] <= w["x"] <= AOI[2] and AOI[1] <= w["y"] <= AOI[3]:
        locs.add((w["id"], w["x"], w["y"]))
locs = sorted(locs); XY = np.array([[x, y] for _, x, y in locs])
gu = json.loads((APP / "data_raw/jezero/step2/sim3464/GeoUnits_v1.geojson").read_text())["features"]
polys = [(shape(f["geometry"]), f["properties"]["symbol"]) for f in gu]
def unit_at(x, y):
    lon, lat = G.xy_to_lonlat(x, y); p = Point(float(lon), float(lat))
    return next((s for g, s in polys if g.contains(p)), None)
H = W_ = 1200
yy, xx = np.mgrid[0:H, 0:W_]
X = AOI[0] + (xx + .5) * res; Y = AOI[3] - (yy + .5) * res
dist = np.hypot(X, Y); bear = (np.degrees(np.arctan2(X, Y)) + 360) % 360
names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
sec = np.array(names)[((bear + 22.5) // 45).astype(int) % 8]
out = {}
for tag, rf, sf in (("v1", "recon_loops_v1.json", "recon_state_v1.npz"), ("v2", "recon_loops.json", "recon_state.npz")):
    R = json.loads((APP / "data_work/jezero" / rf).read_text()); obs = np.load(APP / "data_work/jezero" / sf)["observed"]
    d = {"observed_aoi_pct": round(100 * float(obs.mean()), 1), "loops": len(R["loops"]),
         "km": round(sum(L["length_m"] for L in R["loops"]) / 1000, 1)}
    d["by_direction_within_1200m_pct"] = {s: round(100 * float(obs[(sec == s) & (dist <= 1200)].mean()), 1) for s in names}
    d["by_direction_whole_aoi_pct"] = {s: round(100 * float(obs[sec == s].mean()), 1) for s in names}
    d["by_band_pct"] = {b: round(100 * float(obs[(dist >= lo) & (dist < hi_)].mean()), 1) for b, (lo, hi_) in
                        (("0-600 m", (0, 600)), ("600-1200 m", (600, 1200)), (">1200 m", (1200, 1e9)))}
    pts = np.vstack([np.c_[AOI[0] + (np.array(L["path_rc"])[:, 1] + .5) * res, AOI[3] - (np.array(L["path_rc"])[:, 0] + .5) * res] for L in R["loops"]])
    dd, _ = cKDTree(pts).query(XY)
    un = [locs[i] for i in np.nonzero(dd <= 15)[0]]
    d["unlocked_sites_r15"] = len(un); d["unlocked_units"] = dict(Counter(unit_at(x, y) for _, x, y in un))
    curve = []
    acc = []
    for L in R["loops"]:
        p = np.array(L["path_rc"]); acc.append(np.c_[AOI[0] + (p[:, 1] + .5) * res, AOI[3] - (p[:, 0] + .5) * res])
        if L["id"] in (1, 5, 10, 20, 30):
            curve.append((L["id"], int((cKDTree(np.vstack(acc)).query(XY)[0] <= 15).sum())))
    d["unlocked_by_loop"] = curve
    if tag == "v2":
        d["goal_rule_used"] = [L.get("goal_rule") for L in R["loops"]]
    out[tag] = d
    out[tag + "_obs"] = obs
out["aoi_sites"] = len(locs)
out["all_site_units"] = dict(Counter(unit_at(x, y) for _, x, y in locs))
# upper bound: round trip on the REFERENCE terrain (best case, full knowledge) within one loop budget
T = dict(np.load(APP / "data_work/jezero/terrain_2m.npz"))
c = cell_cost_array(T["class_ref"], T["blocked_rover_ref"], PARAMS)
m = MCP_Geometric(c, fully_connected=True); cc, _ = m.find_costs([(700, 850)])
rc_ = [(int((AOI[3] - y) / res), int((x - AOI[0]) / res)) for _, x, y in locs]
rt = np.array([2 * cc[r] for r in rc_])
out["reachable_upper_bound"] = {"round_trip_le_4000": int((rt <= 4000).sum()), "round_trip_le_3000_planning": int((rt <= 3000).sum()),
                                "note": "habitat->site->habitat on HiRISE reference classes (full knowledge, v2 classes), same path both ways"}
obs1, obs2 = out.pop("v1_obs"), out.pop("v2_obs")
json.dump(out, open(APP / "qa/jezero/S3_rover_v2_report.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items()}, indent=1)[:4000])
o = np.load(APP / "data_work/jezero/ortho_05.npy")[::4, ::4]
fig, ax = plt.subplots(1, 2, figsize=(20, 10.4)); e = [AOI[0], AOI[2], AOI[1], AOI[3]]
for a, ob, t in ((ax[0], obs1, "goal rule v1 (sand v1 classes)"), (ax[1], obs2, "goal rule v2 (sand v2 classes, proposed)")):
    a.imshow(o, cmap="gray", extent=e, vmin=np.nanpercentile(o, 1), vmax=np.nanpercentile(o, 99))
    rg = np.zeros(ob.shape + (4,)); rg[..., 2] = 1; rg[..., 1] = .6; rg[..., 3] = np.where(ob, .5, 0); a.imshow(rg, extent=e)
    a.add_patch(plt.Circle((0, 0), 1200, fill=False, ec="y", ls="--")); a.plot(0, 0, "c*", ms=14)
    for k in range(8):
        th = np.radians(22.5 + 45 * k); a.plot([0, 3000 * np.sin(th)], [0, 3000 * np.cos(th)], c="y", lw=.5)
    a.set_xlim(e[0], e[1]); a.set_ylim(e[2], e[3]); a.set_title(f"{t}: observed {100*ob.mean():.1f} % of the AOI")
fig.suptitle("S3: area seen by the simulated scout rover after 30 loops (blue). Yellow: 1200 m circle and 8 direction sectors. simulated, review pending")
fig.tight_layout(); fig.savefig(APP / "qa/jezero/S3_coverage_v1_v2.png", dpi=80)
