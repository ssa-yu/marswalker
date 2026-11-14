# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Step 1, rover goal rule VERSION 3 (literature methods; manager 2026-11-14, direction.md "第三版定案" R1-R8).

python -m pipeline.rover_v3      # main AOI, 30 loops, run ONCE -> data_work/jezero/v3/recon_loops.json, recon_state.npz

Designed after seeing version 2's coverage, repeat coverage and loop 24; version 2 (T1 rerun) stays the
pre-registered record. Unchanged from version 2 (rover_sim.PARAMS): budget 4,000, planning share 0.75, cost
firm 1 / rough 2.5 / sand 6, sensing 15 m, 30 loops, 2 m grid, 40 m candidate lattice, no penalty within 30 m of
the habitat, margin floor 1.15, soft check every 20 steps, hard energy rule (two-step slack, seen cells only),
return penalty rho = 1.5, the data boundary (arrays only; no Perseverance file).

R1 expected cost (Sofman et al. 2006; Beta-Bernoulli): for prior class k in {firm, rough}: n_k = seen cells whose
   prior is k, s_k = those whose reference is sand; p_k = (s_k + alpha0) / (n_k + alpha0 + beta0), alpha0 = 1,
   beta0 = 4. Unseen cell: E[c] per metre = (1 - p_k) c_k + p_k * 6; unseen and prior-blocked: blocked; seen: true
   cost. p_k recomputed at the start of every loop and at every (re)selection. All planning (candidate feasibility,
   outbound, return, soft turn-back estimate) on E[c]; hard energy rule unchanged. Learned margin = paid / expected
   cost of the same driven cells (E[c] they had as unseen cells, current p_k), floor 1.15.
R2 repeat penalty (Burgard et al. 2005): c'(x) = E[c](x) (1 + 1.5 seen(x)), seen = seen in any loop, except within
   30 m of the habitat. Outbound AND return paths planned on c'; feasibility / budget on E[c] x margin.
R3 candidates (Yamauchi 1997): frontier cell = seen, belief-passable, with an unseen 8-neighbour; 8-connected
   frontier components < 3 cells ignored. Candidate = a frontier cell itself (manager 13th update, after the
   stopped run 1: the original "40 m lattice point within 20 m of a frontier cell" cannot be met beyond the first
   lattice points with 15 m sensing), not the rover's current cell; a candidate with loop gain 0 is not feasible.
R4 score (Singh et al. 2009; Bircher et al. 2016): from the current cell s, Dijkstra on c' gives the outbound paths;
   E[s->q] = E[c] summed along that c' path; E[q->home] = least E[c] cost home (field on E[c]).
   feasible: spent + (E[s->q] + E[q->home]) x margin <= 0.75 x 4,000. Coarse value A150(q) / (E[s->q] + E[q->home])
   (A150 = unseen area within 150 m, version-2 filter); top K = 30 feasible. For each: outbound path (traceback),
   return q -> habitat on c', loop gain G(q) = unseen area within 15 m of outbound U return (dilation & ~seen,
   each cell once). Score G / (E[s->q] + E[q->home]); max; ties within 1 m2 -> smaller E[s->q].
