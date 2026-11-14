"""W3 step 7 (R8): version 2 (T1 rerun) and version 3 side by side. Evaluation only; reads saved runs.
python -m spikes.w3_r8_report -> data_work/jezero/v3/r8_report.json (+ printed table)"""
import json
import math

import numpy as np
from scipy.ndimage import binary_dilation

from pipeline.common import APP
from pipeline.multiwindow_ab import coverage_stats

W = APP / "data_work/jezero"
res = 2.0


def disc(r_m=15.0):
    r = int(math.ceil(r_m / res)); yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return (xx ** 2 + yy ** 2) * res * res <= r_m ** 2


def report(rf, sf, s2f):
    R = json.loads(rf.read_text()); st = np.load(sf)
    ext = R["extent_local_m"]; H = W_ = 1200
    cnt = np.zeros((H, W_), np.int16); D = disc()
    per = []
    for L in R["loops"]:
        m = np.zeros((H, W_), bool); rc = np.array(L["path_rc"]); m[rc[:, 0], rc[:, 1]] = True
        cnt += binary_dilation(m, structure=D)
        km = L["length_m"] / 1000
        per.append({"id": L["id"], "km": round(km, 2), "new_m2": L["new_observed_m2"],
                    "new_m2_per_km": round(L["new_observed_m2"] / km, 0) if km else None, "cost": L["cost_total"],
                    "safety": L["n_safety_return"], "soft_turn_back": L["n_turn_back"], "replan": L["n_replan"],
                    "goal_reached": L.get("goal_reached"), "p_firm": L.get("p_firm"), "p_rough": L.get("p_rough")})
    seen = cnt >= 1
    obs = st["observed"]
    out = {"coverage_by_loop_pct": {L["id"]: round(100 * L["observed_frac_aoi"], 1) for L in R["loops"] if L["id"] in (1, 5, 10, 20, 30)},
           "repeat_coverage_pct": round(100 * float((cnt >= 2).sum()) / float(seen.sum()), 1),
           "seen_by_dilation_equals_observed": bool(np.array_equal(seen, obs)),
           "total_km": round(sum(L["length_m"] for L in R["loops"]) / 1000, 1),
           "loops_over_budget": [L["id"] for L in R["loops"] if L["cost_total"] > L["budget"]],
           "loops_without_reaching_a_target": sum(not L.get("goal_reached") for L in R["loops"]),
           "safety_returns": sum(p["safety"] for p in per), "soft_turn_backs": sum(p["soft_turn_back"] for p in per),
           "replans": sum(p["replan"] for p in per), "coverage": coverage_stats(obs, ext, res), "per_loop": per}
    if s2f.exists():
        S = json.loads(s2f.read_text())["unlock_by_loop"]
        out["unlocked_locations_by_loop"] = {k: v["n_locations"] for k, v in S.items()}
        out["unlocked_units_loop30"] = S["30"]["units"]
    return out


def main():
    rep = {"v2_T1_rerun": report(W / "recon_loops.json", W / "recon_state.npz", W / "step2/step2_result_r15.json"),
           "v3": report(W / "v3/recon_loops.json", W / "v3/recon_state.npz", W / "step2/step2_result_v3_r15.json"),
           "note": "v3 'target reached' counts frontier targets (many per loop); v2 had one goal per loop: not comparable"}
    (W / "v3/r8_report.json").write_text(json.dumps(rep, indent=1, default=str))
    for k in ("v2_T1_rerun", "v3"):
        r = rep[k]; print(k, {q: r[q] for q in r if q not in ("per_loop",)})


if __name__ == "__main__":
    main()
