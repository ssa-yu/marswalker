"""X2 (b): orbital data -> ground-photo terrain label (AI4MARS crowd labels), HiRISE input vs CTX input. Run ONCE.

python -m pipeline.x2_predict   -> data_work/jezero/ai4mars/x2_result.json, web/data/jezero/ai4mars/x2_map.png

Rules (manager 2026-11-14, TECH_LEAD_BRIEF 第十一次更新 B1-B8; fixed before any number):
B1 answers: per waypoint, mean over its labelled Navcam images (AI4MARS NAV merged labels, NLF, all sols, as X1 A3) of the
   sand share (main) and bedrock share (secondary) of labelled pixels. Main table: main-AOI waypoints. Second
   table: "waypoints inside the six windows" (the only places where the HiRISE inputs are local).
   Targets: share regression and "sand-dominant" (share >= 0.5) classification.
B2 inputs, same models and splits: HiRISE version = means within a 30 m circle around the waypoint of the S1 fine /
   coarse coherence and contrast (sandfield.features on the 0.5 m ortho, at 2 m), reference slope and roughness
   (terrain_2m, from the 1 m DTM), and mean and standard deviation of the 0.5 m ortho brightness / its 25 m local
   mean; plus SIM 3464 unit one-hot. CTX version = mean and std of CTX 6 m ortho brightness, prior slope (CTX 20 m),
   SIM 3464 unit. No CRISM, no Perseverance-derived quantity.
B3 kNN (k = 5) and random forest (200 trees, scikit-learn defaults), no tuning.
B4 spatial splits only: main AOI = leave one sol segment out (5 segments, 100 m buffer); full set = leave one window out.
B5 baselines: (1) our HiRISE rule (reference sand share in the same 30 m circle used as the prediction);
   (2) SIM 3464 unit majority (training mean / majority per unit); (3) nearest neighbour (nearest training
   waypoint's value). Metrics: MAE (share), balanced accuracy (sand-dominant).
B6 output: 10 m sand-share map over the main AOI with uncertainty (RF tree std), `derived, model estimate`; never a
   prior, never in the rover rules, never used to recompute route A.
Readings (tech-lead, written before the run; see DATA_LOG): kNN on standardised features (scaler fitted on the
training fold); sol segments = waypoints sorted by sol cut into 5 equal-count groups; buffer = training
waypoints within 100 m of any test waypoint dropped; balanced accuracy on the pooled out-of-fold predictions;
waypoints outside SIM 3464 get the unit "none"; CTX ortho shifted with each window's X3 shift (as the prior DTM).
"""
from __future__ import annotations

import csv
import math
import time

import numpy as np
from PIL import Image
from rasterio.warp import Resampling
from scipy.ndimage import uniform_filter

from .common import APP, Scene, read_json, write_json

RADIUS = 30.0
RES = 2.0
OUT = APP / "data_work/jezero/ai4mars"
AI = APP / "data_raw/jezero/ai4mars"


def window_grids(i, j):
    """2 m feature grids of window (i, j) in its own local frame (habitat at 0, 0; AOI x -1700..700, y -1000..1400)."""
    from . import terrain as TR
    from .multiwindow_ab import shifted_scene, window_inputs
    from .multiwindow_x3 import to_local_win
    from .sandfield import features as sand_features, to_grid
    sc, ws = shifted_scene(i, j)
    inp = window_inputs(i, j)
    aoi = sc.extent("aoi")
    if (i, j) == (0, 0):
        F = dict(np.load(APP / "data_work/jezero/sand_v2_features.npz"))
        T = dict(np.load(APP / "data_work/jezero/terrain_2m.npz"))
        o = np.load(APP / "data_work/jezero/ortho_05.npy").astype("float32")
    else:
        T = dict(np.load(APP / f"data_work/jezero/windows/{i}_{j}/terrain_2m.npz"))
        o = to_local_win(inp["ortho"], ws, aoi, 0.25, Resampling.bilinear); o[o == 0] = np.nan
        o = TR.block(o, 2, "mean")
        F = to_grid(sand_features(o), 4)
    lm = uniform_filter(np.nan_to_num(o), 50) / np.maximum(uniform_filter(np.isfinite(o).astype("float32"), 50), 1e-6)
    ratio = o / np.where(lm > 0, lm, np.nan)
    r1 = TR.block(ratio, 4, "mean"); r2 = TR.block(ratio * ratio, 4, "mean")
    ctx = to_local_win(APP / "data_raw/jezero/prior_ortho.tif", ws, aoi, RES, Resampling.bilinear, shift_xy=inp["shift"])
    return {"fine_coh": F["fine_coh"], "fine_en": F["fine_en"], "coarse_coh": F["coarse_coh"], "coarse_en": F["coarse_en"],
            "slope_ref": T["slope_ref"], "rough_ref": T["rough_ref"], "bright_m1": r1, "bright_m2": r2,
            "ctx": ctx, "ctx2": ctx * ctx, "slope_prior": T["slope_prior"], "class_ref": T["class_ref"], "ext": aoi}


