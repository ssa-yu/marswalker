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


def test_candidates_within_20m_of_frontier_and_frontier_min_size():
    T = synth(hidden_sand=False); P = small()
    bel = BeliefV3(T, P); bel.reveal((80, 80), 0)
    fr = frontier_cells(bel, P)
    assert fr.any() and (bel.observed[fr]).all()
    sel = Selector(P, (80, 80), fr.shape)
    b, info = sel.select(bel, (80, 80), 0.0, P["loop_budget"] * P["planning_frac"])
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(~fr) * P["grid_res_m"]
    assert b is not None and d[b["goal"]] <= 20.0 and info["n_feasible"] >= 1
    # an isolated 2-cell frontier is ignored
    bel2 = BeliefV3(T, P); bel2.observed[:] = True; bel2.observed[10, 10] = False
    bel2.cost[9:12, 9:12] = np.inf; bel2.cost[9, 9] = bel2.cost[9, 10] = 2.0
    assert not frontier_cells(bel2, P).any()


def test_cost_jump_triggers_reselect():
    """A corridor whose prior is firm; on the reference it turns to sand just beyond the first sensing disc.
    Once the sand is seen, the expected remaining cost to the target exceeds 1.5x its estimate -> reselect.
    (Test-only: soft check every 2 steps so the short first leg is checked.)"""
    H = W = 200
    prior = np.full((H, W), 3, np.uint8); prior[85:116, :] = 0
    ref = prior.copy(); ref[85:116, 60:93] = 2; ref[85:116, 108:141] = 2
    T = {"class_prior": prior, "class_ref": ref, "blocked_rover_prior": prior == 3, "blocked_rover_ref": ref == 3}
    P = small(n_loops=1, loop_budget=4000.0, soft_check_every_steps=2)
    _, loops = simulate(T, P, (100, 100), log_fn=lambda m: None)
    reasons = [e.get("reason") for L in loops for e in L["events"] if e["type"] == "replan"]
    assert "cost_x1.5" in reasons
    assert all(L["cost_total"] <= P["loop_budget"] for L in loops)


def test_bv3_expected_map_uses_class_p_and_reference_where_seen():
    from pipeline.astro_plan import PARAMS as AP, per_metre
    from pipeline.compare_v3 import expected_maps_v3
    tm, om = per_metre(AP)
    prior = np.array([[0, 1, 3], [0, 1, 0]], np.uint8); ref = np.array([[2, 2, 3], [0, 0, 1]], np.uint8)
    obs = np.array([[False, False, False], [True, True, False]])
    T, O, cls_b = expected_maps_v3(prior, ref, obs, 0.3, 0.6)
    assert abs(O[0, 0] - (0.7 * om[0] + 0.3 * om[2])) < 1e-12 and abs(O[0, 1] - (0.4 * om[1] + 0.6 * om[2])) < 1e-12
    assert np.isinf(O[0, 2]) and O[1, 0] == om[0] and O[1, 1] == om[0] and abs(O[1, 2] - (0.7 * om[0] + 0.3 * om[2])) < 1e-12
