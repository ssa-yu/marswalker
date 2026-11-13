"""U4 (round 7, DRAFT): multi-stop astronaut walk with a dwell time at every stop. Synthetic tests only.

Status: draft, not run on real terrain (TECH_LEAD_BRIEF 第七次更新 U4: definitions go to manager first).
Reuses pipeline/astro_plan.py (locked walk model, least-O2 paths, unchanged) and adds:
  dwell       every stop costs dwell_min minutes of time and dwell_min * dwell_o2_factor nominal minutes of O2
              (draft: 18 min, factor 1 = the firm-ground walking rate; manager to confirm).
  order rule  same as the step-3 skeleton: visit the most stops, then the least planned O2, subject to
              "after the dwell at each stop the planned O2 used + planned O2 home <= usable O2";
              brute force over orders for <= 7 stops, greedy nearest-feasible beyond.
  evaluation  the planned tour (same cells, same order, nothing replanned) walked on another class grid
              (the reference): actual O2 / time, and how many stops are reached under two draft readings.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

from .astro_plan import PARAMS, cost_grids, field, step_len, usable_o2

DWELL = {"dwell_min": 18.0, "dwell_o2_factor": 1.0, "status": "draft (manager to confirm)",
         "source": "MVP_PLAN draft value 18 min (decisions 2026-11-14)"}


def plan_multistop(cls, base_rc, targets_rc, res, dwell=DWELL, capacity=None, reserve=None, P=PARAMS, brute_max=7):
    o2c, tc = cost_grids(cls, res, P)
    U = usable_o2(capacity, reserve, P)
    dw_t = float(dwell["dwell_min"]); dw_o = dw_t * float(dwell["dwell_o2_factor"])
    base_rc = tuple(base_rc)
    pts = [base_rc] + [tuple(t) for t in targets_rc]
    n = len(targets_rc)
    fields = [field(o2c, p) for p in pts]
    D = np.array([[fields[i][1][pts[j]] for j in range(n + 1)] for i in range(n + 1)])

    def tour_cost(order):
        used, cur = 0.0, 0
        for j in order:
            used += D[cur, j + 1] + dw_o
            if not np.isfinite(used) or used + D[j + 1, 0] > U + 1e-9:
                return math.inf
            cur = j + 1
        return used + D[cur, 0]

    best, best_c = (), 0.0
    if n <= brute_max:
        for k in range(n, 0, -1):
            cands = [(tour_cost(o), o) for s in itertools.combinations(range(n), k) for o in itertools.permutations(s)]
            cands = [c for c in cands if np.isfinite(c[0])]
            if cands:
                best_c, best = min(cands)
                break
    else:
        cur, used, left, order = 0, 0.0, set(range(n)), []
        while left:
            ok = [(D[cur, j + 1], j) for j in left if used + D[cur, j + 1] + dw_o + D[j + 1, 0] <= U + 1e-9]
            if not ok:
                break
            d, j = min(ok)
            used += d + dw_o; cur = j + 1; order.append(j); left.discard(j)
        best, best_c = tuple(order), (used + D[cur, 0]) if order else 0.0
    stops = [0] + [j + 1 for j in best] + [0]
    path, stop_idx = [base_rc], []
    for a, b in zip(stops[:-1], stops[1:]):
        if a == b:
            continue
        seg = [tuple(int(v) for v in x) for x in fields[a][0].traceback(pts[b])]
        path += seg[1:]
        if b != 0:
            stop_idx.append(len(path) - 1)
    return {"usable_o2": U, "order": list(best), "skipped": [j for j in range(n) if j not in best],
            "planned_o2": float(best_c), "path_rc": path, "stop_idx": stop_idx, "dwell": dwell,
            "home_field_o2": fields[0][1], "brute_force": n <= brute_max}


def walk(path, stop_idx, cls_eval, res, dwell=DWELL, P=PARAMS, home=None, U=None):
    """Cumulative time / O2 along the tour on cls_eval (dwell added on arrival at each stop).
    home: O2-home field on cls_eval (for the true return margin). Blocked cells charged at the sand rate."""
    o2c, tc = cost_grids(np.minimum(cls_eval, 2), res, P)
    dw_t = float(dwell["dwell_min"]); dw_o = dw_t * float(dwell["dwell_o2_factor"])
    stops = set(stop_idx)
    t = [0.0]; o = [0.0]
    for k, (a, b) in enumerate(zip(path[:-1], path[1:]), start=1):
        L = step_len(a, b, res)
        t.append(t[-1] + 0.5 * (tc[a] + tc[b]) / res * L + (dw_t if k in stops else 0.0))
        o.append(o[-1] + 0.5 * (o2c[a] + o2c[b]) / res * L + (dw_o if k in stops else 0.0))
    out = {"time_min": t, "o2": o, "total_o2": o[-1], "total_time_min": t[-1]}
    if home is not None and U is not None:
        out["true_margin"] = [U - o[k] - float(home[c]) for k, c in enumerate(path)]
    return out


def evaluate_on_reference(plan, cls_plan, cls_ref, res, dwell=DWELL, P=PARAMS):
    """Draft quantities for round 7 (manager to confirm which are reported)."""
    U = plan["usable_o2"]
    o2c_ref, _ = cost_grids(np.minimum(cls_ref, 2), res, P)
    _, home_ref = field(o2c_ref, plan["path_rc"][0])
    pred = walk(plan["path_rc"], plan["stop_idx"], cls_plan, res, dwell, P)
    act = walk(plan["path_rc"], plan["stop_idx"], cls_ref, res, dwell, P, home=home_ref, U=U)
    o = act["o2"]
    # (i) stops whose dwell ends before the actual O2 used passes the usable O2
    reached_within_usable = sum(1 for k in plan["stop_idx"] if o[k] <= U + 1e-9)
    # (ii) stops after whose dwell the astronaut could still get home on the reference within the usable O2
    reached_safe_return = sum(1 for k in plan["stop_idx"] if act["true_margin"][k] >= -1e-9)
    neg = [k for k, m in enumerate(act["true_margin"]) if m < -1e-9]
    return {"pred_o2": pred["total_o2"], "actual_o2": act["total_o2"], "pred_time_min": pred["total_time_min"],
            "actual_time_min": act["total_time_min"], "n_planned_stops": len(plan["stop_idx"]),
            "actual_within_budget": bool(act["total_o2"] <= U + 1e-9),
            "stops_reached_within_usable": reached_within_usable, "stops_reached_with_safe_return": reached_safe_return,
            "first_step_true_margin_negative": neg[0] if neg else None}