R5 loop: select from the habitat (R4) and drive the outbound path, revealing every step, hard rule every step.
   Every 20 steps: soft turn-back (spent + E[home] x margin >= Bp) as version 2; then if the expected remaining
   cost to the target > its estimate at selection x 1.5 -> reselect (R4) from the current cell. A path cell that
   became impassable -> reselect. At the target -> reselect from there. No feasible candidate -> return home by
   the version-2 return rule (different way home on c'; if it does not fit, least-E path) with its version-2
   lookahead / soft checks on E[c] and c'.
R6 not done: direction balancing, orienteering, D* Lite, any tuning on coverage / repeat coverage / unlocks.
Readings taken where R1-R5 are silent (written before the run, listed in DATA_LOG): see READINGS.
"""
from __future__ import annotations

import math
import time

import numpy as np
from scipy.ndimage import distance_transform_edt, label, uniform_filter
from skimage.graph import MCP_Geometric

from .rover_sim import PARAMS as PARAMS_V2, Belief, cell_cost_array, path_cost, plan

PARAMS = dict(PARAMS_V2)
PARAMS.update({"status": "locked (manager 2026-11-14, version 3)", "goal_rule": "v3_literature",
               "alpha0": 1.0, "beta0": 4.0, "rho": 1.5, "K": 30, "reselect_ratio": 1.5,
               "frontier_min_cells": 3, "candidates": "frontier cells (13th update)", "corridor_m": 15.0})
READINGS = {
    "candidate_not_current_cell": "the rover's current cell is never a candidate (else it would 'reach' it at once, forever)",
    "feasible_before_top_k": "the K = 30 coarse shortlist is taken among feasible candidates; first-pass feasibility uses the coarse quantities E[s->q] (E[c] summed along the c' tree from s) and E[q->home] (E[c] home field); the chosen candidate is re-checked with E[c] summed along its traced outbound path, else the next by score (manager 12th update)",
    "return_for_gain": "the return path used for G(q) is planned on c' as it is at selection time (seen cells so far)",
    "outbound_lookahead": "outbound: the version-2 'cost x2 ahead' path replan is replaced by R5's 1.5x reselect; an impassable cell on the remaining path triggers a reselect at once",
    "score_home_term": "E[q->home] in score and feasibility = least E[c] cost home (same as the coarse value)",
    "margin_expected": "margin denominator: E[c] of each driven step's two cells as unseen cells, with p_k current at that step",
}
SAND = 2


class BeliefV3(Belief):
    def __init__(self, T, P):
        super().__init__(T, P)
        self.P = P
        self.prior_cls = T["class_prior"].astype(np.int8)
        self.prior_blk = T["blocked_rover_prior"].astype(bool) | (self.prior_cls == 3)
        self.n = np.zeros(2); self.s = np.zeros(2)
        self.update_p()

    def reveal(self, rc, t):
        H, W = self.cls.shape
        rr = self.disc[:, 0] + rc[0]; cc = self.disc[:, 1] + rc[1]
        k = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        rr, cc = rr[k], cc[k]
        new = ~self.observed[rr, cc]
        rn, cn = rr[new], cc[new]
        pk = self.prior_cls[rn, cn]
        sand = self._ref_cls[rn, cn] == SAND          # inside the sensing disc only (legal read)
        for j in (0, 1):
            self.n[j] += int((pk == j).sum()); self.s[j] += int(((pk == j) & sand).sum())
        return super().reveal(rc, t)

    def update_p(self):
        a, b = self.P["alpha0"], self.P["beta0"]
        self.p = (self.s + a) / (self.n + a + b)
        cf = self.P["cost_factor"]; res = self.P["grid_res_m"]
        e = np.array([(1 - self.p[0]) * cf["firm"] + self.p[0] * cf["sand"],
                      (1 - self.p[1]) * cf["rough"] + self.p[1] * cf["sand"], cf["sand"], np.inf]) * res
        self.e_unseen = e[np.clip(self.prior_cls, 0, 3)]
        self.e_unseen[self.prior_blk] = np.inf

    def E(self):
        return np.where(self.observed, self.cost, self.e_unseen)

    def true_step_cost(self, a, b, res):
        assert self.observed[a] and self.observed[b], "rover drove onto an unobserved cell"
        d = res * (math.sqrt(2) if (a[0] != b[0] and a[1] != b[1]) else 1.0)
        c = 0.5 * (self._ref_cost[a] + self._ref_cost[b]) / res * d
        pc = 0.5 * (self.e_unseen[a] + self.e_unseen[b]) / res * d
        if np.isfinite(pc):
            self.paid += c; self.prior_pred += pc
        return c


def tree_sum(cc, tb, offsets, step_cost, res):
    """Sum of step_cost (cell cost arrays, MCP convention) along each cell's MCP traceback to the start."""
    H, W = cc.shape
    rr, cl = np.mgrid[0:H, 0:W]
    ok = np.isfinite(cc) & (tb >= 0)
    t = np.where(ok, tb, 0)
    pr = np.clip(np.where(ok, rr - offsets[t, 0], rr), 0, H - 1); pc = np.clip(np.where(ok, cl - offsets[t, 1], cl), 0, W - 1)
    L = res * np.where((pr != rr) & (pc != cl), math.sqrt(2.0), np.where((pr != rr) | (pc != cl), 1.0, 0.0))
    sc = np.where(np.isfinite(step_cost), step_cost, 0.0)
    acc = np.where(ok, 0.5 * (sc + sc[pr, pc]) / res * L, 0.0).ravel()
    ptr = (pr * W + pc).ravel()
    for _ in range(int(math.ceil(math.log2(H * W))) + 1):
        acc = acc + acc[ptr]; ptr = ptr[ptr]
    out = acc.reshape(H, W)
    out[~np.isfinite(cc)] = np.inf
    return out


def needs_reselect(E, path, idx, est, ratio, res):
    """R5 (2): expected remaining cost to the target (E[c] along the rest of the path) > ratio x estimate at selection."""
    return path_cost(E, path[idx:], res) > ratio * est


def frontier_cells(bel, P):
    obs = bel.observed
    pas = np.isfinite(bel.cost) & obs
    un = ~obs
    nb = np.zeros_like(un)
    H, W = un.shape
    pad = np.pad(un, 1, constant_values=False)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr or dc:
                nb |= pad[1 + dr:1 + dr + H, 1 + dc:1 + dc + W]
    fr = pas & nb
    lab, n = label(fr, structure=np.ones((3, 3), int))
    if n:
        sz = np.bincount(lab.ravel()); keep = sz >= P["frontier_min_cells"]; keep[0] = False
        fr = keep[lab]
    return fr


def corridor_gain(paths, observed, res, radius_m):
    """Unseen area (m2) within radius of the union of the paths' cells; each cell counted once."""
    pts = np.array([c for p in paths for c in p])
    r = int(math.ceil(radius_m / res))
    H, W = observed.shape
    r0, c0 = max(pts[:, 0].min() - r, 0), max(pts[:, 1].min() - r, 0)
    r1, c1 = min(pts[:, 0].max() + r + 1, H), min(pts[:, 1].max() + r + 1, W)
    m = np.ones((r1 - r0, c1 - c0), bool)
    m[pts[:, 0] - r0, pts[:, 1] - c0] = False
    near = distance_transform_edt(m) * res <= radius_m
    return float((near & ~observed[r0:r1, c0:c1]).sum()) * res * res


class Selector:
    """R3 + R4 from the current cell. Returns dict(goal, path, est) or None."""

    def __init__(self, P, base_rc, shape):
        self.P = P; self.base = base_rc
        res = P["grid_res_m"]; H, W = shape
        yy, xx = np.mgrid[0:H, 0:W]
        self.near_base = (np.hypot(yy - base_rc[0], xx - base_rc[1]) * res) <= P["base_free_radius_m"]
        lat = int(P["goal_lattice_m"] / res)
        self.lattice = np.zeros(shape, bool); self.lattice[lat // 2::lat, lat // 2::lat] = True
        self.gw = int(round(math.sqrt(math.pi) * P["goal_gain_radius_m"] / res))

    def cprime(self, bel, E):
        return E * np.where(bel.observed & ~self.near_base, 1 + self.P["rho"], 1.0)

    def select(self, bel, cur, spent, Bp, log=None):
        P = self.P; res = P["grid_res_m"]
        bel.update_p()
        E = bel.E(); cp = self.cprime(bel, E)
        ms = MCP_Geometric(cp, fully_connected=True)
        cc_s, tb_s = ms.find_costs([tuple(cur)])
        Es = tree_sum(cc_s, tb_s, np.asarray(ms.offsets), E, res)
        _, Eh = MCP_Geometric(E, fully_connected=True).find_costs([self.base])
        mh = MCP_Geometric(cp, fully_connected=True); mh.find_costs([self.base])
        fr = frontier_cells(bel, P)
        if not fr.any():
            return None, {"n_cand": 0}
        # manager 13th update: candidates are the frontier cells themselves (Yamauchi 1997), not the 40 m lattice
        cand = fr & np.isfinite(E)
        cand[tuple(cur)] = False
        tot = Es + Eh
        feas = cand & np.isfinite(tot) & (spent + tot * bel.margin(P) <= Bp)
        if not feas.any():
            return None, {"n_cand": int(cand.sum()), "n_feasible": 0}
        un = (~bel.observed).astype("float32")
        A = uniform_filter(un, self.gw, mode="constant") * self.gw * self.gw * res * res
        rr, cl = np.nonzero(feas)
        coarse = A[rr, cl] / np.maximum(tot[rr, cl], 1e-9)
        top = np.argsort(-coarse, kind="stable")[:P["K"]]
        scored = []
        for i in top:
            q = (int(rr[i]), int(cl[i]))
            out = [tuple(int(v) for v in x) for x in ms.traceback(q)]
            back = [tuple(int(v) for v in x) for x in mh.traceback(q)][::-1]
            G = corridor_gain([out, back], bel.observed, res, P["corridor_m"])
            if G <= 0:                                              # 13th update: zero loop gain = not feasible
                continue
            scored.append({"goal": q, "path": out, "est": float(Es[q]), "score": float(G / max(tot[q], 1e-9)), "gain_m2": G,
                           "home_E": float(Eh[q]), "tot": float(tot[q])})
        # order: score, ties (within 1 m2 of gain) -> smaller E[s->q]
        order = []
        for c in sorted(scored, key=lambda c: -c["score"]):
            order.append(c)
        best = None
        rest = list(order)
        while rest:
            top_c = rest[0]
            tie = [c for c in rest if abs(c["score"] - top_c["score"]) * top_c["tot"] <= 1.0]
            c = min(tie, key=lambda c: c["est"])
            rest.remove(c)
            # manager 12th update (2): final feasibility on the traced outbound path's E[c] cost
            e_path = path_cost(E, c["path"], res)
            if spent + (e_path + c["home_E"]) * bel.margin(P) <= Bp:
                best = c; best["est"] = e_path
                break
        info = {"n_cand": int(cand.sum()), "n_feasible": int(feas.sum())}
        return best, info


def simulate(T, P, base_rc, log_fn=print):
    res = P["grid_res_m"]; B = P["loop_budget"]; Bp = B * P["planning_frac"]
    bel = BeliefV3(T, P)
    H, W = bel.cls.shape
    t = 0
    base_rc = tuple(base_rc)
    bel.reveal(base_rc, t)
    sel = Selector(P, base_rc, (H, W))
    max_step = max(P["cost_factor"].values()) * res * math.sqrt(2)
    loops = []
    for li in range(1, P["n_loops"] + 1):
        t0_loop = t
        bel.update_p()
        cur = base_rc; spent = 0.0
        hist = [cur]; modes = ["out"]; ts = [t]; events = []; targets = []
        new_cells_loop = 0
        safety = False
        known_home = None
        g = None; path = None; est = None; idx = 0; mode = "out"
        steps_since_soft = 0; planned_cost = {}

        def choose(reason):
            nonlocal g, path, est, idx, mode, planned_cost
            b, info = sel.select(bel, cur, spent, Bp)
            events.append({"t": t, "type": "select", "reason": reason, "spent": round(spent, 1), **info,
                           **({"goal": list(b["goal"]), "score": round(b["score"], 4), "gain_m2": b["gain_m2"], "est": round(b["est"], 1)} if b else {})})
            if b is None:
                mode = "return_start"; g = None
                return
            g, path, est, idx, mode = b["goal"], b["path"], b["est"], 0, "out"
            targets.append(list(g))

        def refresh_known():
            nonlocal known_home
            known_home, _ = MCP_Geometric(bel.known_cost(), fully_connected=True).find_costs([base_rc])  # costs, not traceback (run-2 bug)

        def safe_home_cost():
            v = known_home[cur] if known_home is not None and np.isfinite(known_home[cur]) else math.inf
            return min(v, spent if not safety else math.inf)

        new_cells_loop += bel.reveal(cur, t)
        choose("loop_start")
        while True:
            new_cells_loop += bel.reveal(cur, t)
            if cur == base_rc and len(hist) > 1 and mode != "out":
                break
            # ---- hard energy rule (unchanged) --------------------------------------------------------------
            if not safety and spent + safe_home_cost() + 2 * max_step >= B:
                refresh_known()
                if spent + safe_home_cost() + 2 * max_step >= B:
                    kp, kc = plan(bel.known_cost(), cur, base_rc)
                    rp = hist[::-1]
                    path = kp if (kp is not None and kc <= path_cost(bel.cost, rp, res)) else rp
                    idx = 0; mode = "safety"; safety = True
                    events.append({"t": t, "type": "safety_return", "spent": round(spent, 1)})
            if not safety:
                if mode == "out" and cur == g:
                    events.append({"t": t, "type": "goal_reached", "spent": round(spent, 1)})
                    choose("goal_reached")
                if mode == "out":
                    rest = path[idx + 1:]
                    if any(not np.isfinite(bel.cost[c]) for c in rest):
                        events.append({"t": t, "type": "replan", "reason": "impassable_on_path"})
                        choose("impassable_on_path")
                if mode == "out":
                    steps_since_soft += 1
                    if steps_since_soft >= P["soft_check_every_steps"]:
                        steps_since_soft = 0
                        bel.update_p()
                        E = bel.E()
                        _, hc = plan(E, cur, base_rc)
                        if spent + hc * bel.margin(P) >= Bp:
                            events.append({"t": t, "type": "turn_back", "spent": round(spent, 1)})
                            mode = "return_start"
                        else:
                            if needs_reselect(E, path, idx, est, P["reselect_ratio"], res):
                                events.append({"t": t, "type": "replan", "reason": "cost_x1.5"})
                                choose("cost_x1.5")
                if mode == "return_start":
                    bel.update_p()
                    E = bel.E(); cp = sel.cprime(bel, E)
                    pp, _ = plan(cp, cur, base_rc)
                    if pp is not None and spent + path_cost(E, pp, res) * bel.margin(P) < Bp:
                        path, mode = pp, "return"
                    else:
                        path, _ = plan(E, cur, base_rc); mode = "return_direct"
                        events.append({"t": t, "type": "return_direct", "spent": round(spent, 1)})
                    planned_cost = {c: E[c] for c in path}
                    idx = 0; steps_since_soft = 0
                if mode in ("return", "return_direct"):
                    E = bel.E()
                    ahead = path[idx + 1: idx + 1 + P["lookahead_steps"]]
                    bad = [c for c in ahead if not np.isfinite(E[c]) or E[c] > P["replan_cost_ratio"] * planned_cost.get(c, E[c])]
                    if bad:
                        bel.update_p(); E = bel.E()
                        cst = sel.cprime(bel, E) if mode == "return" else E
                        np_, _ = plan(cst, cur, base_rc)
                        if np_ is None:
                            np_, _ = plan(E, cur, base_rc); mode = "return_direct"
                        events.append({"t": t, "type": "replan", "reason": "impassable_ahead" if any(not np.isfinite(E[c]) for c in bad) else "cost_x2_ahead"})
                        path = np_; idx = 0; planned_cost = {c: E[c] for c in path}
                        if mode == "return" and spent + path_cost(E, path, res) * bel.margin(P) >= Bp:
                            path, _ = plan(E, cur, base_rc); mode = "return_direct"; planned_cost = {c: E[c] for c in path}
                            events.append({"t": t, "type": "return_direct", "spent": round(spent, 1)})
                    if mode == "return":
                        steps_since_soft += 1
                        if steps_since_soft >= P["soft_check_every_steps"]:
                            steps_since_soft = 0
                            if spent + path_cost(E, path[idx:], res) * bel.margin(P) >= Bp:
                                path, _ = plan(E, cur, base_rc); idx = 0; mode = "return_direct"; planned_cost = {c: E[c] for c in path}
                                events.append({"t": t, "type": "return_direct", "spent": round(spent, 1)})
            # ---- step ---------------------------------------------------------------------------------------
            if path is None or idx + 1 >= len(path):
                if cur == base_rc:
                    break
                dp, _ = plan(bel.known_cost(), cur, base_rc)
                path = dp; idx = 0; mode = "safety"; safety = True
                events.append({"t": t, "type": "safety_return", "spent": round(spent, 1), "reason": "path_end"})
                continue
            nxt = path[idx + 1]
            if not bel.observed[nxt]:
                bel.reveal(nxt, t)
            if not np.isfinite(bel.cost[nxt]):
                raise RuntimeError(f"planned step into impassable cell {nxt} (mode {mode})")
            spent += bel.true_step_cost(cur, nxt, res)
            cur = nxt; idx += 1; t += 1
            hist.append(cur); modes.append("out" if mode == "out" else ("return" if mode == "return" else "forced"))
            ts.append(t)
            if len(hist) > 40000:
                raise RuntimeError("loop too long")
        L = sum(res * (math.sqrt(2) if (a[0] != b[0] and a[1] != b[1]) else 1.0) for a, b in zip(hist[:-1], hist[1:]))
        bel.update_p()
        rec = {"id": li, "goal_rc": targets[0] if targets else None, "targets_rc": targets, "goal_rule": "v3_literature",
               "t0": t0_loop, "t1": t, "cost_total": round(spent, 1), "budget": B, "length_m": round(L, 1),
               "new_observed_m2": round(new_cells_loop * res * res, 0),
               "observed_total_m2": round(float(bel.observed.sum()) * res * res, 0),
               "n_targets_selected": len(targets),
               "n_goals_reached": sum(e["type"] == "goal_reached" for e in events),
               "goal_reached": any(e["type"] == "goal_reached" for e in events),
               "n_reselect": sum(e["type"] == "select" and e["reason"] not in ("loop_start",) for e in events),
               "n_replan": sum(e["type"] == "replan" for e in events),
               "n_turn_back": sum(e["type"] == "turn_back" for e in events),
               "n_return_direct": sum(e["type"] == "return_direct" for e in events),
               "n_safety_return": sum(e["type"] == "safety_return" for e in events),
               "margin_after_loop": round(bel.margin(P), 3),
               "p_firm": round(float(bel.p[0]), 4), "p_rough": round(float(bel.p[1]), 4),
               "n_firm": int(bel.n[0]), "s_firm": int(bel.s[0]), "n_rough": int(bel.n[1]), "s_rough": int(bel.s[1]),
               "events": events, "path_rc": hist, "modes": modes, "t": ts}
        loops.append(rec)
        log_fn(f"loop {li}: {len(targets)} targets, reached {rec['n_goals_reached']}, cost {spent:.0f}/{B:.0f} len {L:.0f} m "
               f"new {rec['new_observed_m2']:.0f} m2 p_firm {rec['p_firm']} p_rough {rec['p_rough']} margin {rec['margin_after_loop']} "
               f"replan {rec['n_replan']} turn {rec['n_turn_back']} direct {rec['n_return_direct']} safety {rec['n_safety_return']}")
    return bel, loops


def run():
    from .common import Scene, log, read_json, write_json
    sc = Scene("jezero")
    d = sc.work / "v3"; d.mkdir(exist_ok=True)
    if (d / "recon_loops.json").exists():
        raise SystemExit("version 3 already run once")
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    tm = read_json(sc.work / "terrain_2m.json")
    ext = tm["extent_local_m"]; res = PARAMS["grid_res_m"]
    base_rc = (int(ext[3] / res), int(-ext[0] / res))
    t0 = time.time()
    started = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    bel, loops = simulate(T, PARAMS, base_rc, log_fn=lambda m: log("jezero", "rover_v3", m))
    secs = round(time.time() - t0, 1)
    np.savez_compressed(d / "recon_state.npz", first_t=bel.first_t, observed=bel.observed, belief_cls=bel.cls)
    ref = T["class_ref"]
    for L in loops:
        obs = (bel.first_t >= 0) & (bel.first_t <= L["t1"])
        L["observed_frac_aoi"] = round(float(obs.mean()), 4)
        L["belief_agrees_with_reference_frac"] = round(float(np.mean(np.where(obs, ref, T["class_prior"]) == ref)), 4)
    out = {"params": PARAMS, "readings": READINGS, "terrain_params": tm["params"], "base_rc": list(base_rc),
           "extent_local_m": ext, "aoi_area_m2": ref.size * res * res, "seconds": secs, "started": started,
           "ref_cells_revealed": bel.ref_reads, "label": "simulated", "review": "pending",
           "disclosure": "version 3 was designed after seeing version 2's coverage, repeat coverage and loop 24",
           "initial_belief_agrees_with_reference_frac": round(float(np.mean(T["class_prior"] == ref)), 4), "loops": loops}
    write_json(d / "recon_loops.json", out)
    log("jezero", "rover_v3", f"{len(loops)} loops in {secs} s; observed {loops[-1]['observed_frac_aoi']:.1%}")
    return out


if __name__ == "__main__":
    run()
