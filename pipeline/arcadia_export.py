# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia web export: web/data/arcadia/{arcadia.json, hirise.jpg, classes.png, brain_all.png, brain_seen.png, seen_loop.png}.
python -m pipeline.arcadia export"""
from __future__ import annotations

import numpy as np
import rasterio
from matplotlib import colormaps
from PIL import Image

from .common import Scene, log, read_json, write_json
from .rover_sim import simplify
from .terrain import block

SCENE = "arcadia"
CLASS_RGBA = [(98, 214, 164, 150), (244, 183, 64, 150), (255, 90, 78, 165), (90, 42, 110, 220)]
CLASS_ZH = ["硬地", "崎嶇", "沙地", "不可通行"]


def rc_to_lonlat(sc, rcs, res):
    aoi = sc.extent("aoi")
    rcs = np.asarray(rcs, float)
    x = aoi[0] + (rcs[:, 1] + 0.5) * res; y = aoi[3] - (rcs[:, 0] + 0.5) * res
    lon, lat = sc.grid.xy_to_lonlat(x, y)
    return np.c_[x, y], np.c_[lon, lat]


def line(sc, rcs, res, tol=1.5):
    xy, ll = rc_to_lonlat(sc, rcs, res)
    k = simplify(xy, tol) if len(xy) > 2 else np.arange(len(xy))
    return [[round(float(a), 7), round(float(b), 7)] for a, b in ll[k]]


def pt(sc, x, y):
    lon, lat = sc.grid.xy_to_lonlat(x, y)
    return [round(float(lon), 7), round(float(lat), 7)]


def heat_rgba(score, alpha):
    cm = colormaps["magma"]
    s = np.clip(np.nan_to_num(score, nan=0.0), 0, 1)
    rgba = (cm(s) * 255).astype(np.uint8)
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    rgba[~np.isfinite(score), 3] = 0
    return rgba


def run():
    sc = Scene(SCENE)
    w, out = sc.work, sc.web
    aoi = sc.extent("aoi")
    T = dict(np.load(w / "terrain_2m.npz"))
    score = np.load(w / "brain_score_2m.npy")
    rs = np.load(w / "recon_state.npz")
    rl = read_json(w / "recon_loops.json"); tg = read_json(w / "targets.json"); ast = read_json(w / "astro.json")
    tm = read_json(w / "terrain_2m.json")

    # ---- images ---------------------------------------------------------------------------------------------
    with rasterio.open(w / "ortho_025.tif") as s:
        o = s.read(1, out_shape=(4800, 4800), resampling=rasterio.enums.Resampling.average)
    lo, hi = np.nanpercentile(o, [0.5, 99.5])
    g = (np.clip((np.nan_to_num(o, nan=lo) - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(g).save(out / "hirise.jpg", quality=82)
    c = T["class_ref"]
    rgba = np.array(CLASS_RGBA, np.uint8)[c]
    Image.fromarray(rgba).save(out / "classes.png", optimize=True)
    Image.fromarray(heat_rgba(score, np.full(score.shape, 0.78))).save(out / "brain_all.png", optimize=True)
    seen = rs["seen_2m"]
    Image.fromarray(heat_rgba(score, np.where(seen, 0.85, 0.0))).save(out / "brain_seen.png", optimize=True)
    # loop in which each 4 m cell was first seen (R channel, 0 = never)
    t1 = np.array([L["t1"] for L in rl["loops"]])
    ft = rs["first_t"]
    li = np.where(ft >= 0, np.searchsorted(t1, ft) + 1, 0).astype(np.uint8)
    li = np.minimum(li, len(t1))
    img = np.zeros(li.shape + (4,), np.uint8); img[..., 0] = li; img[..., 3] = 255
    Image.fromarray(img).save(out / "seen_loop.png")

    # ---- vectors --------------------------------------------------------------------------------------------
    rres = rl["params"]["grid_res_m"]
    loops = []
    for L in rl["loops"]:
        loops.append({"id": L["id"], "length_m": L["length_m"], "seen_frac": L["observed_frac_aoi"],
                      "path": line(sc, L["path_rc"], rres)})

    def targets(lst):
        r = []
        for k, p in enumerate(lst):
            x0, y0, x1, y1 = p["block_xy"]
            r.append({"id": f"T{k + 1}", "score": p["mean_score"], "stop": pt(sc, *p["stop_xy"]),
                      "block": [pt(sc, x0, y1), pt(sc, x1, y1), pt(sc, x1, y0), pt(sc, x0, y0), pt(sc, x0, y1)]})
        return r

    def route(r):
        legs = []
        cum = {"distance_m": 0.0, "min": 0.0, "kcal": 0.0}
        for L in r["legs"]:
            d = L["distance_m"]; m = L["walk_min"] + L["dwell_min"]; k = L["walk_kcal"] + L["dwell_kcal"]
            cum = {"distance_m": cum["distance_m"] + d, "min": cum["min"] + m, "kcal": cum["kcal"] + k}
            legs.append({"from": L["from"], "to": L["to"], "distance_m": d, "walk_min": L["walk_min"],
                         "dwell_min": L["dwell_min"], "min": round(m, 1), "kcal": round(k, 1),
                         "o2_l": round(k / 5.0, 1), "cum": {kk: round(v, 1) for kk, v in cum.items()},
                         "path": line(sc, r["path_rc"][L["i0"]:L["i1"] + 1], 2.0)})
        return {"order": [f"T{i}" for i in r["order"]], "n_stops": r["n_stops"], "legs": legs,
                "total": {"distance_m": r["total_distance_m"], "min": r["total_min"], "kcal": r["total_kcal"],
                          "o2_l": r["o2_l"]}, "usable_kcal": r["usable_kcal"]}

    h = sc.cfg["habitat"]
    doc = {
        "scene": SCENE, "title": "Arcadia Planitia · Starship 候選降落點",
        "aoi_corners": sc.grid.corners_lonlat(*aoi),
        "centre": pt(sc, 0.0, 0.0), "base": pt(sc, h["x"], h["y"]),
        "files": {"hirise": "hirise.jpg", "classes": "classes.png", "brain_all": "brain_all.png",
                  "brain_seen": "brain_seen.png", "seen_loop": "seen_loop.png"},
        "classes": [{"zh": z, "color": "#%02x%02x%02x" % tuple(c_[:3])} for z, c_ in zip(CLASS_ZH, CLASS_RGBA)],
        "rover": {"res_m": rres, "loops": loops, "seen_frac": rl["observed_frac"]},
        "targets": {"after": targets(tg["after_recon"]), "before": targets(tg["before_recon"])},
        "route": route(ast["after_recon"]),
        "stats": {"brain_frac": tm["brain_frac"], "class_percent": tm["area_percent_ref"]},
        "credits": "NASA/JPL-Caltech/UArizona HiRISE; USGS DTM; Pearson et al. 2024 model; Pandolf 1977 energy model",
    }
    write_json(out / "arcadia.json", doc)
    log(SCENE, "export", f"wrote {out}")
