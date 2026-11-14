# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia scene (SpaceX Starship candidate site, HiRISE ESP_061075_2195): brain-terrain demo pipeline.

python -m pipeline.arcadia grid|terrain|square|rover|select|astro|export|all

  Study area v3 (Shan 2026-11-15): north-up 3.72 km square cut from the v2 rectangle (3.72 x 11.04 km, config aoi_v2,
  its products in data_work/arcadia/v2_strip/) by `square`; the brain model and terrain rules are not re-run.
  The earlier 2.4 km square is aoi_v1, its outputs in data_work/arcadia/v1_2p4km/.
  grid     ortho 0.5 m (RED_A COG overview level 1), DTM 1 m (padded 30 m), prior DTM = HiRISE DTM averaged to 20 m
  terrain  existing rules (pipeline/terrain.py) on 2 m cells, sand = sandfield v2 (0.5 m features, computed in row
           chunks), brain score >= 0.5 is never sand; rough threshold = this scene's P85 of the roughness (the
           rule's definition; 0.059 m is Jezero's P85); prior = slope classes of the 20 m DTM.
           Products then coarsened to 4 m (class = worst of 2 x 2, slope = mean), the terrain and path grid.
  rover    second-version rover rule (pipeline/rover_sim.simulate), 4 m cells, larger budget and more loops
  select   60 m blocks: >= 50 % seen by the rover, top 12 by mean brain score, centres >= 300 m apart;
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
RES = 2.0                         # terrain feature grid
GRID_RES = 4.0                    # terrain and path grid (rover, blocks, astronaut)


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
    aoi = sc.extent("aoi")
    pad = 30.0
    aoi_pad = (aoi[0] - pad, aoi[1] - pad, aoi[2] + pad, aoi[3] + pad)
    meta = {"base": sc.cfg["base"], "aoi": grid_meta(sc, aoi, 0.5), "products": {}}

    def save(name, arr, tr, extent, res):
        save_local_tif(sc.work / f"{name}.tif", arr, tr, nodata=np.nan)
        meta["products"][name] = {**grid_meta(sc, extent, res), "nan_frac": float(np.mean(~np.isfinite(arr)))}
        log(SCENE, "grid", f"{name} {arr.shape} NaN {np.mean(~np.isfinite(arr)):.3%}")

    a, tr = to_local(src_file(sc, "ortho_05"), sc, aoi, 0.5)
    a[a == 0] = np.nan
    save("ortho_05", a, tr, aoi, 0.5)
    del a
    a, tr = to_local(src_file(sc, "dtm_fine"), sc, aoi_pad, 1.0)
    save("dtm_fine", a, tr, aoi_pad, 1.0)
    # prior: the HiRISE DTM averaged to 20 m (stands in for a CTX 20 m DTM; no separate download)
    ctx = (aoi[0] - 200, aoi[1] - 200, aoi[2] + 200, aoi[3] + 200)
    a, tr = to_local(src_file(sc, "dtm_fine"), sc, ctx, 20.0, Resampling.average)
    save("dtm_prior_ctx", a, tr, ctx, 20.0)
    write_json(sc.work / "grid.json", meta)
    log(SCENE, "grid", f"done in {time.time() - t0:.0f} s")


# ------------------------------------------------------------------------------------------------- terrain
ROUGH_PCTL = 85.0                 # rough threshold = this scene's P85 of the 2 m roughness (rule definition)
CHUNK_PX = 4000                   # 0.5 m rows per sand-feature chunk (2 km)
CHUNK_PAD_PX = 256                # 128 m overlap on each side (> 3 sigma of the 20 m normalisation)


def sand_features_2m(o05):
    """sandfield v2 features on the 0.5 m image, computed in row chunks with overlap, block-averaged to 2 m."""
    from .sandfield import features as sand_features, to_grid
    H = o05.shape[0]; f = int(RES / 0.5)
    parts = []
    for r0 in range(0, H, CHUNK_PX):
        r1 = min(H, r0 + CHUNK_PX)
        a0 = max(0, r0 - CHUNK_PAD_PX); a1 = min(H, r1 + CHUNK_PAD_PX)
        F = sand_features(o05[a0:a1])
        F = {k: v[r0 - a0:r1 - a0] for k, v in F.items()}
        parts.append(to_grid(F, f))
        log(SCENE, "terrain", f"sand features rows {r0}-{r1}")
    return {k: np.concatenate([p[k] for p in parts], 0) for k in parts[0]}


