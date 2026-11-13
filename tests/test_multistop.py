"""U4 multi-stop walk with dwell: SYNTHETIC grids only (no real-terrain number is computed in round 7 yet)."""
import numpy as np

from pipeline.astro_plan import PARAMS as AP, per_metre, plan_tour
from pipeline.multistop import DWELL, evaluate_on_reference, plan_multistop, walk

RES = 2.0


def firm(n=200):
    return np.zeros((n, n), np.uint8)


def test_dwell_adds_exactly_18_per_stop_on_flat_ground():
    cls = firm(); base = (100, 100); tg = [(100, 160), (40, 100), (100, 30)]
    p0 = plan_tour(cls, base, tg, RES)
    p1 = plan_multistop(cls, base, tg, RES)
    assert sorted(p1["order"]) == [0, 1, 2]
    assert abs(p1["planned_o2"] - (p0["o2_total"] + 3 * DWELL["dwell_min"])) < 1e-6


def test_dwell_can_cost_a_stop_when_the_budget_is_tight():
    cls = firm(400); base = (200, 200)
    _, om = per_metre(AP)
    # two stops 300 m out in opposite directions: tour = 4 x 300 m on firm (no dwell)
    tg = [(200, 350), (200, 50)]
    walk_o2 = 4 * 300 * om[0]
    cap = (walk_o2 + 10.0) / (1 - AP["reserve_frac"])      # fits without dwell, not with 2 x 18
    no_dwell = plan_multistop(cls, base, tg, RES, dwell={"dwell_min": 0.0, "dwell_o2_factor": 1.0}, capacity=cap)
    with_dwell = plan_multistop(cls, base, tg, RES, capacity=cap)
    assert len(no_dwell["order"]) == 2 and len(with_dwell["order"]) == 1


def test_planned_margin_never_negative_with_dwell():
    cls = firm(); cls[60:140, 120:130] = 2; base = (100, 100); tg = [(100, 170), (30, 30), (170, 50)]
    p = plan_multistop(cls, base, tg, RES, capacity=150)
    w = walk(p["path_rc"], p["stop_idx"], cls, RES, home=p["home_field_o2"], U=p["usable_o2"])
    assert min(w["true_margin"]) >= -1e-6 and w["total_o2"] <= p["usable_o2"] + 1e-6
    assert abs(w["total_o2"] - p["planned_o2"]) < 1e-6


def test_reference_equal_to_plan_gives_no_error():
    cls = firm(); base = (100, 100); tg = [(100, 160), (40, 100)]
    p = plan_multistop(cls, base, tg, RES)
    e = evaluate_on_reference(p, cls, cls, RES)
    assert abs(e["actual_o2"] - e["pred_o2"]) < 1e-9 and e["stops_reached_with_safe_return"] == 2


def test_hidden_sand_counts_fewer_stops_on_reference():
    plan_map = firm(400); ref = plan_map.copy(); ref[:, 230:400] = 2      # everything east is sand on the reference
    base = (200, 200); tg = [(200, 300), (200, 380)]
    p = plan_multistop(plan_map, base, tg, RES, capacity=130)
    assert len(p["order"]) == 2
    e = evaluate_on_reference(p, plan_map, ref, RES)
    assert e["actual_o2"] > e["pred_o2"]
    assert e["stops_reached_with_safe_return"] <= e["stops_reached_within_usable"] <= 2
    assert e["stops_reached_with_safe_return"] < 2 and e["first_step_true_margin_negative"] is not None
