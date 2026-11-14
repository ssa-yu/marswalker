# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""ST1: Stack et al. 2020 (Mars 2020 Science Team photogeologic map) vs our sand classes v2 — consistency with the
Mars 2020 Science Team photogeologic map, main AOI only. Third reference next to NOAH-H (N1).

.conda-env/bin/python -I tools/stack_run.py invariants   # N3 recomputed, ST1 stop conditions, CRS, AOI coverage
.conda-env/bin/python -I tools/stack_run.py align        # ST8 alignment figure (only Stack boundaries on the ortho)
.conda-env/bin/python -I tools/stack_run.py metrics      # ST2-ST6 (run once)
.conda-env/bin/python -I tools/stack_run.py figures      # ST9 (three-way figure, Chinese labels)

Rules: manager 2026-11-14, TECH_LEAD_BRIEF 第十九次更新 ST0-ST10 (written before any NOAH-H or Stack comparison
number); copied into DATA_LOG "ST1 Stack 2020 cross-check — rule written BEFORE the comparison". Summary:
ST2 one Stack class per 0.25 m pixel: the surficial unit if any covering polygon has one, else bare bedrock (inside a
   polygon), else no data. Surficial overlaps: Ab-l / Ab-s / T over Us -> the former; Ab-l with Ab-s -> "aeolian"
   (merged metrics only; dropped from the large / small descriptions); any other combination -> no data (area kept).
   MAIN: sand (support) = Ab-l, Ab-s; compatible = Us >~75 %, Us 25-75 %; against = bare bedrock, Us >0-25 %, T.
   SIDE (described only): Us >~75 % -> sand (affects M1s only); Us >0-25 % -> compatible (affects M2s only).
ST3 polygons in the CRS of ortho_025.tif (identical here, no transform), rasterised on the 0.25 m AOI grid
   (pixel centre inside), no shift. 2 m cell = 64 pixels; cell valid = >= 50 % pixels with a Stack class (no 30 m
   buffer); block valid = >= 50 % cells valid. 60 m blocks, our sand blocks and coarse / fine layers = N2, N3 code.
   Block shares over valid pixels: l = Ab-l, s = Ab-s, a = all aeolian, k = against; on our sand cells: a_s, k_s.
ST4 M1s = share of valid blocks with a >= 0.5 that are our sand blocks; M2s = share of our valid sand blocks with
   k_s >= 0.5, coarse and fine separately (a layer judges only with n >= 20; both < 20 -> merged).
ST5 thresholds = N5; Stack overall = worst judging direction; main-AOI coverage < 50 % -> insufficient.
ST6 three-way table (ours / NOAH-H r >= 0.5 sand, x >= 0.5 not / Stack a >= 0.5 sand, k >= 0.5 not), six classes,
   reference contradictions only sorted into the pre-listed known causes, else "unexplained".
