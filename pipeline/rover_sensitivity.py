"""T7 rover sensitivity (round 6): three settings written in direction.md 嚴謹度 4 / decisions 2026-11-14,
added AFTER the coverage of the locked run (11.3 %) was known and BEFORE any route A vs B number existed.
Each setting is run once; results are listed next to the locked main result and never replace it.

python -m pipeline.rover_sensitivity run --setting budget_8000      # or budget_16000, sand_x3
python -m pipeline.rover_sensitivity table

Settings (everything else = rover_sim.PARAMS unchanged: goal rule v2, 75 % planning + 25 % reserve,
sensing radius 15 m, 30 loops, rover blocked >= 20 deg, firm 1 / rough 2.5):
  budget_8000    loop_budget 8,000, sand x6
  budget_16000   loop_budget 16,000, sand x6
  sand_x3        loop_budget 4,000, sand x3
Main AOI terrain (terrain_2m.npz, frozen hashes in DATA_LOG). Comparison = pipeline/compare_ab.compare unchanged.
Outputs go to data_work/jezero/sensitivity/<setting>/ ; the main AOI's recon / comparison files are not touched.
A, A+ and REF do not depend on the rover; they are recomputed by compare() and checked equal to the frozen T2 file.
"""
from __future__ import annotations

import argparse
import copy
import time

import numpy as np

from .common import APP, log, read_json, write_json
from .multiwindow_ab import coverage_stats, recon_outputs, write_compare

SETTINGS = {
    "budget_8000": {"loop_budget": 8000.0},
    "budget_16000": {"loop_budget": 16000.0},
    "sand_x3": {"cost_factor": {"firm": 1.0, "rough": 2.5, "sand": 3.0}},
}
WORK = APP / "data_work/jezero"
OUT = WORK / "sensitivity"


def run(name):
    from .rover_sim import PARAMS, simulate
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    if (d / "recon_loops.json").exists():
        raise SystemExit(f"{name} already run once")
    P = copy.deepcopy(PARAMS)
    P.update(copy.deepcopy(SETTINGS[name]))
    T = dict(np.load(WORK / "terrain_2m.npz"))
    tm = read_json(WORK / "terrain_2m.json")
    ext = tm["extent_local_m"]; res = P["grid_res_m"]
    base_rc = (int((ext[3] - 0.0) / res), int((0.0 - ext[0]) / res))
    t0 = time.time()
    bel, loops = simulate(T, P, base_rc, log_fn=lambda m: log("jezero", f"sens {name}", m))
    secs = round(time.time() - t0, 1)
    np.savez_compressed(d / "recon_state.npz", first_t=bel.first_t, observed=bel.observed, belief_cls=bel.cls)
    out = recon_outputs(T, P, base_rc, ext, bel, loops, secs,
                        {"setting": name, "changed": SETTINGS[name],
                         "started": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(t0)),
                         "coverage": coverage_stats(bel.observed, ext, res),
                         "note": "sensitivity; written after the locked run's coverage was known, before any A vs B number"})
    write_json(d / "recon_loops.json", out)
    log("jezero", "sens", f"{name}: {len(loops)} loops {secs} s observed {out['coverage']['observed_aoi_pct']} %")
    cmp = write_compare(d, T, ext, res, "recon_loops.json", "recon_state.npz", {"setting": name})
    # A, A+, REF must equal the frozen T2 numbers (they do not depend on the rover)
    F = read_json(WORK / "compare_ab.json")["summary"]
    same = all(abs(cmp["summary"][g][s][q]["mean"] - F[g][s][q]["mean"]) < 1e-9
               for g in F for s in ("A", "A+", "REF") if F[g].get("n") for q in ("actual_o2", "hazard_m", "crossings"))
    write_json(d / "check_A_Aplus_REF_equal_T2.json", {"equal": bool(same)})
    log("jezero", "sens", f"{name}: compare done; A/A+/REF equal to frozen T2: {same}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["run"])
    ap.add_argument("--setting", choices=list(SETTINGS), required=True)
    a = ap.parse_args()
    run(a.setting)


if __name__ == "__main__":
    main()
