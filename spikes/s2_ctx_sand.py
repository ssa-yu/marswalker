# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""S2: can the sand-field indicator see sand on the CTX 6 m image? (rule written before running)

Indicator on CTX: same structure as the HiRISE coarse band (DoG + structure-tensor coherence + RMS
energy, same fixed thresholds coarse_coh_min / coarse_energy_min, morphology), with the band moved to
the shortest scale CTX can carry: DoG sigma 6-18 m, window sigma 30 m (fine ripples are below CTX
resolution). No threshold is tuned on HiRISE (that would leak reference data into the prior).
Control: the same CTX-scale indicator on the HiRISE image averaged to 6 m (separates "resolution"
from "sensor/illumination").
Evaluation on 60 m blocks inside the AOI: block is sand if >= 50 % of its cells are HiRISE v2 sand.
Decision rule (fixed before running): CTX "sees sand" if ROC AUC of the CTX coherence for that block
label >= 0.80 AND the fixed-threshold CTX map has recall >= 0.5 with precision >= 0.7. Otherwise the
prior keeps no sand class and the comparison figure goes to Limitations.
"""
import json, numpy as np, rasterio, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import rankdata
def roc_auc_score(y, s):
    y = np.asarray(y, bool); r = rankdata(s); n1 = y.sum(); n0 = (~y).sum()
    return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
from pipeline.common import APP
from pipeline import sandfield as sf
from pipeline.terrain import block
P = sf.SAND_V2
AOI = (-1700, -1000, 700, 1400)
def ctx_ind(img6, res=6.0):
    ok = np.isfinite(img6)
    f = np.where(ok, img6, np.nanmean(img6))
    im = f / np.maximum(sf.gaussian_filter(f, 150 / res), 1e-3) - 1
    coh, en = sf.band_features(im, res, [6.0, 18.0], 30.0)
    return coh, en
# CTX crop (context grid -6500..5500 x, -5800..6200 y)
C = rasterio.open(APP / "data_work/jezero/prior_ortho_ctx.tif").read(1).astype("float32")
r0 = int((6200 - 1400) / 6); c0 = int((-1700 + 6500) / 6); n = 400
pad = 50
Cc = C[r0 - pad:r0 + n + pad, c0 - pad:c0 + n + pad]
ccoh, cen = [a[pad:-pad, pad:-pad] for a in ctx_ind(Cc)]
o05 = np.load(APP / "data_work/jezero/ortho_05.npy")
H6 = block(o05, 12, "mean")
hcoh, hen = ctx_ind(H6)
T = dict(np.load(APP / "data_work/jezero/terrain_2m.npz"))
G = dict(np.load(APP / "data_work/jezero/sand_v2_features.npz"))
sand, _ = sf.classify(G, T["slope_ref"], 2.0)
lab = block(sand.astype("float32"), 30, "mean") >= 0.5          # 60 m blocks
def mapit(coh, en):
    raw = (coh >= P["coarse_coh_min"]) & (en >= P["coarse_energy_min"])
    return raw
out = {}
for name, coh, en in (("ctx", ccoh, cen), ("hirise_at_6m", hcoh, hen)):
    b = block(coh, 10, "mean"); m = block(mapit(coh, en).astype("float32"), 10, "mean") >= 0.5
    auc = roc_auc_score(lab.ravel(), b.ravel())
    tp = (m & lab).sum(); prec = tp / max(m.sum(), 1); rec = tp / max(lab.sum(), 1)
    out[name] = {"auc_coherence": round(float(auc), 3), "precision": round(float(prec), 3), "recall": round(float(rec), 3),
                 "mapped_sand_pct": round(100 * float(m.mean()), 1)}
out["hirise_v2_sand_blocks_pct"] = round(100 * float(lab.mean()), 1)
out["ctx_sees_sand"] = bool(out["ctx"]["auc_coherence"] >= 0.8 and out["ctx"]["recall"] >= 0.5 and out["ctx"]["precision"] >= 0.7)
print(json.dumps(out, indent=1))
json.dump(out, open(APP / "qa/jezero/S2_ctx_sand.json", "w"), indent=1)
np.save(APP / "data_work/jezero/ctx_sand_raw_6m.npy", mapit(ccoh, cen))
# figure: CTX | HiRISE (same area) | CTX indicator map | HiRISE v2 sand ; plus zoom
e = [AOI[0], AOI[2], AOI[1], AOI[3]]
Cn = C[r0:r0 + n, c0:c0 + n]
fig, ax = plt.subplots(2, 3, figsize=(21, 14.5))
o2 = block(o05, 4, "mean")
def show(a, img, t):
    a.imshow(img, cmap="gray", extent=e, vmin=np.nanpercentile(img, 1), vmax=np.nanpercentile(img, 99)); a.set_title(t, fontsize=12)
show(ax[0, 0], Cn, "CTX orthoimage 6 m (prior, available before departure)")
show(ax[0, 1], o2, "HiRISE orthoimage (reference), shown at 2 m")
def over(a, img, m, t, col=(1, .45, 0)):
    show(a, img, t); rg = np.zeros(m.shape + (4,)); rg[..., :3] = col; rg[..., 3] = np.where(m, .45, 0); a.imshow(rg, extent=e, interpolation="nearest")
over(ax[0, 2], o2, sand, f"HiRISE sand field v2 (reference) {100*sand.mean():.1f} %")
over(ax[1, 0], Cn, mapit(ccoh, cen), f"Same indicator on CTX (6-18 m band) {100*mapit(ccoh,cen).mean():.1f} %", (0, .8, 1))
over(ax[1, 1], block(o05,12,'mean'), mapit(hcoh, hen), f"Control: same indicator on HiRISE averaged to 6 m {100*mapit(hcoh,hen).mean():.1f} %", (0, .8, 1))
zx, zy = (-700, 100), (-300, 500)
a = ax[1, 2]; z = Cn; a.imshow(Cn, cmap="gray", extent=e, vmin=np.percentile(Cn, 1), vmax=np.percentile(Cn, 99)); a.set_xlim(*zx); a.set_ylim(*zy)
a.set_title("CTX zoom 800 m (x -700..100, y -300..500): ripples are 1-2 pixels wide", fontsize=12)
fig.suptitle(f"S2: does CTX 6 m show the sand fields? AUC (60 m blocks) CTX {out['ctx']['auc_coherence']}, control {out['hirise_at_6m']['auc_coherence']}; "
             f"CTX precision {out['ctx']['precision']}, recall {out['ctx']['recall']} -> sees sand: {out['ctx_sees_sand']}", fontsize=13)
fig.tight_layout(); fig.savefig(APP / "qa/jezero/S2_ctx_vs_hirise_sand.png", dpi=80)