def circle_feats(G, x, y):
    ext = G["ext"]; H, W = G["slope_ref"].shape
    r = int(math.ceil(RADIUS / RES)) + 1
    c0 = int((x - ext[0]) / RES); r0 = int((ext[3] - y) / RES)
    rr, cc = np.mgrid[max(r0 - r, 0):min(r0 + r + 1, H), max(c0 - r, 0):min(c0 + r + 1, W)]
    m = np.hypot(ext[0] + (cc + .5) * RES - x, ext[3] - (rr + .5) * RES - y) <= RADIUS
    rr, cc = rr[m], cc[m]
    mean = lambda k: float(np.nanmean(G[k][rr, cc]))
    b1, b2 = mean("bright_m1"), mean("bright_m2"); c1, c2 = mean("ctx"), mean("ctx2")
    return {"hirise": [mean("fine_coh"), mean("fine_en"), mean("coarse_coh"), mean("coarse_en"), mean("slope_ref"),
                       mean("rough_ref"), b1, math.sqrt(max(b2 - b1 * b1, 0.0))],
            "ctx": [c1, math.sqrt(max(c2 - c1 * c1, 0.0)), mean("slope_prior")],
            "rule_sand": float(np.mean(G["class_ref"][rr, cc] == 2))}


def answers():
    """Per waypoint: mean sand / bedrock share over its NLF (sol >= 13) labelled images."""
    per = {}
    for r in csv.DictReader(open(AI / "index.csv")):
        if r["naming"] != "NLF" or r["has_label"] != "yes" or not r["waypoint_id"]:
            continue
        f = AI / "ai4mars-dataset-merged-0.6/m2020/labels/NAV" / r["label_file"].split("/")[-1]
        if not f.exists():
            continue
        lab = np.asarray(Image.open(f)); lab = lab[..., 0] if lab.ndim == 3 else lab
        n = int((lab != 255).sum())
        if n == 0:
            continue
        per.setdefault(r["waypoint_id"], []).append(((lab == 2).sum() / n, (lab == 1).sum() / n, int(r["sol"])))
    return {w: {"sand": float(np.mean([v[0] for v in L])), "bedrock": float(np.mean([v[1] for v in L])), "n_images": len(L),
                "sol": min(v[2] for v in L)} for w, L in per.items()}


def models():
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return {"knn": (lambda: make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=5)),
                    lambda: make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5))),
            "rf": (lambda: RandomForestRegressor(n_estimators=200, random_state=20261114),
                   lambda: RandomForestClassifier(n_estimators=200, random_state=20261114))}


