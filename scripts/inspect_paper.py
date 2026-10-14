#!/usr/bin/env python3
"""
Inspect a PDF paper and extract page dimensions, text blocks with normalized
bounding boxes [x0, y0, x1, y1], figures, tables, and candidate headings.
Also optionally renders page PNGs via pdftoppm for visual inspection.
"""

import argparse
import json
import os
import subprocess
import sys
import pdfplumber


def group_words_into_blocks(words, page_w, page_h, y_tolerance=12.0):
    """Group pdfplumber words into paragraph-level blocks with normalized bboxes."""
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines = []
    current_line = [sorted_words[0]]
    for w in sorted_words[1:]:
        if abs(w["top"] - current_line[-1]["top"]) <= 5.0:
            current_line.append(w)
        else:
            lines.append(current_line)
            current_line = [w]
    lines.append(current_line)

    line_objs = []
    for ln in lines:
        ln_sorted = sorted(ln, key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ln_sorted)
        x0 = min(w["x0"] for w in ln_sorted)
        top = min(w["top"] for w in ln_sorted)
        x1 = max(w["x1"] for w in ln_sorted)
        bottom = max(w["bottom"] for w in ln_sorted)
        line_objs.append({"text": text, "x0": x0, "top": top, "x1": x1, "bottom": bottom})

    blocks = []
    if not line_objs:
        return blocks

    curr = {
        "lines": [line_objs[0]["text"]],
        "x0": line_objs[0]["x0"],
        "top": line_objs[0]["top"],
        "x1": line_objs[0]["x1"],
        "bottom": line_objs[0]["bottom"],
    }
    for ln in line_objs[1:]:
        vertical_gap = ln["top"] - curr["bottom"]
        horiz_overlap = min(curr["x1"], ln["x1"]) - max(curr["x0"], ln["x0"])
        if vertical_gap <= y_tolerance and horiz_overlap > -20:
            curr["lines"].append(ln["text"])
            curr["x0"] = min(curr["x0"], ln["x0"])
            curr["top"] = min(curr["top"], ln["top"])
            curr["x1"] = max(curr["x1"], ln["x1"])
            curr["bottom"] = max(curr["bottom"], ln["bottom"])
        else:
            blocks.append(curr)
            curr = {
                "lines": [ln["text"]],
                "x0": ln["x0"],
                "top": ln["top"],
                "x1": ln["x1"],
                "bottom": ln["bottom"],
            }
    blocks.append(curr)

    result = []
    for idx, b in enumerate(blocks):
        full_text = " ".join(b["lines"]).strip()
        if not full_text:
            continue
        result.append({
            "block_id": idx + 1,
            "text": full_text[:300] + ("..." if len(full_text) > 300 else ""),
            # Keep the compact field for existing video workflows, while exposing
            # the complete extraction for visual inventories and deep web reading.
            "full_text": full_text,
            "bbox_norm": [
                round(max(0.0, b["x0"] / page_w), 4),
                round(max(0.0, b["top"] / page_h), 4),
                round(min(1.0, b["x1"] / page_w), 4),
                round(min(1.0, b["bottom"] / page_h), 4),
            ],
        })
    return result


def inspect_pdf(pdf_path, out_json, render_dir=None, dpi=150):
    summary = {"pdf_path": os.path.abspath(pdf_path), "num_pages": 0, "pages": []}
    with pdfplumber.open(pdf_path) as pdf:
        summary["num_pages"] = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            pw, ph = float(page.width), float(page.height)
            words = page.extract_words() or []
            blocks = group_words_into_blocks(words, pw, ph)
            images = []
            for img_idx, img in enumerate(page.images or []):
                x0 = max(0.0, float(img.get("x0", 0)) / pw)
                top = max(0.0, float(img.get("top", 0)) / ph)
                x1 = min(1.0, float(img.get("x1", pw)) / pw)
                bottom = min(1.0, float(img.get("bottom", ph)) / ph)
                if (x1 - x0) * (bottom - top) > 0.005:
                    images.append({
                        "image_id": img_idx + 1,
                        "bbox_norm": [round(x0, 4), round(top, 4), round(x1, 4), round(bottom, 4)],
                    })
            summary["pages"].append({
                "page": i + 1,
                "width": pw,
                "height": ph,
                "blocks": blocks,
                "images": images,
            })

    if render_dir:
        os.makedirs(render_dir, exist_ok=True)
        prefix = os.path.join(render_dir, "page")
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), pdf_path, prefix], check=True)
        summary["rendered_pages_dir"] = os.path.abspath(render_dir)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved PDF structure with {summary['num_pages']} pages to {out_json}")


def main():
    parser = argparse.ArgumentParser(description="Inspect PDF structure and normalized bounding boxes.")
    parser.add_argument("--pdf", required=True, help="Path to input PDF")
    parser.add_argument("--out", required=True, help="Path to output JSON file")
    parser.add_argument("--render-dir", default=None, help="Optional directory to render PNG pages")
    parser.add_argument("--dpi", type=int, default=150, help="DPI for page rendering")
    args = parser.parse_args()
    inspect_pdf(args.pdf, args.out, args.render_dir, args.dpi)


if __name__ == "__main__":
    main()
