# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""N1 rules on SYNTHETIC data (no NOAH-H number)."""
import numpy as np

from pipeline import noahh_check as N


def test_mapping_is_a_partition_of_the_14_codes():
    groups = [N.RIPPLE, N.LOOSE, N.UNCERTAIN, N.AGAINST]
    allc = [c for g in groups for c in g]
    assert sorted(allc) == list(range(1, 15)) and len(allc) == 14
    assert set(N.T_CODES) <= set(N.RIPPLE) and set(N.SMALL) <= set(N.RIPPLE) and 9 in N.RIPPLE


def test_pixel_cell_block_aggregation():
    H = W = 60                                    # cells -> 2 x 2 blocks
    nh = np.zeros((H * 8, W * 8), np.uint8)
    nh[:, :W * 4] = 14                            # left half continuous large ripples
    nh[:, W * 4:] = 13                            # right half fractured bedrock
    nh[:8 * 5, :] = 0                             # top 5 cell rows no data
    cnt = N.cell_counts(nh)
    assert cnt.shape == (H, W, 15) and cnt[10, 0, 14] == 64 and cnt[0, 0, 0] == 64
    valid = N.group_counts(cnt, range(1, 15)) >= 32
    ref = np.zeros((H, W), np.uint8); ref[:, :30] = 2            # our sand = left blocks
    layer = np.where(ref == 2, 1, 3).astype(np.uint8)            # all coarse
    B = N.blocks_from_cells(cnt, valid, ref, layer)
    assert B["t"].shape == (2, 2)
    assert np.allclose(B["t"][:, 0], 1) and np.allclose(B["t"][:, 1], 0) and np.allclose(B["x"][:, 1], 1)
    assert B["sand"][:, 0].all() and not B["sand"][:, 1].any() and B["coarse"][:, 0].all()
    M = N.metrics(B)
    assert M["M1"] == 1.0 and M["M1_n"] == 2 and M["M2"] == 0.0 and M["M2_n"] == 2


def test_block_rule_matches_aplus_half_sand():
    H = W = 30
    ref = np.zeros((H, W), np.uint8); ref.ravel()[:450] = 2      # exactly 50 % sand
    cnt = np.zeros((H, W, 15), np.int32); cnt[..., 1] = 64
    B = N.blocks_from_cells(cnt, np.ones((H, W), bool), ref, np.full((H, W), 2, np.uint8))
    assert B["sand"][0, 0]
    from pipeline.compare_ab import aplus_classes
    assert (aplus_classes(np.zeros((H, W), np.uint8), ref) == 2).all()


def test_verdicts_and_boundaries():
    assert N.verdict_m1(0.60, 25) == "agree" and N.verdict_m1(0.40, 25) == "partial" and N.verdict_m1(0.39, 25) == "severe"
    assert N.verdict_m2(0.20, 25) == "agree" and N.verdict_m2(0.35, 25) == "partial" and N.verdict_m2(0.36, 25) == "severe"
    assert N.verdict_m1(0.9, 19) == "insufficient"
    assert N.overall("agree", "insufficient", 0.9) == "partial" and N.overall("agree", "severe", 0.9) == "severe"
    assert N.overall("agree", "agree", 0.4) == "insufficient"
    assert abs(N.kappa([1, 1, 0, 0], [1, 1, 0, 0]) - 1) < 1e-12


def test_layers_reproduce_frozen_classes():
    T, layer, ndiff = N.our_layers()
    assert ndiff == 0 and set(np.unique(layer)) <= {1, 2, 3}
