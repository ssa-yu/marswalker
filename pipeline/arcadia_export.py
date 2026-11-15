# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia web export (study area v2, 3.72 x 11.04 km): web/data/arcadia/
  arcadia.json            vectors, targets, route, parameters for the in-browser planner
  tiles/{z}/{x}/{y}.webp  HiRISE 0.5 m ortho as an XYZ pyramid, z12 (~16 m) .. z16 (~1 m), transparent outside the area
  classes.png, brain_all.png (palette PNG, 4 m), seen_loop.png (R = first loop that saw the 4 m cell)
  cost8.bin.gz            8 m per-metre kcal and minutes (uint16, x 20000; 65535 = blocked), Shooyunn's Pandolf model
python -m pipeline.arcadia export"""
from __future__ import annotations

import gzip
import math
import shutil

import numpy as np
import rasterio
from matplotlib import colormaps
from PIL import Image
from scipy.ndimage import map_coordinates

from .common import Scene, log, read_json, write_json
from .rover_sim import simplify
from .terrain import block

SCENE = "arcadia"
CLASS_RGBA = [(98, 214, 164, 150), (244, 183, 64, 150), (255, 90, 78, 165), (90, 42, 110, 220)]
CLASS_ZH = ["硬地", "崎嶇", "沙地", "不可通行"]
TILE_Z = (12, 16)
COST_SCALE = 20000.0


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


def palette_png(idx, colors, path):
    """idx: uint8 index image; colors: list of RGBA (index i -> colors[i])."""
    im = Image.fromarray(idx.astype(np.uint8), "P")
    pal = [v for c in colors for v in c[:3]]
    im.putpalette(pal + [0] * (768 - len(pal)))
    im.info["transparency"] = bytes(c[3] for c in colors)
    im.save(path, optimize=True, transparency=bytes(c[3] for c in colors))


def heat_png(score, path):
    """Index 0 = no score (transparent), 1..255 = magma(0..1); alpha 0.78 like before."""
    cm = colormaps["magma"]
    cols = [(0, 0, 0, 0)] + [tuple(int(v * 255) for v in cm(i / 254)[:3]) + (199,) for i in range(255)]
    idx = np.where(np.isfinite(score), 1 + np.round(np.clip(np.nan_to_num(score), 0, 1) * 254), 0)
    palette_png(idx, cols, path)
    # same indices as an 8-bit grey image: the page reads the score from it (in-browser area selection, "scout it yourself")
    Image.fromarray(idx.astype(np.uint8), "L").save(path.with_name("brain_score.png"), optimize=True)


def tiles(sc, out):
    """XYZ (web-mercator scheme on Mars lon/lat, as MapLibre draws them) pyramid of the 0.5 m ortho."""
    aoi = sc.extent("aoi")
    with rasterio.open(sc.work / "ortho_05.tif") as s:
        o = s.read(1).astype(np.float32)
    lo, hi = np.nanpercentile(o[::7, ::7], [0.5, 99.5])
    base = block(o, 2, "mean")                       # 1 m
    del o
    levels = {16: base}
    for z in range(15, TILE_Z[0] - 1, -1):
        levels[z] = block(levels[z + 1], 2, "mean")
    ll = sc.grid.corners_lonlat(*aoi)
    W_, E_ = ll[0][0], ll[1][0]; N_, S_ = ll[0][1], ll[2][1]
    tdir = out / "tiles"
    if tdir.exists():
        shutil.rmtree(tdir)
    n_t, nbytes = 0, 0
    for z in range(TILE_Z[0], TILE_Z[1] + 1):
        img = levels[z]; res = 2.0 ** (16 - z)
        n = 2 ** z
        tx = lambda lon: int(math.floor((lon + 180) / 360 * n))
        ty = lambda lat: int(math.floor((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n))
        for x in range(tx(W_), tx(E_) + 1):
            for y in range(ty(N_), ty(S_) + 1):
                u = (x + (np.arange(256) + 0.5) / 256) / n * 360 - 180
                v = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + (np.arange(256) + 0.5) / 256) / n))))
                LON, LAT = np.meshgrid(u, v)
                X, Y = sc.grid.lonlat_to_xy(LON, LAT)
                r = (aoi[3] - Y) / res - 0.5; c = (X - aoi[0]) / res - 0.5
                inside = (X >= aoi[0]) & (X <= aoi[2]) & (Y >= aoi[1]) & (Y <= aoi[3])
                if not inside.any():
                    continue
                val = map_coordinates(img, [r, c], order=1, mode="nearest", cval=np.nan)
                ok = inside & np.isfinite(val)
                g = (np.clip((np.nan_to_num(val, nan=lo) - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
                rgba = np.dstack([g, g, g, np.where(ok, 255, 0).astype(np.uint8)])
                p = tdir / str(z) / str(x); p.mkdir(parents=True, exist_ok=True)
                f = p / f"{y}.webp"
                Image.fromarray(rgba, "RGBA").save(f, quality=70, method=4)
                n_t += 1; nbytes += f.stat().st_size
    log(SCENE, "export", f"tiles z{TILE_Z[0]}-{TILE_Z[1]}: {n_t} files {nbytes / 1e6:.1f} MB")
    return {"url": "tiles/{z}/{x}/{y}.webp", "minzoom": TILE_Z[0], "maxzoom": TILE_Z[1], "stretch": [float(lo), float(hi)],
            "bounds": [W_, S_, E_, N_], "n": n_t, "mb": round(nbytes / 1e6, 2)}


def run(do_tiles=True):
    sc = Scene(SCENE)
    w, out = sc.work, sc.web
    aoi = sc.extent("aoi")
    T = dict(np.load(w / "terrain_4m.npz"))
    from .arcadia import GRID_RES, brain_score_grid, EVA
    score = brain_score_grid()
    rs = np.load(w / "recon_state.npz")
    rl = read_json(w / "recon_loops.json"); tg = read_json(w / "targets.json"); ast = read_json(w / "astro.json")
    tm = read_json(w / "terrain_2m.json")
    A = ast["after_recon"]

    # ---- images ---------------------------------------------------------------------------------------------
    tl = tiles(sc, out) if do_tiles else read_json(out / "arcadia.json")["tiles"]
    (out / "hirise.jpg").unlink(missing_ok=True)   # 0.25 m base image dropped: its stretch left a seam against the tiles
    palette_png(T["class_ref"], CLASS_RGBA, out / "classes.png")
    heat_png(score, out / "brain_all.png")
    for f in ("brain_seen.png",):
        (out / f).unlink(missing_ok=True)
    t1 = np.array([L["t1"] for L in rl["loops"]])
    ft = rs["first_t"]
    li = np.where(ft >= 0, np.searchsorted(t1, ft) + 1, 0).astype(np.uint8)
    li = np.minimum(li, len(t1))
    img = np.zeros(li.shape + (4,), np.uint8); img[..., 0] = li; img[..., 3] = 255
    Image.fromarray(img).save(out / "seen_loop.png", optimize=True)
    # ---- 8 m cost grid for the in-browser planner -----------------------------------------------------------
    C = np.load(w / "cost_8m.npz")
    enc = lambda g: np.where(np.isfinite(g), np.clip(np.round(g * COST_SCALE), 0, 65534), 65535).astype("<u2")
    raw = enc(C["kcal_m"]).tobytes() + enc(C["min_m"]).tobytes()
    (out / "cost8.bin.gz").write_bytes(gzip.compress(raw, 9))

    # ---- vectors --------------------------------------------------------------------------------------------
    rres = rl["params"]["grid_res_m"]
    loops = [{"id": L["id"], "length_m": L["length_m"], "seen_frac": L["observed_frac_aoi"],
              "path": line(sc, L["path_rc"], rres, tol=3.0)} for L in rl["loops"]]

    def targets(lst, rt=None):
        r = []
        for k, p in enumerate(lst):
            x0, y0, x1, y1 = p["block_xy"]
            d = {"id": f"T{k + 1}", "score": p["mean_score"], "stop": pt(sc, *p["stop_xy"]), "xy": p["stop_xy"],
                 "block": [pt(sc, x0, y1), pt(sc, x1, y1), pt(sc, x1, y0), pt(sc, x0, y0), pt(sc, x0, y1)]}
            if rt is not None:
                d["rt_kcal"] = rt[k]
            r.append(d)
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
                         "path": line(sc, r["path_rc"][L["i0"]:L["i1"] + 1], GRID_RES, tol=2.0)})
        return {"order": [f"T{i}" for i in r["order"]], "n_stops": r["n_stops"], "legs": legs,
                "total": {"distance_m": r["total_distance_m"], "min": r["total_min"], "kcal": r["total_kcal"],
                          "o2_l": r["o2_l"]}, "usable_kcal": r["usable_kcal"]}

    h = sc.cfg["habitat"]
    H8, W8 = C["kcal_m"].shape
    doc = {
        "scene": SCENE, "title": "Arcadia Planitia · Starship 候選降落點",
        "aoi_corners": sc.grid.corners_lonlat(*aoi), "aoi_local_m": list(aoi),
        "centre": pt(sc, (aoi[0] + aoi[2]) / 2, (aoi[1] + aoi[3]) / 2), "base": pt(sc, h["x"], h["y"]),
        "base_xy": [h["x"], h["y"]],
        "geo": {"lon0": sc.grid.lon0, "lat0": sc.grid.lat0, "R": 3396190.0},
        "files": {"classes": "classes.png", "brain_all": "brain_all.png", "brain_score": "brain_score.png",
                  "seen_loop": "seen_loop.png", "cost": "cost8.bin.gz"},
        "tiles": tl,
        "classes": [{"zh": z, "color": "#%02x%02x%02x" % tuple(c_[:3])} for z, c_ in zip(CLASS_ZH, CLASS_RGBA)],
        "rover": {"res_m": rres, "loops": loops, "seen_frac": rl["observed_frac"]},
        "targets": {"after": targets(tg["after_recon"], A["round_trip_kcal"])},
        "route": route(A),
        "planner": {"res_m": 8.0, "shape": [H8, W8], "scale": COST_SCALE, "blocked": 65535,
                    "window_m": A["window_m"], "usable_kcal": A["usable_kcal"], "budget_kcal": EVA["budget_kcal"],
                    "reserve_frac": EVA["reserve_frac"], "dwell_min": EVA["dwell_min"],
                    "stand_kcal_per_min": A["standing_kcal_per_min"], "kcal_per_l_o2": EVA["kcal_per_l_o2"],
                    "brute_max": 6, "visited": A["order"]},
        "stats": {"brain_frac": tm["brain_frac"], "class_percent": tm["area_percent_ref_4m"]},
        "credits": "NASA/JPL-Caltech/UArizona HiRISE; USGS DTM; Pearson et al. 2024 model; Pandolf 1977 energy model",
    }
    write_json(out / "arcadia.json", doc)
    log(SCENE, "export", f"wrote {out}")
