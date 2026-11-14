# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""R4 step-2 verification (Q1, Q2, Q4, Q5, Q9, Q10) - facts and check images only; nothing here is a product.

python -I spikes/q_step2.py      (from app/) -> qa/jezero/step2/q_results.json + figures

No parameter here is tuned on sample rankings. Cluster counts, radii and splits are PROPOSALS.
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pipeline.common import LocalGrid  # noqa: E402

S2 = APP / "data_raw/jezero/step2"
OUT = APP / "qa/jezero/step2"; OUT.mkdir(parents=True, exist_ok=True)
G = LocalGrid(77.45088572, 18.44462715)
AOI = (-1700, -1000, 700, 1400)
RIM = (-11300, -1000, -8900, 1400)
OX = ["SiO2", "TiO2", "Al2O3", "FeOT", "MgO", "CaO", "Na2O", "K2O"]
R = {}

# ---------------- waypoints ------------------------------------------------------------------------
W = json.loads((APP / "data_work/jezero/waypoints_all.json").read_text())
W.sort(key=lambda w: (w["sol"], w["site"], w["drive"]))
wsol = np.array([w["sol"] for w in W])


def wp_for_sol(s):
    """Last waypoint whose arrival sol <= s (manager's rule). Also flags ambiguity: a drive ended on sol s."""
    i = int(np.searchsorted(wsol, s, side="right")) - 1
    if i < 0:
        return None, False
    amb = bool(np.any(wsol == s)) and i > 0 and W[i - 1]["sol"] < s
    return W[i], amb


def inbox(x, y, b):
    return b[0] <= x <= b[2] and b[1] <= y <= b[3]


# ---------------- Q1 SuperCam LIBS MOC -------------------------------------------------------------
lines = (S2 / "supercam/supercam_libs_moc.csv").read_text().splitlines()
hdr_i = next(i for i, l in enumerate(lines) if l.startswith("cdr_fname"))
head = {l.split(",")[0]: l.split(",") for l in lines[:hdr_i]}
rmsep = {OX[k]: float(head["RMSEP"][1 + 2 * k]) for k in range(8)}
cols = lines[hdr_i].split(",")
rows = []
n_scct = 0
for l in lines[hdr_i + 1:]:
    p = l.split(",")
    if len(p) < len(cols):
        continue
    fn = p[0]
    m = re.match(r"scam_(\d{4})_\d+_\d+_\w{3}_scam\d+_(.+?)_*(\d{2})p$", fn)
    if not m:
        continue
    sol, tgt, pt = int(m.group(1)), m.group(2).strip("_"), int(m.group(3))
    vals = {c: p[i] for i, c in enumerate(cols)}
    try:
        ox = [float(vals[o]) for o in OX]
    except ValueError:
        continue
    if tgt.lower().startswith("scct"):
        n_scct += 1
        continue  # SuperCam calibration targets on the rover deck, not Mars rocks
    rows.append({"fn": fn, "sol": sol, "target": tgt, "pt": pt, "ox": ox, "total": float(vals["Total"] or "nan"),
                 "dist_mm": float(vals["distance_mm"]) if vals["distance_mm"] else np.nan})
n_rows = len(lines) - hdr_i - 1
tg = defaultdict(list)
for r in rows:
    tg[(r["sol"], r["target"])].append(r)
amb_n = 0
for r in rows:
    w, amb = wp_for_sol(r["sol"])
    r["wp"] = w["id"] if w else None; r["x"] = w["x"] if w else np.nan; r["y"] = w["y"] if w else np.nan; r["amb"] = amb
