# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia smoke tests: target-block rule and the energy grid (skipped when app/eva_energy is absent)."""
import math

import numpy as np
import pytest

from pipeline.arcadia import APP, energy_grids, pick_blocks


def test_pick_blocks_rule():
    score = np.zeros((300, 300), np.float32)
    score[0:30, 0:30] = 0.9        # best block, but unseen
    score[30:60, 0:30] = 0.8       # seen
    score[30:60, 30:60] = 0.7      # seen, adjacent to the 0.8 block (60 m apart < 150 m) -> skipped
    score[210:240, 210:240] = 0.6  # seen, far away
    seen = np.zeros_like(score, bool); seen[30:300, :] = True
    passable = np.ones_like(seen)
    p = pick_blocks(score, passable, seen, extent=(0.0, 0.0, 600.0, 600.0))
    assert [round(q["mean_score"], 2) for q in p[:2]] == [0.8, 0.6]
    for a in p:
        for b in p:
            if a is not b:
                assert math.dist(a["stop_xy"], b["stop_xy"]) >= 150 - 60 * math.sqrt(2)
    assert all(q["seen_frac"] >= 0.5 for q in p)
    p0 = pick_blocks(score, passable, None, extent=(0.0, 0.0, 600.0, 600.0))
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
