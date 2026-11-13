"""Step 2, option A (simplest version): SuperCam LIBS chemistry groups -> candidate stops (switchable).

python -m pipeline.step2_chem            # reads config/step2.json; run once (refuses a second run)

Switches (config/step2.json, key "step2"): enabled (false -> writes only {"enabled": false} for the web page and
nothing else; round 7 refuses), link_rule "i" | "ii", unlock_radius_m (locked 15).

Rules (manager 2026-11-14, direction.md "第 ② 步：A 的鎖定規則", locked before any candidate existed):
 1. Input: SuperCam LIBS MOC table (PDS), on-board calibration targets (SCCT*) excluded. A target = (sol, target
    name). Per target: mean over its points of the 8 oxides, each divided by the RMSEP in the table header.
 2. Location: the rover's site/drive for each LIBS shot (PDS SuperCam masterlist, EDR file name, matched to the
    MOC row by spacecraft clock) -> the Perseverance waypoint with that site/drive (S6-5). The old rule ("last
    waypoint with sol <= measurement sol") is computed alongside and both counts are reported. Position accuracy
    = the rover position (LIBS targets are within 7 m of the rover).
 3. Groups: Ward hierarchical clustering on the RMSEP-scaled target means. k = the largest k <= 4 for which
    EVERY pair of group centroids differs by >= 5 RMSEP in at least one oxide; if k = 2 already fails, k = 1.
    The same rule is applied to "all measurements" and to "measurements the rover has unlocked" (loops 1, 5,
    10, 20, 30); a data set with < 2 targets has k = 1.
 4. Candidate stops (no score, no weight): per group the representative target (closest to its group centroid
    in RMSEP units) and the anomaly (farthest from its own group centroid). Stops are waypoints: candidates at
    the same waypoint are one stop (its card lists every role); at most 8 stops (k <= 4 gives <= 8).
    Card: group, 8 oxides with RMSEP, SIM 3464 unit, Perseverance photos within 15 m, source level.
 5. Link rule (i): the product uses what the rover unlocked by the end of loop 30 (a measurement is unlocked when
    any cell of the rover's driven path through that loop is within unlock_radius_m of the measurement's
    location); "all measurements" only in the "View all data" mode, labelled not brought back by this rover.
    Agreement of the unlocked-data groups with the all-data groups at loops 1/5/10/20/30 is reported as a
    cross-table (no summary index was specified).
 6. Validation (descriptive, no test): the 4 sample sites in the AOI, which group their SuperCam targets fall
    in and whether any is a representative or an anomaly. No ranking -> no permutation test.
 7. Round 7 targets: (i) candidates = main table, (ii) candidates = second table ("not brought back by this rover").
 Not done: C on the map, D, B similarity ranking, any change of k, anything tuned on samples or round-7 numbers.
"""
from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter, defaultdict

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial import cKDTree

from .common import APP, LocalGrid, log, read_json, write_json

OX = ["SiO2", "TiO2", "Al2O3", "FeOT", "MgO", "CaO", "Na2O", "K2O"]
RULES = {"k_max": 4, "min_sep_rmsep": 5.0, "max_stops": 8, "photo_radius_m": 15.0, "loops": [1, 5, 10, 20, 30],
         "product_loop": 30, "status": "locked (manager 2026-11-14, direction.md 第 2 步 A)"}
S2 = APP / "data_raw/jezero/step2"
OUT = APP / "data_work/jezero/step2"
WEB = APP / "web/data/jezero/step2"
AOI = (-1700.0, -1000.0, 700.0, 1400.0)
G = LocalGrid(77.45088572, 18.44462715)


def load_config(path=APP / "config/step2.json"):
    c = json.loads(path.read_text())["step2"]
    assert c["link_rule"] in ("i", "ii"), c
    return {"enabled": bool(c["enabled"]), "link_rule": c["link_rule"], "unlock_radius_m": float(c["unlock_radius_m"])}


# ------------------------------------------------------------------------------------------- pure rules
def choose_k(Z, centroid_fn=None, k_max=RULES["k_max"], min_sep=RULES["min_sep_rmsep"]):
    """Rule 3. Z: targets x 8 in RMSEP units. Returns (k, labels 1..k, table of min pair separations per k)."""
    n = len(Z)
    if n < 2:
        return 1, np.ones(n, int), {}
    Lk = linkage(Z, "ward")
    seps, best = {}, (1, np.ones(n, int))
    for k in range(2, min(k_max, n) + 1):
        lab = fcluster(Lk, k, "maxclust")
        kk = len(set(lab))
        cen = np.array([Z[lab == c].mean(0) for c in sorted(set(lab))])
        sep = min(float(np.max(np.abs(cen[i] - cen[j]))) for i in range(kk) for j in range(i + 1, kk)) if kk > 1 else 0.0
        seps[k] = round(sep, 3)
        if kk == k and sep >= min_sep - 1e-12:
            best = (k, lab)
    return best[0], best[1], seps