Labels: Stack units `derived (third-party expert map)`, Stack et al. 2020, CC BY 4.0 (2025 correction);
consistency with the Mars 2020 Science Team photogeologic map, not validation / ground truth.
"""
from __future__ import annotations

import json
import math
import sys
import time

import numpy as np

from .common import APP, Scene, read_json, write_json
from . import noahh_check as NC

RAW = APP / "data_raw/jezero/stack2020"
SHP = RAW / "M2020_JEZ_geology_edited_equi0_allquads_v6_archive.shp"
OUT = APP / "data_work/jezero/stack2020"
QA = APP / "qa/jezero/stack2020"
CELL_PX, BLOCK, SEED = NC.CELL_PX, NC.BLOCK, NC.SEED

# unit values in the file (SurfUName / BedrkUName), checked against the paper (4 surficial + 15 bedrock units)
SURF_VALUES = {"Aeolian bedforms, large": "Ab-l", "Aeolian bedforms, small": "Ab-s",
               "Undifferentiated smooth": "Us-full", "Moderate Cover Us": "Us-moderate", "Minor Cover Us": "Us-minor",
               "Talus": "T"}
BEDROCK_VALUES = {"Crater floor fractured 1": "Cf-f-1", "Crater floor fractured 2": "Cf-f-2",
                  "Crater floor fractured rough": "Cf-fr", "Margin fractured": "M-f", "Delta blocky": "D-bl",
                  "Delta thinly layered": "D-tnl", "Delta thickly layered": "D-tkl",
                  "Delta truncated curvilinear layered": "D-tcl", "Delta layered rough": "D-lr",
                  "Crater rim blocky": "Cr-bl", "Crater rim breccia": "Cr-br", "Crater rim layered": "Cr-l",
                  "Crater rim rough": "Cr-r", "Neretva Vallis layered": "NV-l", "Nili Planum fractured": "NP-f"}

# per-pixel Stack classes
NODATA, ABL, ABS, AEOL, US_FULL, US_MOD, US_MIN, TALUS, BEDROCK, CONFLICT = range(10)
NAMES = {NODATA: "no data", ABL: "Ab-l", ABS: "Ab-s", AEOL: "Ab-l+Ab-s overlap (aeolian)", US_FULL: "Us >~75 %",
         US_MOD: "Us 25-75 %", US_MIN: "Us >0-25 %", TALUS: "T", BEDROCK: "bare bedrock",
         CONFLICT: "other surficial overlap (no data)"}
SURF_MASKS = ("Ab-l", "Ab-s", "Us-full", "Us-moderate", "Us-minor", "T")
CLASSED = (ABL, ABS, AEOL, US_FULL, US_MOD, US_MIN, TALUS, BEDROCK)
AEOLIAN = (ABL, ABS, AEOL)
MAIN_AGAINST = (BEDROCK, US_MIN, TALUS)
MAIN_COMPAT = (US_FULL, US_MOD)
SIDE_SAND = (ABL, ABS, AEOL, US_FULL)          # side version: Us >~75 % counts as sand (M1s only)
SIDE_AGAINST = (BEDROCK, TALUS)                # side version: Us >0-25 % compatible (M2s only)


# ------------------------------------------------------------------------------------------ pure helpers
def combine(m):
    """ST2. m: dict of boolean arrays: 'any' (inside any polygon) and the six surficial masks. Returns uint8 classes."""
    abl, abs_, t = m["Ab-l"], m["Ab-s"], m["T"]
    usf, usm, usn = m["Us-full"], m["Us-moderate"], m["Us-minor"]
    strong = abl | abs_ | t                                   # these win over Us
    n_us = usf.astype(np.uint8) + usm + usn
    n_strong = abl.astype(np.uint8) + abs_ + t
    out = np.full(abl.shape, NODATA, np.uint8)
    out[m["any"]] = BEDROCK
    # Us only (no strong unit): one grade -> that grade, several grades -> conflict
    us_only = ~strong & (n_us >= 1)
    out[us_only & usf & (n_us == 1)] = US_FULL
    out[us_only & usm & (n_us == 1)] = US_MOD
    out[us_only & usn & (n_us == 1)] = US_MIN
    out[us_only & (n_us > 1)] = CONFLICT
    # strong units (Us underneath is ignored)
    out[(n_strong == 1) & abl] = ABL
    out[(n_strong == 1) & abs_] = ABS
    out[(n_strong == 1) & t] = TALUS
    out[abl & abs_ & ~t] = AEOL
    out[t & (abl | abs_)] = CONFLICT
    return out


def cell_counts(cls):
    """(H*8, W*8) Stack classes -> (H, W, 10) pixel counts per class."""
    H, W = cls.shape[0] // CELL_PX, cls.shape[1] // CELL_PX
    v = cls[:H * CELL_PX, :W * CELL_PX].reshape(H, CELL_PX, W, CELL_PX)
    out = np.zeros((H, W, 10), np.int32)
    for c in range(10):
        out[..., c] = (v == c).sum(axis=(1, 3))
    return out


def cell_valid(cnt):
    return NC.group_counts(cnt, CLASSED) >= 0.5 * CELL_PX * CELL_PX


def blocks_from_cells(cnt, valid, ref, layer):
    """Block quantities (valid pixels of valid cells), our sand blocks and layers exactly as in N1."""
    vc = cnt * valid[..., None]
    vp = NC.block_sum(NC.group_counts(vc, CLASSED)).astype(float)
    sh = lambda g: NC.block_sum(NC.group_counts(vc, g)) / np.maximum(vp, 1)   # noqa: E731
    sand = ref == 2
    sc = vc * sand[..., None]
    s_px = NC.block_sum(NC.group_counts(sc, CLASSED)).astype(float)
    sh_s = lambda g: NC.block_sum(NC.group_counts(sc, g)) / np.maximum(s_px, 1)   # noqa: E731
    block_valid = NC.block_sum(valid.astype(int)) >= 0.5 * BLOCK * BLOCK
    our_sand_block = NC.block_sum(sand.astype(int)) >= 0.5 * BLOCK * BLOCK
    coarse_cells = NC.block_sum((sand & (layer == 1)).astype(int)); sand_cells = NC.block_sum(sand.astype(int))
    coarse_block = (coarse_cells >= 0.5 * np.maximum(sand_cells, 1)) & our_sand_block
    return {"l": sh((ABL,)), "s": sh((ABS,)), "a": sh(AEOLIAN), "k": sh(MAIN_AGAINST),
            "a_side": sh(SIDE_SAND), "k_side": sh(SIDE_AGAINST), "us_full": sh((US_FULL,)),
            "a_s": sh_s(AEOLIAN), "k_s": sh_s(MAIN_AGAINST), "k_s_side": sh_s(SIDE_AGAINST),
            "valid": block_valid, "sand": our_sand_block, "coarse": coarse_block,
            "fine": our_sand_block & ~coarse_block, "s_px": s_px}


def _share(num_mask, den_mask):
    n = int(den_mask.sum())
    return (float(num_mask[den_mask].mean()) if n else math.nan), n


def metrics(B, a_key="a", ks_key="k_s"):
    v = B["valid"]
    m1, n1 = _share(B["sand"], v & (B[a_key] >= 0.5))
    out = {"M1s": m1, "M1s_n": n1}
    for lay in ("coarse", "fine"):
        den = v & B[lay] & (B["s_px"] > 0)
        out[f"M2s_{lay}"], out[f"M2s_{lay}_n"] = _share(B[ks_key] >= 0.5, den)
    den = v & B["sand"] & (B["s_px"] > 0)
    out["M2s_merged"], out["M2s_merged_n"] = _share(B[ks_key] >= 0.5, den)
    return out


def verdict(M, coverage):
    """ST5: per-direction verdicts and the Stack overall verdict (worst judging direction)."""
    v = {"M1s": NC.verdict_m1(M["M1s"], M["M1s_n"])}
    judging = [lay for lay in ("coarse", "fine") if M[f"M2s_{lay}_n"] >= 20]
    if judging:
        for lay in judging:
            v[f"M2s_{lay}"] = NC.verdict_m2(M[f"M2s_{lay}"], M[f"M2s_{lay}_n"])
    else:
        v["M2s_merged"] = NC.verdict_m2(M["M2s_merged"], M["M2s_merged_n"])
    rank = {"agree": 0, "partial": 1, "insufficient": 1, "severe": 2}
    worst = max(v.values(), key=lambda x: rank[x])
    overall = "insufficient" if coverage < 0.5 else ("partial" if worst == "insufficient" else worst)
    return {"directions": v, "judging_M2s_layers": judging or ["merged"], "overall": overall}


THREE_WAY = ("all_three_sand", "all_three_not", "only_ours_sand", "both_refs_sand_ours_not", "refs_contradict", "other")


def three_way(ours, n_say, s_say):
    """ST6 (1). ours: bool; n_say / s_say: +1 sand, -1 not, 0 unclear. Returns int index into THREE_WAY."""
    out = np.full(ours.shape, 5, np.uint8)
    out[ours & (n_say == 1) & (s_say == 1)] = 0
    out[~ours & (n_say == -1) & (s_say == -1)] = 1
    out[ours & (n_say == -1) & (s_say == -1)] = 2
    out[~ours & (n_say == 1) & (s_say == 1)] = 3
    out[((n_say == 1) & (s_say == -1)) | ((n_say == -1) & (s_say == 1))] = 4
    return out


def contradiction_causes(S, N):
    """ST6 (2): pre-listed known causes (each counted on its own; 'dominant' = share >= 0.5)."""
    return {"small_ripple_blind_spot": (S["s"] >= 0.5) & (N["n78"] >= 0.5),
            "herringbone_TAR_as_10": (S["l"] >= 0.5) & (N["n10"] >= 0.5),
            "large_ripples_as_bedrock": (S["l"] >= 0.5) & (N["nbed"] >= 0.5),
            "Ab-l_80pct_and_generalisation": (N["r"] >= 0.5) & (S["k"] >= 0.5) & (S["a"] >= 0.2)}


# ------------------------------------------------------------------------------------------- data
def read_polygons():
    """Shapefile -> list of (shapely geometry (valid), SurfUName, BedrkUName); features without geometry dropped."""
    import shapely
    import shapely.wkb
    from osgeo import ogr
    ogr.UseExceptions()
    ds = ogr.Open(str(SHP)); L = ds.GetLayer(0)
    out, nullg, invalid = [], 0, 0
    for ft in L:
        g = ft.GetGeometryRef()
        if g is None:
            nullg += 1
            continue
        geom = shapely.wkb.loads(bytes(g.ExportToWkb()))
        if not geom.is_valid:
            invalid += 1
            geom = shapely.make_valid(geom)
        out.append((geom, ft.GetField("SurfUName"), ft.GetField("BedrkUName")))
    return out, {"null_geometry": nullg, "invalid_made_valid": invalid, "features": int(L.GetFeatureCount())}


def aoi_transform(sc):
    e = sc.extent("aoi")
    return sc.grid.src_transform(e[0], e[3], 0.25), (int(round((e[3] - e[1]) / 0.25)), int(round((e[2] - e[0]) / 0.25)))


def rasterise(polys, sc):
    """ST3: pixel centre inside, on the 0.25 m AOI grid (CRS identical to ortho_025.tif: no transform), no shift."""
    from rasterio.features import rasterize
    tr, shape = aoi_transform(sc)
    def burn(sel):
        geoms = [g for g, su, bu in polys if sel(su)]
        if not geoms:
            return np.zeros(shape, bool)
        return rasterize(((g, 1) for g in geoms), out_shape=shape, transform=tr, fill=0, all_touched=False, dtype="uint8") > 0
    inv = {v: k for k, v in SURF_VALUES.items()}
    m = {"any": burn(lambda su: True)}
    for key in SURF_MASKS:
        m[key] = burn(lambda su, name=inv[key]: su == name)
    return m


def stack_classes(sc=None):
    sc = sc or Scene("jezero")
    polys, info = read_polygons()
    return combine(rasterise(polys, sc)), polys, info


def check_stop_conditions(polys, info):
    """ST1 (a), (b), (d), (e) on the file; (c) from the README text, recorded in DATA_LOG."""
    import pyproj
    import rasterio
    su = {p[1] for p in polys}; bu = {p[2] for p in polys}
    stops = []
    if (su - {None}) != set(SURF_VALUES):
        stops.append(f"(a/b) surficial values {sorted(map(str, su))}")
    if bu != set(BEDROCK_VALUES):
        stops.append(f"(a) bedrock values {sorted(map(str, bu))}")
    if None in bu:
        stops.append("(d) polygon without a bedrock unit")
    src = pyproj.CRS.from_wkt(SHP.with_suffix(".prj").read_text())
    with rasterio.open(APP / "data_work/jezero/ortho_025.tif") as o:
        dst = pyproj.CRS.from_wkt(o.crs.to_wkt())
    if src != dst:
        try:
            pyproj.Transformer.from_crs(src, dst, always_xy=True)
        except Exception as ex:  # noqa: BLE001
            stops.append(f"(e) CRS {ex}")
    return stops, {"crs_equal": bool(src == dst), **info}


def noahh_blocks():
    """NOAH-H block shares with the N1 code (valid cells, 30 m edge rule) incl. the shares ST6 (2) needs."""
    nh = NC.load_noahh_025()
    cnt, valid = NC.cell_validity(nh)
    vc = cnt * valid[..., None]
    vp = NC.block_sum(NC.group_counts(vc, range(1, 15))).astype(float)
    sh = lambda g: NC.block_sum(NC.group_counts(vc, g)) / np.maximum(vp, 1)   # noqa: E731
    return {"r": sh(NC.RIPPLE), "x": sh(NC.AGAINST), "t": sh(NC.T_CODES), "n78": sh((7, 8)), "n10": sh((10,)),
            "nbed": sh((2, 4, 13)), "valid": NC.block_sum(valid.astype(int)) >= 0.5 * BLOCK * BLOCK}, nh


# ------------------------------------------------------------------------------------------- stages
def stage_invariants():
    """Order of ST10: N3 passed (recomputed class_ref = frozen), ST1 not triggered, coverage."""
    T, layer, ndiff = NC.our_layers()
    nres = read_json(NC.OUT / "n_result.json")
    polys, info = read_polygons()
    stops, facts = check_stop_conditions(polys, info)
    cls, _, _ = stack_classes()
    cov = float(np.isin(cls, CLASSED).mean())                 # pixels with a Stack class (ST5 coverage)
    cov_any = float((cls != NODATA).mean())                   # inside any polygon (incl. overlap conflicts)
    out = {"class_ref_cells_differ": ndiff, "N1_overall": nres["overall"], "st1_stops": stops, **facts,
           "aoi_pixel_share_inside_any_polygon": round(cov_any, 6), "aoi_pixel_share_with_class": round(float(np.isin(cls, CLASSED).mean()), 6)}
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "st_invariants.json", out)
    print(json.dumps(out))
    if ndiff:
        sys.exit("STOP: N3 not passed (recomputed class_ref differs)")
    if stops:
        sys.exit(f"STOP (ST1): {stops}")
    if cov < 0.5:
        print("coverage < 50 %: Stack overall will be 'insufficient'")


def _poly_px(g, tr):
    """Exterior and interior rings of a (multi)polygon in AOI pixel coordinates."""
    inv = ~tr
    rings = []
    for p in getattr(g, "geoms", [g]):
        if p.geom_type != "Polygon":
            continue
        for ring in [p.exterior, *p.interiors]:
            xy = np.asarray(ring.coords)
            c, r = inv * (xy[:, 0], xy[:, 1])
            rings.append((np.asarray(c), np.asarray(r)))
    return rings


def stage_align():
    """ST8: Stack polygon boundaries (lines only, no fill, none of our classes) over the 0.25 m ortho."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import rasterio
    sc = Scene("jezero")
    cls, polys, _ = stack_classes(sc)
    cnt = cell_counts(cls); valid = cell_valid(cnt)
    vc = cnt * valid[..., None]
    vp = NC.block_sum(NC.group_counts(vc, CLASSED)).astype(float)
    l = NC.block_sum(NC.group_counts(vc, (ABL,))) / np.maximum(vp, 1)
    bvalid = NC.block_sum(valid.astype(int)) >= 0.5 * BLOCK * BLOCK
    cand = np.argwhere(bvalid & (l >= 0.2) & (l <= 0.8))
    rng = np.random.default_rng(SEED)
    pick = cand[rng.choice(len(cand), min(6, len(cand)), replace=False)] if len(cand) else []
    o = rasterio.open(APP / "data_work/jezero/ortho_025.tif").read(1)
    tr, shape = aoi_transform(sc)
    QA.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(11, 11))
    ax.imshow(o[::8, ::8], cmap="gray", extent=(0, shape[1], shape[0], 0))
    for g, _, _ in polys:
        for c, r in _poly_px(g, tr):
            if c.max() < 0 or r.max() < 0 or c.min() > shape[1] or r.min() > shape[0]:
                continue
            ax.plot(c, r, color="cyan", lw=0.4)
    ax.set_xlim(0, shape[1]); ax.set_ylim(shape[0], 0); ax.axis("off")
    ax.set_title("ST8: Stack et al. 2020 polygon boundaries (cyan) over the HiRISE 0.25 m ortho, main AOI (no shift)")
    fig.tight_layout(); fig.savefig(QA / "ST1_alignment_overview.png", dpi=90); plt.close(fig)
    fig, axs = plt.subplots(2, 3, figsize=(18, 12))
    s = BLOCK * CELL_PX
    for a_, (bi, bj) in zip(axs.ravel(), pick):
        r0, c0 = bi * s, bj * s
        a_.imshow(o[r0:r0 + s, c0:c0 + s], cmap="gray", extent=(c0, c0 + s, r0 + s, r0))
        for g, _, _ in polys:
            for c, r in _poly_px(g, tr):
                if c.max() < c0 or c.min() > c0 + s or r.max() < r0 or r.min() > r0 + s:
                    continue
                a_.plot(c, r, color="cyan", lw=1.2)
        a_.set_xlim(c0, c0 + s); a_.set_ylim(r0 + s, r0); a_.axis("off")
        a_.set_title(f"block ({bi},{bj}) 60 m: Ab-l share {l[bi, bj]:.2f}")
    for a_ in axs.ravel()[len(pick):]:
        a_.axis("off")
    fig.suptitle("ST8: Stack boundaries on 6 blocks (seed 20261114; 0.2 <= Ab-l share <= 0.8). Look for a systematic offset > 10 m.")
    fig.tight_layout(); fig.savefig(QA / "ST1_alignment_blocks.png", dpi=80); plt.close(fig)
    # combined file required by ST8: overview + blocks side by side
    import matplotlib.image as mpimg
    a1 = mpimg.imread(QA / "ST1_alignment_overview.png"); a2 = mpimg.imread(QA / "ST1_alignment_blocks.png")
    fig, ax = plt.subplots(1, 2, figsize=(26, 10), gridspec_kw={"width_ratios": [a1.shape[1] / a1.shape[0], a2.shape[1] / a2.shape[0]]})
    ax[0].imshow(a1); ax[1].imshow(a2)
    for a_ in ax:
        a_.axis("off")
    fig.tight_layout(); fig.savefig(QA / "ST1_alignment.png", dpi=110); plt.close(fig)
    write_json(OUT / "st8_picks.json", {"blocks": [list(map(int, p)) for p in pick], "n_candidates": int(len(cand))})
    print("ST8 figures written; candidates", len(cand), "picked", [list(map(int, p)) for p in pick])


