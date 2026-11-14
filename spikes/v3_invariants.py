"""Invariant check of a rover run, on its own (manager 15th update: check before any downstream step).
python -m spikes.v3_invariants [dir]  (default data_work/jezero/v3) -> prints PASS/FAIL per invariant, exit 1 on FAIL"""
import json
import sys

import numpy as np

from pipeline.common import APP

d = APP / (sys.argv[1] if len(sys.argv) > 1 else "data_work/jezero/v3")
R = json.loads((d / "recon_loops.json").read_text()); st = np.load(d / "recon_state.npz")
T = np.load(APP / "data_work/jezero/terrain_2m.npz")
imp = (T["class_ref"] == 3) | T["blocked_rover_ref"]
base = tuple(R["base_rc"])
over = [(L["id"], L["cost_total"]) for L in R["loops"] if L["cost_total"] > L["budget"]]
home = [L["id"] for L in R["loops"] if tuple(L["path_rc"][0]) != base or tuple(L["path_rc"][-1]) != base]
bad_imp, bad_unseen = [], []
for L in R["loops"]:
    rc = np.array(L["path_rc"]); t = np.array(L["t"])
    if imp[rc[:, 0], rc[:, 1]].any():
        bad_imp.append(L["id"])
    ft = st["first_t"][rc[:, 0], rc[:, 1]]
    if not ((ft >= 0) & (ft <= t)).all():
        bad_unseen.append(L["id"])
reads = R["ref_cells_revealed"] == int(st["observed"].sum())
res = {"loops": len(R["loops"]), "max_cost": max(L["cost_total"] for L in R["loops"]), "over_budget": over,
       "not_home": home, "on_impassable_reference": bad_imp, "drove_unseen_cell": bad_unseen,
       "reference_reads_equal_observed_cells": reads}
ok = not over and not home and not bad_imp and not bad_unseen and reads and len(R["loops"]) == 30
print(json.dumps(res)); print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
