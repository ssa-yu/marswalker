# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""X1 figures (no new numbers): (1) panels with the image that has the SAME name as the label: 12 images drawn with a
fixed seed + one image at each HiRISE-only sand waypoint (4_1062, 4_1422, 4_922); (2) a sign-off sheet for Shan:
the 3 HiRISE-only waypoints, HiRISE 0.5 m image with our sand class outlined, the 30 m view sector, and the photo.
python -m spikes.x1_panels -> qa/jezero/ai4mars/X1_panels_same_name.png, qa/jezero/X1_hirise_only_sand_signoff.png"""
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from pipeline.ai4mars_check import AI, sector_mask
from pipeline.common import APP

X = json.loads((APP / "data_work/jezero/ai4mars/x1_result.json").read_text())
T = np.load(APP / "data_work/jezero/terrain_2m.npz"); ref = T["class_ref"]
ext = json.loads((APP / "data_work/jezero/terrain_2m.json").read_text())["extent_local_m"]; res = 2.0
pal = np.array([[98, 214, 164], [244, 183, 64], [255, 90, 78], [138, 63, 174]], np.uint8)
HONLY = ["4_1062", "4_1422", "4_922"]


def img_path(stem):
    for ext_ in (".jpeg", ".jpg", ".png"):
        p = AI / "images/ncam" / (stem + ext_)
        if p.exists():
            return p
    return None


def label_path(stem):
    return AI / "labels/NAV" / (stem + "_merged60.png")


imgs = [i for i in X["images"] if i["geometry"] == "sector" and i["hirise_sand"] is not None and img_path(i["stem"])]
rng = np.random.default_rng(20261114)
pick = [imgs[k] for k in rng.choice(len(imgs), 12, replace=False)]
for w in HONLY:
    c = [i for i in imgs if i["wp"] == w]
    pick.append(sorted(c, key=lambda i: abs(i["view"]["elevation_deg"] + 20))[0])

fig, ax = plt.subplots(5, 6, figsize=(24, 19))
for j, i in enumerate(pick):
    a1, a2 = ax.ravel()[2 * j], ax.ravel()[2 * j + 1]
    im = np.asarray(Image.open(img_path(i["stem"])).convert("RGB")).astype(float)
    lp = label_path(i["stem"])
    if lp.exists():
        lab = np.asarray(Image.open(lp)); lab = lab[..., 0] if lab.ndim == 3 else lab
        if lab.shape == im.shape[:2]:
            m = lab == 2; im[m] = 0.5 * im[m] + 0.5 * np.array([255, 60, 40])
    a1.imshow(im.astype(np.uint8)); a1.axis("off")
    a1.set_title(f"{i['wp']} · {i['stem'][:16]}… elev {i['view']['elevation_deg']:.0f}° · photo sand {i['photo_sand']:.2f} (red = labelled sand)", fontsize=7)
    rr, cc = sector_mask(ref.shape, ext, res, i["x"], i["y"], i["view"]["edge_left_deg"], i["view"]["edge_right_deg"])
    r = 17; c0 = int((i["x"] - ext[0]) / res); r0 = int((ext[3] - i["y"]) / res)
    win = pal[ref[r0 - r:r0 + r + 1, c0 - r:c0 + r + 1]].astype(float) * 0.35
    win[rr - (r0 - r), cc - (c0 - r)] = pal[ref[rr, cc]]
    a2.imshow(win.astype(np.uint8)); a2.axis("off")
    a2.set_title(f"HiRISE classes, 30 m view sector: sand {i['hirise_sand']:.2f}" + ("  [HiRISE-only waypoint]" if j >= 12 else ""), fontsize=7)
fig.suptitle("X1 panels with the same-name image (12 random, seed 20261114, + one per HiRISE-only sand waypoint). Green firm, yellow rough, "
             "red sand, purple blocked. Consistency with crowd labels, not validation.", fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(APP / "qa/jezero/ai4mars/X1_panels_same_name.png", dpi=70); plt.close(fig)

# sign-off sheet
o = np.load(APP / "data_work/jezero/ortho_05.npy", mmap_mode="r")
fig, ax = plt.subplots(3, 3, figsize=(18, 17))
for k, w in enumerate(HONLY):
    c = sorted([i for i in imgs if i["wp"] == w], key=lambda i: abs(i["view"]["elevation_deg"] + 20))
    i = c[0]
    R = 50.0; px = int(R / 0.5)
    cx = int((i["x"] - ext[0]) / 0.5); cy = int((ext[3] - i["y"]) / 0.5)
    chip = np.array(o[cy - px:cy + px, cx - px:cx + px], float)
    a = ax[k, 0]; a.imshow(chip, cmap="gray"); a.set_title(f"{w}: HiRISE 0.5 m, 100 m wide (rover waypoint at centre)", fontsize=9); a.axis("off")
    sand = ref[(cy - px) // 4:(cy + px) // 4, (cx - px) // 4:(cx + px) // 4] == 2
    a = ax[k, 1]; a.imshow(chip, cmap="gray")
    ov = np.zeros(sand.shape + (4,)); ov[sand] = (1, 0.25, 0.15, 0.45)
    a.imshow(ov, extent=(0, 2 * px, 2 * px, 0), interpolation="nearest")
    for th in (i["view"]["edge_left_deg"], i["view"]["edge_right_deg"]):
        a.plot([px, px + 60 * math.sin(math.radians(th))], [px, px - 60 * math.cos(math.radians(th))], color="cyan", lw=1.5)
    a.add_patch(plt.Circle((px, px), 60, fill=False, color="cyan", lw=0.8, ls="--"))
    row = [r for r in X['groups']['sector']['rows'] if r['wp'] == w][0]
    a.set_title(f"our sand class (red); this photo's 30 m view sector (cyan): sand {i['hirise_sand']:.2f}\n"
                f"waypoint value used in X1 = mean over its {row['n_images']} photos (many directions): {row['hirise_sand']:.2f}", fontsize=9); a.axis("off")
    a = ax[k, 2]; a.imshow(Image.open(img_path(i["stem"]))); a.axis("off")
    a.set_title(f"Perseverance Navcam {i['stem'][:24]}… (NASA/JPL-Caltech); crowd-labelled sand {i['photo_sand']:.2f}", fontsize=9)
fig.suptitle("For sign-off: the 3 waypoints where our HiRISE class says 'mostly sand' but the photo labels do not (X1). "
             "Question: is the red area really sand (ripple field)?", fontsize=12)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(APP / "qa/jezero/X1_hirise_only_sand_signoff.png", dpi=80); plt.close(fig)
print("ok")
