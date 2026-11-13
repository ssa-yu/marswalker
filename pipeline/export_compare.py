"""Export the T2 route A vs B comparison for the web (web/data/<scene>/compare/).

python -m pipeline.export_compare --scene jezero

compare.json        definitions, summary tables (all targets + three distance bands), per-target rows, labels
routes/t<i>.json    per target: for each knowledge state the walk (lon/lat vertices, Douglas-Peucker 1 m) with,
                    at each kept vertex, cumulative distance, predicted and actual (reference) time and O2,
                    O2 needed to get home on the knowledge state and on the reference (cheapest way), and whether
                    the vertex is inside a hazard zone
hazard_zones.png    hazard zones (RGBA, 2 m)
Nothing is recomputed here: paths and numbers come from data_work/<scene>/compare_ab*.json.
"""
from __future__ import annotations

import argparse

import numpy as np
from PIL import Image

from .astro_plan import PARAMS as ASTRO, field, per_metre, step_len
from .common import Scene, log, read_json, write_json
from .compare_ab import SAND, aplus_classes, belief_after
from .rover_sim import simplify


def run(scene: str):
    sc = Scene(scene)
    C = read_json(sc.work / "compare_ab.json")
    Pth = read_json(sc.work / "compare_ab_paths.json")
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    st = dict(np.load(sc.work / "recon_state.npz"))
    R = read_json(sc.work / C["recon_file"])
    zones = np.load(sc.work / "hazard_zones.npy")
    ext = Pth["ext"]; res = Pth["res"]; base_rc = tuple(Pth["base_rc"])
    prior, ref = T["class_prior"], T["class_ref"]
    loop_t1 = {L["id"]: L["t1"] for L in R["loops"]}
    states = {"A": prior, "A+": aplus_classes(prior, ref)}
    for s in C["states"]:
        if s.startswith("B@"):
            states[s] = belief_after(prior, ref, st["first_t"], loop_t1[int(s[2:])])[0]
    states["REF"] = ref
    tm, om = per_metre(ASTRO)
    ref_eval = np.minimum(ref, SAND)
    home = {s: field(om[c] * res, base_rc)[1] for s, c in states.items()}
    home_ref_actual = field(om[ref_eval] * res, base_rc)[1]  # blocked charged as sand, as in the evaluation
    out = sc.web / "compare"; (out / "routes").mkdir(parents=True, exist_ok=True)
    x0, y1 = ext[0], ext[3]
    for tid, row in enumerate(C["rows"]):
        i = str(row["target"])
        doc = {"target": row["target"], "x": row["x"], "y": row["y"], "band": row["band"], "states": {}}
        for s in C["states"]:
            p = [tuple(c) for c in Pth["paths"][s][i]]
            rc = np.array(p, float)
            x = x0 + (rc[:, 1] + .5) * res; y = y1 - (rc[:, 0] + .5) * res
            d = [0.0]; pt = [0.0]; po = [0.0]; at = [0.0]; ao = [0.0]
            ck = states[s]
            for a, b in zip(p[:-1], p[1:]):
                L = step_len(a, b, res)
                d.append(d[-1] + L)
                pt.append(pt[-1] + .5 * (tm[ck[a]] + tm[ck[b]]) * L); po.append(po[-1] + .5 * (om[ck[a]] + om[ck[b]]) * L)
                at.append(at[-1] + .5 * (tm[ref_eval[a]] + tm[ref_eval[b]]) * L); ao.append(ao[-1] + .5 * (om[ref_eval[a]] + om[ref_eval[b]]) * L)
            zin = np.array([zones[c] > 0 for c in p])
            cls_r = np.array([ref[c] for c in p])
            # keep simplified vertices plus every change of hazard flag / reference class (for colouring)
            keep = set(simplify(np.c_[x, y], 1.0).tolist())
            ch = np.nonzero((zin[1:] != zin[:-1]) | (cls_r[1:] != cls_r[:-1]))[0]
            keep |= set(ch.tolist()) | set((ch + 1).tolist())
            k = np.array(sorted(keep))
            lon, lat = sc.grid.xy_to_lonlat(x[k], y[k])
            r2 = lambda a: [round(float(v), 2) for v in np.asarray(a)[k]]
            doc["states"][s] = {
                "lon": [round(float(v), 7) for v in lon], "lat": [round(float(v), 7) for v in lat],
                "d": r2(d), "pred_t": r2(pt), "pred_o2": r2(po), "act_t": r2(at), "act_o2": r2(ao),
                "home_k": [round(float(home[s][p[j]]), 2) for j in k],
                "home_ref": [round(float(home_ref_actual[p[j]]), 2) for j in k],
                "haz": [int(zin[j]) for j in k], "cls": [int(cls_r[j]) for j in k],
                "turn_idx": int(np.searchsorted(k, (len(p) - 1) // 2)),
            }
        write_json(out / "routes" / f"t{row['target']}.json", doc)
    # hazard-zone layer
    rgba = np.zeros(zones.shape + (4,), np.uint8)
    rgba[zones > 0] = (255, 60, 40, 150)
    Image.fromarray(rgba, "RGBA").save(out / "hazard_zones.png", optimize=True)
    pal = np.array([(98, 214, 164, 60), (244, 183, 64, 170), (255, 90, 78, 185), (138, 63, 174, 230)], np.uint8)
    Image.fromarray(pal[states["A+"]], "RGBA").save(out / "class_aplus.png", optimize=True)
    gm = read_json(sc.work / "grid.json")
    web = {k: C[k] for k in ("label", "review", "computed_at", "definitions", "usable_o2", "n_targets", "unreachable_targets",
                             "n_hazard_zones", "observed_frac", "aplus_sand_frac_aoi", "states", "summary", "rows", "targets")}
    web.update({"astronaut_params": C["astronaut_params"], "aoi_corners": gm["aoi"]["corners_lonlat"], "extent_local_m": ext,
                "base": sc.cfg["base"], "k_coslat": sc.grid.k,
                "files": {"hazard_zones": "hazard_zones.png", "class_aplus": "class_aplus.png",
                          "class_ref": "../recon/class_ref.png", "class_prior": "../recon/class_prior.png",
                          "hirise": "../recon/hirise_1m.jpg", "reveal_t": "../recon/reveal_t.png"},
                "recon_t1": {str(k): v for k, v in loop_t1.items()}})
    write_json(out / "compare.json", web)
    log(scene, "export_compare", f"{len(C['rows'])} targets exported")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