aoi_rows = [r for r in rows if r["wp"] and inbox(r["x"], r["y"], AOI)]
aoi_t = {(r["sol"], r["target"]) for r in aoi_rows}
aoi_w = {r["wp"] for r in aoi_rows}
d = np.array([r["dist_mm"] for r in rows]) / 1000
R["Q1"] = {"rows_in_file": n_rows, "rows_calibration_targets_excluded": n_scct, "rows_parsed": len(rows), "targets_sol_name": len(tg),
           "target_names_unique": len({t for _, t in tg}), "sol_range": [min(r["sol"] for r in rows), max(r["sol"] for r in rows)],
           "rmsep_wt%": rmsep,
           "location_rule": "waypoint with the largest arrival sol <= measurement sol (sorted by sol, site, drive)",
           "rows_on_sols_with_a_drive_end": sum(r["amb"] for r in rows),
           "aoi": {"points": len(aoi_rows), "targets": len(aoi_t), "waypoints": len(aoi_w),
                   "sol_range": [min(r["sol"] for r in aoi_rows), max(r["sol"] for r in aoi_rows)]},
           "distance_m": {"median": round(float(np.nanmedian(d)), 2), "p90": round(float(np.nanpercentile(d, 90)), 2),
                          "max": round(float(np.nanmax(d)), 2)}}

# target means (AOI) and clustering in RMSEP units
T_aoi = []
for key in sorted(aoi_t):
    rr = tg[key]
    T_aoi.append({"key": key, "wp": rr[0]["wp"], "x": rr[0]["x"], "y": rr[0]["y"], "ox": np.mean([r["ox"] for r in rr], 0), "n": len(rr)})
X = np.array([t["ox"] for t in T_aoi])
Z = X / np.array([rmsep[o] for o in OX])
from scipy.cluster.hierarchy import fcluster, linkage  # noqa: E402
Lk = linkage(Z, "ward")
clus = {}
for k in range(2, 8):
    lab = fcluster(Lk, k, "maxclust")
    cen = np.array([X[lab == c].mean(0) for c in range(1, k + 1)])
    sizes = [int((lab == c).sum()) for c in range(1, k + 1)]
    # separation of every centroid pair: largest oxide difference in RMSEP units
    sep = [max(abs(cen[i, j] - cen[l, j]) / rmsep[OX[j]] for j in range(8)) for i in range(k) for l in range(i + 1, k)]
    # silhouette (Euclidean in RMSEP units)
    D = np.sqrt(((Z[:, None, :] - Z[None, :, :]) ** 2).sum(-1))
    sil = []
    for i in range(len(Z)):
        a = D[i, lab == lab[i]].sum() / max((lab == lab[i]).sum() - 1, 1)
        b = min(D[i, lab == c].mean() for c in set(lab) if c != lab[i])
        sil.append((b - a) / max(a, b))
    clus[k] = {"sizes": sizes, "min_pair_sep_rmsep": round(float(min(sep)), 2), "silhouette": round(float(np.mean(sil)), 3),
               "centroids": {OX[j]: [round(float(cen[c, j]), 1) for c in range(k)] for j in range(8)}}
R["Q1"]["clusters_aoi_targets_ward_rmsep_units"] = clus

# SIM 3464 unit at each AOI target location
try:
    from shapely.geometry import Point, shape
    gu = json.loads((S2 / "sim3464/GeoUnits_v1.geojson").read_text())["features"]
    polys = [(shape(f["geometry"]), f["properties"]["symbol"], f["properties"]["name"]) for f in gu]

    def unit_at(x, y):
        lon, lat = G.xy_to_lonlat(x, y)
        p = Point(float(lon), float(lat))
        for g_, s_, n_ in polys:
            if g_.contains(p):
                return s_
        return None
    for t in T_aoi:
        t["unit"] = unit_at(t["x"], t["y"])
    k = 4
    lab = fcluster(Lk, k, "maxclust")
    ct = Counter((int(l), t["unit"]) for l, t in zip(lab, T_aoi))
    R["Q1"]["cluster4_vs_sim3464_unit"] = {f"c{c}|{u}": n for (c, u), n in sorted(ct.items(), key=lambda kv: (kv[0][0], str(kv[0][1])))}
    R["Q1"]["aoi_target_units"] = dict(Counter(t["unit"] for t in T_aoi))
    # AOI area share of units
    from shapely.geometry import box
    lo0, la0 = G.xy_to_lonlat(AOI[0], AOI[1]); lo1, la1 = G.xy_to_lonlat(AOI[2], AOI[3])
    bx = box(float(lo0), float(la0), float(lo1), float(la1))
    ar = defaultdict(float)
    for g_, s_, n_ in polys:
        if g_.intersects(bx):
            ar[f"{s_} ({n_})"] += g_.intersection(bx).area
    tot = bx.area
    R["Q1"]["aoi_sim3464_area_share"] = {k_: round(v / tot, 3) for k_, v in sorted(ar.items(), key=lambda kv: -kv[1])}
