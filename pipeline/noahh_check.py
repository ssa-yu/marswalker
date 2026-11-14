# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""N1: NOAH-H (Wright et al. 2022) vs our sand classes v2 — consistency with an independent classifier, main AOI only.

python -I -m pipeline.noahh_check invariants   # class_ref recomputed cell for cell, code table, coverage
python -I -m pipeline.noahh_check align        # N7 alignment figure (only NOAH-H boundaries on the ortho)
python -I -m pipeline.noahh_check metrics      # N2-N5 (run once)
python -I -m pipeline.noahh_check figures      # N9 (overview + sign-off sheet, Chinese labels)

Rules: manager 2026-11-14, TECH_LEAD_BRIEF 第十八次更新 N0-N11 (written before any NOAH-H number); copied into
DATA_LOG "N1 NOAH-H cross-check — rule written BEFORE the comparison". Summary:
N1 mapping: ripples (support): continuous large 14, 12; isolated large 9; small 6, 5, 3. Loose (compatible): 1, 7, 8.
   Uncertain: 10 (rugged bedrock). Against: bedrock 2, 4, 13; boulder fields 11. No data dropped.
N2 the DC mosaic, nearest neighbour onto the 0.25 m AOI grid of ortho_025.tif, no shift. 2 m cell = 64 pixels;
   cell valid = >= 50 % pixels with a class and >= 30 m from NOAH-H no-data. 60 m blocks = the A+ blocks (30 x 30
   cells from the AOI corner); our sand block = reference sand cells >= 50 %; block valid = >= 50 % cells valid.
   Block shares over valid pixels (of valid cells): t = 14+12, r = all ripple classes, x = against; on our sand
   cells inside the block: r_s, l_s (loose), q_s (uncertain), x_s (against).
N3 layers of our sand: coarse flag / fine flag only / fill (neither), recomputed from the stored features and slope
   with the unchanged code; must reproduce class_ref cell for cell. A sand block is "coarse" if >= 50 % of its
   sand cells are coarse, else "fine".
N4 M1 = share of valid blocks with t >= 0.5 that are our sand blocks; M2 = share of our valid coarse sand blocks
   with x_s >= 0.5. Descriptions only: layer shares (X = coarse), fine-block r_s / l_s / q_s / x_s, 2x2 + Cohen's
   kappa (our sand block x r >= 0.5), 2 m confusion (our 4 classes x 14 codes), share judged sand among blocks
   dominated (>= 0.5) by isolated large ripples (9) or by small ripples (6, 5, 3).
N5 M1 >= 0.60 agree, 0.40-0.60 partial, < 0.40 severe; M2 <= 0.20 agree, 0.20-0.35 partial, > 0.35 severe; boundary
   values to the better side; n < 20 -> insufficient (= partial for the overall); overall = the worse; AOI valid
   coverage < 50 % -> overall insufficient.
