"""R3 terrain classes on the 2 m planning grid (status: PROPOSED, review: pending).

python -m pipeline.terrain --scene jezero

Rules = MVP_PLAN section P3 with the parameter values of MVP_PLAN 5.4, plus the proposed slope baseline.
Written before any route or recon number exists; changed only after a human looks at the check images.

reference (HiRISE, "class_ref"):  slope on a 6 m baseline (central difference +-3 m on the 1 m DTM),
    roughness = std of (DTM - gaussian(3 m)) in a 5 m window, ripple index = orientation coherence x
    normalised gradient energy of the 0.5 m orthoimage (structure tensor, 8 m window).
    blocked  : slope >= 25 deg
    sand     : sand-field indicator v2 (pipeline/sandfield.py; fixed thresholds, slope < 15 deg)
               [v1, withdrawn 2026-11-14: ripple index >= P90 -> only ripple crests]
    rough    : slope >= 8 deg or roughness >= 0.059 m (fixed number, locked by manager)
    firm     : otherwise;  then a 3x3 majority filter.
    Class priority (proposed): blocked > sand > rough > firm.
    blocked_rover: slope >= 20 deg.
prior (CTX, "class_prior"): slope of the 20 m DTM (Horn, 40 m baseline) bilinear to 2 m;
    >= 25 -> blocked, >= 8 -> rough, else firm. No sand: orbital 20 m data cannot see ripples.
2 m aggregation: slope, roughness = max of the 1 m cells; ripple = mean.
"""
from __future__ import annotations

import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from scipy.ndimage import gaussian_filter, map_coordinates, sobel, uniform_filter  # noqa: E402

from .common import Scene, log, read_json, write_json  # noqa: E402
from .layers import slope_deg  # noqa: E402

PARAMS = {
    "status": "proposed", "review": "pending",
    "grid_res_m": 2.0,
    "slope_baseline_m": 6.0,
    "slope_rough_deg": 8.0, "slope_steep_deg": 15.0,
    "slope_block_astronaut_deg": 25.0, "slope_block_rover_deg": 20.0,
    "roughness_sigma_m": 3.0, "roughness_window_m": 5.0, "roughness_rough_m": 0.059,
    "ripple_res_m": 0.5, "ripple_window_m": 8.0, "ripple_norm_sigma_m": 20.0, "sand_method": "sand-field v2 (pipeline/sandfield.py SAND_V2)",
    "prior_slope_baseline_m": 40.0,
    "source": "MVP_PLAN 5.4 values (assumed; carried from the team's earlier prototype), slope baseline proposed by tech-lead",
}
CLASSES = ["firm", "rough", "sand", "blocked"]
CLASS_COLORS = ["#62d6a4", "#f4b740", "#ff5a4e", "#5a2a6e"]


def read(p):
    with rasterio.open(p) as s:
        return s.read(1).astype("float32")