except Exception as e:  # noqa: BLE001
    R["Q1"]["sim3464"] = f"not evaluated: {e}"

fig, axs = plt.subplots(2, 4, figsize=(18, 8.5))
xs = np.array([t["x"] for t in T_aoi]); ys = np.array([t["y"] for t in T_aoi])
jit = np.random.default_rng(1).normal(0, 12, (len(xs), 2))
for j, ax in enumerate(axs.ravel()):
    s = ax.scatter(xs + jit[:, 0], ys + jit[:, 1], c=X[:, j], s=14, cmap="viridis")
    plt.colorbar(s, ax=ax, fraction=.046); ax.set_title(f"{OX[j]} wt% (RMSEP {rmsep[OX[j]]})")
    ax.set_xlim(AOI[0], AOI[2]); ax.set_ylim(AOI[1], AOI[3]); ax.set_aspect("equal"); ax.plot(0, 0, "r*", ms=10)
fig.suptitle(f"Q1: SuperCam LIBS target means in the AOI ({len(T_aoi)} targets at {len(aoi_w)} waypoints, jittered 12 m; location = waypoint by sol)")
fig.tight_layout(); fig.savefig(OUT / "Q1_supercam_oxides_aoi.png", dpi=90); plt.close(fig)

# Raman
import csv  # noqa: E402
rm = list(csv.DictReader(open(S2 / "supercam/supercam_raman.csv", encoding="utf-8", errors="replace")))
rs = []
for r_ in rm:
    m = re.search(r"SCAM_(\d{4})_", r_["Source Product"], re.I)
    if m:
        w, _ = wp_for_sol(int(m.group(1)))
        rs.append((int(m.group(1)), w and inbox(w["x"], w["y"], AOI)))
R["Q1"]["raman"] = {"rows": len(rm), "in_aoi_by_sol": sum(1 for _, a in rs if a), "fields": list(rm[0].keys())[:8]}

# ---------------- Q2 samples -------------------------------------------------------------------------
smp = list(csv.DictReader(open(S2 / "samples/samples_page_2026-11-14.csv")))
q2 = []
for s_ in smp:
    if not s_["sol_sealed"]:
        q2.append({**s_, "wp": None}); continue
    w, amb = wp_for_sol(int(s_["sol_sealed"]))
    feat = s_["feature"].lower().replace(" ", "").replace("'", "")
    sc_hits = sorted({f"{k[1]}@{k[0]}" for k in tg if feat[:5] in k[1].lower().replace("_", "")})
    q2.append({**s_, "wp": w["id"], "x": round(w["x"]), "y": round(w["y"]), "in_aoi": inbox(w["x"], w["y"], AOI),
               "in_rim_window": inbox(w["x"], w["y"], RIM), "supercam_targets_matching_feature": sc_hits[:6]})
rock = [q for q in q2 if q["type"] == "rock core"]
R["Q2"] = {"n_listed": len(q2), "rock_cores": len(rock),
           "rock_cores_in_aoi": [q["name"] for q in rock if q.get("in_aoi")],
           "rock_sites_in_aoi": sorted({q["feature"] for q in rock if q.get("in_aoi")}),
           "rock_sites_total": len({q["feature"] for q in rock}),
           "rock_cores_in_rim_window": [q["name"] for q in rock if q.get("in_rim_window")],
           "table": q2}

