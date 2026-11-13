"""R3 terrain classes on the 2 m planning grid (status: PROPOSED, review: pending).

python -m pipeline.terrain --scene jezero

Rules = MVP_PLAN section P3 with the parameter values of MVP_PLAN 5.4, plus the proposed slope baseline.
Written before any route or recon number exists; changed only after a human looks at the check images.

reference (HiRISE, "class_ref"):  slope on a 6 m baseline (central difference +-3 m on the 1 m DTM),
    roughness = std of (DTM - gaussian(3 m)) in a 5 m window, ripple index = orientation coherence x
    normalised gradient energy of the 0.5 m orthoimage (structure tensor, 8 m window).
    blocked  : slope >= 25 deg
    sand     : ripple >= P90 (AOI) and slope < 15 deg
    rough    : slope >= 8 deg or roughness >= P85 (AOI)
    firm     : otherwise;  then a 3x3 majority filter.
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
    "roughness_sigma_m": 3.0, "roughness_window_m": 5.0, "roughness_rough_percentile": 85,
    "ripple_res_m": 0.5, "ripple_window_m": 8.0, "ripple_percentile": 90, "ripple_norm_sigma_m": 20.0,
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


def classify_ref(slope, rough, ripple, P):
    c = np.zeros(slope.shape, np.uint8)
    rough_thr = np.nanpercentile(rough, P["roughness_rough_percentile"])
    rip_thr = np.nanpercentile(ripple, P["ripple_percentile"])
    c[(slope >= P["slope_rough_deg"]) | (rough >= rough_thr)] = 1
    c[(ripple >= rip_thr) & (slope < P["slope_steep_deg"])] = 2
    c[slope >= P["slope_block_astronaut_deg"]] = 3
    c = majority3(c)
    c[slope >= P["slope_block_astronaut_deg"]] = 3  # never smooth away a blocked cell
    return c, float(rough_thr), float(rip_thr)


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

    class_ref, rough_thr, rip_thr = classify_ref(slope_ref, rough_ref, ripple, P)
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
            "derived_thresholds": {"roughness_P85_m": round(rough_thr, 3), "ripple_P90": round(rip_thr, 4)},
            "area_percent_ref": frac(class_ref), "area_percent_prior": frac(class_prior),
            "blocked_rover_percent": {"ref": round(float(blocked_rover_ref.mean()) * 100, 2),
                                      "prior": round(float(blocked_rover_prior.mean()) * 100, 2)},
            "label": "derived (heuristic, not yet reviewed)"}
    write_json(sc.work / "terrain_2m.json", meta)
    log(scene, "terrain", f"ref {meta['area_percent_ref']} prior {meta['area_percent_prior']} thr {meta['derived_thresholds']}")
    qa_figs(sc, o, class_ref, class_prior, ripple, slope_ref, aoi, rip_thr)
    return meta


def qa_figs(sc, o05, class_ref, class_prior, ripple, slope_ref, aoi, rip_thr):
    cm = ListedColormap(CLASS_COLORS)
    e = [aoi[0], aoi[2], aoi[1], aoi[3]]
    o2 = block(o05, 4, "mean")
    v0, v1 = np.nanpercentile(o2, 1), np.nanpercentile(o2, 99)
    fig, ax = plt.subplots(1, 2, figsize=(16, 8.2))
    for a_, c, t in ((ax[0], class_ref, "reference classes (HiRISE 1 m DTM + 0.25 m image)"), (ax[1], class_prior, "prior classes (CTX 20 m DTM only)")):
        a_.imshow(o2, cmap="gray", extent=e, vmin=v0, vmax=v1)
        a_.imshow(np.ma.masked_where(c == 0, c), cmap=cm, vmin=-.5, vmax=3.5, alpha=.55, extent=e, interpolation="nearest")
        a_.set_title(t); a_.set_xlabel("x east of base (m)")
    ax[0].set_ylabel("y north (m)")
    from matplotlib.patches import Patch
    ax[1].legend(handles=[Patch(color=CLASS_COLORS[k], label=CLASSES[k]) for k in range(4)], loc="lower left")
    fig.suptitle("R3 terrain classes (PROPOSED, heuristic, not yet reviewed): firm not drawn")
    fig.tight_layout(); fig.savefig(sc.qa / "R3_terrain_classes.png", dpi=100); plt.close(fig)

    # ripple zooms: 6 sand blocks and 6 non-sand blocks (100 m), chosen at random with a fixed seed
    rng = np.random.default_rng(20261114)
    res = 2.0; half = 50
    Hh, Ww = class_ref.shape
    margin = int(half / res) + 1
    def pick(mask, n):
        rr, cc = np.nonzero(mask[margin:-margin, margin:-margin])
        i = rng.choice(len(rr), size=min(n, len(rr)), replace=False)
        return [(rr[k] + margin, cc[k] + margin) for k in i]
    sand = pick(class_ref == 2, 6); non = pick(class_ref == 0, 6)
    fig, axs = plt.subplots(2, 6, figsize=(22, 8))
    for row, pts, name in ((0, sand, "classified SAND"), (1, non, "classified FIRM")):
        for k, (r, c) in enumerate(pts):
            cx = aoi[0] + (c + .5) * res; cy = aoi[3] - (r + .5) * res
            r0 = int((aoi[3] - cy - half) / 0.5); c0 = int((cx - half - aoi[0]) / 0.5)
            sub = o05[r0:r0 + 200, c0:c0 + 200]
            axs[row, k].imshow(sub, cmap="gray", extent=[cx - half, cx + half, cy - half, cy + half],
                               vmin=np.nanpercentile(sub, 1), vmax=np.nanpercentile(sub, 99))
            cr = class_ref[r - 25:r + 25, c - 25:c + 25]
            axs[row, k].contour(np.linspace(cx - half, cx + half, cr.shape[1]), np.linspace(cy + half, cy - half, cr.shape[0]),
                                (cr == 2).astype(float), levels=[.5], colors="#ff5a4e", linewidths=.8)
            axs[row, k].set_title(f"{name}\nx {cx:.0f}, y {cy:.0f} m", fontsize=8); axs[row, k].set_xticks([]); axs[row, k].set_yticks([])
    fig.suptitle("R3 ripple check (100 m crops of the 0.5 m HiRISE image; red outline = cells classified sand). "
                 "Question for a person: are the top-row crops sand ripples, and the bottom-row crops not?")
    fig.tight_layout(); fig.savefig(sc.qa / "R3_ripple_check.png", dpi=90); plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    ax[0].hist(ripple[np.isfinite(ripple)].ravel(), 100, log=True); ax[0].axvline(rip_thr, c="r"); ax[0].set_title("ripple index (P90 line)")
    ax[1].hist(slope_ref.ravel(), np.arange(0, 41), log=True, alpha=.6, label="reference 6 m baseline")
    for t in (8, 15, 20, 25):
        ax[1].axvline(t, c="k", lw=.6)
    ax[1].legend(); ax[1].set_title("slope (deg) with thresholds 8 / 15 / 20 / 25")
    fig.tight_layout(); fig.savefig(sc.qa / "R3_distributions.png", dpi=90); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
