"""X1 (a): AI4MARS Perseverance Navcam crowd labels vs our HiRISE terrain classes (independent check). Run ONCE.

python -m pipeline.ai4mars_check   -> data_work/jezero/ai4mars/x1_result.json, qa/jezero/ai4mars/*.png

Rules (manager 2026-11-14, TECH_LEAD_BRIEF 第十一次更新 A1-A5, A7-A8, and 第十三次更新 3; fixed before any number):
A1 data: AI4MARS merged 0.6, m2020 NAV merged labels (0 soil, 1 bedrock, 2 sand, 3 big rock, 255 unlabelled),
   NLF-named images whose site/drive (from the file name) equals a main-AOI waypoint: all 2,215 (incl. sol 9-12 at
   the landing site; manager 14th update). Vgnc
   (SCLK-only) labels are not used. Labels: `measured (crowd labels)`.
A2 placement: each image -> its waypoint (exact site/drive). Viewing direction: Navcam camera model rotated by the
   rover attitude (photo_heading.heading, Raw Images JSON cached in data_raw/jezero/raw_api); field-of-view sector =
   apex at the waypoint, from edge_left to edge_right (clockwise), radius 30 m (assumed: NAV labels stop at ~30 m).
   Images without a computable direction use a 30 m circle around the waypoint and are reported separately.
A3 photo side: per image sand pixels / labelled pixels, bedrock likewise; per waypoint the mean over its images
   (image count reported).
A4 HiRISE side: share of 2 m reference cells in the image's sector (or circle) whose class is sand; firm and rough
   = non-sand (blocked counted as non-sand too and listed). Per waypoint the mean over the same images. The prior
   (CTX classes) has no sand class, so its share is 0 everywhere (reported as is).
A5 comparison (no pass threshold): waypoint-level Spearman rho (photo sand vs HiRISE sand; photo bedrock vs HiRISE
   non-sand); 2x2 with "sand-dominant" = share >= 0.5 on each side: n, agreement, both error counts; fewer than 5
   sand-dominant waypoints -> say the check has little power for sand. Per-waypoint table and 8 comparison panels.
A8 nothing here changes the sand classes, any frozen number or the rover rules; no "ground truth" wording.
"""
from __future__ import annotations

import glob
import json
import math
import re
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.stats import spearmanr

from .common import APP, read_json, write_json
from .photo_heading import heading

AI = APP / "data_raw/jezero/ai4mars/ai4mars-dataset-merged-0.6/m2020"
OUT = APP / "data_work/jezero/ai4mars"
QA = APP / "qa/jezero/ai4mars"
RADIUS_M = 30.0
SAND, BEDROCK, UNL = 2, 1, 255


def label_index():
    """NLF labels with sol >= 13 from data-curator's index.csv (data_raw/jezero/ai4mars/index.csv); label files are
    resolved by name in m2020/labels/NAV/. Vgnc ('unmatched') rows are not used (A1)."""
    import csv
    out = []
    for r in csv.DictReader(open(AI.parents[1] / "index.csv")):
        if r["naming"] != "NLF" or r["has_label"] != "yes":         # manager 14th update: all NLF labels (2,215 in the AOI)
            continue
        f = AI / "labels/NAV" / Path(r["label_file"]).name
        if not f.exists():
            continue
        out.append({"stem": r["image_name"], "label": str(f), "sol": int(r["sol"]), "site": int(r["site"]), "drive": int(r["drive"]),
                    "same_name_in_photos_json": r["same_name_in_photos_json"] == "yes"})
    return out


def raw_meta():
    meta = {}
    for f in glob.glob(str(APP / "data_raw/jezero/raw_api/*.json")):
        for im in json.load(open(f)):
            meta[im["imageid"]] = im
    return meta