def run_terrain():
    from scipy.ndimage import gaussian_filter, map_coordinates, uniform_filter
    from .layers import slope_deg
    from .sandfield import SAND_V2, classify as sand_classify
    from .terrain import PARAMS as P0, CLASSES, block, classify_ref, read
    sc = sc_()
    t0 = time.time()
    gm = read_json(sc.work / "grid.json")
    aoi = sc.extent("aoi")
    W = int((aoi[2] - aoi[0]) / RES); H = int((aoi[3] - aoi[1]) / RES)
    z = read(sc.work / "dtm_fine.tif")
    pad = 30
    h = int(P0["slope_baseline_m"] / 2)
    gx = (np.roll(z, -h, 1) - np.roll(z, h, 1)) / (2 * h)
    gy = (np.roll(z, h, 0) - np.roll(z, -h, 0)) / (2 * h)
    s1 = np.degrees(np.arctan(np.hypot(gx, gy)))[pad:-pad, pad:-pad]
    del gx, gy
    hp = z - gaussian_filter(z, P0["roughness_sigma_m"])
    w = int(P0["roughness_window_m"])
    m1 = uniform_filter(hp, w); m2 = uniform_filter(hp * hp, w)
    r1 = np.sqrt(np.maximum(m2 - m1 * m1, 0))[pad:-pad, pad:-pad]
    del hp, m1, m2, z
    slope_ref = block(s1, 2, "max"); rough_ref = block(r1, 2, "max")
    slope_mean = block(s1, 2, "mean")
    del s1, r1
    P = dict(P0)
    P["roughness_rough_m"] = round(float(np.nanpercentile(rough_ref, ROUGH_PCTL)), 4)
    P["roughness_rule"] = (f"P{ROUGH_PCTL:.0f} of this scene's 2 m roughness (definition of the rule; "
                           f"Jezero P85 = {P0['roughness_rough_m']} m)")
    o = read(sc.work / "ortho_05.tif")
    G = sand_features_2m(o)
    del o
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
    del X, Y
    class_prior = np.zeros((H, W), np.uint8)
    class_prior[slope_prior >= P["slope_rough_deg"]] = 1
    class_prior[slope_prior >= P["slope_block_astronaut_deg"]] = 3
    blocked_rover_prior = slope_prior >= P["slope_block_rover_deg"]
    np.savez_compressed(sc.work / "terrain_2m.npz", slope_ref=slope_ref, slope_mean=slope_mean, rough_ref=rough_ref,
                        class_ref=class_ref, blocked_rover_ref=blocked_rover_ref, slope_prior=slope_prior,
                        class_prior=class_prior, blocked_rover_prior=blocked_rover_prior, sand_v2_raw=sand_v2)
    T4 = coarsen_terrain({"class_ref": class_ref, "class_prior": class_prior, "blocked_rover_ref": blocked_rover_ref,
                          "blocked_rover_prior": blocked_rover_prior}, int(GRID_RES / RES))
    T4["slope_mean"] = block(slope_mean, int(GRID_RES / RES), "mean").astype("float32")
    T4["slope_prior"] = block(slope_prior, int(GRID_RES / RES), "mean").astype("float32")
    np.savez_compressed(sc.work / "terrain_4m.npz", **T4)
    frac = lambda c: {CLASSES[k]: round(float(np.mean(c == k)) * 100, 2) for k in range(4)}
    rough_old = float(np.mean(rough_ref >= P0["roughness_rough_m"]))
    meta = {"params": P, "sand_v2": SAND_V2, "brain_sand_exclude": BRAIN_SAND_EXCLUDE,
            "extent_local_m": list(aoi), "shape": [H, W], "shape_4m": list(T4["class_ref"].shape),
            "brain_frac": round(float(is_brain.mean()), 4),
            "sand_rule_hit_on_brain_frac": round(sand_hit_brain, 4),
            "rough_cells_at_jezero_threshold_frac": round(rough_old, 4),
            "area_percent_ref": frac(class_ref), "area_percent_ref_4m": frac(T4["class_ref"]),
            "area_percent_prior": frac(class_prior), "seconds": round(time.time() - t0, 1)}
    write_json(sc.work / "terrain_2m.json", meta)
    log(SCENE, "terrain", f"rough thr {P['roughness_rough_m']} (0.059 would flag {rough_old:.1%}); "
        f"ref {meta['area_percent_ref']} 4m {meta['area_percent_ref_4m']} prior {meta['area_percent_prior']} "
        f"brain {meta['brain_frac']:.1%} sand-on-brain {sand_hit_brain:.1%} in {meta['seconds']} s")
    return meta


