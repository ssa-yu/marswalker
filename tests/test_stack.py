# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""ST1 rules on SYNTHETIC data (no Stack or NOAH-H number)."""
import numpy as np

from pipeline import stack_check as S


def _masks(shape, **on):
    m = {k: np.zeros(shape, bool) for k in ("any",) + S.SURF_MASKS}
    for k, v in on.items():
        m[k.replace("_", "-")] = v
    return m


def test_mapping_groups_partition_the_classes():
    main = set(S.AEOLIAN) | set(S.MAIN_COMPAT) | set(S.MAIN_AGAINST)
    assert main == set(S.CLASSED) and len(main) == len(S.AEOLIAN) + len(S.MAIN_COMPAT) + len(S.MAIN_AGAINST)
    assert S.US_MIN in S.MAIN_AGAINST and S.US_FULL in S.MAIN_COMPAT and S.US_MOD in S.MAIN_COMPAT and S.TALUS in S.MAIN_AGAINST
    # side version: Us full -> sand, Us minor -> compatible (not against); nothing else changes
    assert set(S.SIDE_SAND) == set(S.AEOLIAN) | {S.US_FULL}
    assert set(S.SIDE_AGAINST) == set(S.MAIN_AGAINST) - {S.US_MIN}
    assert len(S.SURF_VALUES) == 6 and len(S.BEDROCK_VALUES) == 15


def test_overlap_priority():
    sh = (1, 12)
    T = np.ones(sh, bool)
    def col(*idx):
        a = np.zeros(sh, bool); a[0, list(idx)] = True; return a
    m = _masks(sh, any=col(*range(11)),
               Ab_l=col(1, 4, 7, 8, 10), Ab_s=col(2, 4, 8, 10), T=col(3, 9, 10),
               Us_full=col(5, 6, 7, 9), Us_moderate=col(6), Us_minor=col())
    c = S.combine(m)[0]
    # 0 bedrock, 1 Ab-l, 2 Ab-s, 3 T, 4 Ab-l+Ab-s, 5 Us full, 6 Us full+moderate, 7 Ab-l over Us, 8 Ab-l+Ab-s, 9 T over Us,
    # 10 Ab-l+Ab-s+T, 11 outside any polygon
    assert list(c) == [S.BEDROCK, S.ABL, S.ABS, S.TALUS, S.AEOL, S.US_FULL, S.CONFLICT, S.ABL, S.AEOL, S.TALUS, S.CONFLICT, S.NODATA]
    assert T.all()


def test_pixel_cell_block_aggregation_and_metrics():
    H = W = 60                                       # cells -> 2 x 2 blocks
    cls = np.full((H * 8, W * 8), S.BEDROCK, np.uint8)
    cls[:, :W * 4] = S.ABL                           # left half large bedforms
    cls[:8 * 5, :] = S.NODATA                        # top 5 cell rows no data
    cnt = S.cell_counts(cls)
    valid = S.cell_valid(cnt)
    assert cnt.shape == (H, W, 10) and cnt[10, 0, S.ABL] == 64 and not valid[0, 0] and valid[10, 0]
    ref = np.zeros((H, W), np.uint8); ref[:, :30] = 2; ref[:30, 30:] = 2      # sand: left blocks + top-right block
    layer = np.full((H, W), 3, np.uint8); layer[:, :30] = 1; layer[:30, 30:] = 2   # left coarse, top-right fine
    B = S.blocks_from_cells(cnt, valid, ref, layer)
    assert np.allclose(B["a"][:, 0], 1) and np.allclose(B["k"][:, 1], 1) and np.allclose(B["l"][:, 0], 1)
    assert B["coarse"][:, 0].all() and B["fine"][0, 1] and not B["fine"][1, 1]
    M = S.metrics(B)
    assert M["M1s"] == 1.0 and M["M1s_n"] == 2
    assert M["M2s_coarse"] == 0.0 and M["M2s_coarse_n"] == 2 and M["M2s_fine"] == 1.0 and M["M2s_fine_n"] == 1
    assert M["M2s_merged_n"] == 3


def test_verdict_layers():
    M = {"M1s": 0.7, "M1s_n": 30, "M2s_coarse": 0.1, "M2s_coarse_n": 25, "M2s_fine": 0.5, "M2s_fine_n": 19,
         "M2s_merged": 0.2, "M2s_merged_n": 44}
    V = S.verdict(M, 1.0)
    assert V["directions"] == {"M1s": "agree", "M2s_coarse": "agree"} and V["overall"] == "agree"   # fine n < 20: not judging
    M["M2s_fine_n"] = 20
    assert S.verdict(M, 1.0)["overall"] == "severe"
    M.update(M2s_coarse_n=5, M2s_fine_n=5, M2s_merged=0.3, M2s_merged_n=10)
    V = S.verdict(M, 1.0)
    assert V["directions"]["M2s_merged"] == "insufficient" and V["overall"] == "partial"
    assert S.verdict(M, 0.4)["overall"] == "insufficient"


def test_three_way_classes():
    ours = np.array([1, 0, 1, 0, 1, 0, 1, 0], bool)
    n = np.array([1, -1, -1, 1, 1, -1, 0, 1])
    s = np.array([1, -1, -1, 1, -1, 1, 1, 0])
    tw = S.three_way(ours, n, s)
    assert [S.THREE_WAY[i] for i in tw] == ["all_three_sand", "all_three_not", "only_ours_sand", "both_refs_sand_ours_not",
                                            "refs_contradict", "refs_contradict", "other", "other"]


def test_contradiction_causes():
    one = np.array([0.6]); zero = np.array([0.0])
    St = {"l": zero, "s": one, "a": one, "k": zero}; N = {"n78": one, "n10": zero, "nbed": zero, "r": zero}
    c = S.contradiction_causes(St, N)
    assert c["small_ripple_blind_spot"][0] and not c["herringbone_TAR_as_10"][0]
    St = {"l": zero, "s": zero, "a": np.array([0.2]), "k": one}; N = {"n78": zero, "n10": zero, "nbed": zero, "r": one}
    assert S.contradiction_causes(St, N)["Ab-l_80pct_and_generalisation"][0]