Labels: NOAH-H classes `derived (third-party model)`, Wright et al. 2022, CC BY 4.0; consistency, not validation.
"""
from __future__ import annotations

import json
import math
import sys
import time

import numpy as np

from .common import APP, Scene, read_json, write_json

RAW = APP / "data_raw/jezero/noahh"
DC = RAW / "NOAH-H_mosaics/Descriptive_classes/Jezero_NOAHH_mosaic_DC.tif"
OUT = APP / "data_work/jezero/noahh"
QA = APP / "qa/jezero/noahh"
CODES = {14: "Large ripples - rectilinear", 13: "Bedrock - fractured", 12: "Large ripples - simple, continuous",
         11: "Boulder fields", 10: "Bedrock - rugged", 9: "Large ripples - simple, isolated",
         8: "Non-bedrock - smooth lineated", 7: "Non-bedrock - textured", 6: "Small ripples - continuous",
         5: "Small ripples - discontinuous, non-bedrock substrate", 4: "Bedrock - smooth",
         3: "Small ripples - discontinuous, bedrock substrate", 2: "Bedrock - textured", 1: "Non-bedrock - smooth featureless"}
T_CODES = (14, 12)
RIPPLE = (14, 12, 9, 6, 5, 3)
SMALL = (6, 5, 3)
LOOSE = (1, 7, 8)
UNCERTAIN = (10,)
AGAINST = (2, 4, 13, 11)
CELL_PX = 8            # 2 m / 0.25 m
BLOCK = 30             # cells (60 m), = compare_ab.CMP["aplus_block_cells"]
EDGE_M = 30.0
SEED = 20261114


# ------------------------------------------------------------------------------------------ pure helpers
def cell_counts(nh):
    """nh: (H*8, W*8) uint8 codes (0 = no data). Returns (H, W, 15) pixel counts per code 0..14."""
    H, W = nh.shape[0] // CELL_PX, nh.shape[1] // CELL_PX
    v = nh[:H * CELL_PX, :W * CELL_PX].reshape(H, CELL_PX, W, CELL_PX)
    out = np.zeros((H, W, 15), np.int32)
    for c in range(15):
        out[..., c] = (v == c).sum(axis=(1, 3))
    return out


def group_counts(cnt, codes):
    return cnt[..., list(codes)].sum(-1)


def block_sum(a, f=BLOCK):
    H, W = a.shape[:2]
    nb_r, nb_c = H // f, W // f
    a = a[:nb_r * f, :nb_c * f]
    return a.reshape(nb_r, f, nb_c, f, *a.shape[2:]).sum(axis=(1, 3))


def verdict_m1(m, n):
    if n < 20:
        return "insufficient"
    return "agree" if m >= 0.60 else ("partial" if m >= 0.40 else "severe")


def verdict_m2(m, n):
    if n < 20:
        return "insufficient"
    return "agree" if m <= 0.20 else ("partial" if m <= 0.35 else "severe")


def overall(v1, v2, coverage):
    if coverage < 0.5:
        return "insufficient"
    rank = {"agree": 0, "partial": 1, "insufficient": 1, "severe": 2}
    w = max(v1, v2, key=lambda v: rank[v])
    return "partial" if w == "insufficient" else w


def kappa(a, b):
    a = np.asarray(a, bool); b = np.asarray(b, bool); n = len(a)
    po = np.mean(a == b); pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return float((po - pe) / (1 - pe)) if pe < 1 else None


def blocks_from_cells(cnt, cell_valid, ref, layer):
    """Block quantities from per-cell code counts (valid cells only), reference classes and our sand layers."""
    vc = cnt * cell_valid[..., None]
    valid_px = group_counts(vc, range(1, 15))
    B_valid_px = block_sum(valid_px).astype(float)
    t = block_sum(group_counts(vc, T_CODES)) / np.maximum(B_valid_px, 1)
    r = block_sum(group_counts(vc, RIPPLE)) / np.maximum(B_valid_px, 1)
    x = block_sum(group_counts(vc, AGAINST)) / np.maximum(B_valid_px, 1)
    iso = block_sum(group_counts(vc, (9,))) / np.maximum(B_valid_px, 1)
    small = block_sum(group_counts(vc, SMALL)) / np.maximum(B_valid_px, 1)
    sand = ref == 2
    sc = vc * sand[..., None]
    s_px = block_sum(group_counts(sc, range(1, 15))).astype(float)
    shares_s = {k: block_sum(group_counts(sc, g)) / np.maximum(s_px, 1)
                for k, g in (("r_s", RIPPLE), ("l_s", LOOSE), ("q_s", UNCERTAIN), ("x_s", AGAINST))}
    block_valid = block_sum(cell_valid.astype(int)) >= 0.5 * BLOCK * BLOCK
    our_sand_block = block_sum(sand.astype(int)) >= 0.5 * BLOCK * BLOCK
    coarse_cells = block_sum((sand & (layer == 1)).astype(int)); sand_cells = block_sum(sand.astype(int))
    coarse_block = coarse_cells >= 0.5 * np.maximum(sand_cells, 1)
    return {"t": t, "r": r, "x": x, "iso": iso, "small": small, "valid": block_valid, "sand": our_sand_block,
            "coarse": coarse_block & our_sand_block, "s_px": s_px, **shares_s}


def metrics(B):
    v = B["valid"]
    m1_den = v & (B["t"] >= 0.5); m1 = float(B["sand"][m1_den].mean()) if m1_den.any() else math.nan
    m2_den = v & B["coarse"] & (B["s_px"] > 0); m2 = float((B["x_s"][m2_den] >= 0.5).mean()) if m2_den.any() else math.nan
    return {"M1": m1, "M1_n": int(m1_den.sum()), "M2": m2, "M2_n": int(m2_den.sum())}


# ------------------------------------------------------------------------------------------- data
def load_noahh_025():
    """DC mosaic -> 0.25 m AOI grid, nearest neighbour, no shift (same affine reader as the other sources)."""
    from rasterio.warp import Resampling

    from .multiwindow_x3 import to_local_win
    sc = Scene("jezero")
    a = to_local_win(DC, sc, sc.extent("aoi"), 0.25, Resampling.nearest)
    a = np.where(np.isfinite(a), a, 0)
    a[(a < 1) | (a > 14)] = 0
    return a.astype(np.uint8)


def our_layers():
    """N3: recompute flags and classes from stored features and slope with the unchanged code."""
    from . import terrain as TR
    from .sandfield import classify
    T = dict(np.load(APP / "data_work/jezero/terrain_2m.npz"))
    G = dict(np.load(APP / "data_work/jezero/sand_v2_features.npz"))
    sand, parts = classify(G, T["slope_ref"], 2.0)
    c, _ = TR.classify_ref(T["slope_ref"], T["rough_ref"], sand, TR.PARAMS)
    same = int((c != T["class_ref"]).sum())
    layer = np.where(parts["coarse"], 1, np.where(parts["fine"], 2, 3)).astype(np.uint8)   # 1 coarse, 2 fine only, 3 fill
    return T, layer, same


def stage_invariants():
    import rasterio
    T, layer, ndiff = our_layers()
    with rasterio.open(DC) as d:
        info = {"crs": d.crs.to_string(), "transform": list(d.transform)[:6], "nodata": d.nodata, "shape": [d.height, d.width],
                "dtype": d.dtypes[0]}
    clr = DC.parent / "DescriptiveClasses.clr"
    nh = load_noahh_025()
    cov = float((nh > 0).mean())
    out = {"class_ref_cells_differ": ndiff, "dc": info, "clr_file": str(clr.name) if clr.exists() else None,
           "clr_text": clr.read_text(errors="replace")[:2000] if clr.exists() else None, "aoi_valid_pixel_share": round(cov, 4)}
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "n_invariants.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "clr_text"}))
    print(out["clr_text"])
    if ndiff:
        sys.exit("STOP: recomputed class_ref differs from the frozen one")
    if cov < 0.5:
        print("coverage < 50 %: overall verdict will be 'insufficient'")


def stage_names():
    """Name check (after the rule commit): the paper states the landing site is 'Bedrock - fractured' (code 13)."""
    nh = load_noahh_025()
    sc = Scene("jezero"); e = sc.extent("aoi")
    r0, c0 = int((e[3] - 0.0) / 0.25), int((0.0 - e[0]) / 0.25)
    win = nh[r0 - 8:r0 + 8, c0 - 8:c0 + 8]
    vals, n = np.unique(win, return_counts=True)
    mode = int(vals[np.argmax(n)])
    out = {"landing_site_4m_window_mode_code": mode, "expected": 13, "ok": mode == 13}
    write_json(OUT / "n_names_check.json", out); print(out)
    if mode != 13:
        sys.exit("STOP: landing-site code is not 13 (Bedrock - fractured): code table / names inconsistent")


def cell_validity(nh):
    from scipy.ndimage import distance_transform_edt
    cnt = cell_counts(nh)
    nod = nh == 0
    dist = distance_transform_edt(~nod) * 0.25 if nod.any() else np.full(nh.shape, np.inf)
    H, W = cnt.shape[:2]
    dmin = dist[:H * CELL_PX, :W * CELL_PX].reshape(H, CELL_PX, W, CELL_PX).min(axis=(1, 3))
    valid = (group_counts(cnt, range(1, 15)) >= 0.5 * CELL_PX * CELL_PX) & (dmin >= EDGE_M)
    return cnt, valid


def stage_align():
    """N7: NOAH-H class boundaries over the 0.25 m ortho: AOI thumbnail + 6 blocks (t >= 0.5 or boulders >= 0.5)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rasterio
    from scipy.ndimage import binary_dilation
    nh = load_noahh_025()
    cnt, valid = cell_validity(nh)
    vc = cnt * valid[..., None]
    vp = block_sum(group_counts(vc, range(1, 15))).astype(float)
    t = block_sum(group_counts(vc, T_CODES)) / np.maximum(vp, 1)
    bo = block_sum(group_counts(vc, (11,))) / np.maximum(vp, 1)
    bvalid = block_sum(valid.astype(int)) >= 0.5 * BLOCK * BLOCK
    cand = np.argwhere(bvalid & ((t >= 0.5) | (bo >= 0.5)))
    rng = np.random.default_rng(SEED)
    pick = cand[rng.choice(len(cand), min(6, len(cand)), replace=False)] if len(cand) else []
    o = rasterio.open(APP / "data_work/jezero/ortho_025.tif").read(1)
    edge = binary_dilation(np.diff(nh.astype(int), axis=1, prepend=0) != 0) | binary_dilation(np.diff(nh.astype(int), axis=0, prepend=0) != 0)
    QA.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(o[::16, ::16], cmap="gray"); e = edge[::16, ::16]
    ov = np.zeros(e.shape + (4,)); ov[e] = (0, 1, 1, 0.6); ax.imshow(ov); ax.axis("off")
    ax.set_title("N7: NOAH-H class boundaries (cyan) over the HiRISE 0.25 m ortho, main AOI (no shift applied)")
    fig.tight_layout(); fig.savefig(QA / "N7_alignment_overview.png", dpi=90); plt.close(fig)
    fig, axs = plt.subplots(2, 3, figsize=(18, 12))
    for a_, (bi, bj) in zip(axs.ravel(), pick):
        r0, c0 = bi * BLOCK * CELL_PX, bj * BLOCK * CELL_PX; s = BLOCK * CELL_PX
        a_.imshow(o[r0:r0 + s, c0:c0 + s], cmap="gray")
        ov = np.zeros((s, s, 4)); ov[edge[r0:r0 + s, c0:c0 + s]] = (0, 1, 1, 0.8); a_.imshow(ov)
        a_.set_title(f"block ({bi},{bj}) 60 m: t {t[bi, bj]:.2f}, boulders {bo[bi, bj]:.2f}"); a_.axis("off")
    fig.suptitle("N7: NOAH-H boundaries on 6 blocks (seed 20261114; t >= 0.5 or boulder fields >= 0.5). Look for a systematic offset > 10 m.")
    fig.tight_layout(); fig.savefig(QA / "N7_alignment_blocks.png", dpi=80); plt.close(fig)
    write_json(OUT / "n7_picks.json", {"blocks": [list(map(int, p)) for p in pick], "n_candidates": int(len(cand))})
    print("N7 figures written; candidates", len(cand))