# ---------------- Q4 unlock by the simulated rover -------------------------------------------------
rc = json.loads((APP / "data_work/jezero/recon_loops.json").read_text())
ext = rc["extent_local_m"]; res = rc["params"]["grid_res_m"]
locs = sorted({(r["wp"], r["x"], r["y"]) for r in aoi_rows})
from scipy.spatial import cKDTree  # noqa: E402
q4 = {"supercam_distance_m": R["Q1"]["distance_m"], "aoi_measured_locations": len(locs)}
cum = []
pts = []
for L in rc["loops"]:
    p = np.array(L["path_rc"], float)
    pts.append(np.c_[ext[0] + (p[:, 1] + .5) * res, ext[3] - (p[:, 0] + .5) * res])
    cum.append(np.vstack(pts))
for rad in (10, 15, 25):
    curve = []
    for k, P_ in enumerate(cum):
        tr = cKDTree(P_)
        dd, _ = tr.query(np.array([[x, y] for _, x, y in locs]))
        curve.append(int((dd <= rad).sum()))
    q4[f"unlocked_locations_by_loop_r{rad}m"] = curve
tgt_by_wp = Counter(r["wp"] for r in aoi_rows)
q4["note"] = "location = Perseverance waypoint (rover position); unlocked if any simulated rover path cell is within the radius"
R["Q4"] = q4

# ---------------- Q10 effective sample size --------------------------------------------------------
all_locs = sorted({(r["wp"], r["x"], r["y"]) for r in rows if r["wp"]})
def cells(locs_, size):
    return len({(math.floor(x / size), math.floor(y / size)) for _, x, y in locs_})
R["Q10"] = {"measured_locations_aoi": len(locs), "measured_locations_traverse": len(all_locs),
            "distinct_18m_cells_aoi": cells(locs, 18.0), "distinct_18m_cells_traverse": cells(all_locs, 18.0),
            "targets_traverse": len(tg), "points_traverse": len(rows),
            "note": "18 m cells on a base-centred grid stand in for CRISM MTRDR pixels (18 m/pixel; actual CRISM grid differs)."}