def relabel_by_size(lab):
    """Presentation only: groups numbered 1..k by decreasing size (ties: lower original label first)."""
    cnt = Counter(lab.tolist())
    order = sorted(cnt, key=lambda c: (-cnt[c], c))
    m = {c: i + 1 for i, c in enumerate(order)}
    return np.array([m[c] for c in lab], int)


def candidates(Z, lab, wp_ids):
    """Rule 4. Returns list of stops [{wp, roles: [{group, role, idx}]}] and per-target distance to centroid."""
    d = np.zeros(len(Z))
    roles = []
    for g in sorted(set(lab.tolist())):
        idx = np.nonzero(lab == g)[0]
        c = Z[idx].mean(0)
        dd = np.sqrt(((Z[idx] - c) ** 2).sum(1))
        d[idx] = dd
        roles.append({"group": int(g), "role": "representative", "idx": int(idx[np.argmin(dd)])})
        roles.append({"group": int(g), "role": "anomaly", "idx": int(idx[np.argmax(dd)])})
    stops = {}
    for r in roles:
        stops.setdefault(wp_ids[r["idx"]], []).append(r)
    out = [{"wp": w, "roles": rr} for w, rr in stops.items()]
    assert len(out) <= RULES["max_stops"]
    return out, d


def unlocked_mask(loc_xy, loops, ext, res, radius, upto):
    """Rule 5: location unlocked if any driven path cell through loop `upto` is within radius (t1_report method)."""
    pts = [np.c_[ext[0] + (np.array(L["path_rc"])[:, 1] + .5) * res, ext[3] - (np.array(L["path_rc"])[:, 0] + .5) * res]
           for L in loops if L["id"] <= upto]
    if not pts or len(loc_xy) == 0:
        return np.zeros(len(loc_xy), bool)
    dd, _ = cKDTree(np.vstack(pts)).query(np.asarray(loc_xy, float))
    return dd <= radius + 1e-9


# ------------------------------------------------------------------------------------------------ data
def read_moc():
    lines = (S2 / "supercam/supercam_libs_moc.csv").read_text().splitlines()
    hi = next(i for i, l in enumerate(lines) if l.startswith("cdr_fname"))
    head = {l.split(",")[0]: l.split(",") for l in lines[:hi]}
    rmsep = {OX[k]: float(head["RMSEP"][1 + 2 * k]) for k in range(8)}
    cols = lines[hi].split(",")
    rows, n_scct, n_bad = [], 0, 0
    for l in lines[hi + 1:]:
        p = l.split(",")
        if len(p) < len(cols):
            n_bad += 1; continue
        m = re.match(r"scam_(\d{4})_(\d+)_\d+_\w{3}_scam\d+_(.+?)_*(\d{2})p$", p[0])
        if not m:
            n_bad += 1; continue
        v = dict(zip(cols, p))
        try:
            ox = [float(v[o]) for o in OX]
        except ValueError:
            n_bad += 1; continue
        tgt = m.group(3).strip("_")
        if tgt.lower().startswith("scct"):
            n_scct += 1; continue
        rows.append({"fn": p[0], "sol": int(m.group(1)), "sclk": int(m.group(2)), "target": tgt, "pt": int(m.group(4)),
                     "ox": ox, "dist_mm": float(v["distance_mm"]) if v["distance_mm"] else math.nan})
    return rows, rmsep, {"rows_in_file": len(lines) - hi - 1, "calibration_rows_excluded": n_scct, "unparsed_rows": n_bad}


