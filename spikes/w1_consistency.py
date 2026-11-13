"""Agreement of the unlocked-data groups with the all-data groups, from the SAVED cross-tables only (step 2 is not
re-run). Metrics specified by manager 2026-11-14 AFTER the cross-tables were seen (the cross-tables are the record):
ARI (Hubert & Arabie 1985, adjusted Rand index) and the majority-match share (each unlocked group mapped to the
all-data group that holds most of its targets; share of targets that fall in their group's majority).
python -m spikes.w1_consistency [result.json ...] -> prints and writes <result>_consistency.json"""
import json
import sys
from math import comb
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def ari(ct):
    rows, cols, n = {}, {}, 0
    for k, v in ct.items():
        a, b = k.split("|"); rows[a] = rows.get(a, 0) + v; cols[b] = cols.get(b, 0) + v; n += v
    if n < 2:
        return None
    s_ij = sum(comb(v, 2) for v in ct.values()); s_a = sum(comb(v, 2) for v in rows.values()); s_b = sum(comb(v, 2) for v in cols.values())
    exp = s_a * s_b / comb(n, 2); mx = 0.5 * (s_a + s_b)
    return None if mx == exp else (s_ij - exp) / (mx - exp)


def majority(ct):
    best, n = {}, 0
    for k, v in ct.items():
        a, _ = k.split("|"); best[a] = max(best.get(a, 0), v); n += v
    return sum(best.values()) / n if n else None


def main(paths):
    for p in paths:
        R = json.loads(Path(p).read_text())
        out = {"label": "metrics specified after the cross-tables were seen (manager 2026-11-14); the cross-tables are the record",
               "by_loop": {}}
        for k, u in R["unlock_by_loop"].items():
            ct = u["crosstab_unlocked_group_vs_all_data_group"]
            a = ari(ct)
            out["by_loop"][k] = {"n_targets": u["n_targets"], "k_unlocked": u["k"], "crosstab": ct,
                                 "ari": None if a is None else round(a, 3), "majority_match": None if not ct else round(majority(ct), 3)}
        q = Path(p).with_name(Path(p).stem + "_consistency.json")
        q.write_text(json.dumps(out, indent=1))
        web = APP / "web/data/jezero/step2/step2.json"
        if Path(p).name == "step2_result_r15.json" and web.exists():
            W = json.loads(web.read_text())
            if W.get("enabled"):
                W["consistency"] = out
                web.write_text(json.dumps(W, indent=1, ensure_ascii=False))
        print(p, json.dumps(out["by_loop"]))


if __name__ == "__main__":
    main(sys.argv[1:] or [str(APP / "data_work/jezero/step2/step2_result_r15.json")])
