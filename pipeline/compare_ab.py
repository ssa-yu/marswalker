"""T2: route A vs route B on the reference terrain (the "before / after recon" comparison skeleton).

python -m pipeline.compare_ab --scene jezero

Definitions (written into DATA_LOG round 6 BEFORE the first real-terrain run; locked afterwards):

Knowledge states (each is a 2 m class grid: 0 firm, 1 rough, 2 sand, 3 blocked):
  A        prior only (CTX 20 m classes, `class_prior`).
  A+       "optimistic prior, uses reference, bracket only": A, plus sand on every cell of each 60 m block
           (30 x 30 cells, aligned to the AOI corner, same blocks as the S2 test) in which >= 50 % of the
           reference cells are sand; prior-blocked cells stay blocked.
  B@k      rover knowledge after loop k (k = 1, 5, 10, 20, 30 of the locked recon run): reference class where
           the rover had observed the cell by the end of loop k, prior elsewhere.
  REF      reference classes everywhere (upper bound of what recon can give; NOT route B).
Targets: every point of the 300 m lattice aligned to the habitat inside the AOI, >= 300 m from the habitat,
  whose 2 m cell is not blocked (class 3) on the prior nor on the reference. Each target is one test route:
  habitat -> target -> habitat. Distance bands by straight-line distance: [300, 600), [600, 1200), >= 1200 m.
Route on a knowledge state: least-O2 path habitat -> target on that state (astronaut model of
  pipeline/astro_plan.py, locked R3 parameters; 8-connected; a step costs the mean of the two cells'
  per-metre value times the step length), walked back along the same path reversed.
Evaluated on the reference terrain (the same path, nothing replanned):
  predicted time / O2   on the knowledge state the route was planned on;
  actual time / O2      on the reference classes; reference-blocked cells are charged at the sand rate and
                        counted separately (MVP_PLAN P7-3);
  O2 error              actual - predicted (nominal minutes) and 100 x (actual - predicted) / predicted;
  within budget         O2 <= usable O2 (480 x 0.8 = 384 nominal min), for predicted and for actual;
  hazard metres         metres walked inside hazard zones (main signal);
  blocked metres        metres walked on reference-blocked cells;
  sand metres           metres walked on reference sand (any sand cell; informative);
  crossings             runs of the walk inside hazard zones: consecutive in-zone stretches separated by less
                        than 10 m outside a zone are merged; a merged run counts as one crossing if its
                        in-zone metres are >= 10 m;
  zones entered         number of distinct hazard zones the walk touches (footnote only).
Hazard zone: 8-connected component of reference cells in sand or blocked, area >= 400 m2, of which >= 80 %
  of the cells are firm or rough on the prior ("not marked on the prior", R3 wording).
Metres of a step a -> b (length L) are split half to cell a, half to cell b (same convention as the cost).
A target that is unreachable on any knowledge state is listed and dropped from every column (paired table).
Reported per knowledge state and band: n, mean and median of every quantity, counts within budget, totals of
hazard / blocked metres and crossings, and paired differences (state - A) mean and median. Recon share of
the possible improvement = (A - B@k) / (A - REF) on the mean, for actual O2, hazard metres and crossings.
All values: derived from simulated recon + assumed parameters; review pending; sand classes heuristic, not yet
reviewed.
"""
from __future__ import annotations

import argparse
import math
import time

import numpy as np
from scipy.ndimage import label

from .astro_plan import PARAMS as ASTRO, field, per_metre, step_len, usable_o2

CMP = {
    "status": "locked before the first real-terrain run (round 6)",
    "lattice_m": 300.0, "min_dist_m": 300.0,
    "bands_m": {"300-600": [300.0, 600.0], "600-1200": [600.0, 1200.0], ">1200": [1200.0, math.inf]},
    "b_loops": [1, 5, 10, 20, 30],
    "aplus_block_cells": 30, "aplus_sand_frac": 0.5,
    "hazard_min_area_m2": 400.0, "hazard_prior_unmarked_frac": 0.8,
    "crossing_min_m": 10.0, "crossing_merge_gap_m": 10.0,
}
SAND, BLOCKED = 2, 3
GAP_TARGET_DROP_M = 50.0  # direction.md 嚴謹度 2 (locked): targets within 50 m of a HiRISE gap are dropped


