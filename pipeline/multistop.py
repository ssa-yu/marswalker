# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Round 7: multi-stop astronaut walk with a dwell time at every stop (definitions CONFIRMED by manager
2026-11-14, direction.md 第七輪定義; status: confirmed; real-terrain run = pipeline/round7.py, once).

Reuses pipeline/astro_plan.py (locked walk model, least-O2 paths, unchanged) and adds:
  dwell       every visited stop costs 18 minutes of time and 18 nominal minutes of O2 (rate = walking on firm
              ground, 1x), assumed (no source for the O2 rate at rest).
  order rule  (main column) each knowledge state picks its own order and subset: most stops, then least planned
              O2, subject to "after the dwell at each stop, planned O2 used + planned O2 home <= usable O2";
              brute force over orders for <= 7 stops, greedy nearest-feasible beyond.
              (secondary column) route B keeps route A's order and subset; only the legs between consecutive
              stops are re-planned on B's map (plan_fixed_order).
  evaluation  the planned tour (same cells, same order, nothing replanned) walked on the reference.
              Stops reached, main reading (ii): stops at which, when the dwell ends, the astronaut could still
              get home WITHIN the usable O2 by walking the least-O2 way home OF HIS OWN MAP, with that way home
              charged on the reference (true return margin >= 0). Reading (i), listed beside it: stops whose
              dwell ends before the actual O2 used passes the usable O2. Also the first point of the tour where
              the true return margin (same definition) turns negative.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

from skimage.graph import MCP_Geometric

from .astro_plan import PARAMS, cost_grids as _class_grids, field, step_len, usable_o2


def cost_grids(cls, res, P=PARAMS):
    """Class grid -> (O2, time) MCP cell costs; a dict {"o2", "t"} of per-metre arrays (an expected-cost map such as
    B_v3, round 7 v3 chain) is used as given. Blocked cells of a class grid stay impassable."""
    if isinstance(cls, dict):
        return cls["o2"] * res, cls["t"] * res
    return _class_grids(cls, res, P)


def _eval_grid(cls):
    return cls if isinstance(cls, dict) else np.minimum(cls, 2)

DWELL = {"dwell_min": 18.0, "dwell_o2_factor": 1.0, "status": "confirmed (manager 2026-11-14)", "label": "assumed",
         "source": "MVP_PLAN value 18 min (decisions 2026-11-14); O2 rate at rest = firm-ground walking rate (no source)"}


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
    o2c, tc = cost_grids(_eval_grid(cls_eval), res, P)
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


def plan_fixed_order(cls, base_rc, targets_rc, order, res, dwell=DWELL, capacity=None, reserve=None, P=PARAMS):
    """Secondary column: visit `order` (indices into targets_rc) as given; legs re-planned on cls."""
    o2c, _ = cost_grids(cls, res, P)
    U = usable_o2(capacity, reserve, P)
    base_rc = tuple(base_rc)
    pts = [base_rc] + [tuple(targets_rc[j]) for j in order] + [base_rc]
    path, stop_idx, planned = [base_rc], [], 0.0
    dw_o = float(dwell["dwell_min"]) * float(dwell["dwell_o2_factor"])
    for i, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        m, cc = field(o2c, a)
        if not np.isfinite(cc[b]):
            return None
        seg = [tuple(int(v) for v in x) for x in m.traceback(b)]
        path += seg[1:]
        planned += float(cc[b])
        if i < len(order):
            stop_idx.append(len(path) - 1)
    planned += dw_o * len(order)
    _, home = field(o2c, base_rc)
    return {"usable_o2": U, "order": list(order), "skipped": [j for j in range(len(targets_rc)) if j not in order],
            "planned_o2": planned, "path_rc": path, "stop_idx": stop_idx, "dwell": dwell, "home_field_o2": home,
            "brute_force": None, "fixed_order": True}


def own_map_home_cost_on(cls_plan, cls_eval, base_rc, res, P=PARAMS):
    """For every cell: O2 of walking home along the least-O2 way of the PLAN map (cls_plan), charged on cls_eval
    (blocked charged at the sand rate). inf where the plan map has no way home."""
    o2p, _ = cost_grids(cls_plan, res, P)
    o2e, _ = cost_grids(_eval_grid(cls_eval), res, P)
    m = MCP_Geometric(o2p, fully_connected=True)
    cc, tb = m.find_costs([tuple(base_rc)])
    off = np.asarray(m.offsets)
    H, W = o2p.shape
    rr, cc_ = np.mgrid[0:H, 0:W]
    ok = np.isfinite(cc) & (tb >= 0)
    t = np.where(ok, tb, 0)
    pr = np.where(ok, rr - off[t, 0], rr); pc = np.where(ok, cc_ - off[t, 1], cc_)
    pr = np.clip(pr, 0, H - 1); pc = np.clip(pc, 0, W - 1)
    L = res * np.where((pr != rr) & (pc != cc_), math.sqrt(2.0), np.where((pr != rr) | (pc != cc_), 1.0, 0.0))
    step = np.where(ok, 0.5 * (o2e + o2e[pr, pc]) / res * L, 0.0)
    acc = step.ravel().copy()
    ptr = (pr * W + pc).ravel()
    for _ in range(int(math.ceil(math.log2(H * W))) + 1):          # pointer jumping: sum of steps to the base
        acc = acc + acc[ptr]
        ptr = ptr[ptr]
    out = acc.reshape(H, W)
    out[~np.isfinite(cc)] = np.inf
    return out


def evaluate_on_reference(plan, cls_plan, cls_ref, res, dwell=DWELL, P=PARAMS, home_own_on_ref=None):
    """Round-7 quantities of one planned tour, walked on the reference (nothing replanned)."""
    U = plan["usable_o2"]
    base = plan["path_rc"][0]
    if home_own_on_ref is None:
        home_own_on_ref = own_map_home_cost_on(cls_plan, cls_ref, base, res, P)
    pred = walk(plan["path_rc"], plan["stop_idx"], cls_plan, res, dwell, P)
    act = walk(plan["path_rc"], plan["stop_idx"], cls_ref, res, dwell, P, home=home_own_on_ref, U=U)
    o = act["o2"]
    reached_within_usable = sum(1 for k in plan["stop_idx"] if o[k] <= U + 1e-9)            # reading (i)
    reached_safe_return = sum(1 for k in plan["stop_idx"] if act["true_margin"][k] >= -1e-9)  # reading (ii), main
    neg = [k for k, m in enumerate(act["true_margin"]) if m < -1e-9]
    first = None
    if neg:
        k = neg[0]
        first = {"step": k, "rc": list(plan["path_rc"][k]), "elapsed_min": act["time_min"][k], "o2_used": o[k],
                 "after_n_stops": sum(1 for s in plan["stop_idx"] if s <= k)}
    return {"pred_o2": pred["total_o2"], "actual_o2": act["total_o2"], "o2_error": act["total_o2"] - pred["total_o2"],
            "pred_time_min": pred["total_time_min"], "actual_time_min": act["total_time_min"],
            "n_planned_stops": len(plan["stop_idx"]),
            "pred_within_budget": bool(pred["total_o2"] <= U + 1e-9), "actual_within_budget": bool(act["total_o2"] <= U + 1e-9),
            "stops_reached_within_usable": reached_within_usable, "stops_reached_with_safe_return": reached_safe_return,
            "true_margin_at_stops": [act["true_margin"][k] for k in plan["stop_idx"]],
            "first_true_margin_negative": first,
            "first_step_true_margin_negative": neg[0] if neg else None}
