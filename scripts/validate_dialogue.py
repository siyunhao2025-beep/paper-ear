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
DIALOGUE_ACTS = {"claim", "challenge", "evidence_answer", "followup", "concession", "synthesis"}
EMOTIONS = {"neutral", "curious", "skeptical", "serious", "surprised", "excited", "reflective"}
INTERACTION_TAGS = {
    "question",
    "disagreement",
    "surprise",
    "concession",
    "self_correction",
    "reverse_question",
    "unresolved",
}
VOICE_BACKENDS = {"edge-tts", "azure-speech"}
AZURE_VOICE_STYLES = {
    "zh-CN-XiaoxiaoNeural": {
        "affectionate", "angry", "assistant", "calm", "chat", "chat-casual", "cheerful",
        "customerservice", "disgruntled", "excited", "fearful", "friendly", "gentle", "lyrical",
        "newscast", "poetry-reading", "sad", "serious", "sorry", "whispering",
    },
    "zh-CN-YunjianNeural": {
        "angry", "cheerful", "depressed", "disgruntled", "documentary-narration",
        "narration-relaxed", "sad", "serious", "sports-commentary", "sports-commentary-excited",
    },
    "zh-CN-YunxiNeural": {
        "angry", "assistant", "chat", "cheerful", "depressed", "disgruntled", "embarrassed",
        "fearful", "narration-relaxed", "newscast", "sad", "serious",
    },
    "zh-CN-YunyangNeural": {"customerservice", "narration-professional", "newscast-casual"},
}
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


def validate_delivery(delivery, backend, voice, errors, turn_number):
    if not isinstance(delivery, dict):
        add_issue(errors, "invalid_delivery", "delivery must be an object in evidence-dialogue-v2.", turn_number)
        return

    style = delivery.get("provider_style")
    if backend == "azure-speech" and not nonempty_string(style):
        add_issue(errors, "missing_provider_style", "Azure turns require delivery.provider_style.", turn_number)
    elif style is not None and not isinstance(style, str):
        add_issue(errors, "invalid_provider_style", "delivery.provider_style must be a string.", turn_number)
    elif backend == "azure-speech" and voice in AZURE_VOICE_STYLES and style not in AZURE_VOICE_STYLES[voice]:
        add_issue(
            errors,
            "unsupported_provider_style",
            f"Azure voice {voice} does not list style '{style}' in the validated style snapshot.",
            turn_number,
        )

    degree = delivery.get("style_degree")
    if isinstance(degree, bool) or not isinstance(degree, (int, float)) or not 0.01 <= float(degree) <= 2.0:
        add_issue(errors, "invalid_style_degree", "delivery.style_degree must be between 0.01 and 2.0.", turn_number)

    patterns = {
        "rate": r"^[+-]\d+%$",
        "pitch": r"^[+-]\d+(?:\.\d+)?Hz$",
        "volume": r"^[+-]\d+%$",
    }
    for field, pattern in patterns.items():
        value = delivery.get(field)
        if not isinstance(value, str) or not re.fullmatch(pattern, value):
            add_issue(errors, f"invalid_{field}", f"delivery.{field} has an invalid SSML/Edge value.", turn_number)

    for field in ("pause_before_ms", "pause_after_ms"):
        value = delivery.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5000:
            add_issue(errors, f"invalid_{field}", f"delivery.{field} must be an integer from 0 to 5000.", turn_number)

    terms = delivery.get("emphasis_terms")
    if not isinstance(terms, list) or any(not nonempty_string(term) for term in terms):
        add_issue(errors, "invalid_emphasis_terms", "delivery.emphasis_terms must be an array of non-empty strings.", turn_number)


