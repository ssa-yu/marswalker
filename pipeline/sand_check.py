"""Sand-field check figures (version 2 spec, direction.md 沙地的修正與放行 point 2).

For a person who is not a specialist: every crop is 60 m wide at full HiRISE resolution (0.25 m), shown
twice (plain | with the sand classification as a translucent orange fill), with a cross at the centre.
The only question: is the ground under the cross part of a continuous sand/ripple field?
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

SAND_RGBA = (1.0, 0.45, 0.0)


def pick(mask, n, rng, margin):
    rr, cc = np.nonzero(mask[margin:-margin, margin:-margin])
    i = rng.choice(len(rr), size=min(n, len(rr)), replace=False)
    return [(int(rr[k] + margin), int(cc[k] + margin)) for k in i]


def _crop(o025, aoi, cx, cy, half):
    r0 = int(round((aoi[3] - cy - half) / 0.25)); c0 = int(round((cx - half - aoi[0]) / 0.25))
    n = int(2 * half / 0.25)
    return o025[r0:r0 + n, c0:c0 + n]


def draw_pair(ax0, ax1, o025, sand, aoi, res, cx, cy, half, title):
    s = _crop(o025, aoi, cx, cy, half)
    v0, v1 = np.nanpercentile(s, 1), np.nanpercentile(s, 99)
    ext = [cx - half, cx + half, cy - half, cy + half]
    r = int(round((aoi[3] - cy) / res)); c = int(round((cx - aoi[0]) / res)); k = int(half / res)
    m = sand[r - k:r + k, c - k:c + k]
    for a in (ax0, ax1):
        a.imshow(s, cmap="gray", vmin=v0, vmax=v1, extent=ext, interpolation="lanczos")
        a.set_xticks([]); a.set_yticks([])
    rgba = np.zeros(m.shape + (4,)); rgba[..., :3] = SAND_RGBA; rgba[..., 3] = np.where(m, 0.38, 0)
    ax1.imshow(rgba, extent=ext, interpolation="nearest")
    if m.any() and not m.all():
        ax1.contour(np.linspace(cx - half + res / 2, cx + half - res / 2, m.shape[1]),
                    np.linspace(cy + half - res / 2, cy - half + res / 2, m.shape[0]),
                    m.astype(float), levels=[.5], colors=[SAND_RGBA], linewidths=1.0)
    for a in (ax0, ax1):
        a.plot([cx - 6, cx + 6], [cy, cy], c="#00e5ff", lw=1.6); a.plot([cx, cx], [cy - 6, cy + 6], c="#00e5ff", lw=1.6)
        a.plot([cx - 6, cx + 6], [cy, cy], c="k", lw=.5); a.plot([cx, cx], [cy - 6, cy + 6], c="k", lw=.5)
    ax0.set_title(title, fontsize=9, loc="left")
    ax1.set_title("orange = classified sand", fontsize=7, loc="right", color="#b35a00")


def crop_sheet(path, o025, sand, aoi, res, pts, prefix, heading, ncol=4, half=30.0):
    n = len(pts); nrow = int(np.ceil(n / ncol))
    fig, axs = plt.subplots(nrow, 2 * ncol, figsize=(2 * ncol * 2.6, nrow * 2.95 + 0.9))
    axs = np.atleast_2d(axs)
    for a in axs.ravel():
        a.axis("off")
    for i, (cx, cy) in enumerate(pts):
        r, c = divmod(i, ncol)
        a0, a1 = axs[r, 2 * c], axs[r, 2 * c + 1]
        a0.axis("on"); a1.axis("on")
        draw_pair(a0, a1, o025, sand, aoi, res, cx, cy, half, f"{prefix}{i + 1:02d}  x {cx:.0f}, y {cy:.0f}")
    fig.suptitle(heading, fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.9 / (nrow * 2.95 + 0.9)), h_pad=1.2)
    fig.savefig(path, dpi=100); plt.close(fig)


def overview(path, o2, sand_old, sand_new, aoi, title_old, title_new, heading, extra=None):
    e = [aoi[0], aoi[2], aoi[1], aoi[3]]
    v0, v1 = np.nanpercentile(o2, 1), np.nanpercentile(o2, 99)
    panels = [(sand_old, title_old), (sand_new, title_new)]
    fig, axs = plt.subplots(1, len(panels), figsize=(11 * len(panels), 11.6))
    for a, (m, t) in zip(axs, panels):
        a.imshow(o2, cmap="gray", vmin=v0, vmax=v1, extent=e)
        rgba = np.zeros(m.shape + (4,)); rgba[..., :3] = SAND_RGBA; rgba[..., 3] = np.where(m, 0.45, 0)
        a.imshow(rgba, extent=e, interpolation="nearest")
        a.plot(0, 0, marker="*", ms=16, c="#00e5ff", mec="k"); a.text(25, 25, "habitat", color="#00e5ff", fontsize=10)
        a.set_title(f"{t}\nsand = {100 * m.mean():.1f} % of the area", fontsize=12)
        a.set_xlabel("x east of habitat (m)")
        if extra:
            extra(a)
    axs[0].set_ylabel("y north of habitat (m)")
    axs[-1].legend(handles=[Patch(color=SAND_RGBA, alpha=.6, label="classified sand")], loc="lower right")
    fig.suptitle(heading, fontsize=13)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)
