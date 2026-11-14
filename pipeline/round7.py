"""Round 7: multi-stop walks to the step-2 candidate stops, A vs A+ vs B@k vs REF, on the reference. Run ONCE.

python -m pipeline.round7

Definitions: confirmed by manager 2026-11-14 (direction.md 第七輪定義; DATA_LOG round 8 W2 copies them) and
pre-authorised to run once after the step-2 candidates were committed. Designed after seeing round 6; round 6
stays the pre-registered main comparison.
- Targets: step-2 option A candidate stops. Table (i) = the stops from the measurements the rover unlocked by
  loop 30 (main table); table (ii) = the stops from all Perseverance measurements in the AOI (second table, not
  brought back by this rover). One table per set; sets are never merged.
- Knowledge states as round 6 (compare_ab): A, A+, B@1/5/10/20/30 (T1-rerun recon), REF. Same targets for all.
- Main column: each state picks its own order and subset (multistop.plan_multistop: most stops, then least
  planned O2, with dwell 18 min = 18 nominal min O2, "planned used + planned home <= usable" after each dwell,
  brute force <= 7 stops). Secondary column: B@k keeps A's order and subset, legs re-planned on B's map.
- Evaluation on the reference (nothing replanned): planned / actual O2 and time, error, stops planned, stops
  reached (main reading (ii): own-map way home charged on the reference keeps the true return margin >= 0 at
  the end of the dwell; reading (i) beside it), first point where that true margin turns negative, hazard /
  blocked / sand metres, crossings and zones entered on the whole tour (round-6 definitions, compare_ab.
  evaluate_path), actual <= usable (listed, not evidence), differences vs A.
- step2.enabled = false -> refuses to run.
"""
from __future__ import annotations

import time

import numpy as np

from .astro_plan import PARAMS as ASTRO, usable_o2
from .common import APP, Scene, log, read_json, write_json
from .compare_ab import CMP, aplus_classes, belief_after, evaluate_path, hazard_zones
from .multistop import DWELL, evaluate_on_reference, own_map_home_cost_on, plan_fixed_order, plan_multistop
from .step2_chem import load_config

OUT = APP / "data_work/jezero/round7"
TAG = "designed after seeing round 6; round 6 is the pre-registered main comparison"


def states_main(T, first_t, loop_t1, P=CMP):
    prior, ref = T["class_prior"].astype(np.uint8), T["class_ref"].astype(np.uint8)
    S = {"A": prior, "A+": aplus_classes(prior, ref, P)}
    for k in P["b_loops"]:
        S[f"B@{k}"] = belief_after(prior, ref, first_t, loop_t1[k])[0]
    S["REF"] = ref
    return S


def tour_metrics(plan, cls_plan, ref, zones, res, home_own):
    e = evaluate_on_reference(plan, cls_plan, ref, res, DWELL, ASTRO, home_own_on_ref=home_own)
    path = [tuple(c) for c in plan["path_rc"]]
    if len(path) >= 2:
        m = evaluate_path(path, cls_plan["cls"] if isinstance(cls_plan, dict) else cls_plan, ref, zones, res)
        e.update({q: m[q] for q in ("length_m", "hazard_m", "blocked_m", "sand_m", "crossings", "zones_entered")})
    else:
        e.update({q: 0.0 for q in ("length_m", "hazard_m", "blocked_m", "sand_m")}); e.update({"crossings": 0, "zones_entered": 0})
    e["order"] = plan["order"]; e["skipped"] = plan["skipped"]; e["planned_o2_planner"] = plan["planned_o2"]
    return e


def run_table(S, ref, zones, base_rc, stops, ext, res):
    tg = [(int((ext[3] - s["y"]) / res), int((s["x"] - ext[0]) / res)) for s in stops]
    rows, paths = {}, {}
    homes = {s: own_map_home_cost_on(c, ref, base_rc, res, ASTRO) for s, c in S.items()}
    plans = {}
    for s, c in S.items():
        p = plan_multistop(c, base_rc, tg, res)
        plans[s] = p
        rows[s] = {"main": tour_metrics(p, c, ref, zones, res, homes[s])}
        paths[s] = {"main": {"path_rc": p["path_rc"], "stop_idx": p["stop_idx"]}}
    a_order = plans["A"]["order"]
    for s, c in S.items():
        if not s.startswith("B"):
            continue
        p = plan_fixed_order(c, base_rc, tg, a_order, res)
        if p is None:
            rows[s]["secondary_A_order"] = {"error": "A's order is not walkable on this map"}
            continue
        rows[s]["secondary_A_order"] = tour_metrics(p, c, ref, zones, res, homes[s])
        paths[s]["secondary_A_order"] = {"path_rc": p["path_rc"], "stop_idx": p["stop_idx"]}
    diff_q = ["actual_o2", "actual_time_min", "o2_error", "hazard_m", "sand_m", "crossings", "length_m",
              "stops_reached_with_safe_return", "stops_reached_within_usable", "n_planned_stops"]
    for s in rows:
        for col, r in rows[s].items():
            if s != "A" and "error" not in r:
                r["diff_vs_A"] = {q: r[q] - rows["A"]["main"][q] for q in diff_q}
    return {"targets_rc": [list(t) for t in tg], "rows": rows}, paths


