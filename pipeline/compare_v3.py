# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""W3 step 3: route B_v3@k on the main AOI (k = 1, 5, 10, 20, 30), run ONCE after the version-3 recon.

python -m pipeline.compare_v3   -> data_work/jezero/v3/compare_bv3.json

Definition (manager 2026-11-14, direction.md 第三版鏈 (2)): B_v3's map = the version-3 rover's knowledge + expected
cost. Cells seen by the end of loop k: reference class. Unseen and not blocked on the prior: per-metre time and O2 =
(1 - p_k) x value of the prior class + p_k x sand value, p_k = the version-3 rover's own estimate for that prior
class at the end of loop k ((s_k + 1)/(n_k + 5), recorded in v3/recon_loops.json). Unseen prior-blocked: blocked.
Predicted = least-O2 path and its time / O2 on that map; actual = the same path on the reference, every round-6
quantity unchanged (compare_ab.evaluate_path). Same 63 targets as the frozen T2; A, A+, REF are the frozen values
(commit e17452a) read from compare_ab.json, not recomputed. Literature: expected cost of unknown terrain, Sofman
et al. 2006; route B's "unseen = prior" is the freespace assumption (Koenig & Smirnov 1997).
Designed after seeing version 2; round 6 stays the pre-registered main comparison.
"""
from __future__ import annotations

import time

import numpy as np

from .astro_plan import PARAMS as ASTRO, per_metre
from .bstar import evaluate_bstar, route_all_cost
from .common import Scene, log, read_json, write_json
from .compare_ab import CMP, hazard_zones, lattice_targets

SAND, BLOCKED = 2, 3


def expected_maps_v3(prior, ref, observed, p_firm, p_rough):
    tm, om = per_metre(ASTRO)
    cls_b = np.where(observed, ref, prior)
    T = tm[cls_b].astype(float); O = om[cls_b].astype(float)
    p = np.where(prior == 0, p_firm, p_rough)
    unseen = ~observed & (prior != BLOCKED)
    T[unseen] = (1 - p[unseen]) * tm[prior[unseen]] + p[unseen] * tm[SAND]
    O[unseen] = (1 - p[unseen]) * om[prior[unseen]] + p[unseen] * om[SAND]
    return T, O, cls_b


def compare_v3(Tm, first_t, loops, ext, res, P=CMP):
    prior, ref = Tm["class_prior"].astype(np.uint8), Tm["class_ref"].astype(np.uint8)
    base_rc = (int(ext[3] / res), int(-ext[0] / res))
    zones, _ = hazard_zones(ref, prior, res, P)
    targets = lattice_targets(ext, res, prior, ref, P)
    byid = {L["id"]: L for L in loops}
    out = {"p": {}, "rows": {}, "unreachable": {}, "observed_frac": {}}
    for k in P["b_loops"]:
        L = byid[k]
        obs = (first_t >= 0) & (first_t <= L["t1"])
        T, O, cls_b = expected_maps_v3(prior, ref, obs, L["p_firm"], L["p_rough"])
        paths = route_all_cost(O, base_rc, [t["rc"] for t in targets], res)
        out["p"][k] = {"p_firm": L["p_firm"], "p_rough": L["p_rough"]}
        out["observed_frac"][k] = float(obs.mean())
        out["unreachable"][k] = [i for i, pth in enumerate(paths) if pth is None]
        out["rows"][k] = {i: evaluate_bstar(pth, T, O, cls_b, ref, zones, res) for i, pth in enumerate(paths) if pth is not None}
        out.setdefault("paths", {})[k] = {i: pth for i, pth in enumerate(paths) if pth is not None}
    out["targets"] = targets
    return out


def run():
    sc = Scene("jezero")
    d = sc.work / "v3"
    if (d / "compare_bv3.json").exists():
        raise SystemExit("B_v3 already run once")
    Tm = dict(np.load(sc.work / "terrain_2m.npz"))
    ext = read_json(sc.work / "terrain_2m.json")["extent_local_m"]; res = 2.0
    R = read_json(d / "recon_loops.json"); st = dict(np.load(d / "recon_state.npz"))
    F = read_json(sc.work / "compare_ab.json")
    t0 = time.time()
    o = compare_v3(Tm, st["first_t"], R["loops"], ext, res)
    tg_frozen = [(t["x"], t["y"]) for t in F["targets"]]
    assert [(t["x"], t["y"]) for t in o["targets"]] == tg_frozen, "targets differ from the frozen T2"
    rowsF = {r["target"]: r for r in F["rows"]}
    S = F["summary"]["all"]
    summ = {}
    for k, rows in o["rows"].items():
        idx = [i for i in rows if i in rowsF]
        g = {}
        for grp, sel in [("all", idx)] + [(b, [i for i in idx if o["targets"][i]["band"] == b]) for b in CMP["bands_m"]]:
            if not sel:
                continue
            m = lambda n: float(np.mean([rows[i][n] for i in sel]))
            fA = lambda n: float(np.mean([rowsF[i]["A"][n] for i in sel]))
            fR = lambda n: float(np.mean([rowsF[i]["REF"][n] for i in sel]))
            g[grp] = {"n": len(sel), **{f"{n}_mean": m(n) for n in ("pred_o2", "actual_o2", "o2_error", "hazard_m", "crossings", "length_m", "actual_time_min", "pred_time_min")},
                      "n_actual_within_budget": int(sum(rows[i]["actual_within_budget"] for i in sel)),
                      "diff_vs_A_mean": {n: m(n) - fA(n) for n in ("actual_o2", "hazard_m", "crossings", "o2_error")},
                      "diff_vs_frozen_B_mean": {n: float(np.mean([rows[i][n] - rowsF[i][f"B@{k}"][n] for i in sel])) for n in ("actual_o2", "hazard_m", "o2_error")},
                      "share_of_possible_improvement": {n: (fA(n) - m(n)) / (fA(n) - fR(n)) if abs(fA(n) - fR(n)) > 1e-12 else None for n in ("actual_o2", "hazard_m")},
                      "better_worse_same_vs_A_actual_o2": [int(sum(rows[i]["actual_o2"] < rowsF[i]["A"]["actual_o2"] - 1e-9 for i in sel)),
                                                           int(sum(rows[i]["actual_o2"] > rowsF[i]["A"]["actual_o2"] + 1e-9 for i in sel)),
                                                           int(sum(abs(rows[i]["actual_o2"] - rowsF[i]["A"]["actual_o2"]) <= 1e-9 for i in sel))]}
        summ[f"B_v3@{k}"] = g
    out = {"label": "derived (simulated recon v3 + assumed parameters); heuristic, not yet reviewed",
           "disclosure": "version 3 designed after seeing version 2's coverage, repeat coverage and loop 24; round 6 is the pre-registered main comparison",
           "definition": __doc__.split("Definition", 1)[1].split("Designed after", 1)[0],
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "seconds": round(time.time() - t0, 1),
           "frozen_reference": {s: {"actual_o2": S[s]["actual_o2"]["mean"], "pred_o2": S[s]["pred_o2"]["mean"], "hazard_m": S[s]["hazard_m"]["mean"]} for s in ("A", "A+", "B@30", "REF")},
           "p": o["p"], "observed_frac": o["observed_frac"], "unreachable": o["unreachable"], "summary": summ,
           "rows": {str(k): {str(i): {n: (round(v, 3) if isinstance(v, float) else v) for n, v in r.items()} for i, r in rows.items()} for k, rows in o["rows"].items()}}
    write_json(d / "compare_bv3.json", out)
    write_json(d / "compare_bv3_paths.json", {"base_rc": [int(ext[3] / res), int(-ext[0] / res)], "res": res, "ext": ext,
                                              "paths": {f"B_v3@{k}": {str(i): p for i, p in ps.items()} for k, ps in o["paths"].items()}})
    log("jezero", "compare_v3", f"{out['seconds']} s; B_v3@30 actual {summ['B_v3@30']['all']['actual_o2_mean']:.1f}")
    return out


if __name__ == "__main__":
    run()