# -------------------------------------------------------------------------------------------------- square
# Study area v3 (Shan 2026-11-15): a north-up square inside the v2 rectangle, cut from the v2 products (no re-run of
# the brain model or the terrain rules; rough threshold stays the v2 P85 = 0.196 m).
SQUARE_M = 3720.0                 # = v2 width (the largest square that fits)
SQUARE_STEP_M = 120.0             # candidate positions slide by 120 m (keeps 2 / 4 / 8 m rows and 60 m blocks aligned)
SQUARE_BRAIN = (0.35, 0.65)       # brain (score >= 0.5) fraction of the square
BASE_RULE = {"brain_free_m": 100.0, "slope_radius_m": 30.0, "slope_max_deg": 5.5, "edge_min_m": 400.0,
             "max_from_centre_m": 300.0, "class": "firm (4 m terrain grid)"}
V2_DIR = "v2_strip"
V2_FILES = ("grid.json", "terrain_2m.npz", "terrain_2m.json", "terrain_4m.npz", "brain_score_2m.npy", "cost_8m.npz",
            "recon_loops.json", "recon_state.npz", "targets.json", "astro.json", "ortho_05.tif")


def disk(r_cells):
    k = int(math.ceil(r_cells))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    return (yy * yy + xx * xx <= r_cells * r_cells).astype(np.float32)


def base_candidates(T4, brain2, res=GRID_RES):
    """Base rule (as before, on the 4 m grid): firm, no brain cell (2 m score >= 0.5) within 100 m, mean slope
    within 30 m < 5.5 deg. Edge distance and the distance to the square centre are applied per square."""
    from scipy.ndimage import convolve, distance_transform_edt
    from .terrain import block
    is_brain4 = block((np.nan_to_num(brain2) >= BRAIN_SAND_EXCLUDE).astype(np.uint8), int(res / RES), "max") > 0
    far_brain = distance_transform_edt(~is_brain4) * res >= BASE_RULE["brain_free_m"]
    k = disk(BASE_RULE["slope_radius_m"] / res); k /= k.sum()
    flat = convolve(np.nan_to_num(T4["slope_mean"], nan=90.0), k, mode="nearest") < BASE_RULE["slope_max_deg"]
    return (T4["class_ref"] == 0) & far_brain & flat