def run():
    cfg = load_config()
    if not cfg["enabled"]:
        raise SystemExit("step2.enabled = false: round 7 has no targets and does not run")
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "round7.json"
    if f.exists():
        raise SystemExit(f"round 7 already run once: {f}")
    sc = Scene("jezero")
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    tm = read_json(sc.work / "terrain_2m.json")
    ext = tm["extent_local_m"]; res = tm["params"]["grid_res_m"]
    R = read_json(sc.work / "recon_loops.json")
    st = dict(np.load(sc.work / "recon_state.npz"))
    loop_t1 = {L["id"]: L["t1"] for L in R["loops"]}
    base_rc = (int(ext[3] / res), int(-ext[0] / res))
    S = states_main(T, st["first_t"], loop_t1)
    ref = S["REF"]
    zones, nz = hazard_zones(ref, S["A"], res)
    assert np.array_equal(zones > 0, np.load(sc.work / "hazard_zones.npy") > 0), "hazard zones differ from round 6"
    s2 = read_json(APP / f"data_work/jezero/step2/step2_result_r{int(cfg['unlock_radius_m'])}.json")
    t0 = time.time()
    out = {"label": "derived (simulated recon + assumed parameters + Perseverance SuperCam locations); heuristic, not yet reviewed",
           "disclosure": TAG, "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "usable_o2": usable_o2(P=ASTRO),
           "dwell": DWELL, "astronaut_params": ASTRO, "step2_config": cfg, "tables": {}}
    all_paths = {}
    for tab, key, note in (("i", "i", "main table: stops from the measurements the rover unlocked by loop 30"),
                           ("ii", "ii", "second table: stops from all Perseverance measurements in the AOI; not brought back by this rover")):
        stops = s2["datasets"][key]["stops"]
        res_t, paths = run_table(S, ref, zones, base_rc, stops, ext, res)
        res_t.update({"note": note, "stops": [{"wp": s["wp"], "x": s["x"], "y": s["y"],
                                               "roles": [[r["group"], r["role"], r["target"]] for r in s["roles"]]} for s in stops]})
        out["tables"][tab] = res_t
        all_paths[tab] = paths
    out["seconds"] = round(time.time() - t0, 1)
    write_json(f, out)
    write_json(OUT / "round7_paths.json", {"base_rc": list(base_rc), "ext": ext, "res": res, "paths": all_paths})
    log("jezero", "round7", f"done in {out['seconds']} s")
    return out


def run_v3():
    """Chain step 5 (manager 13th update): table (i) only, stops from step2_result_v3_r15.json; main B column =
    B_v3@k (expected-cost map, compare_v3.expected_maps_v3, p_k of the v3 rover), beside it Bv3prior@k (v3
    knowledge, unseen = prior class); each with own order and A's order; A, A+, REF recomputed for the new stops
    with the same code. (ii) not re-run; the W2 tables stay unchanged."""
    from .compare_v3 import expected_maps_v3
    cfg = load_config()
    if not cfg["enabled"]:
        raise SystemExit("step2.enabled = false")
    f = OUT / "round7_v3.json"
    if f.exists():
        raise SystemExit(f"round 7 v3 already run once: {f}")
    sc = Scene("jezero")
    T = dict(np.load(sc.work / "terrain_2m.npz"))
    tm = read_json(sc.work / "terrain_2m.json")
    ext = tm["extent_local_m"]; res = tm["params"]["grid_res_m"]
    R = read_json(sc.work / "v3/recon_loops.json")
    st = dict(np.load(sc.work / "v3/recon_state.npz"))
    byid = {L["id"]: L for L in R["loops"]}
    base_rc = (int(ext[3] / res), int(-ext[0] / res))
    prior, ref = T["class_prior"].astype(np.uint8), T["class_ref"].astype(np.uint8)
    S = {"A": prior, "A+": aplus_classes(prior, ref, CMP)}
    for k in CMP["b_loops"]:
        obs = (st["first_t"] >= 0) & (st["first_t"] <= byid[k]["t1"])
        Tm, Om, cls_b = expected_maps_v3(prior, ref, obs, byid[k]["p_firm"], byid[k]["p_rough"])
        S[f"B_v3@{k}"] = {"o2": Om, "t": Tm, "cls": cls_b}
        S[f"Bv3prior@{k}"] = belief_after(prior, ref, st["first_t"], byid[k]["t1"])[0]
    S["REF"] = ref
    zones, _ = hazard_zones(ref, prior, res)
    assert np.array_equal(zones > 0, np.load(sc.work / "hazard_zones.npy") > 0)
    s2 = read_json(APP / f"data_work/jezero/step2/step2_result_v3_r{int(cfg['unlock_radius_m'])}.json")
    stops = s2["datasets"]["i"]["stops"]
    t0 = time.time()
    res_t, paths = run_table(S, ref, zones, base_rc, stops, ext, res)
    res_t.update({"note": "table (i), version-3 chain: stops from the measurements the v3 rover unlocked by loop 30",
                  "stops": [{"wp": x["wp"], "x": x["x"], "y": x["y"], "roles": [[r["group"], r["role"], r["target"]] for r in x["roles"]]} for x in stops]})
    out = {"label": "derived (simulated recon v3 + assumed parameters + Perseverance SuperCam locations); heuristic, not yet reviewed",
           "disclosure": TAG + "; version 3 designed after seeing version 2", "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
           "seconds": round(time.time() - t0, 1), "usable_o2": usable_o2(P=ASTRO), "dwell": DWELL, "tables": {"i": res_t}}
    write_json(f, out)
    write_json(OUT / "round7_v3_paths.json", {"base_rc": list(base_rc), "ext": ext, "res": res, "paths": {"i": paths}})
    log("jezero", "round7", f"v3 table (i) done in {out['seconds']} s")
    return out


if __name__ == "__main__":
    import sys
    run_v3() if "--v3" in sys.argv else run()
