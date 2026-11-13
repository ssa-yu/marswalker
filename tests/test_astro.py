"""Step 3 skeleton tests on SYNTHETIC terrain only (no real data, no route comparison)."""
import math

import numpy as np
import pytest

from pipeline.astro_plan import PARAMS, per_metre, plan_tour, usable_o2

RES = 4.0


def grid(n=60, fill=0):
    return np.full((n, n), fill, np.uint8)


def check_plan(cls, base, p):
    path = p["path_rc"]
    assert path[0] == tuple(base) and path[-1] == tuple(base), "round trip must end at base"
    assert all(cls[c] != 3 for c in path), "path crosses a blocked cell"
    assert p["o2_total"] <= p["usable_o2"] + 1e-6, "plan uses more O2 than usable"
    assert min(p["timeline"]["margin"]) >= -1e-6, "return margin below zero"
    for a, b in zip(path[:-1], path[1:]):
        assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1


def test_all_firm_matches_analytic():
    cls = grid()
    base = (30, 30)
    p = plan_tour(cls, base, [(30, 50)], RES)
    check_plan(cls, base, p)
    d = 2 * 20 * RES  # out and back, straight east
    v = PARAMS["speed_kmh"] * 1000 / 60
    assert p["dist_total_m"] == pytest.approx(d)
    assert p["time_total_min"] == pytest.approx(d / v)
    assert p["o2_total"] == pytest.approx(d / v)  # firm: O2 factor 1


def test_sand_band_costs_more_and_is_avoided_when_possible():
    cls = grid()
    cls[:, 38:42] = 2  # full-height sand band: must be crossed
    base = (30, 10)
    p = plan_tour(cls, base, [(30, 50)], RES)
    check_plan(cls, base, p)
    tm, om = per_metre()
    assert p["o2_total"] > 2 * 40 * RES * om[0]
    cls2 = cls.copy(); cls2[50:, 38:42] = 0  # a firm gap far south: worth the detour only if cheaper
    p2 = plan_tour(cls2, base, [(30, 50)], RES)
    check_plan(cls2, base, p2)
    assert p2["o2_total"] <= p["o2_total"] + 1e-6


def test_blocked_wall_with_gap():
    cls = grid()
    cls[:, 30] = 3
    cls[5:8, 30] = 0  # gap near the top
    base = (40, 10)
    p = plan_tour(cls, base, [(40, 50)], RES)
    check_plan(cls, base, p)
    assert any(r in (5, 6, 7) and c == 30 for r, c in p["path_rc"]), "must pass through the gap"


def test_unreachable_target_is_skipped():
    cls = grid()
    cls[:, 30] = 3  # no gap
    base = (30, 10)
    p = plan_tour(cls, base, [(30, 50), (30, 20)], RES)
    check_plan(cls, base, p)
    assert p["skipped"] == [0] and p["order"] == [1]


def test_target_beyond_budget_is_skipped_and_margin_holds():
    cls = grid(200)
    base = (100, 100)
    near, far = (100, 120), (100, 199)  # 80 m and 396 m away
    v = PARAMS["speed_kmh"] * 1000 / 60
    cap = (2 * 200 / v) / (1 - PARAMS["reserve_frac"])  # usable O2 = a 200 m round trip
    p = plan_tour(cls, base, [far, near], RES, capacity=cap)
    check_plan(cls, base, p)
    assert p["order"] == [1] and p["skipped"] == [0]
    assert p["usable_o2"] == pytest.approx(usable_o2(cap))


def test_more_oxygen_visits_more_targets():
    cls = grid(120)
    cls[40:80, 60] = 3
    base = (60, 20)
    tg = [(20, 100), (100, 100), (60, 110)]
    seen = []
    for cap in (20, 40, 80, 480):
        p = plan_tour(cls, base, tg, RES, capacity=cap)
        check_plan(cls, base, p)
        seen.append(len(p["order"]))
    assert seen == sorted(seen) and seen[-1] == 3 and seen[0] < 3


def test_order_minimises_o2_for_all_targets():
    cls = grid(80)
    base = (40, 40)
    tg = [(40, 70), (10, 40), (40, 10), (70, 40)]
    p = plan_tour(cls, base, tg, RES)
    check_plan(cls, base, p)
    assert len(p["order"]) == 4
    assert p["o2_total"] == pytest.approx(p["planned_tour_o2"])
    # going around (E, N, W, S or reverse) beats criss-crossing
    D = np.array(p["pair_o2"])
    cross = D[0, 1] + D[1, 3] + D[3, 2] + D[2, 4] + D[4, 0]
    assert p["o2_total"] < cross
    assert math.isfinite(p["min_margin"])
