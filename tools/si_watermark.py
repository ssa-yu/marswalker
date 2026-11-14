# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Z3: copies of the figures and screenshots meant for the project page or slides, with a visible SI watermark in the
lower-right corner and the same sentence in the PNG text field "SI". Originals are not touched; Perseverance raw
images are never processed here (NASA data, not generated; they keep their credit). Output: qa/submission/.
python tools/si_watermark.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

APP = Path(__file__).resolve().parents[1]
MARK = "Made with AI-written code · data: NASA/JPL-Caltech/UArizona/MSSS/USGS · see AI_USE"
SOURCES = [
    "qa/screenshots/Y1_01_panel_Bv3.png", "qa/screenshots/Y1_02_full_table_two_versions.png",
    "qa/screenshots/W3_01_recon_v3_loop30.png", "qa/screenshots/W3_03_step2_v3.png", "qa/screenshots/W3_04_round7_v3.png",
    "qa/screenshots/W1_01_step2_unlocked_card.png", "qa/screenshots/W1_02_step2_view_all_data.png",
    "qa/screenshots/Y4_01_robustness_no_model_map.png", "qa/screenshots/nav_after_index_1600.png",
    "qa/jezero/multiwindow/T6_windows_A_vs_B.png", "qa/jezero/ai4mars/X1_panels_same_name.png",
    "qa/jezero/S2_ctx_vs_hirise_sand.png", "web/scratch/screenshots",
]


def font(px):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            continue
    return ImageFont.load_default()


def mark(src: Path, dst: Path):
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    f = font(max(12, W // 110))
    d0 = ImageDraw.Draw(im)
    x0, y0, x1, y1 = d0.textbbox((0, 0), MARK, font=f)
    tw, th = x1 - x0, y1 - y0
    pad = max(4, th // 3)
    strip = th + 3 * pad                     # a strip below the image, so the mark never covers content
    canvas = Image.new("RGBA", (W, H + strip), (20, 17, 15, 255)); canvas.paste(im, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.text((W - tw - 2 * pad - x0, H + (strip - th) // 2 - y0), MARK, font=f, fill=(255, 255, 255, 235))
    out = canvas.convert("RGB")
    meta = PngImagePlugin.PngInfo(); meta.add_text("SI", MARK)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, pnginfo=meta)


def main():
    out = APP / "qa/submission"; n = 0
    for s in SOURCES:
        p = APP / s
        files = sorted(p.glob("*.png")) if p.is_dir() else ([p] if p.exists() else [])
        for f in files:
            name = (f.parent.name + "__" if p.is_dir() else "") + f.stem + "_SI.png"
            mark(f, out / name); n += 1
    print("watermarked copies:", n, "->", out)


if __name__ == "__main__":
    main()