# ---------------------------------------------------------------------------------------------- knowledge
def aplus_classes(prior, ref, P=CMP):
    f = P["aplus_block_cells"]
    H, W = ref.shape
    out = prior.copy()
    for r0 in range(0, H - f + 1, f):
        for c0 in range(0, W - f + 1, f):
            blk = ref[r0:r0 + f, c0:c0 + f]
            if np.mean(blk == SAND) >= P["aplus_sand_frac"]:
                sub = out[r0:r0 + f, c0:c0 + f]
                sub[sub != BLOCKED] = SAND
    return out


def belief_after(prior, ref, first_t, t1):
    obs = (first_t >= 0) & (first_t <= t1)
    return np.where(obs, ref, prior).astype(np.uint8), obs


def hazard_zones(ref, prior, res, P=CMP, exclude=None):
    """Label array (0 = not a hazard zone) and the number of zones. `exclude`: cells removed from the set before
    labelling (T6 gap rule (b), window (-4,0) only; None everywhere else)."""
    haz = (ref == SAND) | (ref == BLOCKED)
    if exclude is not None:
        haz &= ~exclude
    lab, n = label(haz, structure=np.ones((3, 3), int))
    if n == 0:
        return lab, 0
    idx = lab.ravel()
    area = np.bincount(idx, minlength=n + 1) * res * res
    unmarked = np.bincount(idx, weights=(prior.ravel() <= 1).astype(float), minlength=n + 1)
    cnt = np.bincount(idx, minlength=n + 1)
    keep = (area >= P["hazard_min_area_m2"]) & (unmarked >= P["hazard_prior_unmarked_frac"] * np.maximum(cnt, 1))
    keep[0] = False
    new_id = np.zeros(n + 1, np.int32)
    new_id[keep] = np.arange(1, keep.sum() + 1)
    return new_id[lab], int(keep.sum())


# ------------------------------------------------------------------------------------------------ targets
def lattice_targets(ext, res, prior, ref, P=CMP):
    x0, y0, x1, y1 = ext
    L = P["lattice_m"]
    xs = [k * L for k in range(int(math.ceil(x0 / L)), int(math.floor(x1 / L)) + 1) if x0 <= k * L < x1]
    ys = [k * L for k in range(int(math.ceil(y0 / L)), int(math.floor(y1 / L)) + 1) if y0 < k * L <= y1]
    out = []
    for y in sorted(ys, reverse=True):
        for x in xs:
            d = math.hypot(x, y)
            if d < P["min_dist_m"]:
                continue
            rc = (int((y1 - y) / res), int((x - x0) / res))
            if prior[rc] == BLOCKED or ref[rc] == BLOCKED:
                continue
            band = next(b for b, (lo, hi) in P["bands_m"].items() if lo <= d < hi)
            out.append({"x": x, "y": y, "rc": rc, "dist_m": round(d, 1), "band": band})
    return out


# --------------------------------------------------------------------------------------------- evaluation
def crossings(in_m, P=CMP):
    """in_m: list of (is_in_zone, metres) half-steps along the walk. Returns number of crossings."""
    runs = []  # merged runs: [in_metres, out_gap_pending]
    cur_in, gap, open_ = 0.0, 0.0, False
    for flag, m in in_m:
        if flag:
            if open_ and gap < P["crossing_merge_gap_m"]:
                cur_in += m
            else:
                if open_:
                    runs.append(cur_in)
                cur_in, open_ = m, True
            gap = 0.0
        elif open_:
            gap += m
    if open_:
        runs.append(cur_in)
    return sum(1 for r in runs if r >= P["crossing_min_m"] - 1e-9)


def evaluate_path(path, cls_k, ref, zones, res, P=CMP):
    tm, om = per_metre(ASTRO)
    ref_eval = np.minimum(ref, SAND)  # blocked -> charged as sand
    pt = po = at = ao = 0.0
    length = haz_m = blk_m = sand_m = 0.0
    half = []
    for a, b in zip(path[:-1], path[1:]):
        L = step_len(a, b, res)
        pt += 0.5 * (tm[cls_k[a]] + tm[cls_k[b]]) * L
        po += 0.5 * (om[cls_k[a]] + om[cls_k[b]]) * L
        at += 0.5 * (tm[ref_eval[a]] + tm[ref_eval[b]]) * L
        ao += 0.5 * (om[ref_eval[a]] + om[ref_eval[b]]) * L
        length += L
        for c in (a, b):
            z = zones[c] > 0
            haz_m += 0.5 * L * z
            blk_m += 0.5 * L * (ref[c] == BLOCKED)
            sand_m += 0.5 * L * (ref[c] == SAND)
            half.append((bool(z), 0.5 * L))
    zl = {int(zones[c]) for c in path if zones[c] > 0}
    U = usable_o2(P=ASTRO)
    return {"pred_time_min": pt, "pred_o2": po, "actual_time_min": at, "actual_o2": ao,
            "o2_error": ao - po, "o2_error_pct": 100.0 * (ao - po) / po if po > 0 else math.nan,
            "time_error": at - pt,
            "pred_within_budget": bool(po <= U + 1e-9), "actual_within_budget": bool(ao <= U + 1e-9),
            "length_m": length, "hazard_m": haz_m, "blocked_m": blk_m, "sand_m": sand_m,
            "crossings": crossings(half, P), "zones_entered": len(zl)}