def _desc_polygon_areas(polys, sc):
    """ST4 (f): polygon areas (m2 on the ground, eqc x-scale corrected) per surficial unit, full map and AOI."""
    from shapely.geometry import box
    k = sc.grid.k
    e = sc.extent("aoi"); b = sc.grid.src_bounds(*e)
    A = box(*b)
    out = {}
    for name, key in SURF_VALUES.items():
        full = np.array([g.area * k for g, su, _ in polys if su == name])
        aoi = np.array([g.area * k for g, su, _ in polys if su == name and g.intersects(A)])
        f = lambda a: ({"n": int(len(a)), "min": float(a.min()), "p5": float(np.percentile(a, 5)), "median": float(np.median(a))}  # noqa: E731
                       if len(a) else {"n": 0})
        out[key] = {"full_map": f(full), "aoi_intersecting": f(aoi)}
    return out


def stage_metrics():
    f = OUT / "st_result.json"
    if f.exists():
        raise SystemExit("ST1 metrics already computed once")
    t0 = time.time()
    sc = Scene("jezero")
    T, layer, ndiff = NC.our_layers()
    assert ndiff == 0
    ref = T["class_ref"]
    cls, polys, info = stack_classes(sc)
    cov = float(np.isin(cls, CLASSED).mean())
    cnt = cell_counts(cls); valid = cell_valid(cnt)
    B = blocks_from_cells(cnt, valid, ref, layer)
    M = metrics(B)
    V = verdict(M, cov)
    vb = B["valid"]
    # (a) descriptions
    m1_large = _share(B["sand"], vb & (B["l"] >= 0.5)); m1_small = _share(B["sand"], vb & (B["s"] >= 0.5))
    # (b) side version
    Ms = metrics(B, a_key="a_side", ks_key="k_s_side")
    # (c) 2x2
    a_ = B["sand"][vb]; b_ = (B["a"] >= 0.5)[vb]
    two = {"both_sand": int((a_ & b_).sum()), "ours_only": int((a_ & ~b_).sum()), "stack_only": int((~a_ & b_).sum()),
           "neither": int((~a_ & ~b_).sum()), "agreement": float(np.mean(a_ == b_)), "kappa": NC.kappa(a_, b_), "n": int(vb.sum())}
    # (d) 2 m area confusion (pixel counts in valid cells; polygon generalisation vs grid, not pixel accuracy)
    vc = cnt * valid[..., None]
    conf = {str(kk): {NAMES[c]: int(vc[ref == kk][:, c].sum()) for c in CLASSED} for kk in range(4)}
    conf_main = {str(kk): {"sand": int(vc[ref == kk][:, list(AEOLIAN)].sum()), "compatible": int(vc[ref == kk][:, list(MAIN_COMPAT)].sum()),
                           "against": int(vc[ref == kk][:, list(MAIN_AGAINST)].sum())} for kk in range(4)}
    # (e) ST6 three-way
    N, _ = noahh_blocks()
    nb = dict(np.load(NC.OUT / "n_blocks.npz"))
    same_n = bool(np.allclose(N["r"], nb["r"]) and np.allclose(N["x"], nb["x"]) and (N["valid"] == nb["valid"]).all())
    both = vb & N["valid"]
    n_say = np.where(N["r"] >= 0.5, 1, np.where(N["x"] >= 0.5, -1, 0))
    s_say = np.where(B["a"] >= 0.5, 1, np.where(B["k"] >= 0.5, -1, 0))
    tw = three_way(B["sand"], n_say, s_say)
    S = {"l": B["l"], "s": B["s"], "a": B["a"], "k": B["k"]}
    causes = contradiction_causes(S, N)
    contra = both & (tw == 4)
    any_cause = np.zeros_like(contra)
    for m_ in causes.values():
        any_cause |= m_
    table = {k: int((both & (tw == i)).sum()) for i, k in enumerate(THREE_WAY)}
    ours_s, ours_n = int((both & B["sand"]).sum()), int((both & ~B["sand"]).sum())
    by_layer = {lay: {k: int((both & B[lay] & (tw == i)).sum()) for i, k in enumerate(THREE_WAY)} for lay in ("coarse", "fine")}
    st6 = {"n_blocks_both_valid": int(both.sum()), "table": table, "by_our_layer_for_our_sand_blocks": by_layer,
           "both_refs_against_us": {"only_ours_sand": table["only_ours_sand"], "share_of_our_sand_blocks": table["only_ours_sand"] / max(ours_s, 1),
                                    "both_refs_sand_ours_not": table["both_refs_sand_ours_not"], "share_of_our_non_sand_blocks": table["both_refs_sand_ours_not"] / max(ours_n, 1),
                                    "our_sand_blocks": ours_s, "our_non_sand_blocks": ours_n},
           "contradictions": {"n": int(contra.sum()), **{k: int((contra & m_).sum()) for k, m_ in causes.items()},
                              "explained_by_any": int((contra & any_cause).sum()), "unexplained": int((contra & ~any_cause).sum()),
                              "noahh_sand_stack_not": int((both & (n_say == 1) & (s_say == -1)).sum()),
                              "stack_sand_noahh_not": int((both & (n_say == -1) & (s_say == 1)).sum())},
           "noahh_blocks_recomputed_equal_stored": same_n}
    # (f) polygon sizes
    areas = _desc_polygon_areas(polys, sc)
    conflict_px = int((cls == CONFLICT).sum())
    out = {"label": "consistency with the Mars 2020 Science Team photogeologic map (Stack et al. 2020; derived (third-party expert map), CC BY 4.0); not validation",
           "computed_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "aoi_pixel_share_with_class": cov,
           "conflict_overlap_pixels": conflict_px, "conflict_overlap_m2": conflict_px * 0.0625,
           "valid_cells_share": float(valid.mean()), "valid_blocks": int(vb.sum()), "blocks_total": int(vb.size),
           **M, "verdicts": V, "stack_overall": V["overall"],
           "desc_a_M1s_large": {"M1s": m1_large[0], "n": m1_large[1]}, "desc_a_M1s_small": {"M1s": m1_small[0], "n": m1_small[1]},
           "desc_b_side_version": Ms, "desc_c_two_by_two": two, "desc_d_confusion_2m_pixels": conf, "desc_d_confusion_main_groups": conf_main,
           "desc_e_three_way": st6, "desc_f_polygon_areas_m2": areas, "file_info": info, "seconds": None}
    out["seconds"] = round(time.time() - t0, 1)
    write_json(f, out)
    np.savez_compressed(OUT / "st_blocks.npz", **{k: np.asarray(v) for k, v in B.items()}, three_way=tw, both_valid=both,
                        n_say=n_say, s_say=s_say)
    print(json.dumps({k: out[k] for k in ("M1s", "M1s_n", "M2s_coarse", "M2s_coarse_n", "M2s_fine", "M2s_fine_n", "M2s_merged",
                                          "M2s_merged_n", "verdicts", "aoi_pixel_share_with_class", "valid_blocks")}))
    print(json.dumps({"side": Ms, "two": two, "three_way": st6, "large": m1_large, "small": m1_small}, default=float))


