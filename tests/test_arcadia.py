# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia smoke tests: target-block rule and the energy grid (skipped when app/eva_energy is absent)."""
import math

import numpy as np
import pytest

from pipeline.arcadia import APP, cost_grid_8m, energy_grids, pick_blocks


def test_pick_blocks_rule():
    score = np.zeros((300, 300), np.float32)
    score[0:30, 0:30] = 0.9        # best block, but unseen
    score[30:60, 0:30] = 0.8       # seen
    score[30:60, 30:60] = 0.7      # seen, adjacent to the 0.8 block (60 m apart < 150 m) -> skipped
    score[210:240, 210:240] = 0.6  # seen, far away
    seen = np.zeros_like(score, bool); seen[30:300, :] = True
    passable = np.ones_like(seen)
    p = pick_blocks(score, passable, seen, n=4, min_sep=150.0, res=2.0, extent=(0.0, 0.0, 600.0, 600.0))
    assert [round(q["mean_score"], 2) for q in p[:2]] == [0.8, 0.6]
    for a in p:
        for b in p:
            if a is not b:
                assert math.dist(a["stop_xy"], b["stop_xy"]) >= 150 - 60 * math.sqrt(2)
    assert all(q["seen_frac"] >= 0.5 for q in p)
    p0 = pick_blocks(score, passable, None, n=4, min_sep=150.0, res=2.0, extent=(0.0, 0.0, 600.0, 600.0))
    assert p0[0]["mean_score"] == pytest.approx(0.9)


@pytest.mark.skipif(not (APP / "eva_energy" / "mars_eva_energy.py").exists(), reason="teammate module not in repo")
def test_energy_grid_monotone():
    cls = np.array([[0, 1, 2, 0, 3]], np.uint8)
    slope = np.array([[0, 0, 0, 10, 0]], np.float32)
    k, m, stand = energy_grids(cls, slope)
    assert k[0, 0] < k[0, 1] < k[0, 2]
    assert k[0, 3] > k[0, 0] and math.isinf(k[0, 4])
    assert m[0, 0] < m[0, 1] < m[0, 2]
    assert 3 < stand < 8


def test_pick_blocks_v2_defaults_spacing():
    rng = np.random.default_rng(0)
    score = rng.random((300, 300)).astype(np.float32)
    seen = np.ones_like(score, bool); passable = np.ones_like(seen)
    p = pick_blocks(score, passable, seen, extent=(0.0, 0.0, 1200.0, 1200.0))
    assert 1 <= len(p) <= 12
    for a in p:
        for b in p:
            if a is not b:
                assert math.dist(a["stop_xy"], b["stop_xy"]) >= 300 - 60 * math.sqrt(2)


def test_cost_grid_8m():
    k = np.array([[1.0, 3.0, np.inf, np.inf], [np.inf, 2.0, np.inf, 5.0]])
    k8, m8 = cost_grid_8m(k, k)
    assert k8[0, 0] == 2.0 and math.isinf(k8[0, 1])


def test_base_candidates_rule():
    from pipeline.arcadia import base_candidates
    H = W = 100                                     # 4 m grid, 400 m
    T4 = {"class_ref": np.zeros((H, W), np.uint8), "slope_mean": np.full((H, W), 2.0, np.float32)}
    T4["class_ref"][50, 50] = 1                     # rough cell is never a base
    T4["slope_mean"][:, 80:] = 12.0                 # steep east strip
    brain2 = np.zeros((2 * H, 2 * W), np.float32)
    brain2[0:4, 0:4] = 0.9                          # brain patch in the north-west corner
    ok = base_candidates(T4, brain2)
    assert not ok[50, 50]
    assert not ok[2, 2] and not ok[15, 15]          # within 100 m of the brain patch
    assert ok[60, 40]
    assert not ok[60, 90]                           # mean slope within 30 m >= 5.5 deg


def test_brain_score_png_matches_heat_indices():
    """web brain_score.png (read by the page's in-browser area selection) = the palette indices of brain_all.png."""
    from PIL import Image
    d = APP / "web" / "data" / "arcadia"
    heat, score = Image.open(d / "brain_all.png"), Image.open(d / "brain_score.png")
    assert heat.mode == "P" and score.mode == "L"
    assert (np.array(heat) == np.array(score)).all()