# ---------------- Q5 / Q9 windows --------------------------------------------------------------------
import rasterio  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
cov = {}
with rasterio.open(S2 / "hirise_dtm_full.tif") as H:
    f = 20
    a = H.read(1, out_shape=(H.height // f, H.width // f), resampling=Resampling.nearest)
    nd = H.nodata
    ok = np.isfinite(a) & (a > -1e30) & ((a != nd) if nd is not None else True)
    tr = H.transform * H.transform.scale(f, f)
    def dtm_cov(b):
        xs_ = np.arange(b[0] + 10, b[2], 20.0); ys_ = np.arange(b[1] + 10, b[3], 20.0)
        X_, Y_ = np.meshgrid(xs_, ys_)
        Xs, Ys = G.xy_to_src(X_, Y_)
        c = ((Xs - tr.c) / tr.a).astype(int); r = ((Ys - tr.f) / tr.e).astype(int)
        inside = (c >= 0) & (r >= 0) & (c < ok.shape[1]) & (r < ok.shape[0])
        v = np.zeros(X_.shape, bool); v[inside] = ok[r[inside], c[inside]]
        return round(float(v.mean()), 3)
with rasterio.open(APP / "data_raw/jezero/dtm_prior.tif") as C:
    ca = C.read(1); cok = (ca > -1e30) & np.isfinite(ca) & ((ca != C.nodata) if C.nodata is not None else True); ctr = C.transform
    def ctx_cov(b):
        xs_ = np.arange(b[0] + 10, b[2], 40.0); ys_ = np.arange(b[1] + 10, b[3], 40.0)
        X_, Y_ = np.meshgrid(xs_, ys_); Xs, Ys = G.xy_to_src(X_, Y_)
        c = ((Xs - ctr.c) / ctr.a).astype(int); r = ((Ys - ctr.f) / ctr.e).astype(int)
        inside = (c >= 0) & (r >= 0) & (c < cok.shape[1]) & (r < cok.shape[0])
        v = np.zeros(X_.shape, bool); v[inside] = cok[r[inside], c[inside]]
        return round(float(v.mean()), 3)
win = Counter()
for w in W:
    i = math.floor((w["x"] - AOI[0]) / 2400); j = math.floor((w["y"] - AOI[1]) / 2400)
    win[(i, j)] += 1
q5 = []
for (i, j), n in sorted(win.items()):
    b = (AOI[0] + 2400 * i, AOI[1] + 2400 * j, AOI[0] + 2400 * (i + 1), AOI[1] + 2400 * (j + 1))
    ws = [w for w in W if inbox(w["x"], w["y"], b)]
    sc_ = [r for r in rows if r["wp"] and inbox(r["x"], r["y"], b)]
    q5.append({"cell": [i, j], "bounds_local_m": b, "waypoints": n, "sol_range": [min(w["sol"] for w in ws), max(w["sol"] for w in ws)],
               "hirise_dtm_coverage": dtm_cov(b), "ctx_dtm_coverage": ctx_cov(b),
               "supercam_targets": len({(r["sol"], r["target"]) for r in sc_}), "supercam_locations": len({r["wp"] for r in sc_})})
R["Q5"] = {"cells": q5, "n_cells_with_waypoints": len(q5),
           "n_ge16": sum(c["waypoints"] >= 16 for c in q5), "n_ge36": sum(c["waypoints"] >= 36 for c in q5),
           "n_ge16_and_full_hirise": sum(c["waypoints"] >= 16 and c["hirise_dtm_coverage"] >= 0.99 for c in q5)}
rimc = next((c for c in q5 if c["cell"] == [-4, 0]), None)
# Deahn map
try:
    import pyogrio
    from pyproj import Transformer
    from shapely import transform as stransform, wkb
    from shapely.geometry import box
    GD = str(S2 / "deahn/crater_rim_mapping_v4.gdb")
    meta, _, geoms, fields = pyogrio.raw.read(GD, layer="units_recon_3Sep2024_bedrock_MD_v1")
    trd = Transformer.from_crs(meta["crs"], "+proj=longlat +R=3396190 +no_defs", always_xy=True)
    names = fields[list(meta["fields"]).index("name_recon")]
    lo0, la0 = G.xy_to_lonlat(RIM[0], RIM[1]); lo1, la1 = G.xy_to_lonlat(RIM[2], RIM[3])
    bx = box(float(lo0), float(la0), float(lo1), float(la1))
    ar = defaultdict(float); allb = None
    from shapely import union_all
    gs = []
    for g_, nm in zip(geoms, names):
        s = stransform(wkb.loads(g_), lambda xy: np.c_[trd.transform(xy[:, 0], xy[:, 1])], include_z=False)
        gs.append(s)
        if s.intersects(bx):
            ar[str(nm)] += s.intersection(bx).area
    ext_d = union_all(gs).bounds
    R["Q9"] = {"window": RIM, "window_lonlat": [round(float(lo0), 4), round(float(la0), 4), round(float(lo1), 4), round(float(la1), 4)],
               "deahn_bedrock_extent_lonlat": [round(v, 4) for v in ext_d],
               "bedrock_unit_area_share_of_window": {k: round(v / bx.area, 3) for k, v in sorted(ar.items(), key=lambda kv: -kv[1])},
               "bedrock_mapped_share_of_window": round(sum(ar.values()) / bx.area, 3),
               "cell_stats": rimc,
               "waypoints_in_deahn_extent": None}
    inside = [w for w in W if ext_d[0] <= w["lon"] <= ext_d[2] and ext_d[1] <= w["lat"] <= ext_d[3]]
    R["Q9"]["waypoints_in_deahn_extent"] = {"n": len(inside), "sol_range": [min(w["sol"] for w in inside), max(w["sol"] for w in inside)] if inside else None}
    sm = [q["name"] for q in rock if q.get("in_rim_window")]
    R["Q9"]["rock_cores_in_window"] = sm
except Exception as e:  # noqa: BLE001
    R["Q9"] = {"error": repr(e), "cell_stats": rimc}

(OUT / "q_results.json").write_text(json.dumps(R, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
print(json.dumps({k: (v if k not in ("Q2", "Q5") else {kk: vv for kk, vv in v.items() if kk not in ("table", "cells")}) for k, v in R.items()}, indent=1, default=str)[:9000])
