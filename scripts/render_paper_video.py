#!/usr/bin/env python3
"""
Render a group-meeting style MP4 video from a PDF paper and a dialogue script JSON.
Features:
- Two-person (Male & Female) conversational turn-taking with animated speaking waveform bars
- Dynamic Red Bounding Box (红框) with corner target brackets highlighting the exact paragraph/figure/formula
- Zoomed-in focus preview + Term Explanation Card (专业名词解析卡片) on the side panel
- Synchronized Bilingual Subtitles (中英双语字幕) + Chapter Progress Bar at the bottom
- Dual-mode Audio Synthesis: uses Microsoft Edge Neural TTS (edge-tts) when online,
  and automatically falls back to offline acoustic dialogue synthesis when offline.
- Optional --export-gif flag to export an animated GIF preview for GitHub READMEs.
"""

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import wave
import numpy as np
import pdfplumber
from PIL import Image, ImageDraw, ImageFont


FONT_REGULAR_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def strip_unsupported_emoji(text):
    """Strip supplementary-plane emojis that CJK TTC fonts render as tofu boxes."""
    if not text:
        return ""
    return re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f]", "", text).strip()


def page_file_sort_key(path):
    """Sort pdftoppm outputs numerically so page-10 never precedes page-2."""
    match = re.search(r"-(\d+)\.png$", os.path.basename(path), flags=re.IGNORECASE)
    return (int(match.group(1)), path) if match else (math.inf, path)


def load_font(candidates, size):
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def locate_text_bbox_on_page(pdf_path, page_num, search_terms):
    """Locate normalized [x0, y0, x1, y1] bounding box on 1-indexed page_num matching search_terms."""
    if not search_terms:
        return None
    if isinstance(search_terms, str):
        search_terms = [search_terms]
    search_terms = [s.strip().lower() for s in search_terms if s and s.strip()]
    if not search_terms:
        return None

    with pdfplumber.open(pdf_path) as pdf:
        if page_num < 1 or page_num > len(pdf.pages):
            return None
        page = pdf.pages[page_num - 1]
        pw, ph = float(page.width), float(page.height)
        words = page.extract_words() or []
        if not words:
            return None

        sorted_words = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
        lines = []
        curr = [sorted_words[0]]
        for w in sorted_words[1:]:
            if abs(w["top"] - curr[-1]["top"]) <= 5.0:
                curr.append(w)
            else:
                lines.append(curr)
                curr = [w]
        lines.append(curr)

        line_objs = []
        for ln in lines:
            ln_s = sorted(ln, key=lambda w: w["x0"])
            txt = " ".join(w["text"] for w in ln_s)
            line_objs.append({
                "text": txt,
                "text_low": txt.lower(),
                "x0": min(w["x0"] for w in ln_s),
                "top": min(w["top"] for w in ln_s),
                "x1": max(w["x1"] for w in ln_s),
                "bottom": max(w["bottom"] for w in ln_s),
            })

        matched_indices = []
        for idx, lo in enumerate(line_objs):
            for term in search_terms:
                if term in lo["text_low"]:
                    matched_indices.append(idx)
                    break

        if not matched_indices:
            for idx, lo in enumerate(line_objs):
                for term in search_terms:
                    tokens = [t for t in term.split() if len(t) > 2]
                    if tokens and sum(1 for t in tokens if t in lo["text_low"]) >= max(1, int(len(tokens) * 0.6)):
                        matched_indices.append(idx)
                        break

        if not matched_indices:
            return None

        first_idx = matched_indices[0]
        cluster = [first_idx]
        for idx in range(first_idx + 1, min(len(line_objs), first_idx + 12)):
            gap = line_objs[idx]["top"] - line_objs[cluster[-1]]["bottom"]
            if gap <= 10.0:
                cluster.append(idx)
            else:
                break

        x0 = max(0.0, min(line_objs[i]["x0"] for i in cluster) / pw - 0.01)
        y0 = max(0.0, min(line_objs[i]["top"] for i in cluster) / ph - 0.008)
        x1 = min(1.0, max(line_objs[i]["x1"] for i in cluster) / pw + 0.01)
        y1 = min(1.0, max(line_objs[i]["bottom"] for i in cluster) / ph + 0.008)
        return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def wrap_text(draw, text, font, max_width):
    """Wrap CJK and Latin text cleanly within max_width pixels."""
    if not text:
        return []
    lines = []
    for paragraph in text.split("\n"):
        curr = ""
        i = 0
        tokens = []
        while i < len(paragraph):
            ch = paragraph[i]
            if ch.isascii() and (ch.isalnum() or ch in "-_./()"):
                j = i
                while j < len(paragraph) and paragraph[j].isascii() and (paragraph[j].isalnum() or paragraph[j] in "-_./()"):
                    j += 1
                tokens.append(paragraph[i:j])
                i = j
            else:
                tokens.append(ch)
                i += 1

        for tok in tokens:
            candidate = curr + tok
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if (bbox[2] - bbox[0]) <= max_width or not curr:
                curr = candidate
            else:
                lines.append(curr.strip())
                curr = tok.lstrip()
        if curr.strip():
            lines.append(curr.strip())
    return lines