def read_site_drive():
    """sclk of every LIBS shot -> (site, drive) from the EDR file name in the PDS SuperCam masterlist."""
    out = {}
    with open(S2 / "supercam/m2020_scam_masterlist.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["type"] != "LIBS":
                continue
            e = re.search(r"__(\d{3})(\d{4})scam", r["edr_fname"].lower())
            if e and r["sclk"]:
                out.setdefault(int(r["sclk"]), set()).add((int(e.group(1)), int(e.group(2))))
    return out


def unit_lookup():
    from shapely.geometry import Point, shape
    gu = json.loads((S2 / "sim3464/GeoUnits_v1.geojson").read_text())["features"]
    polys = [(shape(f["geometry"]), f["properties"]["symbol"], f["properties"]["name"]) for f in gu]

    def unit_at(x, y):
        lon, lat = G.xy_to_lonlat(x, y)
        p = Point(float(lon), float(lat))
        return next(({"symbol": s, "name": n} for g, s, n in polys if g.contains(p)), None)
    return unit_at


def inbox(x, y):
    return AOI[0] <= x <= AOI[2] and AOI[1] <= y <= AOI[3]


def build_targets():
    rows, rmsep, info = read_moc()
    sd = read_site_drive()
    W = read_json(APP / "data_work/jezero/waypoints_all.json")
    wid = {(w["site"], w["drive"]): w for w in W}
    Ws = sorted(W, key=lambda w: (w["sol"], w["site"], w["drive"]))
    wsol = np.array([w["sol"] for w in Ws])
    n_nosd = n_multi = n_nowp = 0
    for r in rows:
        s = sd.get(r["sclk"])
        if not s:
            r["wp"] = None; n_nosd += 1
        elif len(s) > 1:
            r["wp"] = None; n_multi += 1
        else:
            w = wid.get(next(iter(s)))
            if w is None:
                n_nowp += 1
            r["wp"] = w
        i = int(np.searchsorted(wsol, r["sol"], side="right")) - 1
        r["wp_old"] = Ws[i] if i >= 0 else None
    info.update({"rows_used": len(rows), "rows_without_site_drive": n_nosd, "rows_with_several_site_drive": n_multi,
                 "rows_site_drive_not_a_waypoint": n_nowp})
    by = defaultdict(list)
    for r in rows:
        by[(r["sol"], r["target"])].append(r)
    T = []
    for (sol, name), rr in sorted(by.items()):
        wps = {r["wp"]["id"] if r["wp"] else None for r in rr}
        assert len(wps) == 1, (sol, name, wps)   # checked: no target spans two site/drives
        w = rr[0]["wp"]; wo = rr[0]["wp_old"]
        T.append({"sol": sol, "target": name, "n_points": len(rr), "ox": np.mean([r["ox"] for r in rr], 0),
                  "ox_sd": np.std([r["ox"] for r in rr], 0), "dist_m_median": float(np.nanmedian([r["dist_mm"] for r in rr]) / 1000),
                  "wp": w["id"] if w else None, "site": w["site"] if w else None, "drive": w["drive"] if w else None,
                  "x": w["x"] if w else math.nan, "y": w["y"] if w else math.nan,
                  "in_aoi": bool(w and inbox(w["x"], w["y"])),
                  "wp_old": wo["id"] if wo else None, "in_aoi_old": bool(wo and inbox(wo["x"], wo["y"]))})
    return T, rmsep, info


def photos_near(x, y, radius):
    P = read_json(APP / "web/data/jezero/photos.json")
    out = []
    for w in P["waypoints"]:
        d = math.hypot(w["x"] - x, w["y"] - y)
        if d <= radius:
            for im in w["images"]:
                out.append({"local": im["local"], "camera": im["camera"], "sol": im["sol"], "credit": im["credit"],
                            "page": im["page"], "wp": w["id"], "dist_m": round(d, 1),
                            **({"heading_deg": im["view"]["heading_deg"]} if "view" in im else {})})
    out.sort(key=lambda p: (p["dist_m"], p["camera"] != "NAVCAM_LEFT", p["sol"]))
    return out


# ------------------------------------------------------------------------------------------- analysis
def analyse(Tset, rmsep, unit_at, tag):
    """Apply rules 3-4 to one data set (list of target dicts). Returns a JSON-able block."""
    R = np.array([rmsep[o] for o in OX])
    X = np.array([t["ox"] for t in Tset]).reshape(-1, 8)
    Z = X / R
    k, lab, seps = choose_k(Z)
    lab = relabel_by_size(lab) if len(Tset) else lab
    block = {"dataset": tag, "n_targets": len(Tset), "n_locations": len({t["wp"] for t in Tset}), "k": int(k),
             "min_pair_sep_rmsep_by_k": seps}
    groups = []
    for g in range(1, k + 1):
        m = lab == g
        if not m.any():
            continue
        cen = X[m].mean(0)
        others = [X[lab == h].mean(0) for h in range(1, k + 1) if h != g and (lab == h).any()]
        diff = {o: round(float((cen[j] - np.mean([c[j] for c in others])) / R[j]), 2) for j, o in enumerate(OX)} if others else {}
        units = Counter((unit_at(t["x"], t["y"]) or {"symbol": "none"})["symbol"] for t, mm in zip(Tset, m) if mm)
        groups.append({"group": g, "n_targets": int(m.sum()), "n_locations": len({t["wp"] for t, mm in zip(Tset, m) if mm}),
                       "centroid_wt%": {o: round(float(cen[j]), 2) for j, o in enumerate(OX)},
                       "diff_vs_other_groups_rmsep": diff, "sim3464_units": dict(units)})
    stops, dist = candidates(Z, lab, [t["wp"] for t in Tset]) if len(Tset) else ([], np.zeros(0))
    for s in stops:
        t0 = Tset[s["roles"][0]["idx"]]
        u = unit_at(t0["x"], t0["y"])
        s.update({"x": round(t0["x"], 2), "y": round(t0["y"], 2), "site": t0["site"], "drive": t0["drive"],
                  "sim3464_unit": u, "photos_within_15m": photos_near(t0["x"], t0["y"], RULES["photo_radius_m"])})
        for r in s["roles"]:
            t = Tset[r["idx"]]
            r.update({"target": t["target"], "sol": t["sol"], "n_points": t["n_points"],
                      "oxides_wt%": {o: round(float(t["ox"][j]), 2) for j, o in enumerate(OX)},
                      "oxides_sd_between_points": {o: round(float(t["ox_sd"][j]), 2) for j, o in enumerate(OX)},
                      "rmsep_wt%": rmsep, "dist_to_group_centroid_rmsep": round(float(dist[r["idx"]]), 2),
                      "libs_distance_m_median": round(t["dist_m_median"], 2)})
            del r["idx"]
    block.update({"groups": groups, "stops": stops,
                  "labels": {f"{t['sol']}|{t['target']}": int(l) for t, l in zip(Tset, lab)}})
    return block, lab


def crosstab(a, b):
    ct = Counter(zip(a.tolist(), b.tolist()))
    return {f"{i}|{j}": n for (i, j), n in sorted(ct.items())}


def sample_sites(T_aoi, blocks, unit_at):
    """Rule 6 (descriptive): the AOI rock-core sites (Q2 list) and the groups of their SuperCam targets."""
    W = read_json(APP / "data_work/jezero/waypoints_all.json")
    Ws = sorted(W, key=lambda w: (w["sol"], w["site"], w["drive"]))
    wsol = np.array([w["sol"] for w in Ws])
    sites = defaultdict(list)
    for s in csv.DictReader(open(S2 / "samples/samples_page_2026-11-14.csv")):
        if s["type"] != "rock core" or not s["sol_sealed"]:
            continue
        w = Ws[int(np.searchsorted(wsol, int(s["sol_sealed"]), side="right")) - 1]
        if inbox(w["x"], w["y"]):
            sites[s["feature"]].append({"sample": s["name"], "sol_sealed": int(s["sol_sealed"]), "wp": w["id"], "x": w["x"], "y": w["y"]})
    out = []
    for feat, ss in sites.items():
        f5 = feat.lower().replace(" ", "").replace("'", "")[:5]
        rec = {"feature": feat, "samples": ss, "location_rule": "waypoint by sol sealed (Q2)", "by_dataset": {}}
        for tag, (blk, Tset) in blocks.items():
            stop_roles = {(r["sol"], r["target"]): (r["group"], r["role"]) for s in blk["stops"] for r in s["roles"]}
            named, near = [], []
            for t in Tset:
                key = f"{t['sol']}|{t['target']}"
                g = blk["labels"].get(key)
                item = {"target": t["target"], "sol": t["sol"], "group": g, "candidate_role": stop_roles.get((t["sol"], t["target"]))}
                if f5 in t["target"].lower().replace("_", ""):
                    named.append(item)
                if min(math.hypot(t["x"] - s["x"], t["y"] - s["y"]) for s in ss) <= RULES["photo_radius_m"]:
                    near.append(item)
            rec["by_dataset"][tag] = {"targets_named_like_the_feature": named,
                                      "targets_within_15m_of_the_sample_waypoint": {"n": len(near),
                                                                                     "groups": dict(Counter(i["group"] for i in near)),
                                                                                     "candidate_roles": [i for i in near if i["candidate_role"]]}}
        out.append(rec)
    return out


def run(cfg=None):
    cfg = cfg or load_config()
    WEB.mkdir(parents=True, exist_ok=True)
    if not cfg["enabled"]:
        for p in WEB.glob("*.json"):
            p.unlink()
        write_json(WEB / "step2.json", {"enabled": False})
        log("jezero", "step2", "step2.enabled = false: nothing computed, web shows nothing of step 2")
        return {"enabled": False}
    OUT.mkdir(parents=True, exist_ok=True)
    res_file = OUT / f"step2_result_r{int(cfg['unlock_radius_m'])}.json"
    if res_file.exists():   # computed once already: switching back on only re-exports the saved result
        out = read_json(res_file)
        export_web(out, cfg)
        log("jezero", "step2", f"already run once ({out['computed_at']}): re-exported {res_file.name}, nothing recomputed")
        return out
    t0 = time.time()
    T, rmsep, info = build_targets()
    unit_at = unit_lookup()
    T_aoi = [t for t in T if t["in_aoi"]]
    loc = {"site_drive": {"targets": len(T_aoi), "points": int(sum(t["n_points"] for t in T_aoi)),
                          "locations": len({t["wp"] for t in T_aoi})},
           "old_sol_rule": {"targets": sum(t["in_aoi_old"] for t in T), "points": int(sum(t["n_points"] for t in T if t["in_aoi_old"])),
                            "locations": len({t["wp_old"] for t in T if t["in_aoi_old"]})},
           "both_rules_in_aoi_targets": sum(t["in_aoi"] and t["in_aoi_old"] for t in T),
           "same_waypoint_both_rules_aoi_targets": sum(t["in_aoi"] and t["wp"] == t["wp_old"] for t in T)}
    blk_all, lab_all = analyse(T_aoi, rmsep, unit_at, "all")
    # (i): unlocked by the rover (T1 rerun, the locked recon)
    R = read_json(APP / "data_work/jezero/recon_loops.json")
    ext = R["extent_local_m"]; res = R["params"]["grid_res_m"]
    xy = np.array([[t["x"], t["y"]] for t in T_aoi])
    per_loop = {}
    blk_i = None
    for k in RULES["loops"]:
        m = unlocked_mask(xy, R["loops"], ext, res, cfg["unlock_radius_m"], k)
        sub = [t for t, mm in zip(T_aoi, m) if mm]
        b, lab_k = analyse(sub, rmsep, unit_at, f"unlocked@{k}")
        per_loop[k] = {"n_targets": b["n_targets"], "n_locations": b["n_locations"], "k": b["k"],
                       "min_pair_sep_rmsep_by_k": b["min_pair_sep_rmsep_by_k"],
                       "group_sizes": [g["n_targets"] for g in b["groups"]],
                       "crosstab_unlocked_group_vs_all_data_group": crosstab(lab_k, lab_all[m]) if len(sub) else {},
                       "units": dict(Counter((unit_at(t["x"], t["y"]) or {"symbol": "none"})["symbol"] for t in sub))}
        if k == RULES["product_loop"]:
            blk_i, sub_i = b, sub
    blocks = {"i_unlocked@30": (blk_i, sub_i), "ii_all": (blk_all, T_aoi)}
    out = {"label": "groups and candidate stops: derived from Perseverance SuperCam measurements (measured); "
                    "rover recon simulated; review pending",
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "seconds": None, "config": cfg, "rules": RULES,
           "rmsep_wt%": rmsep, "input": info, "location": loc,
           "datasets": {"i": blk_i, "ii": blk_all}, "unlock_by_loop": per_loop,
           "samples": sample_sites(T_aoi, blocks, unit_at),
           "position_accuracy": "rover position (site/drive waypoint); LIBS targets are within about 7 m of the rover"}
    out["seconds"] = round(time.time() - t0, 1)
    write_json(res_file, out)
    export_web(out, cfg)
    log("jezero", "step2", f"k all={blk_all['k']} ({blk_all['n_targets']} targets), k unlocked@30={blk_i['k']} "
                           f"({blk_i['n_targets']} targets); stops {len(blk_i['stops'])} / {len(blk_all['stops'])}")
    return out


def export_web(out, cfg):
    W_ = {"enabled": True, "link_rule": cfg["link_rule"], "unlock_radius_m": cfg["unlock_radius_m"],
          "label": out["label"], "rules": out["rules"], "rmsep_wt%": out["rmsep_wt%"], "location": out["location"],
          "position_accuracy": out["position_accuracy"],
          "product": "i" if cfg["link_rule"] == "i" else "ii",
          "datasets": {k: {q: v for q, v in d.items() if q != "labels"} for k, d in out["datasets"].items()},
          "unlock_by_loop": {k: {q: v for q, v in d.items() if q != "crosstab_unlocked_group_vs_all_data_group"}
                             for k, d in out["unlock_by_loop"].items()},
          "samples": out["samples"]}
    for d in W_["datasets"].values():
        for s in d["stops"]:
            s["photos_within_15m"] = s["photos_within_15m"][:6] + ([{"more": len(s["photos_within_15m"]) - 6}] if len(s["photos_within_15m"]) > 6 else [])
    write_json(WEB / "step2.json", W_)


if __name__ == "__main__":
    run()
