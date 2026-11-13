"""T6 multi-window route A vs B (round 6). Same pipeline and parameters as the main AOI, one run per window.

python -m pipeline.multiwindow_ab terrain  --windows "-1,0;-1,1"   # classes on each window (2 m)
python -m pipeline.multiwindow_ab selftest                         # window (0,0) through this code == main terrain_2m.npz
python -m pipeline.multiwindow_ab recon    --windows "-1,0"        # rover recon, locked PARAMS, 30 loops, once
python -m pipeline.multiwindow_ab compare  --windows "-1,0"        # T2 comparison (pipeline/compare_ab.compare), once
python -m pipeline.multiwindow_ab table                            # six-window table + figure (descriptive)

Rules (direction.md 嚴謹度 2, locked before any route number; TECH_LEAD_BRIEF 第六次更新 T6):
- Window (i, j) = main AOI shifted by (2400 i, 2400 j) m on the main local grid (same projection, same pixel
  alignment). Inside a window every coordinate is relative to the window habitat = main habitat shifted by the
  same amount, so the window AOI is again x -1700..700, y -1000..1400 m and the habitat is (0, 0).
  If the habitat cell is impassable on the prior, the rule says "move to the nearest passable cell"; this code
  STOPS instead (which passability, astronaut or rover, is not written down) and reports.
- Inputs per window: HiRISE ortho strip of the window (S4 download), the full HiRISE 1 m DTM mosaic (same
  product as the main AOI's strip), CTX DTM / ortho mosaics shifted by the window's own X3 global shift and
  vertical offset (S4, `qa/jezero/multiwindow/x3_windows.json`).
- Terrain classes: exactly pipeline/terrain.py (functions and PARAMS imported, the run() body repeated line
  for line minus the unused v1 ripple index and the QA figures); sand = pipeline/sandfield.py SAND_V2.
  `selftest` must reproduce the main AOI's terrain_2m.npz cell for cell before any window is used.
- Recon: pipeline/rover_sim.simulate with rover_sim.PARAMS unchanged (budget 4,000, sand x6, 15 m, rule v2,
  30 loops). Comparison: pipeline/compare_ab.compare unchanged (frozen definitions, commit e17452a).
- HiRISE gaps (only window (-4,0), 97.4 % DTM cover): the locked rule says "gap = impassable, targets within
  50 m of the gap dropped", but not in which knowledge states the gap is impassable nor how it enters the
  hazard-zone / blocked-metre definitions. This code records the gap mask and REFUSES to run recon / compare
  on a window with any no-data cell until manager writes that down.
"""
from __future__ import annotations

import argparse
import math
import time
from types import SimpleNamespace

import numpy as np
from rasterio.warp import Resampling
from scipy.ndimage import gaussian_filter, map_coordinates, uniform_filter

from .common import APP, LocalGrid, Scene, log, read_json, write_json
from .multiwindow_x3 import CELL, DTM_FULL, to_local_win

WINDOWS = [(-1, 0), (-1, 1), (-2, 1), (-3, 1), (-4, 0)]
OUT = APP / "data_work/jezero/windows"
X3_BOOK = APP / "qa/jezero/multiwindow/x3_windows.json"


def wdir(i, j):
    d = OUT / f"{i}_{j}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def shifted_scene(i, j):
    """Main local grid with its origin moved to the window habitat (main habitat + (2400 i, 2400 j))."""
    sc = Scene("jezero")
    g = LocalGrid(sc.grid.lon0, sc.grid.lat0)
    g.X0 += CELL * i / g.k
    g.Y0 += CELL * j
    return sc, SimpleNamespace(grid=g)


def window_inputs(i, j):
    sc = Scene("jezero")
    if (i, j) == (0, 0):
        al = read_json(sc.work / "alignment.json")["prior"]
        return {"ortho": sc.raw_path("ortho"), "dtm": DTM_FULL, "shift": tuple(al["applied_shift_m"]),
                "dz": float(al["applied_vertical_offset_m"])}
    rec = read_json(X3_BOOK)["windows"][f"{i},{j}"]
    assert rec["x3"]["items_1_2_pass"], f"window {i},{j} did not pass X3 items 1-2"
    return {"ortho": APP / "data_raw/jezero/windows" / f"{i}_{j}" / "ortho.tif", "dtm": DTM_FULL,
            "shift": tuple(rec["image_registration"]["measured_shift_m"]),
            "dz": float(rec["vertical"]["applied_vertical_offset_m"])}