def run_square():
    import shutil
    import rasterio
    from rasterio.windows import Window
    from .terrain import CLASSES
    sc = sc_()
    cfg_path = APP / "config" / "scenes" / f"{SCENE}.json"
    cfg = read_json(cfg_path)
    v2 = cfg.get("aoi_v2") or dict(cfg["aoi"])
    src = sc.work / V2_DIR
    if not src.exists():
        src.mkdir()
        for f in V2_FILES:
            if (sc.work / f).exists():
                shutil.move(str(sc.work / f), str(src / f))
    T4 = dict(np.load(src / "terrain_4m.npz"))
    brain2 = np.load(src / "brain_score_2m.npy")
    ok_base = base_candidates(T4, brain2)
    xmin, xmax, ymax0, ymin0 = v2["xmin"], v2["xmax"], v2["ymax"], v2["ymin"]
    assert abs((xmax - xmin) - SQUARE_M) < 1e-6
    hab0 = cfg.get("habitat_v2") or cfg["habitat"]
    n_pos = int(round((ymax0 - ymin0 - SQUARE_M) / SQUARE_STEP_M)) + 1
    n4 = int(SQUARE_M / GRID_RES)
    rows = []
    for k in range(n_pos):
        ymax = ymax0 - k * SQUARE_STEP_M; ymin = ymax - SQUARE_M
        r2 = int(k * SQUARE_STEP_M / RES); r4 = int(k * SQUARE_STEP_M / GRID_RES)
        b = brain2[r2:r2 + int(SQUARE_M / RES)]
        bf = float(np.mean(np.nan_to_num(b) >= BRAIN_SAND_EXCLUDE))
        cand = ok_base[r4:r4 + n4]
        rr, cc = np.nonzero(cand)
        x = xmin + (cc + 0.5) * GRID_RES; y = ymax - (rr + 0.5) * GRID_RES
        edge = np.minimum.reduce([x - xmin, xmax - x, y - ymin, ymax - y])
        cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
        dc = np.hypot(x - cx, y - cy)
        sel = (edge >= BASE_RULE["edge_min_m"]) & (dc <= BASE_RULE["max_from_centre_m"])
        base = None
        if sel.any():
            i = np.flatnonzero(sel)[np.argmin(dc[sel])]
            base = {"x": round(float(x[i]), 1), "y": round(float(y[i]), 1), "from_centre_m": round(float(dc[i]), 1)}
        okk = SQUARE_BRAIN[0] <= bf <= SQUARE_BRAIN[1] and base is not None
        rows.append({"k": k, "ymin": ymin, "ymax": ymax, "brain_frac": round(bf, 4), "base": base, "ok": okk,
                     "centre_to_old_base_m": round(float(math.hypot(cx - hab0["x"], cy - hab0["y"])), 1)})
    good = [r for r in rows if r["ok"]]
    if not good:
        raise SystemExit("no square position meets the rule")
    pick = min(good, key=lambda r: r["centre_to_old_base_m"])
    k = pick["k"]
    log(SCENE, "square", f"{len(good)}/{len(rows)} positions qualify; pick y {pick['ymin']}..{pick['ymax']} "
        f"brain {pick['brain_frac']:.1%} base {pick['base']}")
    # ---- cut the v2 products -------------------------------------------------------------------------------
    r2, r4, r8 = (int(k * SQUARE_STEP_M / r) for r in (RES, GRID_RES, 8.0))
    n2, n8 = int(SQUARE_M / RES), int(SQUARE_M / 8.0)
    np.save(sc.work / "brain_score_2m.npy", brain2[r2:r2 + n2])
    del brain2
    T2 = np.load(src / "terrain_2m.npz")
    T2c = {kk: T2[kk][r2:r2 + n2] for kk in T2.files}
    np.savez_compressed(sc.work / "terrain_2m.npz", **T2c)
    T4c = {kk: v[r4:r4 + n4] for kk, v in T4.items()}
    np.savez_compressed(sc.work / "terrain_4m.npz", **T4c)
    C = np.load(src / "cost_8m.npz")
    np.savez_compressed(sc.work / "cost_8m.npz", **{kk: C[kk][r8:r8 + n8] for kk in C.files})
    with rasterio.open(src / "ortho_05.tif") as s:
        w = Window(0, int(k * SQUARE_STEP_M / 0.5), s.width, int(SQUARE_M / 0.5))
        a = s.read(1, window=w)
        prof = s.profile.copy(); prof.update(height=a.shape[0], transform=s.window_transform(w))
    with rasterio.open(sc.work / "ortho_05.tif", "w", **prof) as d:
        d.write(a, 1)
    del a
    # ---- terrain stats of the square (thresholds unchanged) --------------------------------------------------
    tm = read_json(src / "terrain_2m.json")
    frac = lambda c: {CLASSES[q]: round(float(np.mean(c == q)) * 100, 2) for q in range(4)}
    aoi = [xmin, pick["ymin"], xmax, pick["ymax"]]
    tm.update({"extent_local_m": aoi, "shape": list(T2c["class_ref"].shape), "shape_4m": list(T4c["class_ref"].shape),
               "brain_frac": pick["brain_frac"], "area_percent_ref": frac(T2c["class_ref"]),
               "area_percent_ref_4m": frac(T4c["class_ref"]), "area_percent_prior": frac(T2c["class_prior"]),
               "cut_from": "v2 products (data_work/arcadia/v2_strip), rows cut, thresholds unchanged"})
    for kk in ("rough_cells_at_jezero_threshold_frac", "sand_rule_hit_on_brain_frac", "seconds"):
        tm.pop(kk, None)
    write_json(sc.work / "terrain_2m.json", tm)
    write_json(sc.work / "square.json", {"rule": {"side_m": SQUARE_M, "step_m": SQUARE_STEP_M,
               "brain_frac": SQUARE_BRAIN, "base": BASE_RULE, "pick": "closest square centre to the v2 base"},
               "pick": pick, "positions": rows})
    # ---- config ----------------------------------------------------------------------------------------------
    cfg["aoi_v2"] = v2
    cfg["habitat_v2"] = hab0
    cfg["aoi"] = {"xmin": xmin, "ymin": pick["ymin"], "xmax": xmax, "ymax": pick["ymax"], "label": "derived",
                  "rule": (f"Study area v3 (Shan 2026-11-15): north-up {SQUARE_M / 1000:.2f} km square inside aoi_v2, "
                           f"positions every {SQUARE_STEP_M:.0f} m in y; brain fraction {SQUARE_BRAIN[0]:.0%}-"
                           f"{SQUARE_BRAIN[1]:.0%} and a base within {BASE_RULE['max_from_centre_m']:.0f} m of the "
                           f"centre; closest to the v2 base. Products cut from v2 (no re-run).")}
    cfg["habitat"] = {"x": pick["base"]["x"], "y": pick["base"]["y"], "label": "derived",
                      "rule": ("firm 4 m cell, no brain cell (score >= 0.5) within 100 m, mean slope within 30 m "
                               "< 5.5 deg, >= 400 m from the edge; closest to the square centre")}
    write_json(cfg_path, cfg)
    log(SCENE, "square", f"aoi {aoi}, terrain 4 m {tm['area_percent_ref_4m']}")
    return pick