def block(a, f, how):
    H, W = a.shape[0] // f * f, a.shape[1] // f * f
    r = a[:H, :W].reshape(H // f, f, W // f, f)
    return getattr(np, how)(r, axis=(1, 3))


def majority3(c, n=4):
    cnt = np.stack([uniform_filter((c == k).astype("float32"), 3) for k in range(n)])
    return np.argmax(cnt, 0).astype(np.uint8)


def classify_ref(slope, rough, sand, P):
    c = np.zeros(slope.shape, np.uint8)
    rough_thr = P["roughness_rough_m"]
    c[(slope >= P["slope_rough_deg"]) | (rough >= rough_thr)] = 1
    c[sand & (slope < P["slope_steep_deg"])] = 2
    c[slope >= P["slope_block_astronaut_deg"]] = 3
    c = majority3(c)
    c[slope >= P["slope_block_astronaut_deg"]] = 3  # never smooth away a blocked cell
    return c, float(rough_thr)


def run(scene: str):
    sc = Scene(scene)
    P = PARAMS
    gm = read_json(sc.work / "grid.json")
    aoi = sc.extent("aoi")
    res = P["grid_res_m"]
    W = int((aoi[2] - aoi[0]) / res); H = int((aoi[3] - aoi[1]) / res)

    # ---- reference: 1 m DTM (padded 30 m) -------------------------------------------------------------
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

    # ---- ripple index on the 0.5 m ortho ---------------------------------------------------------------
    o = read(sc.work / "ortho_025.tif"); o[o == 0] = np.nan
    o = block(o, 2, "mean")  # 0.5 m
    del_ = None
    rr = P["ripple_res_m"]
    f = np.where(np.isfinite(o), o, np.nanmean(o))
    f = f / np.maximum(gaussian_filter(f, P["ripple_norm_sigma_m"] / rr), 1e-3)
    Ix = sobel(f, 1); Iy = sobel(f, 0)
    wpx = P["ripple_window_m"] / rr
    Jxx = uniform_filter(Ix * Ix, wpx); Jyy = uniform_filter(Iy * Iy, wpx); Jxy = uniform_filter(Ix * Iy, wpx)
    del Ix, Iy
    eng = Jxx + Jyy
    coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (eng + 1e-6)
    del Jxx, Jyy, Jxy
    e_n = np.clip(eng / np.nanpercentile(eng, 99), 0, 1)
    ripple = block((coh * e_n).astype("float32"), 4, "mean")  # 2 m
    del coh, eng, e_n, f

    from .sandfield import SAND_V2, classify as sand_classify, features as sand_features, to_grid
    G = to_grid(sand_features(o), 4)
    sand_v2, _ = sand_classify(G, slope_ref, res)
    np.savez_compressed(sc.work / "sand_v2_features.npz", **G)
    class_ref, rough_thr = classify_ref(slope_ref, rough_ref, sand_v2, P)
    rip_thr = None
    blocked_rover_ref = slope_ref >= P["slope_block_rover_deg"]

    # ---- prior: CTX 20 m, 40 m baseline, bilinear to 2 m ----------------------------------------------
    zp = read(sc.work / "dtm_prior_ctx.tif")
    pe = gm["products"]["dtm_prior_ctx"]["extent_local_m"]; pres = gm["products"]["dtm_prior_ctx"]["res_m"]
    sp20 = slope_deg(zp, pres)
    xs = aoi[0] + (np.arange(W) + 0.5) * res; ys = aoi[3] - (np.arange(H) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    slope_prior = map_coordinates(sp20, [(pe[3] - Y) / pres - 0.5, (X - pe[0]) / pres - 0.5], order=1).astype("float32")
    class_prior = np.zeros((H, W), np.uint8)
    class_prior[slope_prior >= P["slope_rough_deg"]] = 1
    class_prior[slope_prior >= P["slope_block_astronaut_deg"]] = 3
    blocked_rover_prior = slope_prior >= P["slope_block_rover_deg"]

    np.savez_compressed(sc.work / "terrain_2m.npz", slope_ref=slope_ref, rough_ref=rough_ref, ripple=ripple,
                        class_ref=class_ref, blocked_rover_ref=blocked_rover_ref, slope_prior=slope_prior,
                        class_prior=class_prior, blocked_rover_prior=blocked_rover_prior)
    frac = lambda c: {CLASSES[k]: round(float(np.mean(c == k)) * 100, 2) for k in range(4)}
    meta = {"params": P, "extent_local_m": list(aoi), "shape": [H, W],
            "fixed_thresholds": {"roughness_m": rough_thr}, "sand_v2": SAND_V2,
            "area_percent_ref": frac(class_ref), "area_percent_prior": frac(class_prior),
            "blocked_rover_percent": {"ref": round(float(blocked_rover_ref.mean()) * 100, 2),
                                      "prior": round(float(blocked_rover_prior.mean()) * 100, 2)},
            "label": "derived (heuristic, not yet reviewed)"}
    write_json(sc.work / "terrain_2m.json", meta)
    log(scene, "terrain", f"ref {meta['area_percent_ref']} prior {meta['area_percent_prior']}")
    qa_figs(sc, o, class_ref, class_prior, ripple, slope_ref, aoi, rip_thr)
    return meta


V1_CROPS = [(-1467, 1153), (-157, 159), (311, 541), (-1425, -545), (-29, -807), (-181, -831),   # v1 "sand" row
            (-659, 1323), (-895, -797), (9, -747), (-957, 1131), (-1199, 261), (-1591, -309)]  # v1 "firm" row
MUST_FLIP = [(9, -747), (-1199, 261), (-1591, -309)]
CHECK_SEED = 20261114


def qa_figs(sc, o05, class_ref, class_prior, ripple, slope_ref, aoi, rip_thr):
    from .sand_check import crop_sheet, overview, pick
    cm = ListedColormap(CLASS_COLORS)
    e = [aoi[0], aoi[2], aoi[1], aoi[3]]
    o2 = block(o05, 4, "mean")
    v0, v1 = np.nanpercentile(o2, 1), np.nanpercentile(o2, 99)
    fig, ax = plt.subplots(1, 2, figsize=(16, 8.2))
    for a_, c, t in ((ax[0], class_ref, "reference classes v2 (HiRISE 1 m DTM + 0.25 m image)"), (ax[1], class_prior, "prior classes (CTX 20 m DTM only)")):
        a_.imshow(o2, cmap="gray", extent=e, vmin=v0, vmax=v1)
        a_.imshow(np.ma.masked_where(c == 0, c), cmap=cm, vmin=-.5, vmax=3.5, alpha=.55, extent=e, interpolation="nearest")
        a_.set_title(t); a_.set_xlabel("x east of base (m)")
    ax[0].set_ylabel("y north (m)")
    from matplotlib.patches import Patch
    ax[1].legend(handles=[Patch(color=CLASS_COLORS[k], label=CLASSES[k]) for k in range(4)], loc="lower left")
    fig.suptitle("Terrain classes v2 (PROPOSED, heuristic, not yet reviewed): firm not drawn")
    fig.tight_layout(); fig.savefig(sc.qa / "S1_terrain_classes_v2.png", dpi=100); plt.close(fig)

    # ---- sand check v2 (direction.md 沙地的修正與放行 point 2) -------------------------------------------
    import rasterio
    with rasterio.open(sc.work / "ortho_025.tif") as s_:
        o025 = s_.read(1).astype("float32")
    o025[o025 == 0] = np.nan
    res = 2.0
    sand = class_ref == 2
    rng = np.random.default_rng(CHECK_SEED)
    margin = int(32 / res)
    toxy = lambda rc: (aoi[0] + (rc[1] + .5) * res, aoi[3] - (rc[0] + .5) * res)
    sp = [toxy(p) for p in pick(sand, 24, rng, margin)]
    npn = [toxy(p) for p in pick(~sand, 24, rng, margin)]
    q = "Question for each crop: is the ground under the cross part of a continuous sand / ripple field?  (left = plain image, right = same image, orange = classified sand)"
    crop_sheet(sc.qa / "S1_sand_check_v2_A_sand.png", o025, sand, aoi, res, sp, "A",
               "Sheet A: 24 random points CLASSIFIED SAND (v2), 60 m crops, seed 20261114.\n" + q)
    crop_sheet(sc.qa / "S1_sand_check_v2_B_notsand.png", o025, sand, aoi, res, npn, "B",
               "Sheet B: 24 random points classified NOT sand (v2), 60 m crops, seed 20261114.\n" + q)
    crop_sheet(sc.qa / "S1_sand_check_v2_C_v1crops.png", o025, sand, aoi, res, [(float(x), float(y)) for x, y in V1_CROPS], "C",
               "Sheet C: the 12 crop centres of the version-1 check (C01-C06 were v1 'sand', C07-C12 v1 'firm'; "
               "C09, C11, C12 must now be sand).\n" + q)
    import json as _json
    (sc.qa / "S1_sand_check_v2_points.json").write_text(_json.dumps(
        {"seed": CHECK_SEED, "crop_m": 60, "A_sand": sp, "B_notsand": npn, "C_v1": V1_CROPS,
         "must_flip": MUST_FLIP, "must_flip_now_sand": [bool(sand[int((aoi[3] - y) / res), int((x - aoi[0]) / res)]) for x, y in MUST_FLIP]}, indent=1))
    v1p = sc.work / "terrain_2m_v1.npz"
    sand_v1 = (np.load(v1p)["class_ref"] == 2) if v1p.exists() else np.zeros_like(sand)
    overview(sc.qa / "S1_sand_overview_v2.png", o2, sand_v1, sand, aoi,
             "version 1 (withdrawn): ripple index >= P90", "version 2 (proposed): sand-field indicator, fixed thresholds",
             "Sand classification over the whole study area (2.4 km x 2.4 km), HiRISE image; orange = classified sand")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