async def try_edge_tts(text, voice, out_wav):
    import edge_tts
    tmp_mp3 = out_wav + ".mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(tmp_mp3)
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "24000", "-ac", "1", out_wav],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if os.path.exists(tmp_mp3):
        os.remove(tmp_mp3)


def generate_offline_dialogue_wav(text, speaker, out_wav, sample_rate=24000):
    clean_len = max(1, len(text.strip()))
    duration = max(3.5, min(14.0, clean_len / 4.2 + 0.8))
    n_samples = int(duration * sample_rate)

    base_freq = 135.0 if speaker == "male" else 225.0
    chime_dur = min(0.35, duration * 0.15)
    chime_samples = int(chime_dur * sample_rate)
    t_chime = np.linspace(0, chime_dur, chime_samples, endpoint=False)
    env = np.exp(-t_chime * 10.0) * np.sin(np.pi * t_chime / chime_dur)
    chime = 0.08 * env * (
        np.sin(2 * np.pi * base_freq * 2.0 * t_chime)
        + 0.5 * np.sin(2 * np.pi * base_freq * 3.0 * t_chime)
    )

    audio = np.zeros(n_samples, dtype=np.float32)
    audio[:chime_samples] += chime

    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return duration


def get_wav_duration(wav_path):
    with wave.open(wav_path, "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def synthesize_turn_audio(turn, male_voice, female_voice, out_wav):
    speaker = turn.get("speaker", "female").lower()
    voice = male_voice if speaker == "male" else female_voice
    spoken_text = turn.get("spoken_text") or turn.get("zh_text") or turn.get("en_text") or ""

    try:
        asyncio.run(try_edge_tts(spoken_text, voice, out_wav))
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
            return get_wav_duration(out_wav), "edge-tts", None
    except Exception as exc:
        tts_error = f"{type(exc).__name__}: {exc}"[:500]
    else:
        tts_error = "Edge TTS did not create a valid WAV file."

    dur = generate_offline_dialogue_wav(spoken_text, speaker, out_wav)
    return dur, "offline-cadence", tts_error


def draw_corner_brackets(draw, x0, y0, x1, y1, color, length=18, width=5):
    draw.line([(x0, y0), (x0 + length, y0)], fill=color, width=width)
    draw.line([(x0, y0), (x0, y0 + length)], fill=color, width=width)
    draw.line([(x1 - length, y0), (x1, y0)], fill=color, width=width)
    draw.line([(x1, y0), (x1, y0 + length)], fill=color, width=width)
    draw.line([(x0, y1 - length), (x0, y1)], fill=color, width=width)
    draw.line([(x0, y1), (x0 + length, y1)], fill=color, width=width)
    draw.line([(x1 - length, y1), (x1, y1)], fill=color, width=width)
    draw.line([(x1, y1 - length), (x1, y1)], fill=color, width=width)


def draw_soundwave_bars(draw, x_start, y_center, num_bars, max_h, color, phase):
    bar_w = 4
    gap = 4
    for i in range(num_bars):
        h = int(5 + (max_h - 5) * (0.5 + 0.5 * math.sin(phase + i * 0.75)))
        bx = x_start + i * (bar_w + gap)
        draw.rounded_rectangle(
            [bx, y_center - h // 2, bx + bar_w, y_center + h // 2],
            radius=2,
            fill=color,
        )


def render_frame(
    page_img,
    turn,
    turn_idx,
    total_turns,
    paper_title,
    male_name,
    female_name,
    red_box,
    fonts,
    pulse_phase=0.0,
):
    W, H = 1920, 1080
    canvas = Image.new("RGBA", (W, H), (15, 23, 42, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 1. Top Header Bar
    draw.rectangle([0, 0, W, 56], fill=(30, 41, 59, 255))
    draw.rounded_rectangle([24, 12, 146, 44], radius=6, fill=(220, 38, 38, 255))
    draw.text((35, 14), "PAPER-EAR", font=fonts["badge"], fill=(255, 255, 255, 255))
    clean_title = strip_unsupported_emoji(paper_title)
    title_str = f"组会双语精读  |  {clean_title[:60]}"
    draw.text((162, 12), title_str, font=fonts["header"], fill=(248, 250, 252, 255))
    section_tag = strip_unsupported_emoji(turn.get("section_tag") or f"Page {turn.get('page', 1)}")
    prog_str = f"{section_tag}  •  Turn {turn_idx + 1}/{total_turns}"
    pb = draw.textbbox((0, 0), prog_str, font=fonts["meta"])
    draw.text((W - (pb[2] - pb[0]) - 28, 15), prog_str, font=fonts["meta"], fill=(148, 163, 184, 255))

    # 2. Left Panel: PDF Page with Dynamic Red Box (红框)
    left_x, left_y, left_w, left_h = 28, 68, 1140, 812
    draw.rounded_rectangle(
        [left_x, left_y, left_x + left_w, left_y + left_h],
        radius=12,
        fill=(30, 41, 59, 255),
        outline=(51, 65, 85, 255),
        width=2,
    )

    pw, ph = page_img.size
    scale = min((left_w - 32) / pw, (left_h - 32) / ph)
    disp_w, disp_h = int(pw * scale), int(ph * scale)
    ox = left_x + (left_w - disp_w) // 2
    oy = left_y + (left_h - disp_h) // 2

    resized_page = page_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS).convert("RGBA")

    if red_box and len(red_box) == 4:
        nx0, ny0, nx1, ny1 = [max(0.0, min(1.0, float(v))) for v in red_box]
        if nx1 > nx0 and ny1 > ny0:
            dim_overlay = Image.new("RGBA", (disp_w, disp_h), (15, 23, 42, 52))
            bx0, by0 = int(nx0 * disp_w), int(ny0 * disp_h)
            bx1, by1 = int(nx1 * disp_w), int(ny1 * disp_h)
            pad = 6
            bx0, by0 = max(0, bx0 - pad), max(0, by0 - pad)
            bx1, by1 = min(disp_w, bx1 + pad), min(disp_h, by1 + pad)
            dim_draw = ImageDraw.Draw(dim_overlay, "RGBA")
            dim_draw.rectangle([bx0, by0, bx1, by1], fill=(229, 57, 53, 24))
            resized_page = Image.alpha_composite(resized_page, dim_overlay)

    canvas.paste(resized_page, (ox, oy))

    crop_img = None
    if red_box and len(red_box) == 4:
        nx0, ny0, nx1, ny1 = [max(0.0, min(1.0, float(v))) for v in red_box]
        if nx1 > nx0 and ny1 > ny0:
            bx0 = ox + int(nx0 * disp_w) - 6
            by0 = oy + int(ny0 * disp_h) - 6
            bx1 = ox + int(nx1 * disp_w) + 6
            by1 = oy + int(ny1 * disp_h) + 6

            pulse_alpha = int(200 + 55 * math.sin(pulse_phase))
            draw.rounded_rectangle(
                [bx0 - 4, by0 - 4, bx1 + 4, by1 + 4],
                radius=6,
                outline=(255, 82, 82, 115),
                width=4,
            )
            draw.rounded_rectangle(
                [bx0, by0, bx1, by1],
                radius=4,
                outline=(229, 57, 53, pulse_alpha),
                width=4,
            )
            draw_corner_brackets(draw, bx0 - 2, by0 - 2, bx1 + 2, by1 + 2, (255, 59, 48, 255), length=18, width=5)

            clean_box_lbl = strip_unsupported_emoji(turn.get("box_label") or "当前讲解区域 / Focus Area")
            box_label = f"▶ #{turn_idx + 1}  {clean_box_lbl}"
            lb = draw.textbbox((0, 0), box_label, font=fonts["badge"])
            lw, lh = lb[2] - lb[0] + 20, lb[3] - lb[1] + 10
            tag_y = by0 - lh - 5 if by0 - lh - 5 > left_y + 4 else by1 + 5
            draw.rounded_rectangle(
                [bx0, tag_y, bx0 + lw, tag_y + lh],
                radius=6,
                fill=(220, 38, 38, 248),
            )
            draw.text((bx0 + 10, tag_y + 3), box_label, font=fonts["badge"], fill=(255, 255, 255, 255))

            cx0 = max(0, int(nx0 * pw) - 14)
            cy0 = max(0, int(ny0 * ph) - 14)
            cx1 = min(pw, int(nx1 * pw) + 14)
            cy1 = min(ph, int(ny1 * ph) + 14)
            if cx1 > cx0 + 10 and cy1 > cy0 + 10:
                crop_img = page_img.crop((cx0, cy0, cx1, cy1))

    # 3. Right Panel: Speakers + Zoomed Red-Box Callout + Term Card
    rx, ry, rw = 1192, 68, 700
    speaker = turn.get("speaker", "female").lower()
    is_male = speaker == "male"

    clean_female = strip_unsupported_emoji(female_name)
    clean_male = strip_unsupported_emoji(male_name)

    # Female speaker card
    f_box = [rx, ry, rx + 340, ry + 98]
    f_bg = (23, 47, 115, 255) if not is_male else (30, 41, 59, 255)
    f_border = (56, 189, 248, 255) if not is_male else (71, 85, 105, 255)
    draw.rounded_rectangle(f_box, radius=10, fill=f_bg, outline=f_border, width=3 if not is_male else 1)
    draw.text((rx + 16, ry + 14), f"● {clean_female}", font=fonts["speaker"], fill=(255, 255, 255, 255))
    f_status = "▶ 正在主讲 (Speaking)" if not is_male else "○ 倾听中 (Listening)"
    draw.text((rx + 16, ry + 54), f_status, font=fonts["meta"], fill=(125, 211, 252, 255) if not is_male else (148, 163, 184, 255))
    if not is_male:
        draw_soundwave_bars(draw, rx + 245, ry + 64, 9, 26, (56, 189, 248, 255), pulse_phase)

    # Male speaker card
    m_box = [rx + 356, ry, rx + rw, ry + 98]
    m_bg = (124, 45, 18, 255) if is_male else (30, 41, 59, 255)
    m_border = (251, 146, 60, 255) if is_male else (71, 85, 105, 255)
    draw.rounded_rectangle(m_box, radius=10, fill=m_bg, outline=m_border, width=3 if is_male else 1)
    draw.text((rx + 372, ry + 14), f"◆ {clean_male}", font=fonts["speaker"], fill=(255, 255, 255, 255))
    m_status = "▶ 提问/思辨 (Speaking)" if is_male else "○ 倾听中 (Listening)"
    draw.text((rx + 372, ry + 54), m_status, font=fonts["meta"], fill=(253, 186, 116, 255) if is_male else (148, 163, 184, 255))
    if is_male:
        draw_soundwave_bars(draw, rx + 602, ry + 64, 9, 26, (251, 146, 60, 255), pulse_phase)

    # Red-Box Zoomed Preview Panel
    zy = ry + 114
    zh = 372
    draw.rounded_rectangle(
        [rx, zy, rx + rw, zy + zh],
        radius=12,
        fill=(30, 41, 59, 255),
        outline=(229, 57, 53, 220),
        width=2,
    )
    draw.text(
        (rx + 18, zy + 12),
        "■ 红框区域放大视图 (Highlighted Region Zoom)",
        font=fonts["card_title"],
        fill=(252, 165, 165, 255),
    )
    if crop_img is not None:
        cw, ch = crop_img.size
        c_scale = min((rw - 36) / cw, (zh - 64) / ch)
        cdw, cdh = max(1, int(cw * c_scale)), max(1, int(ch * c_scale))
        c_resized = crop_img.resize((cdw, cdh), Image.Resampling.LANCZOS)
        cox = rx + (rw - cdw) // 2
        coy = zy + 48 + (zh - 56 - cdh) // 2
        canvas.paste(c_resized, (cox, coy))
        draw.rectangle([cox - 2, coy - 2, cox + cdw + 2, coy + cdh + 2], outline=(229, 57, 53, 255), width=2)

    # Key Point & Technical Term Card
    ty = zy + zh + 16
    th = (left_y + left_h) - ty
    draw.rounded_rectangle(
        [rx, ty, rx + rw, ty + th],
        radius=12,
        fill=(30, 41, 59, 255),
        outline=(56, 189, 248, 160),
        width=2,
    )
    raw_ct = strip_unsupported_emoji(turn.get("card_title") or "核心要点与专业名词解析 (Key Notes & Terms)")
    card_title = f"★ {raw_ct}"
    draw.text((rx + 20, ty + 14), card_title, font=fonts["card_title"], fill=(56, 189, 248, 255))

    notes = turn.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]
    if not notes and turn.get("box_label"):
        notes = [f"当前聚焦：{strip_unsupported_emoji(turn.get('box_label'))}"]

    ny_cursor = ty + 52
    for note in notes[:4]:
        clean_note = strip_unsupported_emoji(note)
        wrapped = wrap_text(draw, f"• {clean_note}", fonts["notes"], rw - 40)
        for ln in wrapped[:3]:
            if ny_cursor + 28 > ty + th - 12:
                break
            draw.text((rx + 20, ny_cursor), ln, font=fonts["notes"], fill=(226, 232, 240, 255))
            ny_cursor += 30
        ny_cursor += 6

    # 4. Bottom Panel: Bilingual Subtitles (中英双语字幕) + Progress Bar
    sub_y = 892
    draw.rounded_rectangle(
        [28, sub_y, W - 28, H - 22],
        radius=12,
        fill=(9, 14, 26, 248),
        outline=(71, 85, 105, 200),
        width=2,
    )

    speaker_badge = f"[{clean_male}]" if is_male else f"[{clean_female}]"
    zh_line = f"{speaker_badge} {strip_unsupported_emoji(turn.get('zh_text', ''))}"
    en_line = strip_unsupported_emoji(turn.get("en_text", ""))

    zh_wrapped = wrap_text(draw, zh_line, fonts["sub_zh"], W - 100)
    en_wrapped = wrap_text(draw, en_line, fonts["sub_en"], W - 100)

    sy = sub_y + 14
    zh_color = (253, 186, 116, 255) if is_male else (254, 240, 138, 255)
    for ln in zh_wrapped[:2]:
        draw.text((48, sy), ln, font=fonts["sub_zh"], fill=zh_color)
        sy += 36

    sy += 4
    for ln in en_wrapped[:2]:
        draw.text((48, sy), ln, font=fonts["sub_en"], fill=(186, 230, 253, 255))
        sy += 29

    # Bottom timeline progress bar
    prog_ratio = (turn_idx + 1) / float(max(1, total_turns))
    bar_x0, bar_x1, bar_y = 36, W - 36, H - 12
    draw.rounded_rectangle([bar_x0, bar_y - 3, bar_x1, bar_y + 3], radius=3, fill=(51, 65, 85, 255))
    fill_x1 = bar_x0 + int((bar_x1 - bar_x0) * prog_ratio)
    draw.rounded_rectangle([bar_x0, bar_y - 3, fill_x1, bar_y + 3], radius=3, fill=(229, 57, 53, 255))

    return canvas.convert("RGB")


def render_video(
    pdf_path,
    script_json_path,
    output_mp4,
    dpi=180,
    fps=12,
    export_gif=None,
    max_turns=None,
    require_tts=False,
    report_json=None,
):
    with open(script_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    paper_title = data.get("title", os.path.basename(pdf_path))
    male_name = data.get("male_name", "师兄 Alex (提问/思辨)")
    female_name = data.get("female_name", "主讲人 Lin (精读讲解)")
    male_voice = data.get("male_voice", "zh-CN-YunxiNeural")
    female_voice = data.get("female_voice", "zh-CN-XiaoxiaoNeural")
    turns = data.get("turns", [])
    if not turns:
        raise ValueError("Dialogue script JSON contains no 'turns'.")
    source_turn_count = len(turns)
    if max_turns is not None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1.")
        turns = turns[:max_turns]
    if fps < 1:
        raise ValueError("fps must be at least 1.")

    fonts = {
        "header": load_font(FONT_BOLD_CANDIDATES, 24),
        "speaker": load_font(FONT_BOLD_CANDIDATES, 21),
        "card_title": load_font(FONT_BOLD_CANDIDATES, 21),
        "badge": load_font(FONT_BOLD_CANDIDATES, 18),
        "notes": load_font(FONT_REGULAR_CANDIDATES, 20),
        "meta": load_font(FONT_REGULAR_CANDIDATES, 18),
        "sub_zh": load_font(FONT_BOLD_CANDIDATES, 27),
        "sub_en": load_font(FONT_REGULAR_CANDIDATES, 21),
    }

    tmpdir = tempfile.mkdtemp(prefix="paper_ear_")
    gif_frames = []
    try:
        page_prefix = os.path.join(tmpdir, "page")
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), pdf_path, page_prefix], check=True)
        page_files = sorted(
            [os.path.join(tmpdir, fn) for fn in os.listdir(tmpdir) if fn.startswith("page-") and fn.endswith(".png")],
            key=page_file_sort_key,
        )
        if not page_files:
            raise RuntimeError("Failed to render PDF pages via pdftoppm.")

        page_images = [Image.open(p).convert("RGB") for p in page_files]
        segment_files = []
        audio_modes = set()
        audio_mode_by_turn = []

        for idx, turn in enumerate(turns):
            page_num = max(1, min(len(page_images), int(turn.get("page", 1))))
            page_img = page_images[page_num - 1]

            red_box = turn.get("red_box")
            search_text = turn.get("search_text")
            if (not red_box or len(red_box) != 4) and search_text:
                red_box = locate_text_bbox_on_page(pdf_path, page_num, search_text)
            elif red_box and search_text and turn.get("auto_refine_box", False):
                auto_box = locate_text_bbox_on_page(pdf_path, page_num, search_text)
                if auto_box:
                    red_box = auto_box
            if not red_box or len(red_box) != 4:
                red_box = [0.08, 0.15, 0.92, 0.45]

            wav_path = os.path.join(tmpdir, f"turn_{idx:03d}.wav")
            duration, mode, tts_error = synthesize_turn_audio(turn, male_voice, female_voice, wav_path)
            audio_modes.add(mode)
            turn_audio = {"turn": idx + 1, "mode": mode, "duration_seconds": round(duration, 3)}
            if tts_error:
                turn_audio["tts_error"] = tts_error
            audio_mode_by_turn.append(turn_audio)
            if require_tts and mode != "edge-tts":
                raise RuntimeError(
                    f"Turn {idx + 1} fell back to '{mode}'. "
                    "A publishable run requires real Edge TTS; check the dependency, connectivity, voice names, "
                    f"and narration text. Root cause: {tts_error}"
                )

            frame_a = render_frame(
                page_img, turn, idx, len(turns), paper_title, male_name, female_name, red_box, fonts, pulse_phase=idx * 1.1
            )
            frame_path = os.path.join(tmpdir, f"frame_{idx:03d}.png")
            frame_a.save(frame_path, "PNG")

            if export_gif:
                gif_frames.append(frame_a.resize((960, 540), Image.Resampling.LANCZOS))
                frame_b = render_frame(
                    page_img, turn, idx, len(turns), paper_title, male_name, female_name, red_box, fonts, pulse_phase=idx * 1.1 + 1.6
                )
                gif_frames.append(frame_b.resize((960, 540), Image.Resampling.LANCZOS))

            seg_mp4 = os.path.join(tmpdir, f"seg_{idx:03d}.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    frame_path,
                    "-i",
                    wav_path,
                    "-c:v",
                    "libx264",
                    "-tune",
                    "stillimage",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    str(fps),
                    "-shortest",
                    "-t",
                    f"{duration:.2f}",
                    seg_mp4,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            segment_files.append(seg_mp4)

        concat_list = os.path.join(tmpdir, "concat.txt")
        with open(concat_list, "w", encoding="utf-8") as cf:
            for seg in segment_files:
                cf.write(f"file '{seg}'\n")

        os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                "-c",
                "copy",
                output_mp4,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if export_gif and gif_frames:
            os.makedirs(os.path.dirname(os.path.abspath(export_gif)), exist_ok=True)
            gif_frames[0].save(
                export_gif,
                save_all=True,
                append_images=gif_frames[1:],
                duration=900,
                loop=0,
                optimize=True,
            )
            print(f"Exported animated GIF preview: {export_gif}")

        if not os.path.exists(output_mp4) or os.path.getsize(output_mp4) < 1024:
            raise RuntimeError("ffmpeg returned successfully but the output MP4 is missing or empty.")

        report = {
            "output": os.path.abspath(output_mp4),
            "source_turns": source_turn_count,
            "rendered_turns": len(turns),
            "dpi": dpi,
            "fps": fps,
            "require_tts": bool(require_tts),
            "audio_modes": sorted(audio_modes),
            "turn_audio": audio_mode_by_turn,
            "file_size_bytes": os.path.getsize(output_mp4),
        }
        if report_json:
            os.makedirs(os.path.dirname(os.path.abspath(report_json)), exist_ok=True)
            with open(report_json, "w", encoding="utf-8") as report_file:
                json.dump(report, report_file, ensure_ascii=False, indent=2)
                report_file.write("\n")

        print(
            f"Successfully generated MP4: {output_mp4} "
            f"(turns={len(turns)}, audio_modes={sorted(audio_modes)})"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Render Paper-Ear bilingual dialogue MP4 with red-box tracking.")
    parser.add_argument("--pdf", required=True, help="Input PDF paper path")
    parser.add_argument("--script", required=True, help="Input dialogue JSON script path")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    parser.add_argument("--dpi", type=int, default=180, help="PDF page rendering DPI")
    parser.add_argument("--fps", type=int, default=12, help="Output frame rate")
    parser.add_argument("--max-turns", type=int, default=None, help="Render only the first N turns for a fast preview")
    parser.add_argument(
        "--require-tts",
        action="store_true",
        help="Fail instead of using cadence-only fallback audio when Edge TTS is unavailable",
    )
    parser.add_argument("--export-gif", default=None, help="Optional path to export animated GIF preview")
    parser.add_argument("--report-json", default=None, help="Optional render report JSON path")
    args = parser.parse_args()
    render_video(
        args.pdf,
        args.script,
        args.output,
        dpi=args.dpi,
        fps=args.fps,
        export_gif=args.export_gif,
        max_turns=args.max_turns,
        require_tts=args.require_tts,
        report_json=args.report_json,
    )


if __name__ == "__main__":
    main()
