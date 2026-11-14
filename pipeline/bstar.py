# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""U7 (round 7): exploratory B* — rule written by manager (TECH_LEAD_BRIEF 第七次更新), not tuned.
Label: `exploratory, designed after seeing the first comparison`. Listed next to round 6, never in a headline.

python -m pipeline.bstar --scene jezero      (main AOI, run once; writes data_work/jezero/bstar/compare_bstar.json)

B*@k (k = 1, 5, 10, 20, 30) = B@k except for cells NOT seen by the end of loop k and NOT blocked on the prior:
  p_k = among cells seen by the end of loop k whose reference class is not blocked, the share that is sand
        (one number for the whole AOI);
  such an unseen cell gets per-metre time and per-metre O2 = (1 - p_k) x value of its prior class + p_k x sand value.
  Seen cells: reference class (as B@k; reference-blocked = impassable). Prior-blocked unseen cells: blocked.
Planned / predicted = least-O2 path and its time / O2 on this expected-cost map; actual = the same path on the
reference, with every round-6 quantity (pipeline/compare_ab.evaluate_path) unchanged.
"""
from __future__ import annotations

import argparse
import math
import time

import numpy as np

from .astro_plan import PARAMS as ASTRO, field, per_metre, step_len
from .compare_ab import CMP, evaluate_path, hazard_zones, lattice_targets

SAND, BLOCKED = 2, 3


def expected_maps(prior, ref, observed):
    """Per-metre time and O2 arrays of B* (inf = impassable) and p_k."""
    tm, om = per_metre(ASTRO)
    seen_ok = observed & (ref != BLOCKED)
    p = float(np.mean(ref[seen_ok] == SAND)) if seen_ok.any() else 0.0
    cls_b = np.where(observed, ref, prior)
    T = tm[cls_b].astype(float); O = om[cls_b].astype(float)
    unseen = ~observed & (prior != BLOCKED)
    T[unseen] = (1 - p) * tm[prior[unseen]] + p * tm[SAND]
    O[unseen] = (1 - p) * om[prior[unseen]] + p * om[SAND]
    return T, O, p, cls_b


def route_all_cost(O, base_rc, targets_rc, res):
    m, cc = field(O * res, base_rc)
    out = []
    for t in targets_rc:
        if not np.isfinite(cc[t]):
            out.append(None); continue
        p = [tuple(int(v) for v in x) for x in m.traceback(t)]
        out.append(p + p[-2::-1])
    return out


def evaluate_bstar(path, T, O, cls_b, ref, zones, res):
    """Round-6 quantities; the predicted time / O2 come from the expected-cost map instead of a class grid."""
    r = evaluate_path(path, cls_b, ref, zones, res)
    pt = po = 0.0
    for a, b in zip(path[:-1], path[1:]):
        L = step_len(a, b, res)
        pt += 0.5 * (T[a] + T[b]) * L
        po += 0.5 * (O[a] + O[b]) * L
    r["pred_time_min"], r["pred_o2"] = pt, po
    r["o2_error"] = r["actual_o2"] - po
    r["o2_error_pct"] = 100.0 * (r["actual_o2"] - po) / po if po > 0 else math.nan
    r["time_error"] = r["actual_time_min"] - pt
    from .astro_plan import usable_o2
    r["pred_within_budget"] = bool(po <= usable_o2(P=ASTRO) + 1e-9)
    return r


def compare_bstar(Tm, first_t, loop_t1, ext, res, P=CMP):
    prior, ref = Tm["class_prior"].astype(np.uint8), Tm["class_ref"].astype(np.uint8)
    base_rc = (int(ext[3] / res), int(-ext[0] / res))
    zones, _ = hazard_zones(ref, prior, res, P)
    targets = lattice_targets(ext, res, prior, ref, P)
    out = {"p_k": {}, "rows": {}, "unreachable": {}}
    for k in P["b_loops"]:
        if k not in loop_t1:
            continue
        obs = (first_t >= 0) & (first_t <= loop_t1[k])
        T, O, p, cls_b = expected_maps(prior, ref, obs)
        paths = route_all_cost(O, base_rc, [t["rc"] for t in targets], res)
        out["p_k"][k] = p
        out["unreachable"][k] = [i for i, pth in enumerate(paths) if pth is None]
        out["rows"][k] = {i: evaluate_bstar(pth, T, O, cls_b, ref, zones, res) for i, pth in enumerate(paths) if pth is not None}
    out["targets"] = targets
    return out


def run(scene: str):
    from .common import Scene, log, read_json, write_json
    sc = Scene(scene)
    d = sc.work / "bstar"; d.mkdir(exist_ok=True)
    if (d / "compare_bstar.json").exists():
        raise SystemExit("B* already run once")
    Tm = dict(np.load(sc.work / "terrain_2m.npz"))
    ext = read_json(sc.work / "terrain_2m.json")["extent_local_m"]; res = 2.0
    R = read_json(sc.work / "recon_loops.json"); st = dict(np.load(sc.work / "recon_state.npz"))
    loop_t1 = {L["id"]: L["t1"] for L in R["loops"]}
    t0 = time.time()
    o = compare_bstar(Tm, st["first_t"], loop_t1, ext, res)
    F = read_json(sc.work / "compare_ab.json")
    rowsA = {r["target"]: r for r in F["rows"]}
    summ = {}
    for k, rows in o["rows"].items():
        idx = [i for i in rows if i in rowsA]
        g = {}
        for grp, sel in [("all", idx)] + [(b, [i for i in idx if o["targets"][i]["band"] == b]) for b in CMP["bands_m"]]:
            if not sel:
                continue
            q = lambda name, src: float(np.mean([src(i)[name] for i in sel]))
            g[grp] = {"n": len(sel),
                      **{f"{n}_mean": q(n, lambda i: rows[i]) for n in ("pred_o2", "actual_o2", "o2_error", "hazard_m", "crossings", "length_m")},
                      "n_actual_within_budget": int(sum(rows[i]["actual_within_budget"] for i in sel)),
                      "diff_vs_A_mean": {n: float(np.mean([rows[i][n] - rowsA[i]["A"][n] for i in sel])) for n in ("actual_o2", "hazard_m", "crossings")},
                      "diff_vs_B_mean": {n: float(np.mean([rows[i][n] - rowsA[i][f"B@{k}"][n] for i in sel])) for n in ("actual_o2", "hazard_m", "o2_error")}}
        summ[f"B*@{k}"] = g
    out = {"label": "exploratory, designed after seeing the first comparison", "rule": __doc__.split("B*@k", 1)[1].split("python", 1)[0],
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "seconds": round(time.time() - t0, 1),
           "p_k": o["p_k"], "unreachable": o["unreachable"], "summary": summ,
           "rows": {str(k): {str(i): {n: (round(v, 3) if isinstance(v, float) else v) for n, v in r.items()} for i, r in rows.items()} for k, rows in o["rows"].items()}}
    write_json(d / "compare_bstar.json", out)
    log(scene, "bstar", f"p_k {o['p_k']}; {out['seconds']} s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
