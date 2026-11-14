# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia scene (SpaceX Starship candidate site, HiRISE ESP_061075_2195): brain-terrain demo pipeline.

python -m pipeline.arcadia grid|terrain|rover|select|astro|export|all

  grid     ortho 0.25 m (COG window), DTM 1 m (padded 30 m), prior DTM = HiRISE DTM block-averaged to 20 m
  terrain  existing rules (pipeline/terrain.py), sand = sandfield v2, but brain score >= 0.5 is never sand;
           prior = slope classes of the 20 m DTM (same code path as the CTX prior)
  rover    second-version rover rule (pipeline/rover_sim.simulate), 4 m cells, 10 loops
  select   60 m blocks: >= 50 % seen by the rover, top 4 by mean brain score, centres >= 150 m apart;
           stop = highest-score passable cell of the block. Also the "before" version (whole area, no seen rule).
  astro    Shooyunn's Pandolf model (app/eva_energy/mars_eva_energy.py, unchanged) -> kcal and minutes per metre;
           multistop order rule of pipeline/multistop.py; 1,800 kcal, 20 % reserve, 18 min dwell at standing rate
  export   web/data/arcadia/*
The brain score (2 m) comes from spikes/brain_proto (Pearson et al. 2024 U-Net), run in its own venv.
"""
from __future__ import annotations

import argparse
import math
import sys
import time

import numpy as np
import rasterio
from rasterio.warp import Resampling

from .common import APP, Scene, log, read_json, save_local_tif, write_json

SCENE = "arcadia"
BRAIN_SAND_EXCLUDE = 0.5          # brain score >= 0.5 is never sand (rule set 2026-11-15)
RES = 2.0


def sc_():
    return Scene(SCENE)


def base_rc_at(sc, res):
    """Habitat cell (row, col) on a grid of `res` m over the AOI. Habitat = cfg['habitat'] (local m)."""
    aoi = sc.extent("aoi"); h = sc.cfg["habitat"]
    return (int((aoi[3] - h["y"]) // res), int((h["x"] - aoi[0]) // res))


def src_file(sc, sid):
    return sc.raw / sc.source(sid)["file"]


# ---------------------------------------------------------------------------------------------------- grid
def fetch_ortho(sc):
    """Window of the 0.25 m RED_A COG covering the fetch extent, kept in the source CRS."""
    from rasterio.windows import from_bounds
    out = src_file(sc, "ortho")
    if out.exists():
        return out
    ext = sc.extent("fetch")
    X0, Y0, X1, Y1 = sc.grid.src_bounds(*ext)
    with rasterio.open("/vsicurl/" + sc.source("ortho")["url"]) as s:
        w = from_bounds(X0, Y0, X1, Y1, s.transform).round_offsets().round_lengths()
        a = s.read(1, window=w)
        prof = dict(driver="GTiff", width=a.shape[1], height=a.shape[0], count=1, dtype=a.dtype, crs=s.crs,
                    transform=s.window_transform(w), nodata=0, tiled=True, compress="deflate", BIGTIFF="IF_SAFER")
    with rasterio.open(out, "w", **prof) as d:
        d.write(a, 1)
    return out


def run_grid():
    from .grid import grid_meta, to_local
    sc = sc_()
    t0 = time.time()
    fetch_ortho(sc)
    aoi = sc.extent("aoi")
    pad = 30.0
    aoi_pad = (aoi[0] - pad, aoi[1] - pad, aoi[2] + pad, aoi[3] + pad)
    meta = {"base": sc.cfg["base"], "aoi": grid_meta(sc, aoi, 0.25), "products": {}}

    def save(name, arr, tr, extent, res):
        save_local_tif(sc.work / f"{name}.tif", arr, tr, nodata=np.nan)
        meta["products"][name] = {**grid_meta(sc, extent, res), "nan_frac": float(np.mean(~np.isfinite(arr)))}
        log(SCENE, "grid", f"{name} {arr.shape} NaN {np.mean(~np.isfinite(arr)):.3%}")

    a, tr = to_local(src_file(sc, "ortho"), sc, aoi, 0.25)
    a[a == 0] = np.nan
    save("ortho_025", a, tr, aoi, 0.25)
    a, tr = to_local(src_file(sc, "dtm_fine"), sc, aoi_pad, 1.0)
    save("dtm_fine", a, tr, aoi_pad, 1.0)
    # prior: the HiRISE DTM averaged to 20 m (stands in for a CTX 20 m DTM; no separate download)
    ctx = (aoi[0] - 200, aoi[1] - 200, aoi[2] + 200, aoi[3] + 200)
    a, tr = to_local(src_file(sc, "dtm_fine"), sc, ctx, 20.0, Resampling.average)
    save("dtm_prior_ctx", a, tr, ctx, 20.0)
    write_json(sc.work / "grid.json", meta)
    log(SCENE, "grid", f"done in {time.time() - t0:.0f} s")


# ------------------------------------------------------------------------------------------------- terrain
def run_terrain():
    from scipy.ndimage import gaussian_filter, map_coordinates, uniform_filter
    from .layers import slope_deg
    from .sandfield import SAND_V2, classify as sand_classify, features as sand_features, to_grid
    from .terrain import PARAMS as P, CLASSES, block, classify_ref, read
    sc = sc_()
    gm = read_json(sc.work / "grid.json")
    aoi = sc.extent("aoi")
    W = int((aoi[2] - aoi[0]) / RES); H = int((aoi[3] - aoi[1]) / RES)
    z = read(sc.work / "dtm_fine.tif")
    pad = 30
    h = int(P["slope_baseline_m"] / 2)
    gx = (np.roll(z, -h, 1) - np.roll(z, h, 1)) / (2 * h)
    gy = (np.roll(z, h, 0) - np.roll(z, -h, 0)) / (2 * h)
    s1 = np.degrees(np.arctan(np.hypot(gx, gy)))[pad:-pad, pad:-pad]
    hp = z - gaussian_filter(z, P["roughness_sigma_m"])
    w = int(P["roughness_window_m"])
    m1 = uniform_filter(hp, w); m2 = uniform_filter(hp * hp, w)
    r1 = np.sqrt(np.maximum(m2 - m1 * m1, 0))[pad:-pad, pad:-pad]
    slope_ref = block(s1, 2, "max"); rough_ref = block(r1, 2, "max")
    slope_mean = block(s1, 2, "mean")
    o = read(sc.work / "ortho_025.tif")
    o = block(o, 2, "mean")
    G = to_grid(sand_features(o), 4)
    sand_v2, _ = sand_classify(G, slope_ref, RES)
    brain = np.load(sc.work / "brain_score_2m.npy")
    is_brain = np.nan_to_num(brain) >= BRAIN_SAND_EXCLUDE
    sand_hit_brain = float(sand_v2[is_brain].mean()) if is_brain.any() else 0.0
    sand = sand_v2 & ~is_brain
    class_ref, _ = classify_ref(slope_ref, rough_ref, sand, P)
    blocked_rover_ref = slope_ref >= P["slope_block_rover_deg"]
    # prior: 20 m DTM slope, bilinear to 2 m (same path as the CTX prior in pipeline/terrain.py)
    zp = read(sc.work / "dtm_prior_ctx.tif")
    pe = gm["products"]["dtm_prior_ctx"]["extent_local_m"]; pres = gm["products"]["dtm_prior_ctx"]["res_m"]
    sp20 = slope_deg(zp, pres)
    xs = aoi[0] + (np.arange(W) + 0.5) * RES; ys = aoi[3] - (np.arange(H) + 0.5) * RES
    X, Y = np.meshgrid(xs, ys)
    slope_prior = map_coordinates(sp20, [(pe[3] - Y) / pres - 0.5, (X - pe[0]) / pres - 0.5], order=1).astype("float32")
    class_prior = np.zeros((H, W), np.uint8)
    class_prior[slope_prior >= P["slope_rough_deg"]] = 1
    class_prior[slope_prior >= P["slope_block_astronaut_deg"]] = 3
    blocked_rover_prior = slope_prior >= P["slope_block_rover_deg"]
    np.savez_compressed(sc.work / "terrain_2m.npz", slope_ref=slope_ref, slope_mean=slope_mean, rough_ref=rough_ref,
                        class_ref=class_ref, blocked_rover_ref=blocked_rover_ref, slope_prior=slope_prior,
                        class_prior=class_prior, blocked_rover_prior=blocked_rover_prior, sand_v2_raw=sand_v2)
    frac = lambda c: {CLASSES[k]: round(float(np.mean(c == k)) * 100, 2) for k in range(4)}
    meta = {"params": P, "sand_v2": SAND_V2, "brain_sand_exclude": BRAIN_SAND_EXCLUDE,
            "extent_local_m": list(aoi), "shape": [H, W],
            "brain_frac": round(float(is_brain.mean()), 4),
            "sand_rule_hit_on_brain_frac": round(sand_hit_brain, 4),
            "area_percent_ref": frac(class_ref), "area_percent_prior": frac(class_prior)}
    write_json(sc.work / "terrain_2m.json", meta)
    log(SCENE, "terrain", f"ref {meta['area_percent_ref']} prior {meta['area_percent_prior']} "
        f"brain {meta['brain_frac']:.1%} sand-on-brain {sand_hit_brain:.1%}")
    return meta


# --------------------------------------------------------------------------------------------------- rover
ROVER_RES = 4.0
ROVER_LOOPS = 10


def coarsen_terrain(T, f):
    """2 m -> 4 m: class = worst (max code) of the 2x2 cells, blocked if any cell blocked."""
    from .terrain import block
    out = {}
    for k in ("class_ref", "class_prior"):
        out[k] = block(T[k].astype(np.int16), f, "max").astype(np.uint8)
    for k in ("blocked_rover_ref", "blocked_rover_prior"):
        out[k] = block(T[k].astype(np.uint8), f, "max").astype(bool)
    return out


def run_rover():
    from .rover_sim import PARAMS, simulate
    sc = sc_()
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    f = int(ROVER_RES / RES)
    T4 = coarsen_terrain(T, f)
    P = dict(PARAMS); P["grid_res_m"] = ROVER_RES; P["n_loops"] = ROVER_LOOPS
    aoi = sc.extent("aoi")
    base_rc = base_rc_at(sc, ROVER_RES)
    t0 = time.time()
    bel, loops = simulate(T4, P, base_rc, log_fn=lambda m: log(SCENE, "rover", m))
    secs = round(time.time() - t0, 1)
    seen2 = np.repeat(np.repeat(bel.observed, f, 0), f, 1)
    first2 = np.repeat(np.repeat(bel.first_t, f, 0), f, 1)
    np.savez_compressed(sc.work / "recon_state.npz", observed=bel.observed, first_t=bel.first_t,
                        seen_2m=seen2, first_t_2m=first2)
    for L in loops:
        L["observed_frac_aoi"] = round(float(((bel.first_t >= 0) & (bel.first_t <= L["t1"])).mean()), 4)
    out = {"params": P, "base_rc": list(base_rc), "extent_local_m": list(aoi), "seconds": secs,
           "observed_frac": round(float(bel.observed.mean()), 4), "loops": loops}
    write_json(sc.work / "recon_loops.json", out)
    log(SCENE, "rover", f"{len(loops)} loops in {secs} s, seen {out['observed_frac']:.1%}")
    return out


# -------------------------------------------------------------------------------------------------- select
BLOCK_M = 60.0
SEEN_MIN = 0.5
N_PICK = 4
MIN_SEP_M = 150.0


def pick_blocks(score, passable, seen=None, n=N_PICK, block_m=BLOCK_M, seen_min=SEEN_MIN, min_sep=MIN_SEP_M, res=RES,
                extent=(-1200.0, -1200.0, 1200.0, 1200.0)):
    """Rule fixed 2026-11-15. Returns list of dicts (block centre, stop cell, mean score, seen fraction)."""
    b = int(round(block_m / res))
    H, W = score.shape
    nb_r, nb_c = H // b, W // b
    cand = []
    for i in range(nb_r):
        for j in range(nb_c):
            sl = (slice(i * b, (i + 1) * b), slice(j * b, (j + 1) * b))
            s = score[sl]
            if not np.isfinite(s).any():
                continue
            sf = float(seen[sl].mean()) if seen is not None else 1.0
            if sf < seen_min:
                continue
            ok = passable[sl] & np.isfinite(s)
            if not ok.any():
                continue
            cand.append((float(np.nanmean(s)), i, j, sf))
    cand.sort(reverse=True)
    picks = []
    for m, i, j, sf in cand:
        cy = (i + 0.5) * b; cx = (j + 0.5) * b
        if any(math.hypot(cy - p["_c"][0], cx - p["_c"][1]) * res < min_sep for p in picks):
            continue
        sl = (slice(i * b, (i + 1) * b), slice(j * b, (j + 1) * b))
        s = np.where(passable[sl] & np.isfinite(score[sl]), score[sl], -1)
        r, c = np.unravel_index(np.argmax(s), s.shape)
        rc = (i * b + int(r), j * b + int(c))
        x = extent[0] + (rc[1] + 0.5) * res; y = extent[3] - (rc[0] + 0.5) * res
        picks.append({"_c": (cy, cx), "block_rc": [i, j], "mean_score": round(m, 4), "seen_frac": round(sf, 3),
                      "stop_rc": list(rc), "stop_xy": [round(x, 1), round(y, 1)], "stop_score": round(float(score[rc]), 4),
                      "block_xy": [extent[0] + j * block_m, extent[3] - (i + 1) * block_m,
                                   extent[0] + (j + 1) * block_m, extent[3] - i * block_m]})
        if len(picks) == n:
            break
    for p in picks:
        p.pop("_c")
    return picks


def run_select():
    sc = sc_()
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    score = np.load(sc.work / "brain_score_2m.npy")
    seen = np.load(sc.work / "recon_state.npz")["seen_2m"]
    passable = T["class_ref"] < 3
    after = pick_blocks(score, passable, seen)
    before = pick_blocks(score, T["class_prior"] < 3, None)
    out = {"rule": {"block_m": BLOCK_M, "seen_min": SEEN_MIN, "n": N_PICK, "min_sep_m": MIN_SEP_M,
                    "rank": "mean brain score of the block", "stop": "highest-score passable cell"},
           "after_recon": after, "before_recon": before}
    write_json(sc.work / "targets.json", out)
    for k in ("after_recon", "before_recon"):
        log(SCENE, "select", f"{k}: " + "; ".join(f"{p['stop_xy']} {p['mean_score']:.3f}" for p in out[k]))
    return out


# --------------------------------------------------------------------------------------------------- astro
EVA = {"body_kg": 75.0, "suit_kg": 104.0, "gravity_scaling": "split", "speed_kmh": 2.5,
       "speed_factor": [1.0, 0.6, 0.35], "eta_key": ["mars_regolith_plain", "mars_rocky_terrain", "mars_sandy_dunes"],
       "budget_kcal": 1800.0, "reserve_frac": 0.20, "dwell_min": 18.0, "kcal_per_l_o2": 5.0,
       "grade": "|grade| % of the cell slope (isotropic)"}


def eva_module():
    sys.path.insert(0, str(APP / "eva_energy"))
    import mars_eva_energy as m
    return m


def energy_grids(cls, slope_deg, P=EVA):
    """Per-metre kcal and minutes for every cell (Pandolf, split gravity scaling, mu = 0.375 module default).
    The model is linear in G, so it is evaluated at G = 0 and 10 % per class and interpolated exactly."""
    m = eva_module()
    G = np.minimum(np.abs(np.tan(np.radians(slope_deg))) * 100.0, 100.0)
    kcal_m = np.full(cls.shape, np.inf); min_m = np.full(cls.shape, np.inf)
    for k in range(3):
        v = P["speed_kmh"] * P["speed_factor"][k] / 3.6            # m/s
        eta = m.TERRAIN_COEFFICIENTS[P["eta_key"][k]]
        r0 = m.metabolic_rate_w(P["body_kg"], P["suit_kg"], v, 0.0, eta, P["gravity_scaling"])
        r1 = m.metabolic_rate_w(P["body_kg"], P["suit_kg"], v, 10.0, eta, P["gravity_scaling"])
        rate = r0 + (r1 - r0) * G / 10.0                            # W
        kcal_per_min = rate * m.W_TO_KCAL_PER_MIN
        mpm = 1.0 / (v * 60.0)                                      # minutes per metre
        sel = cls == k
        kcal_m[sel] = (kcal_per_min * mpm)[sel]
        min_m[sel] = mpm
    stand = m.metabolic_rate_w(P["body_kg"], P["suit_kg"], 0.0, 0.0, 1.0, P["gravity_scaling"]) * m.W_TO_KCAL_PER_MIN
    return kcal_m, min_m, stand


def run_astro():
    from .multistop import plan_multistop, walk
    sc = sc_()
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    tg = read_json(sc.work / "targets.json")
    base_rc = base_rc_at(sc, RES)
    out = {"eva": EVA}
    for name, cls, slope, targets in (("after_recon", T["class_ref"], T["slope_mean"], tg["after_recon"]),
                                      ("before_recon", T["class_prior"], T["slope_prior"], tg["before_recon"])):
        kcal_m, min_m, stand = energy_grids(cls, slope)
        g = {"o2": kcal_m, "t": min_m}
        dwell = {"dwell_min": EVA["dwell_min"], "dwell_o2_factor": stand}
        t0 = time.time()
        pl = plan_multistop(g, base_rc, [p["stop_rc"] for p in targets], RES, dwell=dwell,
                            capacity=EVA["budget_kcal"], reserve=EVA["reserve_frac"])
        wk = walk(pl["path_rc"], pl["stop_idx"], g, RES, dwell=dwell)
        path = pl["path_rc"]
        cum_d = [0.0]
        for a, b in zip(path[:-1], path[1:]):
            cum_d.append(cum_d[-1] + RES * (math.sqrt(2) if a[0] != b[0] and a[1] != b[1] else 1.0))
        marks = [0] + pl["stop_idx"] + [len(path) - 1]
        legs = []
        for k, (i0, i1) in enumerate(zip(marks[:-1], marks[1:])):
            dw = EVA["dwell_min"] if k < len(pl["stop_idx"]) else 0.0
            walk_min = wk["time_min"][i1] - wk["time_min"][i0] - dw
            walk_kcal = wk["o2"][i1] - wk["o2"][i0] - dw * stand
            legs.append({"from": "base" if k == 0 else f"T{pl['order'][k - 1] + 1}",
                         "to": f"T{pl['order'][k] + 1}" if k < len(pl["order"]) else "base",
                         "i0": i0, "i1": i1, "distance_m": round(cum_d[i1] - cum_d[i0], 1),
                         "walk_min": round(walk_min, 1), "walk_kcal": round(walk_kcal, 1),
                         "dwell_min": dw, "dwell_kcal": round(dw * stand, 1)})
        tot_kcal = wk["total_o2"]
        r = {"order": [i + 1 for i in pl["order"]], "skipped": [i + 1 for i in pl["skipped"]],
             "n_stops": len(pl["order"]), "usable_kcal": pl["usable_o2"], "standing_kcal_per_min": round(stand, 3),
             "total_distance_m": round(cum_d[-1], 1), "total_min": round(wk["total_time_min"], 1),
             "total_kcal": round(tot_kcal, 1), "o2_l": round(tot_kcal / EVA["kcal_per_l_o2"], 1),
             "legs": legs, "path_rc": path, "stop_idx": pl["stop_idx"], "seconds": round(time.time() - t0, 1),
             "kcal_per_m_flat": {c: round(float(v), 4) for c, v in zip(("firm", "rough", "sand"),
                                 [energy_grids(np.array([[k]]), np.array([[0.0]]))[0][0, 0] for k in range(3)])}}
        out[name] = r
        log(SCENE, "astro", f"{name}: stops {r['n_stops']}/{len(targets)} order {r['order']} "
            f"{r['total_distance_m']:.0f} m {r['total_min']:.0f} min {r['total_kcal']:.0f} kcal {r['o2_l']} L")
    write_json(sc.work / "astro.json", out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["grid", "terrain", "rover", "select", "astro", "export", "all"])
    a = ap.parse_args()
    steps = ["grid", "terrain", "rover", "select", "astro", "export"] if a.step == "all" else [a.step]
    for s in steps:
        if s == "export":
            from .arcadia_export import run as run_export
            run_export()
        else:
            globals()[f"run_{s}"]()
