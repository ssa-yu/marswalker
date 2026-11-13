"""Export the step-1 recon simulation for the web viewer (web/data/<scene>/recon/).

python -m pipeline.export_recon --scene jezero

recon.json       params, per-loop stats, events, paths (lon/lat + step index t + mode), labels
reveal_t.png     RGB 24-bit: step index t at which each 2 m cell was first observed (0xFFFFFF = never)
hirise_1m.jpg    HiRISE orthoimage averaged to 1 m (shown only where revealed, or in "view all data")
class_ref.png    reference terrain classes (2 m, palette), class_prior.png prior classes
"""
from __future__ import annotations

import argparse

import numpy as np
from PIL import Image

from .common import Scene, log, read_json, write_json
from .rover_sim import simplify
from .terrain import CLASS_COLORS, CLASSES, block, read

MODE_OF = {"out": "out", "return": "return", "forced": "forced"}


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def run(scene: str):
    sc = Scene(scene)
    R = read_json(sc.work / "recon_loops.json")
    st = dict(np.load(sc.work / "recon_state.npz"))
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    gm = read_json(sc.work / "grid.json")
    out = sc.web / "recon"; out.mkdir(parents=True, exist_ok=True)
    ext = R["extent_local_m"]; res = R["params"]["grid_res_m"]

    ft = st["first_t"].astype(np.int64)
    v = np.where(ft < 0, 0xFFFFFF, ft).astype(np.uint32)
    rgb = np.dstack([(v >> 16) & 255, (v >> 8) & 255, v & 255]).astype(np.uint8)
    Image.fromarray(rgb, "RGB").save(out / "reveal_t.png", optimize=True)

    o = read(sc.work / "ortho_025.tif"); o[o == 0] = np.nan
    o1 = block(o, 4, "mean")
    lo, hi = np.nanpercentile(o1, 0.5), np.nanpercentile(o1, 99.5)
    g = np.clip((o1 - lo) / (hi - lo) * 255, 0, 255)
    Image.fromarray(np.nan_to_num(g).astype(np.uint8), "L").save(out / "hirise_1m.jpg", quality=82, optimize=True)

    for name, c in (("class_ref", T["class_ref"]), ("class_prior", T["class_prior"])):
        pal = np.array([hex_rgb(h) + (a,) for h, a in zip(CLASS_COLORS, (70, 200, 220, 235))], np.uint8)
        Image.fromarray(pal[c], "RGBA").save(out / f"{name}.png", optimize=True)

    x0, y1 = ext[0], ext[3]
    loops = []
    for L in R["loops"]:
        rc = np.array(L["path_rc"], float)
        x = x0 + (rc[:, 1] + 0.5) * res; y = y1 - (rc[:, 0] + 0.5) * res
        lon, lat = sc.grid.xy_to_lonlat(x, y)
        md = np.array(L["modes"]); t = np.array(L["t"])
        segs = []
        i = 0
        while i < len(md):
            j = i
            while j + 1 < len(md) and md[j + 1] == md[i]:
                j += 1
            a = max(i - 1, 0)  # connect to previous vertex
            xy = np.c_[x[a:j + 1], y[a:j + 1]]
            keep = simplify(xy, 1.0) + a
            segs.append({"mode": MODE_OF.get(md[i], md[i]),
                         "c": [[round(float(lon[k]), 7), round(float(lat[k]), 7)] for k in keep],
                         "t": [int(t[k]) for k in keep]})
            i = j + 1
        ev = []
        for e in L["events"]:
            k = int(np.searchsorted(t, e["t"]))
            k = min(k, len(t) - 1)
            ev.append({**e, "lon": round(float(lon[k]), 7), "lat": round(float(lat[k]), 7)})
        gr, gc = L["goal_rc"]
        glon, glat = sc.grid.xy_to_lonlat(x0 + (gc + .5) * res, y1 - (gr + .5) * res)
        keep = {k: L.get(k) for k in ("id", "t0", "t1", "cost_total", "budget", "length_m", "new_observed_m2", "observed_total_m2",
                                  "overlap_ratio", "n_replan", "n_turn_back", "n_return_direct", "n_safety_return",
                                  "goal_reached", "observed_frac_aoi", "belief_agrees_with_reference_frac", "margin_after_loop")}
        keep.update({"goal": [round(float(glon), 7), round(float(glat), 7)], "segments": segs, "events": ev})
        loops.append(keep)
    # acceptance (MVP_PLAN P6): start/end at base, never on impassable reference terrain, never on a cell
    # before it was observed (so the planner could not have used an unobserved reference value)
    base_rc = tuple(R["base_rc"]); imp = (T["class_ref"] == 3) | T["blocked_rover_ref"]
    se, ni, nu = True, True, True
    for L in R["loops"]:
        pr = [tuple(c) for c in L["path_rc"]]
        se &= pr[0] == base_rc and pr[-1] == base_rc
        for c, tt in zip(pr, L["t"]):
            ni &= not bool(imp[c]); nu &= 0 <= int(st["first_t"][c]) <= tt
    ov = sorted(L["overlap_ratio"] for L in R["loops"] if L["overlap_ratio"] is not None)
    acc = {"start_end_at_base": bool(se), "no_impassable": bool(ni), "no_unobserved_reads": bool(nu),
           "max_cost_over_budget": max(L["cost_total"] - L["budget"] for L in R["loops"]) <= 0,
           "median_overlap": ov[(len(ov) - 1) // 2] if ov else None}
    P = R["params"]
    doc = {"acceptance": acc, "label": "simulated", "review": "pending", "status": "parameters locked (manager 2026-11-14); sand classes heuristic, not yet reviewed",
           "aoi_corners": gm["aoi"]["corners_lonlat"], "extent_local_m": ext, "grid_res_m": res,
           "base": sc.cfg["base"], "aoi_area_m2": R["aoi_area_m2"],
           "initial_belief_agrees_with_reference_frac": R["initial_belief_agrees_with_reference_frac"],
           "params": P, "terrain_params": R["terrain_params"], "classes": CLASSES, "class_colors": CLASS_COLORS,
           "files": {"reveal_t": "reveal_t.png", "hirise": "hirise_1m.jpg", "class_ref": "class_ref.png", "class_prior": "class_prior.png"},
           "t_max": int(max(L["t1"] for L in R["loops"])) if R["loops"] else 0,
           "loops": loops, "seconds": R["seconds"]}
    write_json(out / "recon.json", doc)
    sizes = {p.name: p.stat().st_size for p in out.iterdir()}
    log(scene, "export_recon", f"{len(loops)} loops; files {sizes}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