def route(cls_k, base_rc, target_rc, res):
    """Least-O2 path base -> target on cls_k, then back along the same cells. None if unreachable."""
    _, om = per_metre(ASTRO)
    m, cc = field(om[cls_k] * res, base_rc)
    if not np.isfinite(cc[target_rc]):
        return None
    out = [tuple(int(v) for v in x) for x in m.traceback(target_rc)]
    return out + out[-2::-1]


def route_all(cls_k, base_rc, targets_rc, res):
    _, om = per_metre(ASTRO)
    m, cc = field(om[cls_k] * res, base_rc)
    paths = []
    for t in targets_rc:
        if not np.isfinite(cc[t]):
            paths.append(None); continue
        out = [tuple(int(v) for v in x) for x in m.traceback(t)]
        paths.append(out + out[-2::-1])
    return paths


QTY = ["pred_time_min", "actual_time_min", "time_error", "pred_o2", "actual_o2", "o2_error", "o2_error_pct",
       "length_m", "hazard_m", "blocked_m", "sand_m", "crossings", "zones_entered"]
DIFF_QTY = ["actual_time_min", "actual_o2", "o2_error", "hazard_m", "blocked_m", "crossings", "length_m"]


def summarise(rows_by_state, idx, states):
    """rows_by_state[state][i] = evaluate_path dict; idx = target indices of the group."""
    out = {}
    if not idx:
        return {"n": 0}
    for s in states:
        R = [rows_by_state[s][i] for i in idx]
        d = {"n": len(R)}
        for q in QTY:
            v = np.array([r[q] for r in R], float)
            d[q] = {"mean": float(np.mean(v)), "median": float(np.median(v))}
        for q in ("hazard_m", "blocked_m", "sand_m", "crossings", "length_m"):
            d[q]["total"] = float(np.sum([r[q] for r in R]))
        d["n_pred_within_budget"] = int(sum(r["pred_within_budget"] for r in R))
        d["n_actual_within_budget"] = int(sum(r["actual_within_budget"] for r in R))
        d["n_routes_with_crossing"] = int(sum(r["crossings"] > 0 for r in R))
        if s != "A":
            d["diff_vs_A"] = {}
            for q in DIFF_QTY:
                v = np.array([rows_by_state[s][i][q] - rows_by_state["A"][i][q] for i in idx], float)
                d["diff_vs_A"][q] = {"mean": float(np.mean(v)), "median": float(np.median(v))}
        out[s] = d
    for s in states:
        if s.startswith("B@") or s == "A+":
            sh = {}
            for q in ("actual_o2", "hazard_m", "crossings"):
                a, b, r = (out[k][q]["mean"] for k in ("A", s, "REF"))
                sh[q] = (a - b) / (a - r) if abs(a - r) > 1e-12 else None
            out[s]["share_of_possible_improvement"] = sh
    return out