def stage_figures():
    """ST9: three-way figure for Shan (Chinese labels); internal QA only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Patch
    import rasterio
    for fp in ("/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
               "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"):
        try:
            font_manager.fontManager.addfont(fp); plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name(); break
        except Exception:  # noqa: BLE001
            continue
    R = read_json(OUT / "st_result.json"); RN = read_json(NC.OUT / "n_result.json")
    B = dict(np.load(OUT / "st_blocks.npz"))
    T, layer, ndiff = NC.our_layers(); ref = T["class_ref"]
    cls, _, _ = stack_classes()
    nh = NC.load_noahh_025()
    words = {"agree": "一致", "partial": "部分一致", "severe": "嚴重不一致", "insufficient": "不足以判定"}
    f2 = lambda v: "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.2f}"   # noqa: E731
    line_n = (f"NOAH-H（AI 模型）：{words[RN['overall']]}。外部說是沙的方塊，我們也判沙：{100 * RN['M1']:.0f}%（n={RN['M1_n']}），M2 誤判 {RN['M2']:.2f}（n={RN['M2_n']}），"
              f"它只看得到我們沙地的 X={100 * RN['X_coarse_share']:.0f}%（粗沙紋層）。")
    vd = R["verdicts"]["directions"]
    dname = {"M1s": "M1s", "M2s_coarse": "M2s 粗層", "M2s_fine": "M2s 細層", "M2s_merged": "M2s 兩層合併"}
    line_s = (f"Stack 2020（63 位專家手畫）：{words[R['stack_overall']]}。外部說是沙的方塊，我們也判沙：{100 * R['M1s']:.0f}%（n={R['M1s_n']}）；"
              f"M2s 誤判 粗層 {f2(R['M2s_coarse'])}（n={R['M2s_coarse_n']}）、細層 {f2(R['M2s_fine'])}（n={R['M2s_fine_n']}）"
              f"——判定用：{'，'.join(f'{dname[k]} {words[v]}' for k, v in vd.items())}；細層只有 Stack 一個參考。")
    cap = ("NOAH-H＝歐洲太空總署的 AI 模型（在別處訓練）；Stack 2020＝毅力號科學團隊 63 位專家手畫的地圖；"
           "兩者和我們一樣只看軌道照片，不是地面答案。　NOAH-H: Wright et al. 2022; Stack et al. 2020; CC BY 4.0")
    o = rasterio.open(APP / "data_work/jezero/ortho_025.tif").read(1)[::8, ::8]
    fig = plt.figure(figsize=(22, 17))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1], hspace=0.12)
    ax0, ax1, ax2 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2])
    ext = (0, o.shape[1], o.shape[0], 0)
    # ours: coarse / fine / fill
    ax0.imshow(o, cmap="gray", extent=ext)
    sand = ref == 2
    ov = np.zeros(ref.shape + (4,))
    ov[sand & (layer == 1)] = (0.85, 0.2, 0.1, 0.75); ov[sand & (layer == 2)] = (1.0, 0.65, 0.1, 0.75); ov[sand & (layer == 3)] = (0.6, 0.2, 0.8, 0.75)
    ax0.imshow(ov, extent=ext, interpolation="nearest"); ax0.set_title("我們的沙地")
    ax0.legend(handles=[Patch(color=(0.85, 0.2, 0.1), label="粗沙紋層"), Patch(color=(1.0, 0.65, 0.1), label="細沙紋層"),
                        Patch(color=(0.6, 0.2, 0.8), label="填補")], loc="lower left", fontsize=9)
    # NOAH-H five colours (same as N9)
    grp = np.zeros(nh.shape, np.uint8)
    for codes, g in ((NC.RIPPLE[:3], 1), (NC.SMALL, 2), (NC.LOOSE, 3), (NC.UNCERTAIN, 4), (NC.AGAINST, 5)):
        grp[np.isin(nh, codes)] = g
    pal5 = np.array([[30, 30, 30], [230, 60, 40], [250, 160, 60], [210, 200, 150], [150, 150, 220], [70, 110, 70]], np.uint8)
    ax1.imshow(pal5[grp[::8, ::8]], extent=ext, interpolation="nearest"); ax1.set_title("NOAH-H（AI 模型）")
    ax1.legend(handles=[Patch(color=pal5[i] / 255, label=t) for i, t in ((1, "大型沙紋"), (2, "小型沙紋"), (3, "鬆散物"), (4, "不確定"), (5, "岩盤／礫石"))],
               loc="lower left", fontsize=9)
    # Stack five colours
    sg = np.zeros(cls.shape, np.uint8)
    sg[np.isin(cls, (ABL, AEOL))] = 1; sg[cls == ABS] = 2; sg[np.isin(cls, (US_FULL, US_MOD, US_MIN))] = 3; sg[cls == TALUS] = 4; sg[cls == BEDROCK] = 5
    pals = np.array([[30, 30, 30], [230, 60, 40], [250, 160, 60], [210, 200, 150], [140, 90, 60], [70, 110, 70]], np.uint8)
    ax2.imshow(pals[sg[::8, ::8]], extent=ext, interpolation="nearest"); ax2.set_title("Stack 2020（專家手畫）")
    ax2.legend(handles=[Patch(color=pals[i] / 255, label=t) for i, t in ((1, "大型風成床形"), (2, "小型風成床形"), (3, "平滑覆蓋物"), (4, "崖錐"), (5, "裸露岩床"))],
               loc="lower left", fontsize=9)
    for a_ in (ax0, ax1, ax2):
        a_.axis("off"); a_.title.set_fontsize(13)
    # three-way blocks
    ax3 = fig.add_subplot(gs[1, :])
    tw, both = B["three_way"], B["both_valid"]
    pal6 = np.array([[40, 160, 70], [235, 235, 235], [230, 120, 40], [60, 120, 220], [170, 60, 170], [150, 150, 150]], np.uint8)
    img = np.dstack([pal6[tw], np.where(both, 200, 0).astype(np.uint8)])
    ax3.imshow(o, cmap="gray", extent=ext, alpha=0.6)
    ax3.imshow(img, extent=ext, interpolation="nearest"); ax3.axis("off")
    tb = R["desc_e_three_way"]["table"]
    labels = ["三方都說沙", "三方都說不是", "只有我們說沙（兩個參考都說不是）", "兩個參考都說沙、我們說不是", "兩個參考互相矛盾", "其他（有一方不明）"]
    ax3.legend(handles=[Patch(color=pal6[i] / 255, label=f"{labels[i]}：{tb[THREE_WAY[i]]} 塊") for i in range(6)],
               loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=11)
    ax3.set_title("60 m 方塊三方對照（我們／NOAH-H／Stack；兩個參考都有效的方塊）", fontsize=13, pad=10)
    fig.suptitle(line_n + "\n" + line_s, fontsize=13)
    fig.text(0.5, 0.01, cap, ha="center", fontsize=11)
    QA.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.04, wspace=0.03); fig.savefig(QA / "ST1_three_way.png", dpi=75); plt.close(fig)
    print("ST9 figure written")


if __name__ == "__main__":
    {"invariants": stage_invariants, "align": stage_align, "metrics": stage_metrics, "figures": stage_figures}[sys.argv[1]]()
