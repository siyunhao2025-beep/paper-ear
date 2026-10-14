#!/usr/bin/env python3
"""Validate Paper Ear prerequisites, PDF metadata, and dialogue-script integrity."""

import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path


CLAIM_TYPES = {"paper_evidence", "author_claim", "inference", "critique"}
ANCHOR_KINDS = {"section", "figure", "table", "equation", "appendix", "page"}
REQUIRED_TOOLS = ("ffmpeg", "ffprobe", "pdftoppm")
RENDER_MODULES = {"PIL": "Pillow", "numpy": "numpy", "edge_tts": "edge-tts"}


def add_issue(items, code, message, turn=None):
    issue = {"code": code, "message": message}
    if turn is not None:
        issue["turn"] = turn
    items.append(issue)


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def load_pdf_page_count(pdf_path, errors):
    try:
        import pdfplumber
    except ImportError:
        add_issue(errors, "missing_python_dependency", "Python package 'pdfplumber' is not installed.")
        return 0

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            count = len(pdf.pages)
    except Exception as exc:
        add_issue(errors, "unreadable_pdf", f"Could not open PDF: {exc}")
        return 0

    if count < 1:
        add_issue(errors, "empty_pdf", "The PDF contains no pages.")
    return count


def validate_tools(errors):
    missing = [tool for tool in REQUIRED_TOOLS if shutil.which(tool) is None]
    for tool in missing:
        add_issue(errors, "missing_tool", f"Required executable '{tool}' was not found on PATH.")
    return missing


def validate_python_dependencies(errors):
    missing = []
    for module, package in RENDER_MODULES.items():
        if importlib.util.find_spec(module) is None:
            missing.append(package)
            add_issue(
                errors,
                "missing_python_dependency",
                f"Python package '{package}' is not installed (import name: {module}).",
            )
    return missing


def validate_red_box(value, errors, turn_number):
    if not isinstance(value, list) or len(value) != 4:
        add_issue(errors, "invalid_red_box", "red_box must contain four normalized numbers.", turn_number)
        return
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        add_issue(errors, "invalid_red_box", "red_box entries must be numbers.", turn_number)
        return
    x0, y0, x1, y1 = (float(v) for v in value)
    if any(v < 0.0 or v > 1.0 for v in (x0, y0, x1, y1)):
        add_issue(errors, "red_box_out_of_range", "red_box coordinates must be within 0.0..1.0.", turn_number)
    if x0 >= x1 or y0 >= y1:
        add_issue(errors, "red_box_order", "red_box must satisfy x0 < x1 and y0 < y1.", turn_number)