def validate_interaction_quality(turns, errors):
    acts = [turn.get("dialogue_act") if isinstance(turn, dict) else None for turn in turns]
    tag_sets = []
    for turn in turns:
        tags = turn.get("interaction_tags", []) if isinstance(turn, dict) else []
        tag_sets.append(set(tags) if isinstance(tags, list) else set())

    question_turns = [
        index
        for index, (act, tags) in enumerate(zip(acts, tag_sets), start=1)
        if act in {"challenge", "followup"} or "question" in tags
    ]
    stats = {
        "substantive_questions": len(question_turns),
        "followups": sum(act == "followup" for act in acts),
        "disagreements": sum("disagreement" in tags for tags in tag_sets),
        "surprise_moments": sum("surprise" in tags for tags in tag_sets),
        "concessions": sum(act == "concession" or "concession" in tags for act, tags in zip(acts, tag_sets)),
        "self_corrections": sum("self_correction" in tags for tags in tag_sets),
        "reverse_questions": sum("reverse_question" in tags for tags in tag_sets),
        "unresolved_questions": sum("unresolved" in tags for tags in tag_sets),
    }
    stats["question_challenge_followup_ratio"] = round(len(question_turns) / len(turns), 4) if turns else 0.0

    if not 15 <= len(turns) <= 20:
        add_issue(errors, "interaction_turn_count", f"evidence-dialogue-v2 requires 15–20 turns; found {len(turns)}.")

    minimums = {
        "substantive_questions": 6,
        "followups": 3,
        "disagreements": 2,
        "surprise_moments": 2,
        "concessions": 1,
        "self_corrections": 1,
        "reverse_questions": 1,
        "unresolved_questions": 1,
    }
    for key, minimum in minimums.items():
        if stats[key] < minimum:
            add_issue(errors, f"interaction_{key}", f"evidence-dialogue-v2 requires at least {minimum} {key.replace('_', ' ')}; found {stats[key]}.")

    ratio = stats["question_challenge_followup_ratio"]
    if ratio < 0.35 or ratio > 0.50:
        add_issue(errors, "interaction_question_ratio", f"Question/challenge/follow-up turns must be 35–50%; found {ratio:.1%}.")

    exposition_streak = 0
    for index, act in enumerate(acts, start=1):
        if act in {"claim", "evidence_answer", "synthesis"}:
            exposition_streak += 1
            if exposition_streak >= 3:
                add_issue(errors, "interaction_exposition_streak", "Do not place three exposition turns in a row.", index)
                break
        else:
            exposition_streak = 0

    for question_turn in question_turns:
        answered = False
        for candidate in range(question_turn + 1, min(len(turns), question_turn + 2) + 1):
            response = turns[candidate - 1]
            if isinstance(response, dict) and response.get("responds_to_turn") == question_turn:
                answered = True
                break
        if not answered:
            add_issue(
                errors,
                "interaction_unanswered_question",
                "Each challenge/follow-up must receive a response within the next one or two turns.",
                question_turn,
            )

    reverse_ok = any(
        isinstance(turn, dict)
        and turn.get("speaker", "").lower() == "female"
        and "reverse_question" in tags
        for turn, tags in zip(turns, tag_sets)
    )
    if stats["reverse_questions"] and not reverse_ok:
        add_issue(errors, "interaction_reverse_question_role", "At least one reverse question must be asked by the presenter (female speaker).")
    return stats


