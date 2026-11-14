# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""T2 route A vs B: definitions checked on SYNTHETIC grids only (written and passed before the real run)."""
import math

import numpy as np

from pipeline.compare_ab import (CMP, aplus_classes, belief_after, compare, crossings, evaluate_path,
                                 hazard_zones, lattice_targets, route)
from pipeline.astro_plan import per_metre

RES = 2.0


def test_crossing_rule():
    h = lambda *seq: [(f, m) for f, m in seq]
    assert crossings(h((True, 12.0))) == 1
    assert crossings(h((True, 8.0))) == 0
    assert crossings(h((True, 6.0), (False, 4.0), (True, 6.0))) == 1          # gap < 10 m: merged, 12 m inside
    assert crossings(h((True, 6.0), (False, 12.0), (True, 6.0))) == 0         # two short stretches
    assert crossings(h((True, 12.0), (False, 12.0), (True, 12.0))) == 2
    assert crossings(h((False, 50.0), (True, 10.0), (False, 50.0))) == 1      # exactly 10 m counts
    assert crossings(h((True, 5.0), (False, 9.9), (True, 5.0))) == 1


def test_hazard_zone_area_and_prior_marking():
    prior = np.zeros((60, 60), np.uint8); ref = prior.copy()
    ref[5:15, 5:15] = 2            # 100 cells = 400 m2 -> zone
    ref[30:35, 30:35] = 2          # 25 cells = 100 m2 -> too small
    ref[40:55, 40:55] = 2; prior[40:55, 40:55] = 2   # marked on the prior -> not a zone
    z, n = hazard_zones(ref, prior, RES)
    assert n == 1 and (z[5:15, 5:15] > 0).all() and (z[30:35, 30:35] == 0).all() and (z[40:55, 40:55] == 0).all()


def test_aplus_block_rule():
    prior = np.zeros((60, 60), np.uint8); ref = prior.copy()
    ref[0:30, 0:15] = 2            # block (0,0): exactly 50 % sand -> whole block becomes sand
    ref[0:30, 30:44] = 2           # block (0,1): 46.7 % -> stays prior
    prior[0, 0] = 3
    a = aplus_classes(prior, ref)
    assert a[0, 0] == 3 and (a[0:30, 0:30][1:] == 2).all() and (a[0:30, 30:60] == 0).all()


def test_lattice_targets():
    ext = (-700.0, -700.0, 700.0, 700.0)   # 700 x 700 cells
    n = int(1400 / RES)
    prior = np.zeros((n, n), np.uint8); ref = prior.copy()
    t = lattice_targets(ext, RES, prior, ref)
    xs = sorted({p["x"] for p in t}); assert xs == [-600, -300, 0, 300, 600]
    assert len(t) == 24 and all(p["dist_m"] >= 300 for p in t)
    rc = t[0]["rc"]; ref[rc] = 3
    assert len(lattice_targets(ext, RES, prior, ref)) == 23
    assert {p["band"] for p in t} == {"300-600", "600-1200"}


def test_hidden_sand_band_A_vs_ref():
    """Prior all firm; reference has a sand band with a gap. A walks straight through, REF uses the gap."""
    n = 200
    prior = np.zeros((n, n), np.uint8); ref = prior.copy()
    ref[:, 100:110] = 2; ref[0:20, 100:110] = 0       # band 20 m wide, gap at the top
    base, tgt = (100, 20), (100, 180)
    z, _ = hazard_zones(ref, prior, RES)
    pa = route(prior, base, tgt, RES); pr = route(ref, base, tgt, RES)
    ea = evaluate_path(pa, prior, ref, z, RES); er = evaluate_path(pr, ref, ref, z, RES)
    _, om = per_metre()
    assert math.isclose(ea["pred_o2"], 2 * 160 * RES * om[0], rel_tol=1e-9)   # straight, firm
    assert ea["actual_o2"] > ea["pred_o2"] and ea["o2_error"] > 0
    assert ea["crossings"] == 2 and math.isclose(ea["hazard_m"], 2 * 20.0, abs_tol=2.01)
    assert math.isclose(er["pred_o2"], er["actual_o2"]) and er["o2_error"] == 0
    assert er["actual_o2"] <= ea["actual_o2"] and er["hazard_m"] <= ea["hazard_m"]
    assert pa[0] == base and pa[-1] == base and tgt in pa


def test_blocked_on_reference_charged_as_sand_and_counted():
    n = 60
    prior = np.zeros((n, n), np.uint8); ref = prior.copy(); ref[:, 30] = 3
    pa = route(prior, (30, 5), (30, 55), RES)
    z, _ = hazard_zones(ref, prior, RES)
    e = evaluate_path(pa, prior, ref, z, RES)
    _, om = per_metre()
    assert math.isclose(e["blocked_m"], 2 * RES, rel_tol=1e-9)
    assert math.isfinite(e["actual_o2"])
    assert math.isclose(e["actual_o2"] - e["pred_o2"], 2 * RES * (om[2] - om[0]), rel_tol=1e-9)


def test_compare_end_to_end_B_between_A_and_REF():
    """Recon that saw everything gives B == REF; recon that saw nothing gives B == A."""
    n = 400   # 800 m square, habitat at centre
    rng = np.random.default_rng(1)
    prior = np.zeros((n, n), np.uint8)
    ref = prior.copy()
    for _ in range(12):
        r, c = rng.integers(20, n - 40, 2); ref[r:r + 30, c:c + 30] = 2
    ext = (-400.0, -400.0, 400.0, 400.0)
    first_t = np.full((n, n), -1, np.int32)
    first_t[:, :] = 0                     # loop 1 saw everything
    out = compare({"class_prior": prior, "class_ref": ref}, first_t, {1: 0}, ext, RES, base_xy=(0.0, 0.0))
    s = out["summary"]["all"]
    assert s["B@1"]["actual_o2"]["mean"] == s["REF"]["actual_o2"]["mean"]
    assert s["A"]["actual_o2"]["mean"] >= s["REF"]["actual_o2"]["mean"]
    first_t[:] = -1
    out = compare({"class_prior": prior, "class_ref": ref}, first_t, {1: 0}, ext, RES, base_xy=(0.0, 0.0))
    s = out["summary"]["all"]
    assert s["B@1"]["actual_o2"]["mean"] == s["A"]["actual_o2"]["mean"]
    assert s["B@1"]["diff_vs_A"]["hazard_m"]["mean"] == 0


def test_belief_after_uses_only_observed_reference():
    prior = np.zeros((10, 10), np.uint8); ref = np.full((10, 10), 2, np.uint8)
    ft = np.full((10, 10), -1, np.int32); ft[0:3] = 5; ft[3:5] = 50
    b, obs = belief_after(prior, ref, ft, 10)
    assert (b[0:3] == 2).all() and (b[3:] == 0).all() and obs.sum() == 30
