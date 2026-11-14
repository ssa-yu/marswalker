"""Rover goal rule version 3 (R7 tests) on SYNTHETIC maps only."""
import math
from pathlib import Path

import numpy as np
import pytest

from pipeline import rover_v3 as V
from pipeline.rover_v3 import PARAMS, BeliefV3, Selector, corridor_gain, frontier_cells, simulate


def synth(H=160, W=160, hidden_sand=True):
    prior = np.zeros((H, W), np.uint8); ref = prior.copy()
    if hidden_sand:
        ref[30:130, 20:60] = 2; ref[20:40, 100:150] = 3
    return {"class_prior": prior, "class_ref": ref, "blocked_rover_prior": np.zeros((H, W), bool), "blocked_rover_ref": ref == 3}


def small(**kw):
    P = dict(PARAMS); P.update(n_loops=3, loop_budget=1200.0, goal_gain_radius_m=40.0); P.update(kw)
    return P


@pytest.fixture(scope="module")
def run3():
    T = synth(); P = small()
    bel, loops = simulate(T, P, (80, 80), log_fn=lambda m: None)
    return T, P, bel, loops


def test_every_loop_home_within_budget(run3):
    T, P, bel, loops = run3
    assert len(loops) == 3
    for L in loops:
        assert tuple(L["path_rc"][0]) == (80, 80) and tuple(L["path_rc"][-1]) == (80, 80)
        assert L["cost_total"] <= P["loop_budget"]
        rc = np.array(L["path_rc"]); assert not T["blocked_rover_ref"][rc[:, 0], rc[:, 1]].any()


def test_unseen_reference_never_read(run3):
    T, P, bel, loops = run3
    assert bel.ref_reads == int(bel.observed.sum())
    assert (bel.cls[~bel.observed] == T["class_prior"][~bel.observed]).all()
    for L in loops:
        rc = np.array(L["path_rc"]); t = np.array(L["t"])
        ft = bel.first_t[rc[:, 0], rc[:, 1]]
        assert (ft >= 0).all() and (ft <= t).all()


def test_no_perseverance_files_named():
    src = Path(V.__file__).read_text().lower()
    for bad in ("waypoint", "traverse", "supercam", "photo", "sample", "deahn", "m20_", "step2"):
        assert bad not in src, bad


def test_p_firm_rises_when_prior_firm_is_all_sand():
    H = W = 100
    prior = np.zeros((H, W), np.uint8); ref = np.full((H, W), 2, np.uint8)
    T = {"class_prior": prior, "class_ref": ref, "blocked_rover_prior": np.zeros((H, W), bool), "blocked_rover_ref": np.zeros((H, W), bool)}
    bel = BeliefV3(T, dict(PARAMS))
    p0 = bel.p[0]
    assert abs(p0 - 0.2) < 1e-12                             # alpha0 / (alpha0 + beta0)
    seq = []
    for c in range(10, 90, 10):
        bel.reveal((50, c), 0); bel.update_p(); seq.append(bel.p[0])
    assert all(b > a for a, b in zip([p0] + seq[:-1], seq)) and seq[-1] > 0.95
    assert abs(bel.p[0] - (bel.s[0] + 1) / (bel.n[0] + 5)) < 1e-12 and bel.s[0] == bel.n[0]
    # expected cost of an unseen prior-firm cell
    e = (1 - bel.p[0]) * 1 + bel.p[0] * 6
    assert abs(bel.e_unseen[0, 0] - e * PARAMS["grid_res_m"]) < 1e-9


def test_loop_gain_counts_unseen_once():
    obs = np.zeros((60, 60), bool); obs[:, :30] = True
    p1 = [(30, c) for c in range(10, 50)]
    g1 = corridor_gain([p1], obs, 2.0, 15.0)
    g2 = corridor_gain([p1, p1[::-1]], obs, 2.0, 15.0)          # same path twice: counted once
    assert g1 == g2 > 0
    assert corridor_gain([[(30, c) for c in range(5, 10)]], obs, 2.0, 4.0) == 0.0   # all seen -> 0