# --------------------------------------------------------------------------------------------------- rover
ROVER_RES = GRID_RES
ROVER_PLAN_WINDOW_M = 400.0       # point-to-point plans search start/goal box + 400 m (speed; whole grid if no path)
ROVER_OVERRIDES = {        # study area v3 (3.72 km square, base near the centre): v2 rule, budget and bands scaled down
    "n_loops": 24, "loop_budget": 4000.0 * 5, "sense_radius_m": 30.0,
    "bands_m": {"near": [300.0, 1000.0], "mid": [1000.0, 1600.0], "far": [1600.0, 1e9]},
    "goal_lattice_m": 100.0, "goal_gain_radius_m": 300.0, "base_free_radius_m": 60.0,
}


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
    from . import rover_sim
    from .rover_sim import PARAMS, simulate
    rover_sim.PLAN_WINDOW_CELLS = int(ROVER_PLAN_WINDOW_M / ROVER_RES)
    sc = sc_()
    T4 = dict(np.load(sc.work / "terrain_4m.npz"))
    f = int(ROVER_RES / RES)
    P = dict(PARAMS); P["grid_res_m"] = ROVER_RES; P.update(ROVER_OVERRIDES)
    P["plan_window_m"] = ROVER_PLAN_WINDOW_M
    aoi = sc.extent("aoi")
    base_rc = base_rc_at(sc, ROVER_RES)
    t0 = time.time()
    bel, loops = simulate(T4, P, base_rc, log_fn=lambda m: log(SCENE, "rover", m))
    secs = round(time.time() - t0, 1)
    np.savez_compressed(sc.work / "recon_state.npz", observed=bel.observed, first_t=bel.first_t)
    br, bc = base_rc
    H, W = bel.observed.shape
    rr, cc = np.nonzero(bel.observed)
    far = float(np.hypot(rr - br, cc - bc).max() * ROVER_RES) if rr.size else 0.0
    for L in loops:
        L["observed_frac_aoi"] = round(float(((bel.first_t >= 0) & (bel.first_t <= L["t1"])).mean()), 4)
        pr = np.array(L["path_rc"])
        L["max_dist_m"] = round(float(np.hypot(pr[:, 0] - br, pr[:, 1] - bc).max() * ROVER_RES), 1)
    out = {"params": P, "base_rc": list(base_rc), "extent_local_m": list(aoi), "seconds": secs,
           "observed_frac": round(float(bel.observed.mean()), 4),
           "max_path_dist_m": max(L["max_dist_m"] for L in loops), "max_seen_dist_m": round(far, 1),
           "total_length_m": round(sum(L["length_m"] for L in loops), 1), "loops": loops}
    write_json(sc.work / "recon_loops.json", out)
    log(SCENE, "rover", f"{len(loops)} loops in {secs} s, seen {out['observed_frac']:.1%}, "
        f"farthest {out['max_path_dist_m']} m, total {out['total_length_m'] / 1000:.1f} km")
    return out