def sector_mask(shape, ext, res, x0, y0, left, right, radius=RADIUS_M):
    """Cells (2 m grid) whose centre is within radius of (x0, y0) and whose bearing lies clockwise from left to right."""
    H, W = shape
    r = int(math.ceil(radius / res)) + 1
    c0 = int((x0 - ext[0]) / res); r0 = int((ext[3] - y0) / res)
    rr, cc = np.mgrid[max(r0 - r, 0):min(r0 + r + 1, H), max(c0 - r, 0):min(c0 + r + 1, W)]
    X = ext[0] + (cc + .5) * res - x0; Y = ext[3] - (rr + .5) * res - y0
    d = np.hypot(X, Y)
    m = d <= radius
    if left is not None:
        b = (np.degrees(np.arctan2(X, Y)) + 360) % 360
        span = (right - left) % 360
        m &= ((b - left) % 360) <= span
    return rr[m], cc[m]


def run():
    OUT.mkdir(parents=True, exist_ok=True); QA.mkdir(parents=True, exist_ok=True)
    f = OUT / "x1_result.json"
    if f.exists():
        raise SystemExit("X1 already run once")
    t0 = time.time()
    W = read_json(APP / "data_work/jezero/waypoints_all.json")
    wp = {(w["site"], w["drive"]): w for w in W if w.get("in_aoi")}
    T = dict(np.load(APP / "data_work/jezero/terrain_2m.npz"))
    ext = read_json(APP / "data_work/jezero/terrain_2m.json")["extent_local_m"]; res = 2.0
    ref, prior = T["class_ref"], T["class_prior"]
    meta = raw_meta()
    labs = label_index()
    imgs, n_not_aoi, n_empty = [], 0, 0
    for L in labs:
        w = wp.get((L["site"], L["drive"]))
        if w is None:
            n_not_aoi += 1; continue
        lab = np.asarray(Image.open(L["label"]))
        if lab.ndim == 3:
            lab = lab[..., 0]
        n = int((lab != UNL).sum())
        if n == 0:
            n_empty += 1; continue
        m = meta.get(L["stem"])
        view = None
        if m and m.get("attitude") and "camera_model_component_list" in m.get("camera", {}):
            try:
                view = heading(m)
            except Exception:  # noqa: BLE001
                view = None
        rr, cc = sector_mask(ref.shape, ext, res, w["x"], w["y"], view["edge_left_deg"] if view else None, view["edge_right_deg"] if view else None)
        rc = ref[rr, cc]; pc = prior[rr, cc]
        imgs.append({"stem": L["stem"], "wp": w["id"], "same_name_in_photos_json": L["same_name_in_photos_json"], "sol": L["sol"], "x": w["x"], "y": w["y"],
                     "photo_sand": float((lab == SAND).sum() / n), "photo_bedrock": float((lab == BEDROCK).sum() / n),
                     "photo_soil": float((lab == 0).sum() / n), "photo_bigrock": float((lab == 3).sum() / n), "labelled_px": n,
                     "geometry": "sector" if view else "circle", "view": view, "n_cells": int(len(rc)),
                     "hirise_sand": float(np.mean(rc == SAND)) if len(rc) else None,
                     "hirise_blocked": float(np.mean(rc == 3)) if len(rc) else None,
                     "prior_sand": float(np.mean(pc == SAND)) if len(pc) else None})
    out = {"label": "AI4MARS: measured (crowd labels); HiRISE classes: derived (heuristic, not yet reviewed); "
                    "agreement with crowd labels, not ground truth", "rules": __doc__.split("Rules", 1)[1],
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "n_labels_nlf": len(labs), "n_not_in_aoi": n_not_aoi,
           "n_no_labelled_pixel": n_empty, "n_images": len(imgs), "groups": {}}
    for geo in ("sector", "circle"):
        G = [i for i in imgs if i["geometry"] == geo and i["hirise_sand"] is not None]
        byw = {}
        for i in G:
            byw.setdefault(i["wp"], []).append(i)
        rows = []
        for w_, L_ in sorted(byw.items()):
            rows.append({"wp": w_, "n_images": len(L_), "x": L_[0]["x"], "y": L_[0]["y"],
                         **{q: float(np.mean([i[q] for i in L_])) for q in ("photo_sand", "photo_bedrock", "hirise_sand", "hirise_blocked", "prior_sand")}})
        g = {"n_images": len(G), "n_waypoints": len(rows), "rows": rows}
        if len(rows) >= 3:
            ps = np.array([r["photo_sand"] for r in rows]); hs = np.array([r["hirise_sand"] for r in rows])
            pb = np.array([r["photo_bedrock"] for r in rows])
            g["spearman_sand"] = {"rho": float(spearmanr(ps, hs).statistic), "n": len(rows)}
            g["spearman_bedrock_vs_hirise_nonsand"] = {"rho": float(spearmanr(pb, 1 - hs).statistic), "n": len(rows)}
            a, b = ps >= 0.5, hs >= 0.5
            g["two_by_two"] = {"both_sand": int((a & b).sum()), "photo_sand_only": int((a & ~b).sum()),
                               "hirise_sand_only": int((~a & b).sum()), "neither": int((~a & ~b).sum()),
                               "agreement": float(np.mean(a == b)), "n": len(rows)}
            g["sand_dominant_waypoints"] = {"photo": int(a.sum()), "hirise": int(b.sum())}
            g["power_note"] = ("fewer than 5 sand-dominant waypoints: little power for sand" if min(a.sum(), b.sum()) < 5 else "")
        out["groups"][geo] = g
    out["images"] = imgs
    out["seconds"] = round(time.time() - t0, 1)
    write_json(f, out)
    figures(out, ref, ext, res)
    return out