def stage_metrics():
    f = OUT / "n_result.json"
    if f.exists():
        raise SystemExit("N1 metrics already computed once")
    t0 = time.time()
    T, layer, ndiff = our_layers()
    assert ndiff == 0
    ref = T["class_ref"]
    nh = load_noahh_025()
    cnt, valid = cell_validity(nh)
    B = blocks_from_cells(cnt, valid, ref, layer)
    M = metrics(B)
    cov = float((nh > 0).mean())
    v1, v2 = verdict_m1(M["M1"], M["M1_n"]), verdict_m2(M["M2"], M["M2_n"])
    ov = overall(v1, v2, cov)
    sand = ref == 2
    layer_share = {k: float(((layer == i) & sand).sum() / sand.sum()) for i, k in ((1, "coarse"), (2, "fine_only"), (3, "fill"))}
    vb = B["valid"]
    fine_blocks = vb & B["sand"] & ~B["coarse"] & (B["s_px"] > 0)
    desc_fine = {k: {"n": int(fine_blocks.sum()), "median": float(np.median(B[k][fine_blocks])) if fine_blocks.any() else None,
                     "mean": float(np.mean(B[k][fine_blocks])) if fine_blocks.any() else None} for k in ("r_s", "l_s", "q_s", "x_s")}
    a = B["sand"][vb]; b = (B["r"] >= 0.5)[vb]
    two = {"both_sand": int((a & b).sum()), "ours_only": int((a & ~b).sum()), "noahh_only": int((~a & b).sum()), "neither": int((~a & ~b).sum()),
           "agreement": float(np.mean(a == b)), "kappa": kappa(a, b), "n": int(vb.sum())}
    conf = {}
    vc = cnt * valid[..., None]
    for k in range(4):
        conf[str(k)] = {str(c): int(vc[ref == k][:, c].sum()) for c in range(1, 15)}
    iso_b = vb & (B["iso"] >= 0.5); small_b = vb & (B["small"] >= 0.5)
    desc_e = {"isolated_large_dominant": {"n": int(iso_b.sum()), "share_our_sand": float(B["sand"][iso_b].mean()) if iso_b.any() else None},
              "small_ripples_dominant": {"n": int(small_b.sum()), "share_our_sand": float(B["sand"][small_b].mean()) if small_b.any() else None}}
    out = {"label": "consistency with an independent classifier (NOAH-H, Wright et al. 2022, CC BY 4.0; derived (third-party model)); not validation",
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "aoi_valid_pixel_share": cov,
           "valid_cells_share": float(valid.mean()), "valid_blocks": int(vb.sum()), "blocks_total": int(vb.size),
           **M, "verdict_M1": v1, "verdict_M2": v2, "overall": ov, "X_coarse_share": layer_share["coarse"], "layer_shares": layer_share,
           "fine_blocks_shares": desc_fine, "two_by_two": two, "confusion_2m_pixels": conf, "dominance_e": desc_e,
           "option_B_allowed": layer_share["coarse"] >= 0.5, "seconds": None}
    out["seconds"] = round(time.time() - t0, 1)
    write_json(f, out)
    np.savez_compressed(OUT / "n_blocks.npz", **{k: np.asarray(v) for k, v in B.items()})
    print(json.dumps({k: out[k] for k in ("M1", "M1_n", "M2", "M2_n", "verdict_M1", "verdict_M2", "overall", "X_coarse_share", "layer_shares", "two_by_two", "aoi_valid_pixel_share", "valid_blocks")}))