def validate_script(script_path, page_count, strict, errors, warnings):
    try:
        data = json.loads(script_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        add_issue(errors, "script_encoding", f"Dialogue script is not valid UTF-8: {exc}")
        return {}, 0
    except json.JSONDecodeError as exc:
        add_issue(errors, "script_json", f"Dialogue script is not valid JSON: {exc}")
        return {}, 0

    if not isinstance(data, dict):
        add_issue(errors, "script_root", "Dialogue script root must be a JSON object.")
        return {}, 0

    if not nonempty_string(data.get("title")):
        add_issue(errors, "missing_title", "Root field 'title' must be a non-empty string.")

    for field in ("male_name", "female_name", "male_voice", "female_voice"):
        if not nonempty_string(data.get(field)):
            target = errors if strict else warnings
            add_issue(target, f"missing_{field}", f"Root field '{field}' is required in strict mode.")

    turns = data.get("turns")
    if not isinstance(turns, list) or not turns:
        add_issue(errors, "missing_turns", "Root field 'turns' must be a non-empty array.")
        return data, 0

    for index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            add_issue(errors, "invalid_turn", "Each turn must be a JSON object.", index)
            continue

        page = turn.get("page")
        if isinstance(page, bool) or not isinstance(page, int):
            add_issue(errors, "invalid_page", "page must be an integer.", index)
        elif page < 1 or (page_count and page > page_count):
            add_issue(errors, "page_out_of_range", f"page must be between 1 and {page_count}.", index)

        speaker = turn.get("speaker")
        if not isinstance(speaker, str) or speaker.lower() not in {"female", "male"}:
            add_issue(errors, "invalid_speaker", "speaker must be 'female' or 'male'.", index)

        for field in ("zh_text", "en_text", "section_tag", "box_label", "card_title"):
            if not nonempty_string(turn.get(field)):
                target = errors if strict else warnings
                add_issue(target, f"missing_{field}", f"Turn field '{field}' is required in strict mode.", index)

        zh_text = turn.get("zh_text", "")
        en_text = turn.get("en_text", "")
        if isinstance(zh_text, str) and len(zh_text.strip()) > 110:
            add_issue(warnings, "long_zh_subtitle", "Chinese subtitle may overflow; split or shorten the turn.", index)
        if isinstance(en_text, str) and len(re.findall(r"\b\w+\b", en_text)) > 38:
            add_issue(warnings, "long_en_subtitle", "English subtitle may overflow; split or shorten the turn.", index)

        search_text = turn.get("search_text")
        red_box = turn.get("red_box")
        if red_box is None and not nonempty_string(search_text) and not (
            isinstance(search_text, list) and any(nonempty_string(v) for v in search_text)
        ):
            add_issue(errors, "missing_target", "Provide red_box or non-empty search_text.", index)
        if red_box is not None:
            validate_red_box(red_box, errors, index)

        notes = turn.get("notes")
        if not isinstance(notes, list) or not notes or any(not nonempty_string(v) for v in notes):
            target = errors if strict else warnings
            add_issue(target, "invalid_notes", "notes must contain one or more non-empty strings in strict mode.", index)
        elif len(notes) > 3:
            add_issue(warnings, "dense_notes", "More than three notes may overflow the card.", index)

        claim_type = turn.get("claim_type")
        if claim_type not in CLAIM_TYPES:
            target = errors if strict else warnings
            add_issue(
                target,
                "invalid_claim_type",
                "claim_type must be paper_evidence, author_claim, inference, or critique.",
                index,
            )

        anchor = turn.get("source_anchor")
        if not isinstance(anchor, dict):
            target = errors if strict else warnings
            add_issue(target, "missing_source_anchor", "source_anchor object is required in strict mode.", index)
        else:
            anchor_page = anchor.get("page")
            if anchor_page != page:
                add_issue(errors, "anchor_page_mismatch", "source_anchor.page must match turn.page.", index)
            if anchor.get("kind") not in ANCHOR_KINDS:
                add_issue(errors, "invalid_anchor_kind", f"source_anchor.kind must be one of {sorted(ANCHOR_KINDS)}.", index)
            if not nonempty_string(anchor.get("label")):
                add_issue(errors, "missing_anchor_label", "source_anchor.label must be a non-empty string.", index)
            if anchor.get("kind") in {"section", "equation"} and not nonempty_string(search_text):
                add_issue(warnings, "missing_search_text", "Text/equation anchors benefit from a distinctive search_text.", index)

    return data, len(turns)


def main():
    parser = argparse.ArgumentParser(description="Validate Paper Ear tools, PDF, and dialogue JSON.")
    parser.add_argument("--pdf", required=True, help="Input PDF paper path")
    parser.add_argument("--script", help="Optional dialogue-script JSON path")
    parser.add_argument("--strict", action="store_true", help="Require evidence and display metadata for publication")
    parser.add_argument("--json-out", help="Optional JSON report path")
    args = parser.parse_args()

    errors = []
    warnings = []
    pdf_path = Path(args.pdf).expanduser().resolve()
    script_path = Path(args.script).expanduser().resolve() if args.script else None

    if not pdf_path.is_file():
        add_issue(errors, "missing_pdf", f"PDF does not exist: {pdf_path}")
        page_count = 0
    else:
        page_count = load_pdf_page_count(pdf_path, errors)

    missing_tools = validate_tools(errors)
    missing_python_dependencies = validate_python_dependencies(errors)
    turn_count = 0
    if script_path is not None:
        if not script_path.is_file():
            add_issue(errors, "missing_script", f"Dialogue script does not exist: {script_path}")
        else:
            _, turn_count = validate_script(script_path, page_count, args.strict, errors, warnings)

    report = {
        "ok": not errors,
        "strict": bool(args.strict),
        "pdf": str(pdf_path),
        "script": str(script_path) if script_path else None,
        "stats": {
            "pages": page_count,
            "turns": turn_count,
            "missing_tools": missing_tools,
            "missing_python_dependencies": missing_python_dependencies,
        },
        "errors": errors,
        "warnings": warnings,
    }

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "PASS" if report["ok"] else "FAIL"
    print(f"{status}: pages={page_count}, turns={turn_count}, errors={len(errors)}, warnings={len(warnings)}")
    for issue in errors:
        prefix = f"turn {issue['turn']}: " if "turn" in issue else ""
        print(f"ERROR [{issue['code']}] {prefix}{issue['message']}")
    for issue in warnings:
        prefix = f"turn {issue['turn']}: " if "turn" in issue else ""
        print(f"WARN  [{issue['code']}] {prefix}{issue['message']}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
