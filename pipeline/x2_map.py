"""X2 B6: 10 m sand-share map over the main AOI from the HiRISE-input random forest (trained once on all 72 main-AOI
waypoints, same features and settings as x2_predict), with uncertainty = standard deviation across the 200 trees.
Label: derived, model estimate. Never a prior, never in the rover rules, never used to recompute route A.
python -m pipeline.x2_map -> web/data/jezero/ai4mars/x2_map.png, x2_map_sd.png, x2_map.json"""
from __future__ import annotations

import json
import math

import numpy as np
from PIL import Image
from scipy.signal import fftconvolve

from .common import APP, read_json
from .x2_predict import RADIUS, RES, window_grids


def disc_mean(a, valid):
    r = int(math.ceil(RADIUS / RES)); yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    k = ((xx * RES) ** 2 + (yy * RES) ** 2 <= RADIUS ** 2).astype("float32")
    num = fftconvolve(np.where(valid, a, 0.0), k, mode="same"); den = fftconvolve(valid.astype("float32"), k, mode="same")
    return num / np.maximum(den, 1e-6)


def run():
    from sklearn.ensemble import RandomForestRegressor
    X2 = read_json(APP / "data_work/jezero/ai4mars/x2_result.json")
    rows = [r for r in X2["rows"] if r["window"] == "0,0"]
    units = sorted({r["unit"] for r in rows})
    Xtr = np.array([r["hirise"] + [1.0 if r["unit"] == u else 0.0 for u in units] for r in rows]); ytr = np.array([r["sand"] for r in rows])
    rf = RandomForestRegressor(n_estimators=200, random_state=20261114).fit(Xtr, ytr)
    G = window_grids(0, 0)
    keys = ["fine_coh", "fine_en", "coarse_coh", "coarse_en", "slope_ref", "rough_ref", "bright_m1", "bright_m2"]
    M = {}
    for k in keys:
        a = G[k].astype("float64"); v = np.isfinite(a); M[k] = disc_mean(np.nan_to_num(a), v)
    sd = np.sqrt(np.maximum(M["bright_m2"] - M["bright_m1"] ** 2, 0))
    step = int(10 / RES)
    sl = (slice(step // 2, None, step), slice(step // 2, None, step))
    from .step2_chem import unit_lookup
    unit_at = unit_lookup(); ext = G["ext"]
    H, W = M["fine_coh"][sl].shape
    feats = np.stack([M[k][sl] for k in keys[:7]] + [sd[sl]], -1).reshape(-1, 8)
    xs = ext[0] + (np.arange(W) * step + step // 2 + .5) * RES; ys = ext[3] - (np.arange(H) * step + step // 2 + .5) * RES
    U = []
    for y in ys:
        for x in xs:
            u = unit_at(x, y); U.append(u["symbol"] if u else "none")
    oh = np.array([[1.0 if u == v else 0.0 for v in units] for u in U])
    Xp = np.c_[feats, oh]
    trees = np.stack([t.predict(Xp) for t in rf.estimators_])
    pred = trees.mean(0).reshape(H, W); unc = trees.std(0).reshape(H, W)
    out = APP / "web/data/jezero/ai4mars"; out.mkdir(parents=True, exist_ok=True)
    def png(a, name, vmax):
        v = np.clip(a / vmax, 0, 1); rgba = np.zeros((H, W, 4), np.uint8)
        rgba[..., 0] = 255; rgba[..., 1] = (200 * (1 - v)).astype(np.uint8); rgba[..., 2] = 60; rgba[..., 3] = (220 * v).astype(np.uint8)
        Image.fromarray(rgba, "RGBA").save(out / name)
    png(pred, "x2_map.png", 1.0); png(unc, "x2_map_sd.png", max(float(unc.max()), 1e-6))
    json.dump({"label": "derived, model estimate (random forest on HiRISE features, trained on AI4MARS crowd labels at 72 waypoints); "
                        "not a prior, not used by the rover or route A", "grid_m": 10, "extent_local_m": ext,
               "pred_mean": float(pred.mean()), "pred_range": [float(pred.min()), float(pred.max())], "sd_range": [float(unc.min()), float(unc.max())]},
              open(out / "x2_map.json", "w"), indent=1)
    print("map", pred.shape, float(pred.mean()), float(unc.mean()))


if __name__ == "__main__":
    run()
