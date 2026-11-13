"""Export round 7 (multi-stop walks to the step-2 stops) for the astronaut page. Reformat only, nothing recomputed.

python -m pipeline.export_round7  -> web/data/jezero/compare/round7.json   (removed when step2.enabled = false)
"""
from __future__ import annotations

import numpy as np

from .common import APP, Scene, read_json, write_json
from .rover_sim import simplify
from .step2_chem import load_config

KEEP = ["n_planned_stops", "stops_reached_with_safe_return", "stops_reached_within_usable", "pred_o2", "actual_o2",
        "o2_error", "pred_time_min", "actual_time_min", "hazard_m", "blocked_m", "sand_m", "crossings", "zones_entered",
        "length_m", "actual_within_budget", "pred_within_budget", "order", "skipped", "true_margin_at_stops",
        "first_true_margin_negative", "diff_vs_A"]


def run():
    out_f = APP / "web/data/jezero/compare/round7.json"
    if not load_config()["enabled"]:
        out_f.unlink(missing_ok=True)
        print("step2 disabled: round7.json removed"); return
    R = read_json(APP / "data_work/jezero/round7/round7.json")
    P = read_json(APP / "data_work/jezero/round7/round7_paths.json")
    g = Scene("jezero").grid
    ext, res = P["ext"], P["res"]
    tables = {}
    for tab, T in R["tables"].items():
        rows = {s: {c: ({q: r[q] for q in KEEP if q in r} if "error" not in r or not isinstance(r["error"], str) else r)
                    for c, r in cols.items()} for s, cols in T["rows"].items()}
        paths = {}
        for s, cols in P["paths"][tab].items():
            for c, p in cols.items():
                rc = np.array(p["path_rc"], float).reshape(-1, 2)
                x = ext[0] + (rc[:, 1] + .5) * res; y = ext[3] - (rc[:, 0] + .5) * res
                keep = set(simplify(np.c_[x, y], 1.0).tolist()) if len(rc) > 2 else set(range(len(rc)))
                keep |= set(p["stop_idx"]) | {0, len(rc) - 1}
                k = np.array(sorted(keep), int)
                lon, lat = g.xy_to_lonlat(x[k], y[k])
                pos = {int(v): i for i, v in enumerate(k)}
                paths.setdefault(s, {})[c] = {"lon": [round(float(v), 7) for v in lon], "lat": [round(float(v), 7) for v in lat],
                                              "stop_vertex": [pos[i] for i in p["stop_idx"]]}
        tables[tab] = {"note": T["note"], "stops": T["stops"], "rows": rows, "paths": paths}
    write_json(out_f, {"label": R["label"], "disclosure": R["disclosure"], "computed_at": R["computed_at"],
                       "usable_o2": R["usable_o2"], "dwell": R["dwell"], "tables": tables})
    print("exported", out_f)


if __name__ == "__main__":
    run()
