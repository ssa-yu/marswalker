"""Step 1: autonomous scout-rover reconnaissance simulation (the "scratch-off" map).

python -m pipeline.rover_sim --scene jezero

The rover starts knowing only the PRIOR terrain (CTX 20 m classes). Each step it "scratches off" a disc of
radius sense_radius_m: inside it the belief map switches to the REFERENCE classes (HiRISE). It plans only
on its belief map. Unobserved cells keep the prior value and the reference value of an unobserved cell is
never read by the planner (enforced by `Belief`; checked in tests).

One loop (MVP_PLAN P6, with an added hard energy rule):
  1. goal = argmax over a 40 m lattice of unobserved area within goal_gain_radius_m, among goals whose
     belief cost from base is between goal_min_frac and outbound_frac of the budget (so each loop uses its
     budget). Deviation from MVP_PLAN P6: its score gain/(cost+100) picked a goal 20 m from the base every
     loop (tested 2026-11-14). Gain is plain unobserved area: no science value (step 2 is not decided).
  Budgets: loop_budget is the hard energy limit; goals and the soft rules below use planning_frac of it,
  the rest is a reserve that only the hard rule (4.) may spend.
  2. outbound on the belief map; replan when a cell in the next 10 steps became impassable or more than
     twice as expensive as planned ("replan" event); soft turn-back when
        spent + belief_cost_home * home_margin >= budget      ("turn_back" event).
  3. return on a cost that charges already-observed cells (1 + revisit_penalty) times, so it takes a
     different way home; if that route does not fit the budget the rover takes the plain belief route
     ("return_direct").
  Margin: home_margin is a floor; the rover multiplies planned costs by the ratio (actual energy paid /
  energy the orbital prior predicted for the same cells) learned on everything it has driven so far.
  4. hard energy rule (guarantee, checked every step): the rover always keeps enough energy to get home
     over terrain it has ALREADY SEEN (exact reference cost of observed cells, or retracing its own path).
     If the next step would break this, it goes home that way ("safety_return").
Costs are paid with the reference cost of the cells actually driven (the rover only ever drives observed
cells, because the next cell is always inside the sensing disc).
All parameters are PROPOSED (status in DATA_LOG R3), labelled assumed; outputs are simulated.
"""
from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np
from scipy.ndimage import distance_transform_edt, uniform_filter
from skimage.graph import MCP_Geometric

from .common import Scene, log, read_json, write_json

PARAMS = {
    "status": "proposed", "review": "pending", "label": "assumed",
    "grid_res_m": 2.0,
    "cost_factor": {"firm": 1.0, "rough": 2.5, "sand": 6.0},  # cost units per metre (MVP_PLAN 5.4)
    "loop_budget": 4000.0,          # cost units per loop = 4 km on firm ground (hard limit, never exceeded)
    "planning_frac": 0.75,          # goals and soft checks use 75 % of it; the rest is the reserve
    "outbound_frac": 0.45,
    "home_margin": 1.15,            # minimum; raised to the learned ratio (see below)
    "adaptive_margin": True,
    "sense_radius_m": 15.0,
    "revisit_penalty": 1.5,
    "base_free_radius_m": 30.0,
    "goal_lattice_m": 40.0,
    "goal_gain_radius_m": 150.0,
    "goal_min_frac": 0.25,
    "gain_stop_frac": 0.05,
    "lookahead_steps": 10,
    "replan_cost_ratio": 2.0,
    "soft_check_every_steps": 20,
    "overlap_buffer_m": 6.0,
    "n_loops": 30,
    "goal_rule": "v2_sector_band",   # S3 version 2 (DATA_LOG round 5); "v1" = original ring rule
    "sector_order": ["N", "S", "E", "W", "NE", "SW", "SE", "NW"],
    "bands_m": {"near": [100.0, 600.0], "mid": [600.0, 1200.0], "far": [1200.0, 1e9]},
    "band_order": ["near", "mid", "far"],
}
SECTOR_BEARING = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}


