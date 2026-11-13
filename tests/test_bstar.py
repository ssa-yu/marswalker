"""U7 B*: SYNTHETIC grids only (written before the single main-AOI run)."""
import numpy as np

from pipeline.astro_plan import per_metre
from pipeline.bstar import compare_bstar, expected_maps

RES = 2.0


def test_expected_cost_mixes_prior_and_sand_with_p_from_seen_cells():
    prior = np.zeros((10, 10), np.uint8); prior[0, 0] = 3
    ref = np.zeros((10, 10), np.uint8); ref[:, :5] = 2; ref[9, 9] = 3
    obs = np.zeros((10, 10), bool); obs[:, 3:7] = True; obs[9, 9] = True     # seen: 20 sand, 20 firm, 1 blocked
    T, O, p, cls_b = expected_maps(prior, ref, obs)
    tm, om = per_metre()
    assert abs(p - 0.5) < 1e-12                       # blocked seen cell excluded from p
    assert abs(O[5, 9] - (0.5 * om[0] + 0.5 * om[2])) < 1e-12      # unseen, prior firm
    assert O[5, 4] == om[2] and O[5, 5] == om[0]      # seen cells: reference
    assert np.isinf(O[0, 0]) and np.isinf(O[9, 9])    # prior-blocked unseen; reference-blocked seen


def test_nothing_seen_except_firm_equals_prior_and_all_seen_equals_reference():
    prior = np.zeros((10, 10), np.uint8); ref = prior.copy(); ref[2:5, 2:5] = 2
    obs = np.zeros((10, 10), bool); obs[8:, 8:] = True                        # seen only firm -> p = 0
    T, O, p, _ = expected_maps(prior, ref, obs)
    tm, om = per_metre()
    assert p == 0 and np.allclose(O[~obs], om[0])
    T, O, p, _ = expected_maps(prior, ref, np.ones((10, 10), bool))
    assert np.allclose(O, om[ref])


def test_bstar_with_p_one_prices_every_unseen_cell_as_sand():
    H = W = 300; prior = np.zeros((H, W), np.uint8); ref = prior.copy()
    ref[:, 100:200] = 2                                 # wide sand belt, partly seen
    first_t = np.full((H, W), -1, np.int32); first_t[140:160, 100:200] = 0
    ext = [-300.0, -300.0, 300.0, 300.0]               # base at (150, 150), inside the seen strip
    o = compare_bstar({"class_prior": prior, "class_ref": ref}, first_t, {1: 0}, ext, RES,
                      P={**__import__("pipeline.compare_ab", fromlist=["CMP"]).CMP, "b_loops": [1]})
    assert o["p_k"][1] == 1.0 and all(r["pred_o2"] > 0 for r in o["rows"][1].values())
    # with p = 1 every unseen non-blocked cell costs like sand: prediction never below the all-firm length cost
    for i, r in o["rows"][1].items():
        assert r["pred_o2"] >= r["length_m"] * per_metre()[1][2] - 1e-6
