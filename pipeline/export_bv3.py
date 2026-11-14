"""Export route B_v3@k (W3 chain) for the astronaut page. Reformat only: paths and numbers come from
data_work/jezero/v3/compare_bv3*.json; per-vertex values are the same accumulations as export_compare.

python -m pipeline.export_bv3 -> web/data/jezero/compare/compare_v3.json, compare/routes_v3/t<i>.json
"""
from __future__ import annotations

import numpy as np

from .astro_plan import PARAMS as ASTRO, field, per_metre, step_len
from .common import Scene, log, read_json, write_json
from .compare_ab import SAND, hazard_zones
from .compare_v3 import expected_maps_v3
from .export_compare import finite
from .rover_sim import simplify


def run():
    sc = Scene("jezero")
    d = sc.work / "v3"
    C = read_json(d / "compare_bv3.json"); P = read_json(d / "compare_bv3_paths.json")
    R = read_json(d / "recon_loops.json"); st = dict(np.load(d / "recon_state.npz"))
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    F = read_json(sc.work / "compare_ab.json")
    ext, res, base_rc = P["ext"], P["res"], tuple(P["base_rc"])
    prior, ref = T["class_prior"].astype(np.uint8), T["class_ref"].astype(np.uint8)
    zones, _ = hazard_zones(ref, prior, res)
    tm, om = per_metre(ASTRO)
    ref_eval = np.minimum(ref, SAND)
    home_ref = field(om[ref_eval] * res, base_rc)[1]
    byid = {L["id"]: L for L in R["loops"]}
    maps = {}
    for k in (1, 5, 10, 20, 30):
        obs = (st["first_t"] >= 0) & (st["first_t"] <= byid[k]["t1"])
        Tm, Om, _ = expected_maps_v3(prior, ref, obs, byid[k]["p_firm"], byid[k]["p_rough"])
        maps[k] = (Tm, Om, field(Om * res, base_rc)[1])
    out = sc.web / "compare"; (out / "routes_v3").mkdir(parents=True, exist_ok=True)
    x0, y1 = ext[0], ext[3]
    for row in F["rows"]:
        i = str(row["target"]); doc = {"target": row["target"], "states": {}}
        for k, (Tm, Om, hk) in maps.items():
            p = [tuple(c) for c in P["paths"][f"B_v3@{k}"][i]]
            rc = np.array(p, float); x = x0 + (rc[:, 1] + .5) * res; y = y1 - (rc[:, 0] + .5) * res
            dd = [0.0]; pt = [0.0]; po = [0.0]; at = [0.0]; ao = [0.0]
            for a, b in zip(p[:-1], p[1:]):
                L = step_len(a, b, res)
                dd.append(dd[-1] + L); pt.append(pt[-1] + .5 * (Tm[a] + Tm[b]) * L); po.append(po[-1] + .5 * (Om[a] + Om[b]) * L)
                at.append(at[-1] + .5 * (tm[ref_eval[a]] + tm[ref_eval[b]]) * L); ao.append(ao[-1] + .5 * (om[ref_eval[a]] + om[ref_eval[b]]) * L)
            zin = np.array([zones[c] > 0 for c in p]); cls_r = np.array([ref[c] for c in p])
            keep = set(simplify(np.c_[x, y], 1.0).tolist())
            ch = np.nonzero((zin[1:] != zin[:-1]) | (cls_r[1:] != cls_r[:-1]))[0]
            keep |= set(ch.tolist()) | set((ch + 1).tolist())
            kk = np.array(sorted(keep))
            lon, lat = sc.grid.xy_to_lonlat(x[kk], y[kk])
            r2 = lambda a: [round(float(v), 2) for v in np.asarray(a)[kk]]
            doc["states"][f"B_v3@{k}"] = {"lon": [round(float(v), 7) for v in lon], "lat": [round(float(v), 7) for v in lat],
                                          "d": r2(dd), "pred_t": r2(pt), "pred_o2": r2(po), "act_t": r2(at), "act_o2": r2(ao),
                                          "home_k": [round(float(hk[p[j]]), 2) for j in kk], "home_ref": [round(float(home_ref[p[j]]), 2) for j in kk],
                                          "haz": [int(zin[j]) for j in kk], "cls": [int(cls_r[j]) for j in kk],
                                          "turn_idx": int(np.searchsorted(kk, (len(p) - 1) // 2))}
        write_json(out / "routes_v3" / f"t{i}.json", doc)
    # summary in the compare.json shape for the page (means only; from compare_bv3.json, not recomputed)
    S = {}
    for k in (1, 5, 10, 20, 30):
        g = C["summary"][f"B_v3@{k}"]["all"]
        S[f"B_v3@{k}"] = {"n": g["n"], **{q: {"mean": g[f"{q}_mean"]} for q in ("pred_o2", "actual_o2", "o2_error", "hazard_m", "crossings", "length_m", "actual_time_min", "pred_time_min")},
                          "n_actual_within_budget": g["n_actual_within_budget"],
                          "diff_vs_A": {q: {"mean": v} for q, v in g["diff_vs_A_mean"].items()},
                          "share_of_possible_improvement": g["share_of_possible_improvement"],
                          "better_worse_same_vs_A_actual_o2": g["better_worse_same_vs_A_actual_o2"],
                          "diff_vs_frozen_B": g["diff_vs_frozen_B_mean"]}
    rows = {}
    for k in (1, 5, 10, 20, 30):
        for i, r in C["rows"][str(k)].items():
            rows.setdefault(i, {})[f"B_v3@{k}"] = r
    rv = read_json(sc.work / "v3/recon_loops.json")
    write_json(out / "compare_v3.json", finite({"label": C["label"], "disclosure": C["disclosure"], "computed_at": C["computed_at"],
                                                "p": C["p"], "observed_frac": C["observed_frac"], "summary_all": S, "rows": rows,
                                                "recon_t1": {str(L["id"]): L["t1"] for L in rv["loops"]},
                                                "files": {"reveal_t": "../recon_v3/reveal_t.png"}}))
    log("jezero", "export_bv3", f"{len(F['rows'])} targets")


if __name__ == "__main__":
    run()
