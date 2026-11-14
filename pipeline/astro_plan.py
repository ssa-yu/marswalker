# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Step 3 skeleton: astronaut walk planner (oxygen budget, visit targets, always keep a way home).

python -m pipeline.astro_plan --scene jezero

Status: SKELETON, review: pending. Targets are PLACEHOLDERS (step 2 not decided). On real terrain this
module only produces PLANNED values on ONE knowledge state (the orbital prior classes). It never evaluates a
route on the HiRISE reference terrain and never compares route A with route B.

Model (all parameters locked by manager 2026-11-14, labelled assumed):
  walking speed on firm ground 2.5 km/h; speed factor firm/rough/sand = 1 / 0.6 / 0.35;
  oxygen-use factor (multiplier on the nominal rate) firm/rough/sand = 1 / 1.5 / 2.1; blocked = impassable.
  time on a stretch  = length / (2.5 km/h * speed factor)
  O2 on a stretch    = time * O2 factor         (in "nominal minutes": 1 min of walking on firm ground = 1)
  usable O2          = O2 capacity (480 nominal min) * (1 - reserve 20 %)
  return margin at a point = usable O2 still left - O2 needed to walk home from there on the cheapest route.
Paths: least-O2 path on the class grid, 8-connected (skimage MCP_Geometric: a step costs the mean of the two
cells' per-metre O2 times the step length). The path cost is symmetric, so one field from the base gives the
O2 needed to get home from every cell.
Tour: targets are visited in the order that visits the most targets and then uses the least O2, subject to
"after reaching each target the astronaut can still walk home within the usable O2" (brute force over orders
for <= 7 targets, greedy nearest-feasible beyond). Targets that do not fit are skipped and reported.
"""
from __future__ import annotations

import argparse
import itertools
import math

import numpy as np
from skimage.graph import MCP_Geometric

PARAMS = {
    "status": "locked (manager 2026-11-14)", "label": "assumed",
    "speed_kmh": 2.5,
    "o2_capacity_nominal_min": 480.0,
    "reserve_frac": 0.20,
    "speed_factor": {"firm": 1.0, "rough": 0.6, "sand": 0.35},
    "o2_factor": {"firm": 1.0, "rough": 1.5, "sand": 2.1},
    "source": "MVP_PLAN 5.6 (team prototype; teammates are checking the original sources)",
}
CLASSES = ["firm", "rough", "sand", "blocked"]
UI = {"margin_warn_frac": 0.15, "label": "assumed (interface threshold only)"}


def per_metre(P=PARAMS):
    """(minutes per metre, O2 nominal-minutes per metre) for classes firm, rough, sand, blocked."""
    v = P["speed_kmh"] * 1000.0 / 60.0  # m/min on firm
    tm = [1.0 / (v * P["speed_factor"][k]) for k in CLASSES[:3]] + [math.inf]
    om = [tm[i] * P["o2_factor"][k] for i, k in enumerate(CLASSES[:3])] + [math.inf]
    return np.array(tm), np.array(om)


def cost_grids(cls, res, P=PARAMS):
    """Cell cost arrays for MCP (value * res = cost of crossing one cell straight)."""
    tm, om = per_metre(P)
    return om[cls] * res, tm[cls] * res


def usable_o2(capacity=None, reserve=None, P=PARAMS):
    c = P["o2_capacity_nominal_min"] if capacity is None else capacity
    r = P["reserve_frac"] if reserve is None else reserve
    return c * (1.0 - r)


def field(cost, start):
    m = MCP_Geometric(cost, fully_connected=True)
    cc, _ = m.find_costs([tuple(start)])
    return m, cc


def step_len(a, b, res):
    return res * (math.sqrt(2.0) if (a[0] != b[0] and a[1] != b[1]) else 1.0)


def path_integral(arr, path, res):
    """Same convention as MCP_Geometric: mean of the two cells' per-metre value times step length."""
    s = 0.0
    for a, b in zip(path[:-1], path[1:]):
        s += 0.5 * (arr[a] + arr[b]) / res * step_len(a, b, res)
    return s


def plan_tour(cls, base_rc, targets_rc, res, capacity=None, reserve=None, P=PARAMS, brute_max=7):
    """Plan base -> targets -> base. Returns a dict with order, skipped, legs (paths) and a timeline."""
    o2c, tc = cost_grids(cls, res, P)
    U = usable_o2(capacity, reserve, P)
    base_rc = tuple(base_rc)
    pts = [base_rc] + [tuple(t) for t in targets_rc]
    n = len(targets_rc)
    fields = [field(o2c, p) for p in pts]
    D = np.array([[fields[i][1][pts[j]] for j in range(n + 1)] for i in range(n + 1)])
    home = fields[0][1]

    def tour_cost(order):
        """O2 of base -> order -> base, or inf if any 'can I still get home' check fails."""
        used, cur = 0.0, 0
        for j in order:
            used += D[cur, j + 1]
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
    else:  # greedy nearest-feasible
        cur, used, left = 0, 0.0, set(range(n))
        order = []
        while left:
            ok = [(D[cur, j + 1], j) for j in left if used + D[cur, j + 1] + D[j + 1, 0] <= U]
            if not ok:
                break
            d, j = min(ok)
            used += d; cur = j + 1; order.append(j); left.discard(j)
        best, best_c = tuple(order), (used + D[cur, 0]) if order else 0.0
    skipped = [j for j in range(n) if j not in best]

    # legs and per-step timeline
    stops = [0] + [j + 1 for j in best] + [0]
    path = [base_rc]
    leg_ends = []
    for a, b in zip(stops[:-1], stops[1:]):
        if a == b:
            continue
        seg = [tuple(x) for x in fields[a][0].traceback(pts[b])]
        path += seg[1:]
        leg_ends.append(len(path) - 1)
    tl = {"t_min": [0.0], "o2_used": [0.0], "dist_m": [0.0], "o2_home": [float(home[base_rc])]}
    for a, b in zip(path[:-1], path[1:]):
        L = step_len(a, b, res)
        tl["t_min"].append(tl["t_min"][-1] + 0.5 * (tc[a] + tc[b]) / res * L)
        tl["o2_used"].append(tl["o2_used"][-1] + 0.5 * (o2c[a] + o2c[b]) / res * L)
        tl["dist_m"].append(tl["dist_m"][-1] + L)
        tl["o2_home"].append(float(home[b]))
    used = np.array(tl["o2_used"]); oh = np.array(tl["o2_home"])
    tl["margin"] = list(U - used - oh)
    return {"usable_o2": U, "capacity": P["o2_capacity_nominal_min"] if capacity is None else capacity,
            "reserve_frac": P["reserve_frac"] if reserve is None else reserve,
            "order": list(best), "skipped": skipped, "o2_total": float(used[-1]) if len(path) > 1 else 0.0,
            "time_total_min": tl["t_min"][-1], "dist_total_m": tl["dist_m"][-1],
            "min_margin": float(min(tl["margin"])), "path_rc": path, "leg_end_idx": leg_ends, "timeline": tl,
            "pair_o2": D.tolist(), "brute_force": n <= brute_max, "planned_tour_o2": float(best_c)}


def downsample_max(cls, f):
    """Coarser class grid: each block takes its most costly class (firm < rough < sand < blocked)."""
    H, W = cls.shape[0] // f * f, cls.shape[1] // f * f
    return cls[:H, :W].reshape(H // f, f, W // f, f).max(axis=(1, 3)).astype(np.uint8)


# Placeholder target rule (written before the first run, 2026-11-14): the four points of the locked 300 m
# comparison lattice (aligned to the base) nearest to 600 m east, west, north and south of the base. If such a
# point is blocked on the planning grid, the nearest passable cell is used instead.
PLACEHOLDER_RULE = ("Four points of the 300 m comparison lattice aligned to the base, nearest to 600 m east, west, "
                    "north and south of the base (nearest passable cell if blocked). Placeholder only: step 2 "
                    "(where it is worth sending the astronaut) is not decided.")
PLACEHOLDER_XY = [(600.0, 0.0), (0.0, 600.0), (-600.0, 0.0), (0.0, -600.0)]


def run(scene: str, res_web: float = 4.0):
    from .common import Scene, log, read_json, write_json
    from PIL import Image
    sc = Scene(scene)
    T = np.load(sc.work / "terrain_2m.npz")
    tm = read_json(sc.work / "terrain_2m.json")
    ext = tm["extent_local_m"]; r0 = tm["params"]["grid_res_m"]
    f = int(round(res_web / r0))
    cls = downsample_max(T["class_prior"], f)  # prior = what is known before departure
    res = r0 * f
    H, W = cls.shape
    to_rc = lambda x, y: (int((ext[3] - y) / res), int((x - ext[0]) / res))
    base_rc = to_rc(0.0, 0.0)
    if cls[base_rc] == 3:
        raise RuntimeError("base cell blocked")
    targets = []
    for x, y in PLACEHOLDER_XY:
        rc = to_rc(x, y)
        if cls[rc] == 3:
            free = np.argwhere(cls != 3)
            rc = tuple(free[np.argmin(np.hypot(*(free - rc).T))])
        targets.append(rc)
    plan = plan_tour(cls, base_rc, targets, res)
    xy = lambda rc: [round(ext[0] + (rc[1] + 0.5) * res, 1), round(ext[3] - (rc[0] + 0.5) * res, 1)]
    out_dir = sc.web / "astronaut"; out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(cls, mode="L").save(out_dir / "class_prior_4m.png", optimize=True)
    tmin, omin = per_metre()
    tl = plan["timeline"]
    out = {
        "label": "derived (planned values on the prior; heuristic, not yet reviewed)", "review": "pending",
        "status": "step 3 skeleton",
        "knowledge_state": "prior (CTX 20 m DTM classes, before any recon). Planned values only; not evaluated on the HiRISE reference terrain.",
        "params": PARAMS, "ui": UI,
        "per_metre": {"time_min": tmin[:3].tolist(), "o2_nominal_min": omin[:3].tolist(), "classes": CLASSES},
        "grid": {"res_m": res, "shape": [H, W], "extent_local_m": ext, "class_png": "class_prior_4m.png",
                 "class_png_values": "0 firm, 1 rough, 2 sand, 3 blocked; each 4 m cell = most costly 2 m class inside"},
        "base": {"lon": sc.cfg["base"]["lon"], "lat": sc.cfg["base"]["lat"], "k_coslat": sc.grid.k, "R": 3396190.0,
                 "rc": list(base_rc), "label": "assumed"},
        "targets": [{"id": f"P{i + 1}", "rc": [int(r), int(c)], "xy_m": xy((r, c)),
                     "label": "placeholder target — step ② not decided"} for i, (r, c) in enumerate(targets)],
        "target_rule": PLACEHOLDER_RULE,
        "reference_plan_python": {"usable_o2": plan["usable_o2"], "order": plan["order"], "skipped": plan["skipped"],
                                  "o2_total": round(plan["o2_total"], 2), "time_total_min": round(plan["time_total_min"], 2),
                                  "dist_total_m": round(plan["dist_total_m"], 1), "min_margin": round(plan["min_margin"], 2),
                                  "note": "computed by pipeline/astro_plan.py at the default slider values; the page recomputes the same plan in JS and shows the difference"},
    }
    write_json(out_dir / "astronaut.json", out)
    log(scene, "astro", f"grid {H}x{W} @ {res} m; targets {out['targets']}; plan order {plan['order']} skipped {plan['skipped']} "
                        f"O2 {plan['o2_total']:.1f}/{plan['usable_o2']:.0f} time {plan['time_total_min']:.1f} min dist {plan['dist_total_m']:.0f} m "
                        f"min margin {plan['min_margin']:.1f}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
