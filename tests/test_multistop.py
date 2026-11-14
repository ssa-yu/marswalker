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


# ---- round 7 confirmed definitions (manager 2026-11-14): secondary column and reading (ii) ----
from pipeline.astro_plan import cost_grids, field  # noqa: E402
from pipeline.multistop import own_map_home_cost_on, plan_fixed_order  # noqa: E402


def test_own_map_home_cost_matches_traceback_on_reference():
    plan_map = firm(120); ref = plan_map.copy(); ref[40:80, 50:70] = 2; plan_map[30:90, 40:45] = 3
    base = (60, 20)
    H = own_map_home_cost_on(plan_map, ref, base, RES)
    o2p, _ = cost_grids(plan_map, RES); o2e, _ = cost_grids(np.minimum(ref, 2), RES)
    m, cc = field(o2p, base)
    for c in [(60, 100), (10, 110), (100, 60), (60, 20)]:
        path = [tuple(int(v) for v in x) for x in m.traceback(c)]
        s = sum(0.5 * (o2e[a] + o2e[b]) / RES * RES * (np.sqrt(2) if a[0] != b[0] and a[1] != b[1] else 1) for a, b in zip(path[:-1], path[1:]))
        assert abs(H[c] - s) < 1e-6, (c, H[c], s)


def test_reading_ii_uses_own_map_way_home_charged_on_reference():
    # plan map thinks the straight way home is firm; on the reference that way is sand, a firm detour exists.
    plan_map = firm(200); ref = plan_map.copy(); ref[90:110, 60:140] = 2
    base = (100, 40); tg = [(100, 160)]
    p = plan_multistop(plan_map, base, tg, RES, capacity=400)
    e = evaluate_on_reference(p, plan_map, ref, RES)
    # own-map way home goes straight through the sand: its reference cost is higher than the best reference way
    o2e, _ = cost_grids(ref, RES); _, best_home = field(o2e, base)
    own = own_map_home_cost_on(plan_map, ref, base, RES)
    assert own[tg[0]] > best_home[tg[0]] + 1.0
    k = p["stop_idx"][0]
    assert abs(e["true_margin_at_stops"][0] - (p["usable_o2"] - walk(p["path_rc"], p["stop_idx"], ref, RES)["o2"][k] - own[tg[0]])) < 1e-6


def test_secondary_column_keeps_A_order_and_subset():
    a_map = firm(200); b_map = a_map.copy(); b_map[60:140, 100:110] = 2
    base = (100, 100); tg = [(100, 170), (30, 30), (170, 50)]
    pa = plan_multistop(a_map, base, tg, RES)
    pb = plan_fixed_order(b_map, base, tg, pa["order"], RES)
    assert pb["order"] == pa["order"] and len(pb["stop_idx"]) == len(pa["order"])
    assert [pb["path_rc"][k] for k in pb["stop_idx"]] == [tg[j] for j in pa["order"]]
    assert pb["path_rc"][0] == base and pb["path_rc"][-1] == base
    w = walk(pb["path_rc"], pb["stop_idx"], b_map, RES)
    assert abs(w["total_o2"] - pb["planned_o2"]) < 1e-6


def test_round7_table_plumbing_on_synthetic_grid():
    from pipeline.compare_ab import hazard_zones
    from pipeline.round7 import run_table
    prior = firm(150); ref = prior.copy(); ref[60:90, 20:70] = 2
    first_t = np.full(prior.shape, -1, np.int32); first_t[60:75, 60:90] = 0
    S = {"A": prior, "B@1": np.where(first_t >= 0, ref, prior).astype(np.uint8), "REF": ref}
    zones, _ = hazard_zones(ref, prior, RES)
    ext = [-150.0, -150.0, 150.0, 150.0]; base = (75, 75)
    stops = [{"x": -100.0, "y": 0.0}, {"x": 60.0, "y": 80.0}]
    t, paths = run_table(S, ref, zones, base, stops, ext, RES)
    r = t["rows"]
    assert set(r) == {"A", "B@1", "REF"} and "secondary_A_order" in r["B@1"]
    assert r["B@1"]["secondary_A_order"]["order"] == r["A"]["main"]["order"]
    assert r["REF"]["main"]["o2_error"] == 0 or abs(r["REF"]["main"]["o2_error"]) < 1e-6
    assert r["A"]["main"]["stops_reached_with_safe_return"] <= r["A"]["main"]["n_planned_stops"]


def test_round7_accepts_expected_cost_map():
    from pipeline.astro_plan import PARAMS as AP2, per_metre as pm
    from pipeline.compare_ab import hazard_zones
    from pipeline.round7 import run_table
    tm, om = pm(AP2)
    prior = firm(120); ref = prior.copy(); ref[40:80, 20:50] = 2
    E = {"o2": np.full(prior.shape, 0.8 * om[0] + 0.2 * om[2]), "t": np.full(prior.shape, 0.8 * tm[0] + 0.2 * tm[2]), "cls": prior}
    S = {"A": prior, "B_v3@1": E, "REF": ref}
    zones, _ = hazard_zones(ref, prior, RES)
    t, _ = run_table(S, ref, zones, (60, 60), [{"x": -80.0, "y": 0.0}, {"x": 40.0, "y": 60.0}], [-120.0, -120.0, 120.0, 120.0], RES)
    r = t["rows"]["B_v3@1"]
    assert r["main"]["pred_o2"] > t["rows"]["A"]["main"]["pred_o2"]        # expected cost is dearer than the prior
    assert r["secondary_A_order"]["order"] == t["rows"]["A"]["main"]["order"]
