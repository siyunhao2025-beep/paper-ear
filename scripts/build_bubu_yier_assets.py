#!/usr/bin/env python3
"""Build the Bubu/Yier sprite library and branded preview assets.

The checked-in source sheets are AI-generated RGBA images arranged as a strict
5 x 2 grid.  This script slices them into normalized transparent sprites,
then creates the README catalogues, video intro background, hero banner, voice
preview card, and Xiaohongshu cover used by the ``bubu-yier-v1`` profile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_DIR = ROOT / "assets" / "characters"
BRAND_DIR = ROOT / "assets" / "brand"


def load_font(size: int, *, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    source = image.convert("RGB")
    scale = max(target_w / source.width, target_h / source.height)
    resized = source.resize(
        (round(source.width * scale), round(source.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def alpha_bbox(image: Image.Image, threshold: int = 8) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    binary = alpha.point(lambda value: 255 if value > threshold else 0)
    bbox = binary.getbbox()
    if bbox is None:
        raise ValueError("Sprite cell is fully transparent")
    return bbox


def normalize_sprite(cell: Image.Image, canvas_size: int = 512, content_size: int = 458) -> Image.Image:
    crop = cell.crop(alpha_bbox(cell))
    scale = min(content_size / crop.width, content_size / crop.height)
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    position = ((canvas_size - resized.width) // 2, (canvas_size - resized.height) // 2)
    canvas.alpha_composite(resized, position)
    return canvas


def ordered_poses(manifest: dict, character: str) -> list[dict]:
    poses = [pose for pose in manifest["poses"] if pose["character"] == character]
    if len(poses) != 20:
        raise ValueError(f"Expected exactly 20 {character} poses, found {len(poses)}")
    return poses


def slice_sheet(sheet_path: Path, poses: Sequence[dict]) -> None:
    if len(poses) != 10:
        raise ValueError(f"Each source sheet must map to 10 poses, got {len(poses)}")
    sheet = Image.open(sheet_path).convert("RGBA")
    for index, pose in enumerate(poses):
        row, column = divmod(index, 5)
        left = round(column * sheet.width / 5)
        right = round((column + 1) * sheet.width / 5)
        top = round(row * sheet.height / 2)
        bottom = round((row + 1) * sheet.height / 2)
        # Two decorations in the generated Bubu 11--20 source sheet cross a
        # nominal cell boundary.  Preserve the complete globe for pose 16,
        # then discard its small spill from pose 17; likewise discard a thin
        # flowchart pointer that spills from pose 13 into pose 14.
        if pose["id"] == "bubu_generalization":
            right = min(sheet.width, right + round(sheet.width / 34))
        elif pose["id"] == "bubu_replication_check":
            left = min(right - 1, left + round(sheet.width / 34))
        elif pose["id"] == "bubu_data_doubt":
            left = min(right - 1, left + round(sheet.width / 50))
        sprite = normalize_sprite(sheet.crop((left, top, right, bottom)))
        output = CHARACTER_DIR / pose["asset"]
        output.parent.mkdir(parents=True, exist_ok=True)
        sprite.save(output, optimize=True)


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, sizes: Iterable[int], *, bold: bool = False):
    for size in sizes:
        font = load_font(size, bold=bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
    return load_font(min(sizes), bold=bold)


def build_catalog(manifest: dict, character: str, output: Path) -> None:
    poses = ordered_poses(manifest, character)
    width, header_h, cell_w, cell_h = 2000, 132, 400, 408
    image = Image.new("RGB", (width, header_h + 4 * cell_h), "#071B36")
    draw = ImageDraw.Draw(image)
    display_name = "一二" if character == "yier" else "布布"
    role = "女声主讲" if character == "yier" else "男声追问"
    accent = "#28D8E8" if character == "yier" else "#FF7465"
    draw.text((56, 26), f"{display_name} · 20 套科研讲解动作", font=load_font(50, bold=True), fill="white")
    draw.text((width - 440, 42), role, font=load_font(32, bold=True), fill=accent)

    for index, pose in enumerate(poses):
        row, column = divmod(index, 5)
        x0 = column * cell_w
        y0 = header_h + row * cell_h
        card = (x0 + 12, y0 + 12, x0 + cell_w - 12, y0 + cell_h - 12)
        draw.rounded_rectangle(card, radius=24, fill="#102A4D", outline="#315477", width=2)
        sprite = Image.open(CHARACTER_DIR / pose["asset"]).convert("RGBA")
        sprite.thumbnail((278, 278), Image.Resampling.LANCZOS)
        image.paste(sprite, (x0 + (cell_w - sprite.width) // 2, y0 + 18), sprite)
        caption = pose["caption_zh"]
        caption_font = fit_text(draw, caption, cell_w - 48, range(32, 21, -1), bold=True)
        caption_box = draw.textbbox((0, 0), caption, font=caption_font)
        draw.text((x0 + (cell_w - (caption_box[2] - caption_box[0])) // 2, y0 + 294), caption, font=caption_font, fill="white")
        detail = f"{pose['emotion_zh']} · {pose['action_zh']}"
        detail_font = fit_text(draw, detail, cell_w - 44, range(22, 15, -1))
        detail_box = draw.textbbox((0, 0), detail, font=detail_font)
        draw.text((x0 + (cell_w - (detail_box[2] - detail_box[0])) // 2, y0 + 342), detail, font=detail_font, fill="#B8C8DB")
        draw.text((x0 + 28, y0 + 24), f"{index + 1:02d}", font=load_font(24, bold=True), fill=accent)
    image.save(output, optimize=True)


def add_text_card(base: Image.Image, box: tuple[int, int, int, int], *, alpha: int = 208) -> Image.Image:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle(box, radius=34, fill=(3, 20, 46, alpha), outline=(42, 220, 236, 225), width=3)
    return Image.alpha_composite(base.convert("RGBA"), overlay)


def build_brand_assets(manifest: dict) -> None:
    source = Image.open(BRAND_DIR / "source" / "bubu_yier_lab_hero.png")
    intro = cover_crop(source, (1920, 1080))
    intro.save(ROOT / "assets" / "bubu_yier_intro_bg.png", optimize=True)

    hero = add_text_card(intro.convert("RGBA"), (64, 62, 1035, 362))
    draw = ImageDraw.Draw(hero)
    draw.text((112, 102), "PAPER-EAR", font=load_font(86, bold=True), fill="white", stroke_width=2, stroke_fill="#06152C")
    draw.text((114, 207), "两只小熊，把一篇论文讲明白", font=load_font(51, bold=True), fill="#FFFFFF")
    draw.text((116, 289), "一二女声主讲 · 布布男声追问 · 原图证据 · 双语字幕", font=load_font(29), fill="#BDEEF4")
    hero.convert("RGB").save(ROOT / "assets" / "hero_banner_bubu_yier.jpg", quality=94, optimize=True)

    preview = ImageEnhance.Brightness(intro).enhance(0.42).convert("RGBA")
    overlay = Image.new("RGBA", preview.size, (2, 14, 34, 82))
    preview = Image.alpha_composite(preview, overlay)
    yier = Image.open(CHARACTER_DIR / "yier_calm_explain.png").convert("RGBA")
    bubu = Image.open(CHARACTER_DIR / "bubu_gentle_question.png").convert("RGBA")
    yier.thumbnail((500, 500), Image.Resampling.LANCZOS)
    bubu.thumbnail((500, 500), Image.Resampling.LANCZOS)
    preview.alpha_composite(yier, (208, 500))
    preview.alpha_composite(bubu, (1210, 500))
    draw = ImageDraw.Draw(preview)
    draw.rounded_rectangle((250, 92, 1670, 448), radius=42, fill=(4, 21, 47, 222), outline="#2ADCEA", width=4)
    title = "两句试听 · 一二主讲 × 布布追问"
    draw.text((960, 145), title, font=load_font(62, bold=True), fill="white", anchor="ma")
    draw.text((960, 254), "听懂方法 · 看清证据 · 跟上科研节奏", font=load_font(40, bold=True), fill="#C7F6FA", anchor="ma")
    draw.text((960, 347), "AI 合成声线 · 非官方配音", font=load_font(30), fill="#FFBEA7", anchor="ma")
    preview.save(ROOT / "assets" / "voice_preview_bubu_yier.png", optimize=True)

    xhs = Image.open(BRAND_DIR / "source" / "xhs_cover_corrected.png").convert("RGB")
    xhs.save(ROOT / "assets" / "xhs_cover_bubu_yier.png", quality=95, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-sprites", action="store_true", help="Rebuild only catalogues and brand assets.")
    args = parser.parse_args()

    manifest_path = CHARACTER_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    yier = ordered_poses(manifest, "yier")
    bubu = ordered_poses(manifest, "bubu")
    if not args.skip_sprites:
        slice_sheet(CHARACTER_DIR / "source" / "yier_01_10.png", yier[:10])
        slice_sheet(CHARACTER_DIR / "source" / "yier_11_20.png", yier[10:])
        slice_sheet(CHARACTER_DIR / "source" / "bubu_01_10.png", bubu[:10])
        slice_sheet(CHARACTER_DIR / "source" / "bubu_11_20.png", bubu[10:])

    build_catalog(manifest, "yier", ROOT / "assets" / "yier_pose_catalog.png")
    build_catalog(manifest, "bubu", ROOT / "assets" / "bubu_pose_catalog.png")
    build_brand_assets(manifest)
    print("Built 40 transparent sprites, two catalogues, and four brand assets.")


if __name__ == "__main__":
    main()