def test_candidates_are_frontier_cells_and_frontier_min_size():
    T = synth(hidden_sand=False); P = small()
    bel = BeliefV3(T, P); bel.reveal((80, 80), 0)
    fr = frontier_cells(bel, P)
    assert fr.any() and (bel.observed[fr]).all()
    sel = Selector(P, (80, 80), fr.shape)
    b, info = sel.select(bel, (80, 80), 0.0, P["loop_budget"] * P["planning_frac"])
    assert b is not None and fr[b["goal"]] and info["n_feasible"] >= 1 and b["gain_m2"] > 0
    # an isolated 2-cell frontier is ignored
    bel2 = BeliefV3(T, P); bel2.observed[:] = True; bel2.observed[10, 10] = False
    bel2.cost[9:12, 9:12] = np.inf; bel2.cost[9, 9] = bel2.cost[9, 10] = 2.0
    assert not frontier_cells(bel2, P).any()


def test_cost_jump_triggers_reselect():
    """R5 (2): when newly seen sand raises the expected remaining cost above 1.5x the estimate, a reselect is due;
    the check is the one simulate() calls every 20 steps."""
    from pipeline.rover_v3 import needs_reselect
    res = 2.0
    path = [(0, c) for c in range(51)]                        # 100 m
    E = np.full((1, 51), 2.0 * res)                            # estimate made with E = 2 per m
    est = 2.0 * 100.0
    assert not needs_reselect(E, path, 10, est, 1.5, res)      # nothing new: remaining 160 < 300
    E[0, 15:] = 6.0 * res                                      # sand seen on the way
    assert needs_reselect(E, path, 10, est, 1.5, res)          # remaining 10 + 6 x 70 = 430 > 300
    import inspect
    from pipeline import rover_v3
    assert "needs_reselect(E, path, idx, est" in inspect.getsource(rover_v3.simulate)


def test_bv3_expected_map_uses_class_p_and_reference_where_seen():
    from pipeline.astro_plan import PARAMS as AP, per_metre
    from pipeline.compare_v3 import expected_maps_v3
    tm, om = per_metre(AP)
    prior = np.array([[0, 1, 3], [0, 1, 0]], np.uint8); ref = np.array([[2, 2, 3], [0, 0, 1]], np.uint8)
    obs = np.array([[False, False, False], [True, True, False]])
    T, O, cls_b = expected_maps_v3(prior, ref, obs, 0.3, 0.6)
    assert abs(O[0, 0] - (0.7 * om[0] + 0.3 * om[2])) < 1e-12 and abs(O[0, 1] - (0.4 * om[1] + 0.6 * om[2])) < 1e-12
    assert np.isinf(O[0, 2]) and O[1, 0] == om[0] and O[1, 1] == om[0] and abs(O[1, 2] - (0.7 * om[0] + 0.3 * om[2])) < 1e-12


def test_flat_map_first_loop_keeps_seeing_new_ground():
    """13th update: on flat ground the newly seen area grows with distance driven (no shuttling between two points)."""
    H = W = 400
    prior = np.zeros((H, W), np.uint8)
    T = {"class_prior": prior, "class_ref": prior.copy(), "blocked_rover_prior": np.zeros((H, W), bool), "blocked_rover_ref": np.zeros((H, W), bool)}
    P = dict(PARAMS); P.update(n_loops=1, loop_budget=1200.0)
    bel, loops = simulate(T, P, (200, 200), log_fn=lambda m: None)
    L = loops[0]
    assert L["new_observed_m2"] >= 0.5 * 30.0 * L["length_m"] * 0.5     # at least half a 30 m swath over half the km
    tg = [tuple(t) for t in L["targets_rc"]]
    assert len(set(tg)) == len(tg)                                       # never the same target twice
    sel = [e for e in L["events"] if e["type"] == "select" and "gain_m2" in e]
    assert all(e["gain_m2"] > 0 for e in sel)


def test_hard_rule_keeps_budget_when_home_lies_behind_sand():
    """Run-2 bug (find_costs returns (costs, traceback); the traceback had been used as the home cost): the hard
    energy rule must hold when the way home is long and the rover sits in sand far out. Tight budget, sand belt."""
    H = W = 260
    prior = np.zeros((H, W), np.uint8); ref = prior.copy(); ref[:, 140:250] = 2
    T = {"class_prior": prior, "class_ref": ref, "blocked_rover_prior": np.zeros((H, W), bool), "blocked_rover_ref": np.zeros((H, W), bool)}
    P = small(n_loops=4, loop_budget=1500.0)
    _, loops = simulate(T, P, (130, 100), log_fn=lambda m: None)
    assert all(L["cost_total"] <= P["loop_budget"] for L in loops), [L["cost_total"] for L in loops]


def test_refresh_known_uses_costs_not_traceback():
    import inspect
    src = inspect.getsource(V.simulate)
    assert "known_home, _ = MCP_Geometric" in src and "_, known_home = MCP_Geometric" not in src
