# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
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


def test_planner_loads_no_perseverance_files(monkeypatch):
    """S3: the rover planner must not open waypoint, traverse, SuperCam, photo or sample files.
    Static: the planner module never names them. Dynamic: run a short simulation with every file-open
    entry point recorded and check nothing was opened at all (the planner gets arrays only)."""
    import builtins, io, re
    import pipeline.rover_sim as rs
    src = Path(rs.__file__).read_text().lower()
    for bad in ("waypoint", "traverse", "supercam", "photo", "sample", "deahn", "m20_", "step2"):
        assert bad not in src, bad
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])
    monkeypatch.setattr(io, "open", lambda f, *a, **k: (opened.append(str(f)), real_open(f, *a, **k))[1])
    real_load = np.load
    monkeypatch.setattr(np, "load", lambda f, *a, **k: (opened.append(str(f)), real_load(f, *a, **k))[1])
    H = W = 100
    z = np.zeros((H, W), np.uint8)
    T = {"class_ref": z, "class_prior": z, "blocked_rover_ref": z.astype(bool), "blocked_rover_prior": z.astype(bool)}
    P = dict(PARAMS); P.update(n_loops=3, loop_budget=500.0, goal_lattice_m=20.0, goal_gain_radius_m=20.0)
    simulate(T, P, (50, 50), log_fn=lambda m: None)
    assert opened == [], opened


def test_hard_energy_rule_never_overshoots_on_sandy_map():
    """Round-5 bug: the hard rule only guaranteed B + one step. Sandy synthetic maps, tight budget."""
    rng = np.random.default_rng(5)
    H = W = 90
    for k in range(3):
        ref = (rng.random((H, W)) < 0.45).astype(np.uint8) * 2   # 45 % sand, hidden from the prior
        prior = np.zeros((H, W), np.uint8)
        T = {"class_ref": ref, "class_prior": prior, "blocked_rover_ref": np.zeros((H, W), bool),
             "blocked_rover_prior": np.zeros((H, W), bool)}
        P = dict(PARAMS); P.update(n_loops=4, loop_budget=700.0, goal_lattice_m=20.0, goal_gain_radius_m=20.0)
        _, loops = simulate(T, P, (45, 45), log_fn=lambda m: None)
        for L in loops:
            assert L["cost_total"] <= P["loop_budget"], (k, L["id"], L["cost_total"])
