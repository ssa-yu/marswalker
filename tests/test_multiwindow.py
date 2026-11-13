"""T6 / T7 plumbing on SYNTHETIC grids only (no real-terrain numbers). Real-terrain guard: window (0,0) through
pipeline/multiwindow_ab.build_terrain reproduces the main terrain_2m.npz cell for cell (selftest, see DATA_LOG)."""
import json

import numpy as np
import pytest

from pipeline import multiwindow_ab as MW
from pipeline.common import write_json
from pipeline.rover_sim import PARAMS, simulate


def synth(H=150, W=150):
    prior = np.zeros((H, W), np.uint8)
    ref = prior.copy()
    ref[40:110, 20:60] = 2           # hidden sand belt west of the base
    ref[20:30, 100:140] = 3          # hidden blocked ridge
    return {"class_prior": prior, "class_ref": ref, "blocked_rover_prior": prior == 3, "blocked_rover_ref": ref == 3,
            "nodata": np.zeros((H, W), bool)}


def test_recon_and_compare_plumbing(tmp_path):
    T = synth()
    res = 2.0
    ext = [-200.0, -100.0, 100.0, 200.0]            # habitat (0,0) at row 100, col 100
    base_rc = (int(ext[3] / res), int(-ext[0] / res))
    P = dict(PARAMS); P.update({"n_loops": 3, "loop_budget": 900.0})
    bel, loops = simulate(T, P, base_rc, log_fn=lambda m: None)
    out = MW.recon_outputs(T, P, base_rc, ext, bel, loops, 0.0, {"coverage": MW.coverage_stats(bel.observed, ext, res)})
    assert len(out["loops"]) == 3 and all(L["cost_total"] <= 900.0 for L in out["loops"])
    assert 0 < out["coverage"]["observed_aoi_pct"] < 100
    write_json(tmp_path / "recon_loops.json", out)
    np.savez_compressed(tmp_path / "recon_state.npz", first_t=bel.first_t, observed=bel.observed, belief_cls=bel.cls)
    # compare_ab.compare needs loop ids 1, 5, 10, 20, 30; with 3 loops only B@1 exists
    cmp = MW.write_compare(tmp_path, T, ext, res, "recon_loops.json", "recon_state.npz")
    assert "B@1" in cmp["states"] and "A" in cmp["states"] and "REF" in cmp["states"]
    with pytest.raises(SystemExit):        # each comparison runs once
        MW.write_compare(tmp_path, T, ext, res, "recon_loops.json", "recon_state.npz")


def _gap_window():
    """Synthetic window with a no-data strip on the west edge and a sand belt touching it."""
    T = synth()
    T["nodata"][50:100, :3] = True           # gap: a 6 m wide strip on the west edge
    T["class_ref"][60:90, 0:30] = 2          # sand that runs into the gap
    T["slope_prior"] = np.zeros(T["class_prior"].shape, np.float32)
    return T


def test_gap_rule_blocked_in_every_state_and_not_hazard():
    from pipeline.compare_ab import aplus_classes, belief_after, compare, hazard_zones
    T0 = _gap_window()
    T, gap = MW.apply_gap_rule(T0)
    assert (T["class_prior"][gap] == 3).all() and (T["class_ref"][gap] == 3).all()
    assert T["blocked_rover_prior"][gap].all() and T["blocked_rover_ref"][gap].all()
    # A+ and every B@k keep the gap blocked; the rover's belief too, also after sensing it
    assert (aplus_classes(T["class_prior"], T["class_ref"])[gap] == 3).all()
    ft = np.zeros(gap.shape, np.int32)       # rover saw everything at t = 0
    b, _ = belief_after(T["class_prior"], T["class_ref"], ft, 0)
    assert (b[gap] == 3).all()
    res = 2.0
    ext = [-200.0, -100.0, 100.0, 200.0]
    base_rc = (int(ext[3] / res), int(-ext[0] / res))
    P = dict(PARAMS); P.update({"n_loops": 2, "loop_budget": 900.0})
    bel, loops = simulate(T, P, base_rc, log_fn=lambda m: None)
    assert np.isinf(bel.cost[gap]).all() and (bel.cls[gap] == 3).all()
    # (b) gap cells are not in any hazard zone; without the exclusion the sand belt would include them
    z_ex, _ = hazard_zones(T["class_ref"], T["class_prior"], res, exclude=gap)
    z_in, _ = hazard_zones(T["class_ref"], T["class_prior"], res)
    assert not (z_ex[gap] > 0).any() and (z_in[gap] > 0).any()
    # (c) observed share over non-gap cells
    out = MW.recon_outputs(T, P, base_rc, ext, bel, loops, 0.0, gap=gap)
    obs = (bel.first_t >= 0) & (bel.first_t <= loops[-1]["t1"])
    assert out["loops"][-1]["observed_frac_aoi"] == round(float(obs[~gap].mean()), 4)
    cov = MW.coverage_stats(bel.observed, ext, res, gap=gap)
    assert cov["observed_aoi_pct"] == round(100 * float(bel.observed[~gap].mean()), 1)
    # (d) targets within 50 m of the gap dropped; routes never touch the gap
    r = compare(T, bel.first_t, {1: loops[0]["t1"]}, ext, res, gap=gap, base_rc=base_rc)
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(~gap) * res
    assert all(d[t["rc"]] > 50 for t in r["targets"])
    assert all(d[t["rc"]] <= 50 for t in r["dropped_near_gap"])
    assert r["observed_frac"]["B@1"] == float(obs_at(bel, loops[0]["t1"])[~gap].mean())


def obs_at(bel, t1):
    return (bel.first_t >= 0) & (bel.first_t <= t1)


def test_gap_none_reproduces_frozen_compare():
    """compare(gap=None) is the frozen T2 code path: same result as with an all-false gap mask."""
    from pipeline.compare_ab import compare
    T = synth()
    res = 2.0; ext = [-200.0, -100.0, 100.0, 200.0]
    ft = np.full(T["class_prior"].shape, -1, np.int32); ft[90:110, 90:110] = 0
    a = compare(T, ft, {1: 0}, ext, res)
    b = compare(T, ft, {1: 0}, ext, res, gap=np.zeros(ft.shape, bool))
    assert a["summary"] == b["summary"] and a["n_hazard_zones"] == b["n_hazard_zones"]


def test_habitat_moves_to_nearest_cell_passable_for_both():
    T = synth()
    T["slope_prior"] = np.zeros(T["class_prior"].shape, np.float32)
    T["class_prior"][95:106, 95:106] = 3                      # astronaut-blocked around the habitat
    T["blocked_rover_prior"] = T["class_prior"] == 3
    T["blocked_rover_prior"][94, 100] = True                  # rover-blocked only (20-25 deg) at distance 6
    rc, moved = MW.habitat_rc(T, (100, 100))
    assert moved and np.hypot(rc[0] - 100, rc[1] - 100) == 6 and rc != (94, 100)
    rc2, moved2 = MW.habitat_rc(synth() | {"slope_prior": T["slope_prior"]}, (100, 100))
    assert rc2 == (100, 100) and not moved2


def test_shifted_grid_is_exact_cell_shift():
    _, ws = MW.shifted_scene(-1, 1)
    from pipeline.common import Scene
    g0 = Scene("jezero").grid
    X0, Y0 = ws.grid.xy_to_src(0.0, 0.0)
    X1, Y1 = g0.xy_to_src(-2400.0, 2400.0)
    assert abs(X0 - X1) < 1e-6 and abs(Y0 - Y1) < 1e-6