def figures(out, ref, ext, res):
    """8 comparison panels (waypoints spread over the photo-sand range, sector group): photo + HiRISE sector."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    G = [i for i in out["images"] if i["geometry"] == "sector"]
    if not G:
        return
    G = sorted(G, key=lambda i: i["photo_sand"])
    pick = [G[int(round(j * (len(G) - 1) / 7))] for j in range(8)] if len(G) >= 8 else G
    fig, ax = plt.subplots(4, 4, figsize=(16, 16))
    img_dir = AI / "images/ncam"
    pal = np.array([[98, 214, 164], [244, 183, 64], [255, 90, 78], [138, 63, 174]], np.uint8)
    for j, i in enumerate(pick):
        a1, a2 = ax.ravel()[2 * j], ax.ravel()[2 * j + 1]
        cand = sorted(glob.glob(str(img_dir / (i["stem"] + ".*"))))
        if cand:
            a1.imshow(Image.open(cand[-1]), cmap="gray")
        a1.set_title(f"{i['stem'][:22]}… photo sand {i['photo_sand']:.2f}", fontsize=8); a1.axis("off")
        rr, cc = sector_mask(ref.shape, ext, res, i["x"], i["y"], i["view"]["edge_left_deg"], i["view"]["edge_right_deg"])
        r = int(RADIUS_M / res) + 2; c0 = int((i["x"] - ext[0]) / res); r0 = int((ext[3] - i["y"]) / res)
        win = pal[ref[r0 - r:r0 + r + 1, c0 - r:c0 + r + 1]].astype(float) * 0.35
        win[rr - (r0 - r), cc - (c0 - r)] = pal[ref[rr, cc]]
        a2.imshow(win.astype(np.uint8)); a2.set_title(f"HiRISE classes in the 30 m view sector: sand {i['hirise_sand']:.2f}", fontsize=8); a2.axis("off")
    fig.suptitle("X1: AI4MARS crowd labels (Perseverance Navcam) vs HiRISE reference classes (green firm, yellow rough, red sand, purple blocked); "
                 "agreement with crowd labels, not ground truth", fontsize=10)
    fig.tight_layout(); fig.savefig(QA / "X1_panels.png", dpi=80); plt.close(fig)


if __name__ == "__main__":
    run()