def validate_script(script_path, page_count, strict, errors, warnings):
    try:
        data = json.loads(script_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        add_issue(errors, "script_encoding", f"Dialogue script is not valid UTF-8: {exc}")
        return {}, 0, {}
    except json.JSONDecodeError as exc:
        add_issue(errors, "script_json", f"Dialogue script is not valid JSON: {exc}")
        return {}, 0, {}

    if not isinstance(data, dict):
        add_issue(errors, "script_root", "Dialogue script root must be a JSON object.")
        return {}, 0, {}

    if not nonempty_string(data.get("title")):
        add_issue(errors, "missing_title", "Root field 'title' must be a non-empty string.")

    for field in ("male_name", "female_name"):
        if not nonempty_string(data.get(field)):
            target = errors if strict else warnings
            add_issue(target, f"missing_{field}", f"Root field '{field}' is required in strict mode.")

    backend = str(data.get("voice_backend") or "edge-tts").lower()
    if backend not in VOICE_BACKENDS:
        add_issue(errors, "invalid_voice_backend", f"voice_backend must be one of {sorted(VOICE_BACKENDS)}.")

    profiles = data.get("voice_profiles")
    if profiles is not None and not isinstance(profiles, dict):
        add_issue(errors, "invalid_voice_profiles", "voice_profiles must be an object keyed by female and male.")
        profiles = {}
    profiles = profiles or {}
    voice_by_speaker = {}
    for speaker in ("male", "female"):
        profile = profiles.get(speaker)
        legacy_voice = data.get(f"{speaker}_voice")
        voice = profile.get("voice") if isinstance(profile, dict) else legacy_voice
        voice_by_speaker[speaker] = voice
        if not nonempty_string(voice):
            target = errors if strict else warnings
            add_issue(target, f"missing_{speaker}_voice", f"Provide voice_profiles.{speaker}.voice or {speaker}_voice.")

    interaction_v2 = data.get("interaction_mode") == "evidence-dialogue-v2"

    turns = data.get("turns")
    if not isinstance(turns, list) or not turns:
        add_issue(errors, "missing_turns", "Root field 'turns' must be a non-empty array.")
        return data, 0, {}

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

        if interaction_v2:
            dialogue_act = turn.get("dialogue_act")
            if dialogue_act not in DIALOGUE_ACTS:
                add_issue(errors, "invalid_dialogue_act", f"dialogue_act must be one of {sorted(DIALOGUE_ACTS)}.", index)

            responds_to = turn.get("responds_to_turn")
            if isinstance(responds_to, bool) or not isinstance(responds_to, int) or responds_to < 0 or responds_to >= index:
                add_issue(errors, "invalid_responds_to_turn", "responds_to_turn must be 0 or an earlier 1-based turn number.", index)
            elif dialogue_act in {"evidence_answer", "followup", "concession"} and responds_to == 0:
                add_issue(errors, "missing_response_link", f"{dialogue_act} must point to an earlier turn.", index)

            emotion = turn.get("emotion")
            if emotion not in EMOTIONS:
                add_issue(errors, "invalid_emotion", f"emotion must be one of {sorted(EMOTIONS)}.", index)
            intensity = turn.get("emotion_intensity")
            if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not 0.0 <= float(intensity) <= 1.0:
                add_issue(errors, "invalid_emotion_intensity", "emotion_intensity must be between 0.0 and 1.0.", index)

            active_speaker = speaker.lower() if isinstance(speaker, str) else ""
            validate_delivery(turn.get("delivery"), backend, voice_by_speaker.get(active_speaker), errors, index)
            tags = turn.get("interaction_tags")
            if not isinstance(tags, list) or any(tag not in INTERACTION_TAGS for tag in tags):
                add_issue(errors, "invalid_interaction_tags", f"interaction_tags must use only {sorted(INTERACTION_TAGS)}.", index)
            if dialogue_act in {"challenge", "followup"} or (isinstance(tags, list) and "question" in tags):
                if not nonempty_string(turn.get("question_target")):
                    add_issue(errors, "missing_question_target", "Questions require a concrete question_target.", index)

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

        anchor = turn.get("evidence_anchor") or turn.get("source_anchor")
        if not isinstance(anchor, dict):
            target = errors if strict else warnings
            add_issue(target, "missing_evidence_anchor", "evidence_anchor or source_anchor is required in strict mode.", index)
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

    interaction_stats = validate_interaction_quality(turns, errors) if interaction_v2 else {}
    return data, len(turns), interaction_stats


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
    interaction_stats = {}
    if script_path is not None:
        if not script_path.is_file():
            add_issue(errors, "missing_script", f"Dialogue script does not exist: {script_path}")
        else:
            _, turn_count, interaction_stats = validate_script(script_path, page_count, args.strict, errors, warnings)

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
            "interaction": interaction_stats,
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