def compare(T, first_t, loop_t1, ext, res, P=CMP, base_xy=(0.0, 0.0), gap=None, base_rc=None):
    """Pure function: arrays in, results out (used by the tests on synthetic grids and by run()).
    gap / base_rc: only for the T6 gap rule (manager 2026-11-14; window (-4,0)); None reproduces the frozen T2 code.
    With a gap: the caller has already made gap cells blocked in prior and reference (rule (a)); here gap cells
    leave the hazard-zone set (b), the observed share is taken over non-gap cells (c), lattice targets within
    50 m of the gap are dropped (d), and no route may touch a gap cell (asserted)."""
    prior, ref = T["class_prior"].astype(np.uint8), T["class_ref"].astype(np.uint8)
    if base_rc is None:
        base_rc = (int((ext[3] - base_xy[1]) / res), int((base_xy[0] - ext[0]) / res))
    zones, nz = hazard_zones(ref, prior, res, P, exclude=gap)
    targets = lattice_targets(ext, res, prior, ref, P)
    dropped_near_gap = []
    if gap is not None and gap.any():
        from scipy.ndimage import distance_transform_edt
        dgap = distance_transform_edt(~gap) * res
        dropped_near_gap = [t for t in targets if dgap[t["rc"]] <= GAP_TARGET_DROP_M]
        targets = [t for t in targets if dgap[t["rc"]] > GAP_TARGET_DROP_M]
    states = {"A": prior, "A+": aplus_classes(prior, ref, P)}
    observed_frac = {}
    for k in P["b_loops"]:
        if k in loop_t1:
            b, obs = belief_after(prior, ref, first_t, loop_t1[k])
            states[f"B@{k}"] = b
            observed_frac[f"B@{k}"] = float(obs[~gap].mean()) if gap is not None else float(obs.mean())
    states["REF"] = ref
    names = list(states)
    paths = {s: route_all(states[s], base_rc, [t["rc"] for t in targets], res) for s in names}
    unreachable = [i for i in range(len(targets)) if any(paths[s][i] is None for s in names)]
    keep = [i for i in range(len(targets)) if i not in unreachable]
    if gap is not None:
        assert not any(gap[c] for s in names for i in keep for c in paths[s][i]), "a route touched a gap cell"
    rows = {s: {i: evaluate_path(paths[s][i], states[s], ref, zones, res, P) for i in keep} for s in names}
    groups = {"all": keep}
    for b in P["bands_m"]:
        groups[b] = [i for i in keep if targets[i]["band"] == b]
    summary = {g: summarise(rows, idx, names) for g, idx in groups.items()}
    return {"targets": targets, "unreachable": unreachable, "states": names, "rows": rows, "paths": paths,
            "summary": summary, "n_hazard_zones": nz, "base_rc": base_rc, "observed_frac": observed_frac,
            "aplus_sand_frac": float(np.mean(states["A+"] == SAND)), "zones": zones,
            **({"dropped_near_gap": dropped_near_gap} if gap is not None else {})}


def run(scene: str, recon_file="recon_loops.json", state_file="recon_state.npz", out_name="compare_ab.json"):
    from .common import Scene, log, read_json, write_json
    sc = Scene(scene)
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    tm = read_json(sc.work / "terrain_2m.json")
    ext = tm["extent_local_m"]; res = tm["params"]["grid_res_m"]
    R = read_json(sc.work / recon_file)
    st = dict(np.load(sc.work / state_file))
    loop_t1 = {L["id"]: L["t1"] for L in R["loops"]}
    t0 = time.time()
    res_ = compare(T, st["first_t"], loop_t1, ext, res)
    secs = round(time.time() - t0, 1)
    tg = res_["targets"]
    rows_out = []
    for i in sorted(res_["rows"]["A"]):
        rows_out.append({"target": i, "x": tg[i]["x"], "y": tg[i]["y"], "dist_m": tg[i]["dist_m"], "band": tg[i]["band"],
                         **{s: {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res_["rows"][s][i].items()}
                            for s in res_["states"]}})
    paths = {s: {str(i): res_["paths"][s][i] for i in sorted(res_["rows"]["A"])} for s in res_["states"]}
    out = {"label": "derived (simulated recon + assumed parameters); heuristic, not yet reviewed", "review": "pending",
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "seconds": secs,
           "definitions": CMP, "astronaut_params": ASTRO, "usable_o2": usable_o2(P=ASTRO),
           "recon_file": recon_file, "n_targets": len(tg), "unreachable_targets": res_["unreachable"],
           "n_hazard_zones": res_["n_hazard_zones"], "observed_frac": res_["observed_frac"],
           "aplus_sand_frac_aoi": res_["aplus_sand_frac"], "states": res_["states"],
           "targets": [{k: (list(v) if k == "rc" else v) for k, v in t.items()} for t in tg],
           "summary": res_["summary"], "rows": rows_out}
    write_json(sc.work / out_name, out)
    write_json(sc.work / out_name.replace(".json", "_paths.json"), {"base_rc": list(res_["base_rc"]), "res": res, "ext": ext, "paths": paths})
    np.save(sc.work / "hazard_zones.npy", res_["zones"])
    log(scene, "compare_ab", f"{len(tg)} targets, {len(res_['unreachable'])} unreachable, {res_['n_hazard_zones']} zones, {secs} s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
