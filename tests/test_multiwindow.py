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


def test_window_with_nodata_is_refused(tmp_path, monkeypatch):
    T = synth(); T["nodata"][5, 5] = True
    d = tmp_path / "-4_0"; d.mkdir()
    np.savez_compressed(d / "terrain_2m.npz", **T)
    (d / "terrain_2m.json").write_text(json.dumps({"habitat": {"class_prior": 0, "blocked_rover_prior": False}}))
    monkeypatch.setattr(MW, "OUT", tmp_path)
    with pytest.raises(SystemExit):
        MW.load_T(-4, 0)


def test_shifted_grid_is_exact_cell_shift():
    _, ws = MW.shifted_scene(-1, 1)
    from pipeline.common import Scene
    g0 = Scene("jezero").grid
    X0, Y0 = ws.grid.xy_to_src(0.0, 0.0)
    X1, Y1 = g0.xy_to_src(-2400.0, 2400.0)
    assert abs(X0 - X1) < 1e-6 and abs(Y0 - Y1) < 1e-6