def evaluate(rows, folds, buffer_m):
    """Out-of-fold predictions for every model x input version and the three baselines."""
    from sklearn.metrics import balanced_accuracy_score
    units = sorted({r["unit"] for r in rows})
    oh = lambda r: [1.0 if r["unit"] == u else 0.0 for u in units]
    X = {"hirise": np.array([r["hirise"] + oh(r) for r in rows]), "ctx": np.array([r["ctx"] + oh(r) for r in rows])}
    y = np.array([r["sand"] for r in rows]); yb = (y >= 0.5).astype(int)
    xy = np.array([[r["gx"], r["gy"]] for r in rows])
    fold = np.array([r["fold"] for r in rows])
    pred = {}
    fold_info = []
    M = models()
    for f in sorted(set(fold)):
        te = fold == f
        d = np.min(np.hypot(xy[:, None, 0] - xy[None, te, 0], xy[:, None, 1] - xy[None, te, 1]), axis=1) if buffer_m else np.full(len(rows), np.inf)
        tr = (~te) & (d > buffer_m)
        fold_info.append({"fold": str(f), "n_test": int(te.sum()), "n_train_after_buffer": int(tr.sum()),
                          "n_train_sand_dominant": int(yb[tr].sum()), "n_test_sand_dominant": int(yb[te].sum())})
        for v, Xv in X.items():
            for mn, (mr, mc) in M.items():
                m = mr().fit(Xv[tr], y[tr]); pred.setdefault(f"{mn}_{v}", np.zeros(len(rows)))[te] = m.predict(Xv[te])
                if len(set(yb[tr])) > 1:
                    c = mc().fit(Xv[tr], yb[tr]); pred.setdefault(f"{mn}_{v}_cls", np.zeros(len(rows)))[te] = c.predict(Xv[te])
                else:
                    pred.setdefault(f"{mn}_{v}_cls", np.zeros(len(rows)))[te] = yb[tr][0]
        pred.setdefault("base_hirise_rule", np.zeros(len(rows)))[te] = [r["rule_sand"] for r, t in zip(rows, te) if t]
        um = {u: float(np.mean(y[tr][[rows[k]["unit"] == u for k in np.nonzero(tr)[0]]])) if any(rows[k]["unit"] == u for k in np.nonzero(tr)[0]) else float(np.mean(y[tr])) for u in units}
        pred.setdefault("base_unit_majority", np.zeros(len(rows)))[te] = [um[r["unit"]] for r, t in zip(rows, te) if t]
        nn = [int(np.argmin(np.where(tr, np.hypot(xy[:, 0] - xy[k, 0], xy[:, 1] - xy[k, 1]), np.inf))) for k in np.nonzero(te)[0]]
        pred.setdefault("base_nearest", np.zeros(len(rows)))[te] = y[nn]
    out = {}
    for k, p in pred.items():
        if k.endswith("_cls"):
            continue
        cls = pred.get(k + "_cls", (p >= 0.5).astype(int))
        out[k] = {"mae": float(np.mean(np.abs(p - y))), "balanced_accuracy": float(balanced_accuracy_score(yb, cls)) if len(set(yb)) > 1 else None}
    return out, {"n": len(rows), "n_sand_dominant": int(yb.sum()), "units": units, "folds": fold_info}


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "x2_result.json"
    if f.exists():
        raise SystemExit("X2 already run once")
    t0 = time.time()
    from .step2_chem import unit_lookup
    unit_at = unit_lookup()
    A = answers()
    W = {w["id"]: w for w in read_json(APP / "data_work/jezero/waypoints_all.json")}
    wins = [(0, 0), (-1, 0), (-1, 1), (-2, 1), (-3, 1), (-4, 0)]
    rows = []
    for (i, j) in wins:
        G = window_grids(i, j)
        e = G["ext"]
        for wid, a in A.items():
            w = W.get(wid)
            if w is None:
                continue
            x, y = w["x"] - 2400 * i, w["y"] - 2400 * j
            if not (e[0] + RADIUS <= x <= e[2] - RADIUS and e[1] + RADIUS <= y <= e[3] - RADIUS):
                continue
            cf = circle_feats(G, x, y)
            if not all(np.isfinite(cf["hirise"] + cf["ctx"])):
                continue
            u = unit_at(w["x"], w["y"])
            rows.append({"wp": wid, "window": f"{i},{j}", "gx": w["x"], "gy": w["y"], "sol": a["sol"], "sand": a["sand"],
                         "bedrock": a["bedrock"], "n_images": a["n_images"], "unit": u["symbol"] if u else "none", **cf})
        del G
    main = sorted([r for r in rows if r["window"] == "0,0"], key=lambda r: r["sol"])
    for k, r in enumerate(main):
        r["fold"] = min(4, k * 5 // len(main))
    res_main, info_main = evaluate(main, None, 100.0) if len(main) >= 10 else ({}, {"n": len(main)})
    for r in rows:
        r["fold"] = r["window"]
    nwin = len({r["window"] for r in rows})
    if nwin >= 2 and len(rows) >= 10:
        res_all, info_all = evaluate(rows, None, 0.0)
    else:   # AI4MARS NAV labels exist only for sols 9-288, i.e. inside the main window: leave-one-window-out impossible
        res_all, info_all = {}, {"n": len(rows), "windows_with_labels": sorted({r["window"] for r in rows}),
                                 "not_computed": "labelled waypoints in fewer than 2 of the six windows"}
    out = {"label": "derived, model estimate; answers = AI4MARS crowd labels (measured); agreement with crowd labels, not expert accuracy",
           "rules": __doc__.split("Rules", 1)[1], "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
           "main_aoi": {"info": info_main, "results": res_main}, "waypoints_inside_the_six_windows": {"info": info_all, "results": res_all},
           "rows": rows}
    out["seconds"] = round(time.time() - t0, 1)
    write_json(f, out)
    return out


if __name__ == "__main__":
    run()
