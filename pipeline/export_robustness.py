"""Export T6 (multi-window) and T7 (rover sensitivity) results for the web full-table dialog. Reformat only.

python -m pipeline.export_robustness  -> web/data/jezero/compare/robustness.json
"""
from __future__ import annotations

from .common import APP, read_json, write_json

W = APP / "data_work/jezero"


def main():
    out = {"label": "derived (simulated recon + assumed parameters); heuristic, not yet reviewed"}
    t6 = W / "windows/t6_table.json"
    if t6.exists():
        out["t6"] = read_json(t6)
    t6_5 = W / "windows/t6_table_5windows.json"
    if t6_5.exists():
        out["t6_5windows"] = {"stats": read_json(t6_5)["stats"],
                              "note": "statistics over the first five windows, before (-4,0) ran (kept, not replaced)"}
    t7 = {}
    main_cmp = read_json(W / "compare_ab.json")
    main_rec = read_json(W / "recon_loops.json")
    t7["locked (main result)"] = {"recon": {L["id"]: L["observed_frac_aoi"] for L in main_rec["loops"]},
                                  "summary": main_cmp["summary"], "changed": "budget 4,000, sand x6"}
    for s, lab in (("budget_8000", "budget 8,000, sand x6"), ("budget_16000", "budget 16,000, sand x6"), ("sand_x3", "budget 4,000, sand x3")):
        p = W / "sensitivity" / s
        if (p / "compare_ab.json").exists():
            R = read_json(p / "recon_loops.json")
            t7[s] = {"recon": {L["id"]: L["observed_frac_aoi"] for L in R["loops"]}, "coverage": R.get("coverage"),
                     "summary": read_json(p / "compare_ab.json")["summary"], "changed": lab,
                     "km": round(sum(L["length_m"] for L in R["loops"]) / 1000, 1),
                     "max_loop_energy": max(L["cost_total"] for L in R["loops"]), "budget": R["params"]["loop_budget"]}
    out["t7"] = t7
    write_json(APP / "web/data/jezero/compare/robustness.json", out)
    print("exported", list(out), list(t7))


if __name__ == "__main__":
    main()