# ------------------------------------------------------------------------------------------------ terrain
def build_terrain(i, j, save=True):
    from . import terrain as TR
    from .layers import slope_deg
    from .sandfield import SAND_V2, classify as sand_classify, features as sand_features, to_grid
    sc, ws = shifted_scene(i, j)
    inp = window_inputs(i, j)
    P = TR.PARAMS
    aoi = sc.extent("aoi")
    res = P["grid_res_m"]
    W = int((aoi[2] - aoi[0]) / res); H = int((aoi[3] - aoi[1]) / res)
    t0 = time.time()

    # ---- reference: 1 m DTM (padded 30 m) -- same lines as terrain.run ----------------------------------
    pad = 30
    aoi_pad = (aoi[0] - pad, aoi[1] - pad, aoi[2] + pad, aoi[3] + pad)
    z = to_local_win(inp["dtm"], ws, aoi_pad, 1.0, Resampling.bilinear)
    dtm_nodata_1m = ~np.isfinite(z)
    h = int(P["slope_baseline_m"] / 2)
    gx = (np.roll(z, -h, 1) - np.roll(z, h, 1)) / (2 * h)
    gy = (np.roll(z, h, 0) - np.roll(z, -h, 0)) / (2 * h)
    s1 = np.degrees(np.arctan(np.hypot(gx, gy)))[pad:-pad, pad:-pad]
    hp = z - gaussian_filter(z, P["roughness_sigma_m"])
    w = int(P["roughness_window_m"])
    m1 = uniform_filter(hp, w); m2 = uniform_filter(hp * hp, w)
    r1 = np.sqrt(np.maximum(m2 - m1 * m1, 0))[pad:-pad, pad:-pad]
    slope_ref = TR.block(s1, 2, "max"); rough_ref = TR.block(r1, 2, "max")
    del gx, gy, hp, m1, m2

    # ---- sand v2 on the 0.5 m ortho ----------------------------------------------------------------------
    o = to_local_win(inp["ortho"], ws, aoi, 0.25, Resampling.bilinear); o[o == 0] = np.nan
    o = TR.block(o, 2, "mean")  # 0.5 m
    ortho_nodata_2m = TR.block((~np.isfinite(o)).astype("float32"), 4, "max") > 0
    G = to_grid(sand_features(o), 4)
    sand_v2, _ = sand_classify(G, slope_ref, res)
    del o, G
    class_ref, rough_thr = TR.classify_ref(slope_ref, rough_ref, sand_v2, P)
    blocked_rover_ref = slope_ref >= P["slope_block_rover_deg"]

    # ---- prior: CTX 20 m, 40 m baseline, bilinear to 2 m (context extent shifted with the window) ----------
    ctx = sc.extent("context")
    pres = 20.0
    zp = to_local_win(APP / "data_raw/jezero/dtm_prior.tif", ws, ctx, pres, Resampling.bilinear, shift_xy=inp["shift"]) + inp["dz"]
    pe = ctx
    sp20 = slope_deg(zp, pres)
    xs = aoi[0] + (np.arange(W) + 0.5) * res; ys = aoi[3] - (np.arange(H) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    slope_prior = map_coordinates(sp20, [(pe[3] - Y) / pres - 0.5, (X - pe[0]) / pres - 0.5], order=1).astype("float32")
    class_prior = np.zeros((H, W), np.uint8)
    class_prior[slope_prior >= P["slope_rough_deg"]] = 1
    class_prior[slope_prior >= P["slope_block_astronaut_deg"]] = 3
    blocked_rover_prior = slope_prior >= P["slope_block_rover_deg"]

    # ---- no-data bookkeeping (recorded only; nothing is changed because of it) ------------------------------
    dtm_nodata_2m = TR.block(dtm_nodata_1m[pad:-pad, pad:-pad].astype("float32"), 2, "max") > 0
    slope_nan_2m = ~np.isfinite(slope_ref)
    nodata = dtm_nodata_2m | ortho_nodata_2m | slope_nan_2m | ~np.isfinite(slope_prior)
    base_rc = (int((aoi[3] - 0.0) / res), int((0.0 - aoi[0]) / res))
    frac = lambda c: {TR.CLASSES[k]: round(float(np.mean(c == k)) * 100, 2) for k in range(4)}
    meta = {"window": [i, j], "habitat_main_local_m": [CELL * i, CELL * j],
            "habitat_lonlat": [round(float(v), 7) for v in Scene("jezero").grid.xy_to_lonlat(CELL * i, CELL * j)],
            "extent_local_m": list(aoi), "shape": [H, W], "params": P, "sand_v2": SAND_V2,
            "inputs": {"ortho": str(inp["ortho"]), "dtm": str(inp["dtm"]), "prior_shift_m": list(inp["shift"]),
                       "prior_dz_m": inp["dz"]},
            "fixed_thresholds": {"roughness_m": rough_thr},
            "area_percent_ref": frac(class_ref), "area_percent_prior": frac(class_prior),
            "blocked_rover_percent": {"ref": round(float(blocked_rover_ref.mean()) * 100, 2),
                                      "prior": round(float(blocked_rover_prior.mean()) * 100, 2)},
            "nodata_2m": {"any_pct": round(float(nodata.mean()) * 100, 3), "dtm_pct": round(float(dtm_nodata_2m.mean()) * 100, 3),
                          "ortho_pct": round(float(ortho_nodata_2m.mean()) * 100, 3), "n_cells": int(nodata.sum())},
            "habitat": {"base_rc": list(base_rc), "class_prior": int(class_prior[base_rc]),
                        "blocked_rover_prior": bool(blocked_rover_prior[base_rc]),
                        "class_ref": int(class_ref[base_rc])},
            "seconds": round(time.time() - t0, 1),
            "label": "derived (heuristic, not yet reviewed)"}
    arrs = dict(slope_ref=slope_ref, rough_ref=rough_ref, class_ref=class_ref, blocked_rover_ref=blocked_rover_ref,
                slope_prior=slope_prior, class_prior=class_prior, blocked_rover_prior=blocked_rover_prior, nodata=nodata)
    if save:
        d = wdir(i, j)
        np.savez_compressed(d / "terrain_2m.npz", **arrs)
        write_json(d / "terrain_2m.json", meta)
    log("jezero", "mwab", f"({i},{j}) terrain ref {meta['area_percent_ref']} prior {meta['area_percent_prior']} "
                         f"nodata {meta['nodata_2m']} habitat {meta['habitat']} {meta['seconds']} s")
    return arrs, meta


def selftest():
    arrs, meta = build_terrain(0, 0, save=False)
    M = dict(np.load(APP / "data_work/jezero/terrain_2m.npz"))
    out = {}
    for k in ("class_ref", "class_prior", "blocked_rover_ref", "blocked_rover_prior"):
        out[k] = {"cells_differ": int(np.sum(arrs[k] != M[k])), "n": int(M[k].size)}
    for k in ("slope_ref", "rough_ref", "slope_prior"):
        out[k] = {"max_abs_diff": float(np.nanmax(np.abs(arrs[k] - M[k])))}
    out["nodata_2m"] = meta["nodata_2m"]
    write_json(OUT / "selftest_0_0.json", out)
    log("jezero", "mwab", f"selftest (0,0) vs main terrain_2m.npz: {out}")
    return out


def load_T(i, j):
    d = OUT / f"{i}_{j}"
    T = dict(np.load(d / "terrain_2m.npz"))
    meta = read_json(d / "terrain_2m.json")
    if T["nodata"].any():
        raise SystemExit(f"window ({i},{j}) has {int(T['nodata'].sum())} no-data cells: the gap rule's knowledge "
                         "states are not written down yet -> not run (waiting for manager)")
    hb = meta["habitat"]
    if hb["class_prior"] == 3 or hb["blocked_rover_prior"]:
        raise SystemExit(f"window ({i},{j}) habitat impassable on the prior {hb}: 'nearest passable cell' needs a "
                         "definition (astronaut or rover) -> not run (waiting for manager)")
    return T, meta


# -------------------------------------------------------------------------------------------------- recon
def recon_outputs(T, P, base_rc, ext, bel, loops, secs, extra=None):
    """Same post-processing as rover_sim.run (that function writes to the main AOI's files, so it is not called)."""
    res = P["grid_res_m"]
    H, W = bel.cls.shape
    ref = T["class_ref"]
    for L in loops:
        obs = (bel.first_t >= 0) & (bel.first_t <= L["t1"])
        L["observed_frac_aoi"] = round(float(obs.mean()), 4)
        bl = np.where(obs, ref, T["class_prior"])
        L["belief_agrees_with_reference_frac"] = round(float(np.mean(bl == ref)), 4)
    out = {"params": P, "base_rc": list(base_rc), "extent_local_m": ext, "aoi_area_m2": H * W * res * res,
           "seconds": secs, "ref_cells_revealed": bel.ref_reads, "label": "simulated", "review": "pending",
           "initial_belief_agrees_with_reference_frac": round(float(np.mean(T["class_prior"] == ref)), 4),
           "loops": loops, **(extra or {})}
    return out


def coverage_stats(observed, ext, res, base_xy=(0.0, 0.0)):
    """Same statistics as spikes/t1_report.py (by 8 directions within 1200 m, by distance band)."""
    H, W = observed.shape
    yy, xx = np.mgrid[0:H, 0:W]
    X = ext[0] + (xx + .5) * res - base_xy[0]; Y = ext[3] - (yy + .5) * res - base_xy[1]
    dist = np.hypot(X, Y); bear = (np.degrees(np.arctan2(X, Y)) + 360) % 360
    names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    sec = np.array(names)[((bear + 22.5) // 45).astype(int) % 8]
    return {"observed_aoi_pct": round(100 * float(observed.mean()), 1),
            "by_direction_within_1200m_pct": {s: round(100 * float(observed[(sec == s) & (dist <= 1200)].mean()), 1) for s in names},
            "by_band_pct": {b: round(100 * float(observed[(dist >= lo) & (dist < hi)].mean()), 1) for b, (lo, hi) in
                            (("0-600 m", (0, 600)), ("600-1200 m", (600, 1200)), (">1200 m", (1200, 1e9)))}}


def run_recon(i, j):
    from .rover_sim import PARAMS, simulate
    T, meta = load_T(i, j)
    d = OUT / f"{i}_{j}"
    if (d / "recon_loops.json").exists():
        raise SystemExit(f"window ({i},{j}) recon already run once: {d / 'recon_loops.json'}")
    P = dict(PARAMS)
    ext = meta["extent_local_m"]; res = P["grid_res_m"]
    base_rc = tuple(meta["habitat"]["base_rc"])
    t0 = time.time()
    bel, loops = simulate(T, P, base_rc, log_fn=lambda m: log("jezero", f"mwab {i},{j}", m))
    secs = round(time.time() - t0, 1)
    np.savez_compressed(d / "recon_state.npz", first_t=bel.first_t, observed=bel.observed, belief_cls=bel.cls)
    out = recon_outputs(T, P, base_rc, ext, bel, loops, secs,
                        {"window": [i, j], "started": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(t0)),
                         "coverage": coverage_stats(bel.observed, ext, res)})
    write_json(d / "recon_loops.json", out)
    log("jezero", "mwab", f"({i},{j}) recon {len(loops)} loops {secs} s observed {out['coverage']['observed_aoi_pct']} %")


# ------------------------------------------------------------------------------------------------ compare
def write_compare(d, T, ext, res, recon_file, state_file, extra=None):
    """Same output as compare_ab.run, written into directory d (compare_ab.run writes the main AOI files)."""
    from .astro_plan import PARAMS as ASTRO, usable_o2
    from .compare_ab import CMP, compare
    if (d / "compare_ab.json").exists():
        raise SystemExit(f"comparison already run once: {d / 'compare_ab.json'}")
    R = read_json(d / recon_file)
    st = dict(np.load(d / state_file))
    loop_t1 = {L["id"]: L["t1"] for L in R["loops"]}
    t0 = time.time()
    res_ = compare(T, st["first_t"], loop_t1, ext, res)
    secs = round(time.time() - t0, 1)
    tg = res_["targets"]
    rows_out = []
    for k in sorted(res_["rows"]["A"]):
        rows_out.append({"target": k, "x": tg[k]["x"], "y": tg[k]["y"], "dist_m": tg[k]["dist_m"], "band": tg[k]["band"],
                         **{s: {q: (round(v, 3) if isinstance(v, float) else v) for q, v in res_["rows"][s][k].items()}
                            for s in res_["states"]}})
    paths = {s: {str(k): res_["paths"][s][k] for k in sorted(res_["rows"]["A"])} for s in res_["states"]}
    out = {"label": "derived (simulated recon + assumed parameters); heuristic, not yet reviewed", "review": "pending",
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "seconds": secs,
           "definitions": CMP, "astronaut_params": ASTRO, "usable_o2": usable_o2(P=ASTRO),
           "recon_file": recon_file, "n_targets": len(tg), "unreachable_targets": res_["unreachable"],
           "n_hazard_zones": res_["n_hazard_zones"], "observed_frac": res_["observed_frac"],
           "aplus_sand_frac_aoi": res_["aplus_sand_frac"], "states": res_["states"],
           "targets": [{q: (list(v) if q == "rc" else v) for q, v in t.items()} for t in tg],
           "summary": res_["summary"], "rows": rows_out, **(extra or {})}
    write_json(d / "compare_ab.json", out)
    write_json(d / "compare_ab_paths.json", {"base_rc": list(res_["base_rc"]), "res": res, "ext": ext, "paths": paths})
    np.save(d / "hazard_zones.npy", res_["zones"])
    return out


def run_compare(i, j):
    T, meta = load_T(i, j)
    d = OUT / f"{i}_{j}"
    out = write_compare(d, T, meta["extent_local_m"], meta["params"]["grid_res_m"], "recon_loops.json", "recon_state.npz",
                        {"window": [i, j]})
    log("jezero", "mwab", f"({i},{j}) compare {out['n_targets']} targets, {len(out['unreachable_targets'])} unreachable, "
                         f"{out['n_hazard_zones']} zones, {out['seconds']} s")


# -------------------------------------------------------------------------------------------------- table
ROW_STATES = ["A", "A+", "B@1", "B@5", "B@10", "B@20", "B@30", "REF"]


def window_row(cmp_json, recon_json):
    S = cmp_json["summary"]["all"]
    r = {"n_targets": S["A"]["n"], "n_unreachable": len(cmp_json["unreachable_targets"]),
         "n_hazard_zones": cmp_json["n_hazard_zones"], "observed_pct_after_30": round(100 * cmp_json["observed_frac"].get("B@30", math.nan), 1)}
    for s in ROW_STATES:
        if s not in S:
            continue
        r[s] = {"actual_o2_mean": S[s]["actual_o2"]["mean"], "actual_o2_median": S[s]["actual_o2"]["median"],
                "hazard_m_mean": S[s]["hazard_m"]["mean"], "hazard_m_median": S[s]["hazard_m"]["median"],
                "crossings_mean": S[s]["crossings"]["mean"], "n_actual_within_budget": S[s]["n_actual_within_budget"]}
        if s != "A":
            r[s]["diff_vs_A"] = {q: S[s]["diff_vs_A"][q] for q in ("hazard_m", "actual_o2", "crossings")}
        if "share_of_possible_improvement" in S[s]:
            r[s]["share"] = S[s]["share_of_possible_improvement"]
    r["bands"] = {b: {"n": cmp_json["summary"][b]["n"],
                      **({s: {"hazard_m_mean": cmp_json["summary"][b][s]["hazard_m"]["mean"],
                              "actual_o2_mean": cmp_json["summary"][b][s]["actual_o2"]["mean"]}
                          for s in ("A", "B@30", "REF")} if cmp_json["summary"][b]["n"] else {})}
                  for b in ("300-600", "600-1200", ">1200")}
    return r


STATS = {"quantities": {"main": "hazard_m", "secondary": "actual_o2"}, "state": "B@30",
         "per_window": "mean over the window's targets of (B@30 - A) (= T2 column 'vs A')",
         "bootstrap": "95 % percentile interval of the median of the window values; windows resampled with replacement, "
                      "10,000 draws, seed 20261114 (tech-lead proposal written before any window number, DATA_LOG T6 settings)",
         "test": "Wilcoxon signed-rank, exact, two-sided, only with 6 windows all of the same sign (direction.md 嚴謹度 3)",
         "sets": {"all": "every window that ran", "excl_main": "the same without the main AOI (0,0) (manager 2026-11-14)"}}


def window_stats(vals):
    v = np.array(vals, float)
    n = len(v)
    out = {"n": n, "values": [round(float(x), 2) for x in v], "n_negative": int((v < 0).sum()), "n_positive": int((v > 0).sum()),
           "median": round(float(np.median(v)), 2) if n else None}
    if n >= 2:
        rng = np.random.default_rng(20261114)
        bm = np.median(v[rng.integers(0, n, size=(10000, n))], axis=1)
        out["median_ci95_bootstrap"] = [round(float(x), 2) for x in np.percentile(bm, [2.5, 97.5])]
    same_sign = n > 0 and (out["n_negative"] == n or out["n_positive"] == n)
    if n >= 6 and same_sign:
        from scipy.stats import wilcoxon
        out["wilcoxon_exact_two_sided_p"] = float(wilcoxon(v, alternative="two-sided", method="exact").pvalue)
    else:
        out["wilcoxon_exact_two_sided_p"] = None
        out["p_not_reported_because"] = (f"{n} windows (< 6)" if n < 6 else "signs differ")
    return out


def table():
    rows = {"0,0": window_row(read_json(APP / "data_work/jezero/compare_ab.json"), None)}
    not_run = {}
    for i, j in WINDOWS:
        p = OUT / f"{i}_{j}" / "compare_ab.json"
        if p.exists():
            rows[f"{i},{j}"] = window_row(read_json(p), None)
        else:
            not_run[f"{i},{j}"] = "no comparison (see DATA_LOG)"
    st = {}
    for qn, q in STATS["quantities"].items():
        for sn, keys in (("all", list(rows)), ("excl_main", [k for k in rows if k != "0,0"])):
            st[f"{qn}_{q}_{sn}"] = {"windows": keys, **window_stats([rows[k][STATS["state"]]["diff_vs_A"][q]["mean"] for k in keys])}
    out = {"label": "derived (simulated recon + assumed parameters); heuristic, not yet reviewed", "rules": STATS,
           "windows": rows, "not_run": not_run, "stats": st}
    write_json(OUT / "t6_table.json", out)
    figure_t6(rows)
    log("jezero", "mwab", f"table: {list(rows)}; stats {st}")
    return out


def figure_t6(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    keys = list(rows)
    fig, ax = plt.subplots(1, 2, figsize=(12, 0.6 * len(keys) + 2.2))
    for a, (q, ttl) in zip(ax, (("hazard_m", "Hazard metres per walk, route − route A (main)"),
                                ("actual_o2", "Actual O2 per walk, route − route A (nominal min; secondary)"))):
        y = np.arange(len(keys))[::-1]
        b = [rows[k]["B@30"]["diff_vs_A"][q]["mean"] for k in keys]
        r = [rows[k]["REF"]["diff_vs_A"][q]["mean"] for k in keys]
        a.axvline(0, color="#888", lw=1)
        a.scatter(r, y, s=70, facecolors="none", edgecolors="#8a8a8a", lw=1.6, label="reference bound − A (not a recon result)", zorder=3)
        a.scatter(b, y, s=70, color="#1f5fa8", label="B after 30 loops − A", zorder=4)
        for yy, bv in zip(y, b):
            a.annotate(f"{bv:+.0f}" if q == "hazard_m" else f"{bv:+.1f}", (bv, yy), xytext=(0, 9), textcoords="offset points",
                       ha="center", fontsize=9, color="#222")
        a.set_yticks(y); a.set_yticklabels([f"({k})" + (" main AOI" if k == "0,0" else "") for k in keys])
        a.set_title(ttl, fontsize=10); a.grid(axis="x", color="#e5e5e5", lw=.6); a.set_axisbelow(True)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    ax[0].legend(loc="lower left", fontsize=8, frameon=False)
    fig.suptitle("T6 multi-window route A vs B (means over each window's test points; derived, simulated recon, "
                 "sand classes heuristic, not yet reviewed)", fontsize=10)
    fig.tight_layout()
    out = APP / "qa/jezero/multiwindow"; out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "T6_windows_A_vs_B.png", dpi=110); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["terrain", "selftest", "recon", "compare", "table"])
    ap.add_argument("--windows", default=None)
    a = ap.parse_args()
    wins = [tuple(int(v) for v in s.split(",")) for s in a.windows.split(";")] if a.windows else WINDOWS
    if a.stage == "selftest":
        selftest(); return
    if a.stage == "table":
        table(); return
    for i, j in wins:
        {"terrain": lambda: build_terrain(i, j), "recon": lambda: run_recon(i, j),
         "compare": lambda: run_compare(i, j)}[a.stage]()


if __name__ == "__main__":
    main()