# -------------------------------------------------------------------------------------------------- select
BLOCK_M = 60.0
SEEN_MIN = 0.5
N_PICK = 12                       # Shan 2026-11-15 evening: top 12 over the whole area
MIN_SEP_M = 300.0


def pick_blocks(score, passable, seen=None, n=N_PICK, block_m=BLOCK_M, seen_min=SEEN_MIN, min_sep=MIN_SEP_M, res=GRID_RES,
                extent=(-1200.0, -1200.0, 1200.0, 1200.0)):
    """Rule fixed 2026-11-15 (v2: top 12, >= 300 m apart). Returns list of dicts (block centre, stop cell, mean score,
    seen fraction)."""
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


def brain_score_grid():
    """Brain score on the 4 m grid = mean of the 2 x 2 finite 2 m scores."""
    from .terrain import block
    s2 = np.load(sc_().work / "brain_score_2m.npy")
    f = int(GRID_RES / RES)
    v = block(np.isfinite(s2).astype(np.float32), f, "sum")
    t = block(np.nan_to_num(s2, nan=0.0), f, "sum")
    return np.where(v > 0, t / np.maximum(v, 1), np.nan).astype(np.float32)


def run_select():
    sc = sc_()
    T = dict(np.load(sc.work / "terrain_4m.npz"))
    score = brain_score_grid()
    seen = np.load(sc.work / "recon_state.npz")["observed"]
    passable = T["class_ref"] < 3
    ext = tuple(sc.extent("aoi"))
    after = pick_blocks(score, passable, seen, extent=ext)
    before = pick_blocks(score, T["class_prior"] < 3, None, extent=ext)
    out = {"rule": {"block_m": BLOCK_M, "seen_min": SEEN_MIN, "n": N_PICK, "min_sep_m": MIN_SEP_M, "grid_res_m": GRID_RES,
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


WALK_WINDOW_M = 2000.0     # candidate stops: chosen areas within +-2 km (square) of the start (same rule as the page)


def cost_grid_8m(kcal_m, min_m):
    """4 m per-metre costs -> 8 m for the in-browser planner: mean of the finite 2 x 2 values; blocked (inf) when
    3 or 4 of the 4 cells are blocked."""
    from .terrain import block
    out = []
    for g in (kcal_m, min_m):
        fin = np.isfinite(g)
        n = block(fin.astype(np.float32), 2, "sum")
        t = block(np.where(fin, g, 0.0), 2, "sum")
        out.append(np.where(n >= 2, t / np.maximum(n, 1), np.inf))
    return out


def plan_from(kcal_m, min_m, stand, start_rc, targets, res, window_m=WALK_WINDOW_M):
    """Multi-stop plan from start_rc to the chosen areas inside the +-window, plus the round-trip kcal (walk both ways
    + one dwell) of every chosen area from start_rc. Same order rule as pipeline/multistop.py (brute force <= 6)."""
    from .astro_plan import field
    from .multistop import plan_multistop, walk
    g = {"o2": kcal_m, "t": min_m}
    dwell = {"dwell_min": EVA["dwell_min"], "dwell_o2_factor": stand}
    sr, scl = start_rc
    cand = [k for k, p in enumerate(targets)
            if max(abs(p["stop_rc"][0] - sr), abs(p["stop_rc"][1] - scl)) * res <= window_m]
    _, f0 = field(kcal_m * res, tuple(start_rc))
    rt = [round(float(2 * f0[tuple(p["stop_rc"])] + EVA["dwell_min"] * stand), 1) for p in targets]
    if cand:
        pl = plan_multistop(g, start_rc, [targets[k]["stop_rc"] for k in cand], res, dwell=dwell,
                            capacity=EVA["budget_kcal"], reserve=EVA["reserve_frac"], brute_max=6)
        order = [cand[i] for i in pl["order"]]
        path, stop_idx, usable = pl["path_rc"], pl["stop_idx"], pl["usable_o2"]
    else:
        order, path, stop_idx = [], [tuple(start_rc)], []
        usable = EVA["budget_kcal"] * (1 - EVA["reserve_frac"])
    wk = walk(path, stop_idx, g, res, dwell=dwell)
    return {"cand": cand, "order": order, "path": path, "stop_idx": stop_idx, "walk": wk, "usable": usable,
            "round_trip_kcal": rt}


def run_astro():
    sc = sc_()
    T = dict(np.load(sc.work / "terrain_4m.npz"))
    tg = read_json(sc.work / "targets.json")
    base_rc = base_rc_at(sc, GRID_RES)
    targets = tg["after_recon"]
    t0 = time.time()
    kcal_m, min_m, stand = energy_grids(T["class_ref"], T["slope_mean"])
    pr = plan_from(kcal_m, min_m, stand, base_rc, targets, GRID_RES)
    wk, path = pr["walk"], pr["path"]
    cum_d = [0.0]
    for a_, b_ in zip(path[:-1], path[1:]):
        cum_d.append(cum_d[-1] + GRID_RES * (math.sqrt(2) if a_[0] != b_[0] and a_[1] != b_[1] else 1.0))
    marks = [0] + pr["stop_idx"] + [len(path) - 1]
    legs = []
    for k, (i0, i1) in enumerate(zip(marks[:-1], marks[1:])):
        dw = EVA["dwell_min"] if k < len(pr["stop_idx"]) else 0.0
        legs.append({"from": "base" if k == 0 else f"T{pr['order'][k - 1] + 1}",
                     "to": f"T{pr['order'][k] + 1}" if k < len(pr["order"]) else "base",
                     "i0": i0, "i1": i1, "distance_m": round(cum_d[i1] - cum_d[i0], 1),
                     "walk_min": round(wk["time_min"][i1] - wk["time_min"][i0] - dw, 1),
                     "walk_kcal": round(wk["o2"][i1] - wk["o2"][i0] - dw * stand, 1),
                     "dwell_min": dw, "dwell_kcal": round(dw * stand, 1)})
    tot = wk["total_o2"]
    r = {"order": [i + 1 for i in pr["order"]], "candidates": [i + 1 for i in pr["cand"]],
         "n_stops": len(pr["order"]), "n_targets": len(targets), "usable_kcal": pr["usable"],
         "standing_kcal_per_min": round(stand, 3), "window_m": WALK_WINDOW_M,
         "round_trip_kcal": pr["round_trip_kcal"],
         "total_distance_m": round(cum_d[-1], 1), "total_min": round(wk["total_time_min"], 1),
         "total_kcal": round(tot, 1), "o2_l": round(tot / EVA["kcal_per_l_o2"], 1),
         "legs": legs, "path_rc": [list(map(int, p)) for p in path], "stop_idx": pr["stop_idx"],
         "seconds": round(time.time() - t0, 1),
         "kcal_per_m_flat": {c: round(float(v), 4) for c, v in zip(("firm", "rough", "sand"),
                             [energy_grids(np.array([[k]]), np.array([[0.0]]))[0][0, 0] for k in range(3)])}}
    k8, m8 = cost_grid_8m(kcal_m, min_m)
    np.savez_compressed(sc.work / "cost_8m.npz", kcal_m=k8.astype(np.float32), min_m=m8.astype(np.float32))
    out = {"eva": EVA, "grid_res_m": GRID_RES, "after_recon": r}
    write_json(sc.work / "astro.json", out)
    log(SCENE, "astro", f"stops {r['n_stops']} of {len(pr['cand'])} candidates in the window ({len(targets)} areas) "
        f"order {r['order']} {r['total_distance_m']:.0f} m {r['total_min']:.0f} min {r['total_kcal']:.0f} kcal "
        f"{r['o2_l']} L; round trips {r['round_trip_kcal']} in {r['seconds']} s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["grid", "terrain", "square", "rover", "select", "astro", "export", "all"])
    a = ap.parse_args()
    steps = ["grid", "terrain", "rover", "select", "astro", "export"] if a.step == "all" else [a.step]
    for s in steps:
        if s == "export":
            from .arcadia_export import run as run_export
            run_export()
        else:
            globals()[f"run_{s}"]()
