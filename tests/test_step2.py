# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Step 2 option A rules on SYNTHETIC data only (no SuperCam number is looked at here)."""
import json

import numpy as np

from pipeline import step2_chem as S


def blobs(centres, n=12, sd=0.3, seed=0):
    rng = np.random.default_rng(seed)
    return np.vstack([np.asarray(c, float) + rng.normal(0, sd, (n, 8)) for c in centres])


def test_k_is_largest_with_every_pair_5_rmsep_apart():
    c = [np.zeros(8), np.r_[8, np.zeros(7)], np.r_[0, 0, 0, 0, 8, 0, 0, 0]]
    k, lab, seps = S.choose_k(blobs(c))
    assert k == 3 and len(set(lab)) == 3 and seps[2] >= 5 and seps[3] >= 5


def test_k_capped_at_4():
    c = [np.eye(8)[i] * 10 for i in range(6)]
    k, _, _ = S.choose_k(blobs(c))
    assert k == 4


def test_k_is_1_when_groups_closer_than_5_rmsep_or_too_few_targets():
    c = [np.zeros(8), np.r_[3, np.zeros(7)]]
    k, lab, _ = S.choose_k(blobs(c))
    assert k == 1 and set(lab) == {1}
    assert S.choose_k(np.zeros((1, 8)))[0] == 1
    assert S.choose_k(np.zeros((0, 8)))[0] == 1


def test_candidates_rep_and_anomaly_one_stop_per_waypoint():
    Z = np.array([[0.0] * 8, [0.1] + [0] * 7, [2.0] + [0] * 7, [20.0] + [0] * 7, [20.2] + [0] * 7])
    lab = np.array([1, 1, 1, 2, 2])
    wps = ["a", "a", "b", "c", "d"]
    stops, d = S.candidates(Z, lab, wps)
    roles = {(r["group"], r["role"]): s["wp"] for s in stops for r in s["roles"]}
    assert roles[(1, "anomaly")] == "b" and roles[(1, "representative")] == "a"
    assert len({s["wp"] for s in stops}) == len(stops) <= 8
    # group 2 has two targets at the same distance from its centroid -> rep and anomaly are different targets
    assert {roles[(2, "representative")], roles[(2, "anomaly")]} == {"c", "d"}


def test_unlock_uses_driven_path_within_radius_and_loop():
    ext, res = [-100.0, -100.0, 100.0, 100.0], 2.0
    # loop 1 drives along row 50 (y = 100 - 101 = -1 m), loop 2 along row 10 (y = 79 m)
    loops = [{"id": 1, "path_rc": [[50, c] for c in range(40, 60)]}, {"id": 2, "path_rc": [[10, c] for c in range(40, 60)]}]
    loc = [[0.0, 10.0], [0.0, 20.0], [0.0, 70.0]]
    assert S.unlocked_mask(loc, loops, ext, res, 15, 1).tolist() == [True, False, False]
    assert S.unlocked_mask(loc, loops, ext, res, 15, 2).tolist() == [True, False, True]


def test_switch_off_writes_only_disabled_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "WEB", tmp_path)
    (tmp_path / "old.json").write_text("{}")
    out = S.run({"enabled": False, "link_rule": "i", "unlock_radius_m": 15.0})
    assert out == {"enabled": False}
    assert [p.name for p in tmp_path.iterdir()] == ["step2.json"]
    d = json.loads((tmp_path / "step2.json").read_text())
    assert d["enabled"] is False and set(d) == {"si", "enabled"}


def test_config_switches_present():
    c = S.load_config()
    assert set(c) == {"enabled", "link_rule", "unlock_radius_m"} and c["unlock_radius_m"] == 15