def stage_figures():
    """N9: overview (Chinese labels) and the sign-off sheet; internal QA only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import rasterio
    for fp in ("/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
               "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"):
        try:
            font_manager.fontManager.addfont(fp); plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name(); break
        except Exception:  # noqa: BLE001
            continue
    R = read_json(OUT / "n_result.json")
    B = dict(np.load(OUT / "n_blocks.npz"))
    T = dict(np.load(APP / "data_work/jezero/terrain_2m.npz")); ref = T["class_ref"]
    nh = load_noahh_025()
    words = {"agree": "一致", "partial": "部分一致", "severe": "嚴重不一致", "insufficient": "不足以判定"}
    head = (f"判定：{words[R['overall']]}（M1 漏判方向 {R['M1']:.2f}，n={R['M1_n']}：{words[R['verdict_M1']]}；"
            f"M2 誤判方向 {R['M2']:.2f}，n={R['M2_n']}：{words[R['verdict_M2']]}）。NOAH-H 只看得到我們沙地的 {100 * R['X_coarse_share']:.0f}%（粗沙紋層）")
    grp = np.zeros(nh.shape, np.uint8)
    for codes, g in ((RIPPLE[:3], 1), (SMALL, 2), (LOOSE, 3), (UNCERTAIN, 4), (AGAINST, 5)):
        grp[np.isin(nh, codes)] = g
    pal5 = np.array([[30, 30, 30], [230, 60, 40], [250, 160, 60], [210, 200, 150], [150, 150, 220], [70, 110, 70]], np.uint8)
    o = rasterio.open(APP / "data_work/jezero/ortho_025.tif").read(1)[::8, ::8]
    fig, ax = plt.subplots(1, 3, figsize=(21, 8))
    ax[0].imshow(o, cmap="gray"); s = np.zeros(ref.shape + (4,)); s[ref == 2] = (1, 0.3, 0.1, 0.55)
    ax[0].imshow(s, extent=(0, o.shape[1], o.shape[0], 0)); ax[0].set_title("我們的沙地（紅）"); ax[0].axis("off")
    ax[1].imshow(pal5[grp[::8, ::8]]); ax[1].set_title("NOAH-H：紅＝大型沙紋，橘＝小型沙紋，米＝鬆散物，紫＝不確定，綠＝岩盤／礫石，黑＝無資料"); ax[1].axis("off")
    S, rr, vb = B["sand"], B["r"] >= 0.5, B["valid"]
    tt = B["t"] >= 0.5
    cat = np.full(S.shape, 0, np.uint8)
    cat[vb & S & rr] = 1; cat[vb & S & ~rr] = 2; cat[vb & ~S & tt] = 3; cat[vb & ~S & ~tt] = 4
    pal = np.array([[60, 60, 60], [40, 160, 70], [230, 120, 40], [60, 120, 220], [220, 220, 220]], np.uint8)
    ax[2].imshow(o, cmap="gray", alpha=0.5)
    ax[2].imshow(np.dstack([pal[cat], np.full(cat.shape, 170, np.uint8)]), extent=(0, o.shape[1], o.shape[0], 0), interpolation="nearest")
    ax[2].set_title("60 m 方塊：綠＝兩邊都說沙，橘＝只有我們說沙，藍＝只有 NOAH-H 說連續大沙紋，白＝兩邊都說不是，灰＝無效"); ax[2].axis("off")
    for a_ in ax:
        a_.title.set_fontsize(10)
    fig.suptitle(head + "\nNOAH-H 類別：Wright et al. 2022，CC BY 4.0（第三方模型）；一致性對照，不是驗證", fontsize=12)
    QA.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(QA / "N1_overview.png", dpi=80); plt.close(fig)
    # sign-off sheet
    from scipy.ndimage import binary_dilation
    cnt, valid = cell_validity(nh)
    cov90 = (block_sum(valid.astype(int)) >= 0.9 * BLOCK * BLOCK)
    rng = np.random.default_rng(SEED)
    sets = {"top_sand": cov90 & S & (B["r"] >= 0.5), "top_not": cov90 & ~S & (B["r"] < 0.1),
            "ours_not_noahh": cov90 & S & (B["x_s"] >= 0.5), "noahh_not_ours": cov90 & ~S & (B["t"] >= 0.5)}
    want = {"top_sand": 2, "top_not": 2, "ours_not_noahh": 3, "noahh_not_ours": 3}
    o25 = rasterio.open(APP / "data_work/jezero/ortho_025.tif").read(1)
    picks = {}
    for k, m in sets.items():
        idx = np.argwhere(m)
        sel = idx[rng.choice(len(idx), min(want[k], len(idx)), replace=False)] if len(idx) else []
        picks[k] = {"n_available": int(len(idx)), "blocks": [list(map(int, x)) for x in sel]}
        for j, (bi, bj) in enumerate(sel):
            r0, c0 = bi * BLOCK * CELL_PX, bj * BLOCK * CELL_PX; s_ = BLOCK * CELL_PX
            img = o25[r0:r0 + s_, c0:c0 + s_]
            ours = np.kron(ref[bi * BLOCK:(bi + 1) * BLOCK, bj * BLOCK:(bj + 1) * BLOCK] == 2, np.ones((CELL_PX, CELL_PX), bool))
            nr = np.isin(nh[r0:r0 + s_, c0:c0 + s_], RIPPLE)
            fig, ax = plt.subplots(1, 3, figsize=(15, 5.3))
            for a_, (m_, col, ttl) in zip(ax, ((None, None, "原圖（0.25 m，60 m 寬）"), (ours, (1, 0.35, 0.1), "我們判的沙地（橘框）"),
                                               (nr, (0.1, 0.6, 1), "NOAH-H 判的沙紋（藍框）"))):
                a_.imshow(img, cmap="gray"); a_.axis("off"); a_.set_title(ttl, fontsize=11)
                if m_ is not None:
                    e = binary_dilation(m_) & ~m_
                    ov = np.zeros(e.shape + (4,)); ov[binary_dilation(e, iterations=2)] = (*col, 0.95); a_.imshow(ov)
            fig.tight_layout(); fig.savefig(QA / f"N1_{k}_{j + 1}.png", dpi=70); plt.close(fig)
    write_json(QA / "N1_signoff_picks.json", picks)
    lab = {"top_sand": "範例：兩邊都說是沙", "top_not": "範例：兩邊都說不是沙",
           "ours_not_noahh": "爭議：我們說沙、NOAH-H 說岩盤／礫石", "noahh_not_ours": "爭議：NOAH-H 說連續大沙紋、我們說不是"}
    html = ["<!doctype html>", "<!-- SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md -->",
            '<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>沙地對照 NOAH-H</title>',
            "<style>:root{--bg:#fafaf7;--fg:#1d1d1b;--muted:#666;--line:#ddd}@media (prefers-color-scheme: dark){:root{--bg:#161616;--fg:#eee;--muted:#aaa;--line:#333}}"
            "body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1200px;padding:16px}img{width:100%;height:auto;border:1px solid var(--line)}.muted{color:var(--muted)}</style></head><body>",
            "<h1>我們的沙地 對照 NOAH-H（請 Shan 看圖）</h1>", f"<p><b>{head}</b></p>",
            "<p>每張小圖 60 m 寬，三格：原圖｜我們判的沙地（橘框）｜NOAH-H 判的沙紋（藍框）。<b>每張只要回答：像上排的「沙」、像上排的「不是沙」、還是看不出來？</b></p>",
            '<p class="muted">NOAH-H classes: Wright et al. 2022, CC BY 4.0（第三方深度學習模型，同樣只看 HiRISE；一致性對照，不是驗證）。內部 QA，不上產品頁。種子 20261114。</p>']
    for k in ("top_sand", "top_not", "ours_not_noahh", "noahh_not_ours"):
        html.append(f"<h2>{lab[k]}（可抽 {picks[k]['n_available']} 塊，抽 {len(picks[k]['blocks'])} 塊）</h2>")
        for j in range(len(picks[k]["blocks"])):
            html.append(f'<p>{lab[k][:2]} {j + 1}：像沙／不像沙／看不出來？</p><img src="N1_{k}_{j + 1}.png" alt="{lab[k]} {j + 1}">')
    html.append('<h2>另外 3 個有地面照片的地點</h2><p>HiRISE 說是沙、但照片的群眾標註說不是（X1）。每列同樣只問：像沙／不像沙／看不出來？</p>'
                '<img src="../X1_hirise_only_sand_signoff.png" alt="3 waypoints with ground photos"></body></html>')
    (QA / "N1_signoff.html").write_text("\n".join(html))
    print("figures written", {k: (v["n_available"], len(v["blocks"])) for k, v in picks.items()})


if __name__ == "__main__":
    {"invariants": stage_invariants, "align": stage_align, "metrics": stage_metrics, "figures": stage_figures}[sys.argv[1]]()