def choose_goal_v2(li, cand, gain, gain_min, home, sector, dist, P):
    """S3 goal rule v2: loop li -> (sector, band) schedule; highest gain, ties -> cheaper. Returns (rc, how)."""
    order = P["sector_order"]
    sec = order[(li - 1) % len(order)]
    band = P["band_order"][((li - 1) // len(order)) % len(P["band_order"])]
    lo, hi = P["bands_m"][band]
    elig = cand & (gain >= gain_min)
    inband = (dist >= lo) & (dist < hi)
    tries = [(elig & (sector == sec) & inband, f"{sec}/{band}"),
             (elig & (sector == sec), f"{sec}/any-band")]
    k = order.index(sec)
    for j in range(1, len(order)):
        s2 = order[(k + j) % len(order)]
        tries.append((elig & (sector == s2) & inband, f"fallback {s2}/{band}"))
    tries.append((elig, "fallback any"))
    for m, how in tries:
        if m.any():
            g = np.where(m, gain, -1.0)
            best = g.max()
            tie = m & (g >= best - 1.0)
            hc = np.where(tie, home, np.inf)
            return np.unravel_index(np.argmin(hc), hc.shape), how
    return None, "none"

CLASSES = ["firm", "rough", "sand", "blocked"]
N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def cell_cost_array(cls, blk, P):
    f = np.array([P["cost_factor"]["firm"], P["cost_factor"]["rough"], P["cost_factor"]["sand"], np.inf])
    c = f[cls] * P["grid_res_m"]
    c[blk] = np.inf
    return c


class Belief:
    """Rover knowledge. Only reveal() touches reference arrays, and only inside the sensing disc."""

    def __init__(self, T, P):
        self._ref_cost = cell_cost_array(T["class_ref"], T["blocked_rover_ref"], P)
        self._ref_cls = T["class_ref"]
        self.prior_cost = cell_cost_array(T["class_prior"], T["blocked_rover_prior"], P)
        self.paid = 0.0; self.prior_pred = 0.0
        self.cls = T["class_prior"].copy()
        self.cost = cell_cost_array(T["class_prior"], T["blocked_rover_prior"], P)
        self.observed = np.zeros(self.cls.shape, bool)
        self.first_t = np.full(self.cls.shape, -1, np.int32)
        self.ref_reads = 0
        r = int(math.ceil(P["sense_radius_m"] / P["grid_res_m"]))
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        m = (xx ** 2 + yy ** 2) * P["grid_res_m"] ** 2 <= P["sense_radius_m"] ** 2
        self.disc = np.c_[yy[m], xx[m]]

    def reveal(self, rc, t):
        H, W = self.cls.shape
        rr = self.disc[:, 0] + rc[0]; cc = self.disc[:, 1] + rc[1]
        k = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        rr, cc = rr[k], cc[k]
        new = ~self.observed[rr, cc]
        rn, cn = rr[new], cc[new]
        self.observed[rn, cn] = True
        self.first_t[rn, cn] = t
        self.cls[rn, cn] = self._ref_cls[rn, cn]
        self.cost[rn, cn] = self._ref_cost[rn, cn]
        self.ref_reads += int(new.sum())
        return int(new.sum())

    def true_step_cost(self, a, b, res):
        """Energy actually spent between neighbouring cells a -> b. Only legal on observed cells."""
        assert self.observed[a] and self.observed[b], "rover drove onto an unobserved cell"
        d = res * (math.sqrt(2) if (a[0] != b[0] and a[1] != b[1]) else 1.0)
        c = 0.5 * (self._ref_cost[a] + self._ref_cost[b]) / res * d
        pc = 0.5 * (self.prior_cost[a] + self.prior_cost[b]) / res * d
        if np.isfinite(pc):
            self.paid += c; self.prior_pred += pc
        return c

    def margin(self, P):
        """Learned: how much more the driven terrain cost than the orbital prior predicted."""
        if not P.get("adaptive_margin") or self.prior_pred <= 0:
            return P["home_margin"]
        return max(P["home_margin"], self.paid / self.prior_pred)

    def known_cost(self):
        c = self.cost.copy()
        c[~self.observed] = np.inf
        return c


def path_cost(cost, path, res):
    s = 0.0
    for a, b in zip(path[:-1], path[1:]):
        d = res * (math.sqrt(2) if (a[0] != b[0] and a[1] != b[1]) else 1.0)
        s += 0.5 * (cost[a] + cost[b]) / res * d
    return s


def plan(cost, start, goal):
    """Min-cost path start->goal on `cost` (cell cost = factor*res). Returns (path list, cost) or (None, inf)."""
    m = MCP_Geometric(cost, fully_connected=True)
    cc, _ = m.find_costs([start], [goal])
    if not np.isfinite(cc[goal]):
        return None, math.inf
    p = [tuple(x) for x in m.traceback(goal)]
    return p, float(cc[goal])


def field_from(cost, start):
    m = MCP_Geometric(cost, fully_connected=True)
    cc, _ = m.find_costs([start])
    return m, cc


def simulate(T, P, base_rc, log_fn=print):
    res = P["grid_res_m"]; B = P["loop_budget"]; Bp = B * P["planning_frac"]
    bel = Belief(T, P)
    H, W = bel.cls.shape
    t = 0
    bel.reveal(base_rc, t)
    yy, xx = np.mgrid[0:H, 0:W]
    near_base = (np.hypot(yy - base_rc[0], xx - base_rc[1]) * res) <= P["base_free_radius_m"]
    lat = int(P["goal_lattice_m"] / res)
    lattice = np.zeros((H, W), bool); lattice[lat // 2::lat, lat // 2::lat] = True
    dxm = (xx - base_rc[1]) * res; dym = (base_rc[0] - yy) * res
    dist = np.hypot(dxm, dym)
    bearing = (np.degrees(np.arctan2(dxm, dym)) + 360) % 360
    names = list(SECTOR_BEARING)
    sector = np.array(names)[((bearing + 22.5) // 45).astype(int) % 8]
    gw = int(round(math.sqrt(math.pi) * P["goal_gain_radius_m"] / res))  # square of equal area
    max_step = max(P["cost_factor"].values()) * res * math.sqrt(2)
    loops, gain0 = [], None
    for li in range(1, P["n_loops"] + 1):
        t0_loop = t
        obs_before = int(bel.observed.sum())
        mh, home = field_from(bel.cost, base_rc)
        un = (~bel.observed).astype("float32")
        unobs = uniform_filter(un, gw, mode="constant") * gw * gw * res * res
        unobs_wide = uniform_filter(un, 3 * gw, mode="constant") * 9 * gw * gw * res * res
        cand = lattice & np.isfinite(home) & (home <= P["outbound_frac"] * Bp) & (bel.cost < np.inf)
        how = "v1"
        if P.get("goal_rule", "v1") == "v1":
            ring = cand & (home >= P["goal_min_frac"] * Bp)
            if ring.any():
                cand = ring
            if not cand.any():
                log_fn(f"loop {li}: no reachable candidate"); break
            score = np.where(cand, unobs + 0.25 * unobs_wide, -1)
            g = np.unravel_index(np.argmax(score), score.shape)
            if gain0 is None:
                gain0 = float(unobs[g])
            if unobs[g] < P["gain_stop_frac"] * gain0:
                log_fn(f"loop {li}: nothing left to explore (gain {unobs[g]:.0f} m2)"); break
        else:
            gain = unobs + 0.25 * unobs_wide
            if gain0 is None:
                gain0 = float(np.where(cand, gain, -1).max())
            g, how = choose_goal_v2(li, cand, gain, P["gain_stop_frac"] * gain0, home, sector, dist, P)
            if g is None:
                log_fn(f"loop {li}: nothing left to explore"); break
        path = [tuple(x) for x in mh.traceback(g)]
        planned_cost = {c: bel.cost[c] for c in path}
        mode = "out"; cur = base_rc; spent = 0.0
        hist = [cur]; modes = ["out"]; ts = [t]; events = []
        known_home = None; known_stamp = -1
        idx = 0; steps_since_soft = 0
        new_cells_loop = 0
        out_cells = set()
        safety = False

        def safe_home_cost():
            nonlocal known_home, known_stamp
            v = known_home[cur] if known_home is not None and np.isfinite(known_home[cur]) else math.inf
            return min(v, spent_retrace())

        def spent_retrace():
            return spent if not safety else math.inf

        def refresh_known():
            nonlocal known_home, known_stamp
            _, known_home = field_from(bel.known_cost(), base_rc)
            known_stamp = t

        while True:
            new_cells_loop += bel.reveal(cur, t)
            if cur == base_rc and len(hist) > 1:
                break
            # ---- hard energy rule ---------------------------------------------------------------------
            if not safety:
                # 2 x max_step: the next step costs <= max_step AND can lengthen the way home by <= max_step.
                # (round-5 fix: with 1 x max_step the v2 run overshot the budget by <= 4.8 units in 5 loops.)
                if spent + safe_home_cost() + 2 * max_step >= B:
                    refresh_known()
                    if spent + safe_home_cost() + 2 * max_step >= B:
                        kp, kc = plan(bel.known_cost(), cur, base_rc)
                        rp = hist[::-1]
                        rc_ = path_cost(bel.cost, rp, res)
                        path = kp if (kp is not None and kc <= rc_) else rp
                        idx = 0; mode = "safety"; safety = True
                        events.append({"t": t, "type": "safety_return", "spent": round(spent, 1)})
            # ---- goal / turn-back / replan --------------------------------------------------------------
            if not safety:
                if mode == "out" and cur == g:
                    events.append({"t": t, "type": "goal_reached", "spent": round(spent, 1)})
                    mode = "return_start"
                if mode == "out":
                    steps_since_soft += 1
                    if steps_since_soft >= P["soft_check_every_steps"]:
                        steps_since_soft = 0
                        _, hc = plan(bel.cost, cur, base_rc)
                        if spent + hc * bel.margin(P) >= Bp:
                            events.append({"t": t, "type": "turn_back", "spent": round(spent, 1)})
                            mode = "return_start"
                if mode == "return_start":
                    pen = bel.cost * np.where(bel.observed & ~near_base, 1 + P["revisit_penalty"], 1.0)
                    pp, _ = plan(pen, cur, base_rc)
                    dp, dc = plan(bel.cost, cur, base_rc)
                    if pp is not None and spent + path_cost(bel.cost, pp, res) * bel.margin(P) < Bp:
                        path, mode = pp, "return"
                    else:
                        path, mode = dp, "return_direct"
                        events.append({"t": t, "type": "return_direct", "spent": round(spent, 1)})
                    planned_cost = {c: bel.cost[c] for c in path}
                    idx = 0
                    if mode == "return" and spent + dc * bel.margin(P) >= B:
                        pass
                # lookahead replan
                ahead = path[idx + 1: idx + 1 + P["lookahead_steps"]]
                bad = [c for c in ahead if not np.isfinite(bel.cost[c]) or bel.cost[c] > P["replan_cost_ratio"] * planned_cost.get(c, bel.cost[c])]
                if bad:
                    target = g if mode == "out" else base_rc
                    if mode == "return":
                        cst = bel.cost * np.where(bel.observed & ~near_base, 1 + P["revisit_penalty"], 1.0)
                    else:
                        cst = bel.cost
                    np_, nc = plan(cst, cur, target)
                    if np_ is None and mode == "out":
                        events.append({"t": t, "type": "goal_unreachable"})
                        mode = "return_start"
                        continue
                    if np_ is None:
                        np_, nc = plan(bel.cost, cur, base_rc)
                        mode = "return_direct"
                    events.append({"t": t, "type": "replan", "reason": "impassable_ahead" if any(not np.isfinite(bel.cost[c]) for c in bad) else "cost_x2_ahead"})
                    path = np_; idx = 0
                    planned_cost = {c: bel.cost[c] for c in path}
                    if mode == "return" and spent + path_cost(bel.cost, path, res) * bel.margin(P) >= Bp:
                        dp, _ = plan(bel.cost, cur, base_rc)
                        path = dp; mode = "return_direct"; planned_cost = {c: bel.cost[c] for c in path}
                        events.append({"t": t, "type": "return_direct", "spent": round(spent, 1)})
                if mode == "return" and steps_since_soft >= 0:
                    steps_since_soft += 1
                    if steps_since_soft >= P["soft_check_every_steps"]:
                        steps_since_soft = 0
                        rem = path_cost(bel.cost, path[idx:], res)
                        if spent + rem * bel.margin(P) >= Bp:
                            dp, _ = plan(bel.cost, cur, base_rc)
                            path = dp; idx = 0; mode = "return_direct"; planned_cost = {c: bel.cost[c] for c in path}
                            events.append({"t": t, "type": "return_direct", "spent": round(spent, 1)})
            # ---- step -----------------------------------------------------------------------------------
            if idx + 1 >= len(path):
                # end of a path that is not base (should not happen): go home directly
                dp, _ = plan(bel.known_cost(), cur, base_rc)
                path = dp; idx = 0; mode = "safety"; safety = True
                events.append({"t": t, "type": "safety_return", "spent": round(spent, 1), "reason": "path_end"})
                continue
            nxt = path[idx + 1]
            if not bel.observed[nxt]:
                bel.reveal(nxt, t)  # cannot happen with 2 m steps < sensing radius; kept as a guard
            if not np.isfinite(bel.cost[nxt]):
                raise RuntimeError(f"planned step into impassable cell {nxt} (mode {mode})")
            spent += bel.true_step_cost(cur, nxt, res)
            cur = nxt; idx += 1; t += 1
            hist.append(cur); modes.append("out" if mode == "out" else ("return" if mode == "return" else ("forced" if mode in ("return_direct", "safety") else mode)))
            ts.append(t)
            if mode == "out":
                out_cells.add(cur)
            if len(hist) > 20000:
                raise RuntimeError("loop too long")
        # ---- loop stats ---------------------------------------------------------------------------------
        hist_a = np.array(hist)
        md = np.array(modes)
        L = 0.0
        for a, b in zip(hist[:-1], hist[1:]):
            L += res * (math.sqrt(2) if (a[0] != b[0] and a[1] != b[1]) else 1.0)
        outm = np.zeros((H, W), bool)
        oi = hist_a[md == "out"]
        if len(oi):
            outm[oi[:, 0], oi[:, 1]] = True
        ret = hist_a[md != "out"]
        ret = np.array([c for c in ret if not near_base[tuple(c)]]) if len(ret) else ret
        if len(oi) and len(ret):
            dist = distance_transform_edt(~outm) * res
            overlap = float(np.mean(dist[ret[:, 0], ret[:, 1]] <= P["overlap_buffer_m"]))
        else:
            overlap = None
        rec = {"id": li, "goal_rc": [int(g[0]), int(g[1])], "goal_rule": how, "t0": t0_loop, "t1": t,
               "cost_total": round(spent, 1), "budget": B, "length_m": round(L, 1),
               "new_observed_m2": round(new_cells_loop * res * res, 0),
               "observed_total_m2": round(float(bel.observed.sum()) * res * res, 0),
               "overlap_ratio": None if overlap is None else round(overlap, 3),
               "n_replan": sum(e["type"] == "replan" for e in events),
               "n_turn_back": sum(e["type"] == "turn_back" for e in events),
               "n_return_direct": sum(e["type"] == "return_direct" for e in events),
               "n_safety_return": sum(e["type"] == "safety_return" for e in events),
               "goal_reached": any(e["type"] == "goal_reached" for e in events),
               "margin_after_loop": round(bel.margin(P), 3),
               "events": events, "path_rc": hist, "modes": modes, "t": ts}
        loops.append(rec)
        log_fn(f"loop {li}: goal {g} cost {spent:.0f}/{B:.0f} len {L:.0f} m new {rec['new_observed_m2']:.0f} m2 "
               f"margin {rec['margin_after_loop']} overlap {rec['overlap_ratio']} replan {rec['n_replan']} turn {rec['n_turn_back']} direct {rec['n_return_direct']} safety {rec['n_safety_return']}")
    return bel, loops


def simplify(xy, tol):
    """Douglas-Peucker on an (n,2) array; returns kept indices."""
    keep = np.zeros(len(xy), bool); keep[0] = keep[-1] = True
    stack = [(0, len(xy) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = xy[i], xy[j]; ab = b - a; n = np.hypot(*ab)
        seg = xy[i + 1:j]
        d = np.abs(ab[0] * (seg[:, 1] - a[1]) - ab[1] * (seg[:, 0] - a[0])) / n if n > 0 else np.hypot(*(seg - a).T)
        k = int(np.argmax(d))
        if d[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return np.nonzero(keep)[0]


def run(scene: str, n_loops: int | None = None):
    sc = Scene(scene)
    P = dict(PARAMS)
    if n_loops:
        P["n_loops"] = n_loops
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    tm = read_json(sc.work / "terrain_2m.json")
    ext = tm["extent_local_m"]; res = P["grid_res_m"]
    base_rc = (int((ext[3] - 0.0) / res), int((0.0 - ext[0]) / res))
    t0 = time.time()
    bel, loops = simulate(T, P, base_rc, log_fn=lambda m: log(scene, "rover", m))
    secs = round(time.time() - t0, 1)
    np.savez_compressed(sc.work / "recon_state.npz", first_t=bel.first_t, observed=bel.observed, belief_cls=bel.cls)
    H, W = bel.cls.shape
    aoi_area = H * W * res * res
    ref = T["class_ref"]
    # stats per loop (coverage curve etc.)
    for L in loops:
        obs = (bel.first_t >= 0) & (bel.first_t <= L["t1"])
        L["observed_frac_aoi"] = round(float(obs.mean()), 4)
        bl = np.where(obs, ref, T["class_prior"])
        L["belief_agrees_with_reference_frac"] = round(float(np.mean(bl == ref)), 4)
    out = {"params": P, "terrain_params": tm["params"], "base_rc": list(base_rc), "extent_local_m": ext,
           "aoi_area_m2": aoi_area, "seconds": secs, "ref_cells_revealed": bel.ref_reads,
           "label": "simulated", "review": "pending",
           "initial_belief_agrees_with_reference_frac": round(float(np.mean(T["class_prior"] == ref)), 4),
           "loops": loops}
    write_json(sc.work / "recon_loops.json", out)
    log(scene, "rover", f"{len(loops)} loops in {secs} s; observed {loops[-1]['observed_frac_aoi'] if loops else 0:.1%} of AOI")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    ap.add_argument("--loops", type=int, default=None)
    a = ap.parse_args()
    run(a.scene, a.loops)
