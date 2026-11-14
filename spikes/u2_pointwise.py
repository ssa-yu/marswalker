# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""U2 (round 7): per-test-point distribution summary of the FROZEN T2 numbers (evaluation only).

python -m spikes.u2_pointwise
Reads data_work/jezero/compare_ab.json only (compare_ab is NOT run). Writes
qa/jezero/U2_pointwise_summary.json and web/data/jezero/compare/pointwise.json.

Describes how the 63 test points spread; it is NOT a significance test (the points share the walk out of
the habitat, one recon run and one AOI, so they are not independent). Added after the numbers were seen;
no number was changed.
For each state S in A+, B@1, B@5, B@10, B@20, B@30, REF and each quantity, per point d = S - A:
  actual_o2, hazard_m, crossings: better = d < 0, worse = d > 0, same = d == 0 (on the stored values,
      rounded to 0.001);
  o2_error (prediction error, actual - planned): better = |error_S| < |error_A|, worse = >, same = equal.
  mean, median, quartiles (numpy linear), min, max of d; 95 % percentile interval of the mean of d from
  10,000 resamples of the points with replacement (seed 20261114).
All points and each distance band.
"""
import json
from pipeline.common import SI_DATA

import numpy as np

from pipeline.common import APP

SEED = 20261114
NBOOT = 10000
STATES = ["A+", "B@1", "B@5", "B@10", "B@20", "B@30", "REF"]
QTY = ["actual_o2", "hazard_m", "o2_error", "crossings"]


def summarise(rows, s, q, rng):
    a = np.array([r["A"][q] for r in rows], float)
    b = np.array([r[s][q] for r in rows], float)
    d = b - a
    if q == "o2_error":
        key = np.abs(b) - np.abs(a)
    else:
        key = d
    idx = rng.integers(0, len(d), size=(NBOOT, len(d)))
    bm = d[idx].mean(axis=1)
    lo, hi = np.percentile(bm, [2.5, 97.5])
    return {"n": int(len(d)), "better": int((key < 0).sum()), "worse": int((key > 0).sum()), "same": int((key == 0).sum()),
            "mean": round(float(d.mean()), 2), "median": round(float(np.median(d)), 2),
            "q1": round(float(np.percentile(d, 25)), 2), "q3": round(float(np.percentile(d, 75)), 2),
            "min": round(float(d.min()), 2), "max": round(float(d.max()), 2),
            "mean_ci95_resample_points": [round(float(lo), 2), round(float(hi), 2)]}


def main():
    C = json.loads((APP / "data_work/jezero/compare_ab.json").read_text())
    rows = C["rows"]
    groups = {"all": rows}
    for b in ("300-600", "600-1200", ">1200"):
        groups[b] = [r for r in rows if r["band"] == b]
    out = {"label": "describes the spread over the 63 test points; not a significance test; added after the numbers "
                    "were seen; no number changed",
           "source": "data_work/jezero/compare_ab.json (frozen T2, commit e17452a)", "seed": SEED, "n_resamples": NBOOT,
           "rules": __doc__.split("For each state", 1)[1].split("All points", 1)[0].strip(), "groups": {}}
    for g, R in groups.items():
        rng = np.random.default_rng(SEED)
        out["groups"][g] = {s: {q: summarise(R, s, q, rng) for q in QTY} for s in STATES}
    # the three homepage shortcuts (U3): B@30 - A actual O2 per point
    d = [(r["B@30"]["actual_o2"] - r["A"]["actual_o2"], r["target"], r["x"], r["y"]) for r in rows]
    ds = sorted(d)
    med_val = float(np.median([v for v, *_ in d]))
    med = min(d, key=lambda t: (abs(t[0] - med_val), t[1]))
    out["shortcuts_B30_actual_o2"] = {
        "rule": "B@30 - A actual O2 per point: median point = the point whose difference is closest to the median of the 63 "
                "differences (ties -> lower target id); most improved = most negative difference; most worsened = most positive",
        "median_value": round(med_val, 3),
        "median": {"target": med[1], "x": med[2], "y": med[3], "diff": round(med[0], 3)},
        "most_improved": {"target": ds[0][1], "x": ds[0][2], "y": ds[0][3], "diff": round(ds[0][0], 3)},
        "most_worsened": {"target": ds[-1][1], "x": ds[-1][2], "y": ds[-1][3], "diff": round(ds[-1][0], 3)}}
    (APP / "qa/jezero/U2_pointwise_summary.json").write_text(json.dumps(out, indent=1))
    (APP / "web/data/jezero/compare/pointwise.json").write_text(json.dumps({"si": SI_DATA, **out}, indent=1))
    a = out["groups"]["all"]["B@30"]
    print("B@30 all:", {q: {k: a[q][k] for k in ("better", "worse", "same", "mean", "median", "mean_ci95_resample_points")} for q in QTY})
    print("shortcuts:", out["shortcuts_B30_actual_o2"])


if __name__ == "__main__":
    main()
