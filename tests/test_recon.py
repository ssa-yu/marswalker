"""Step-1 recon acceptance (MVP_PLAN P6) on the exported simulation + belief isolation on a synthetic map."""
import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.rover_sim import PARAMS, Belief, simulate

APP = Path(__file__).resolve().parents[1]
WORK = APP / "data_work" / "jezero"


@pytest.fixture(scope="module")
def recon():
    p = WORK / "recon_loops.json"
    if not p.exists():
        pytest.skip("run python -m pipeline.rover_sim first")
    return json.loads(p.read_text())


def test_each_loop_starts_and_ends_at_base(recon):
    b = tuple(recon["base_rc"])
    for L in recon["loops"]:
        assert tuple(L["path_rc"][0]) == b and tuple(L["path_rc"][-1]) == b, L["id"]


def test_no_loop_over_budget(recon):
    for L in recon["loops"]:
        assert L["cost_total"] <= L["budget"], L["id"]


def test_never_on_impassable_reference_and_only_on_observed_cells(recon):
    T = dict(np.load(WORK / "terrain_2m.npz")); st = dict(np.load(WORK / "recon_state.npz"))
    imp = (T["class_ref"] == 3) | T["blocked_rover_ref"]
    for L in recon["loops"]:
        rc = np.array(L["path_rc"]); t = np.array(L["t"])
        assert not imp[rc[:, 0], rc[:, 1]].any(), L["id"]
        ft = st["first_t"][rc[:, 0], rc[:, 1]]
        assert (ft >= 0).all() and (ft <= t).all(), L["id"]


def test_median_return_overlap_below_30pct(recon):
    ov = [L["overlap_ratio"] for L in recon["loops"] if L["overlap_ratio"] is not None]
    assert np.median(ov) < 0.30


def test_planner_cannot_see_unobserved_reference():
    """Synthetic: a sand wall hidden from the prior. Before the rover gets near, its belief there is prior."""
    H = W = 120
    prior = np.zeros((H, W), np.uint8); ref = prior.copy(); ref[:, 70:74] = 3
    T = {"class_ref": ref, "class_prior": prior, "blocked_rover_ref": np.zeros((H, W), bool), "blocked_rover_prior": np.zeros((H, W), bool)}
    P = dict(PARAMS); P.update(n_loops=2, loop_budget=600.0, goal_lattice_m=20.0, goal_gain_radius_m=20.0)
    bel = Belief(T, P)
    bel.reveal((60, 20), 0)
    assert (bel.cls[:, 70:74] == 0).all() and not bel.observed[:, 70:74].any()
    assert bel.ref_reads == int(bel.observed.sum())
    bel2, loops = simulate(T, P, (60, 20), log_fn=lambda m: None)
    for L in loops:
        assert L["cost_total"] <= P["loop_budget"]
        rc = np.array(L["path_rc"]); assert not (ref[rc[:, 0], rc[:, 1]] == 3).any()
    # every revealed cell is exactly the reference, every unrevealed cell is exactly the prior
    assert (bel2.cls[bel2.observed] == ref[bel2.observed]).all() and (bel2.cls[~bel2.observed] == prior[~bel2.observed]).all()
