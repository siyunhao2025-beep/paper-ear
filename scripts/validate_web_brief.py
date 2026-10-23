#!/usr/bin/env python3
"""Validate an evidence-grounded Paper Ear web-reader brief."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from document_binding import collect_input_identity, validate_document_binding


CLAIM_TYPES = {"paper_evidence", "author_claim", "inference", "critique"}
ANCHOR_KINDS = {"section", "figure", "table", "equation", "appendix", "page"}
VISUAL_KINDS = {"figure", "table", "equation"}
EVIDENCE_STRENGTHS = {"strong", "moderate", "tentative"}
BRAND_PROFILE = "bubu-yier-v1"


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def issue(items, code, message, location=None):
    item = {"code": code, "message": message}
    if location:
        item["location"] = location
    items.append(item)


def load_page_count(pdf_path, errors):
    try:
        import pdfplumber
    except ImportError:
        issue(errors, "missing_dependency", "Python package 'pdfplumber' is required.")
        return 0
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            return len(pdf.pages)
    except Exception as exc:
        issue(errors, "unreadable_pdf", f"Could not open PDF: {exc}")
        return 0


def valid_bbox(value):
    if not isinstance(value, list) or len(value) != 4:
        return False
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        return False
    x0, y0, x1, y1 = (float(v) for v in value)
    return all(0.0 <= v <= 1.0 for v in (x0, y0, x1, y1)) and x0 < x1 and y0 < y1


def validate_anchor(anchor, page_count, errors, location, expected_kind=None):
    if not isinstance(anchor, dict):
        issue(errors, "missing_source_anchor", "source_anchor must be an object.", location)
        return
    page = anchor.get("page")
    if isinstance(page, bool) or not isinstance(page, int) or page < 1 or (page_count and page > page_count):
        issue(errors, "invalid_anchor_page", f"source_anchor.page must be within 1..{page_count}.", location)
    kind = anchor.get("kind")
    if kind not in ANCHOR_KINDS:
        issue(errors, "invalid_anchor_kind", f"source_anchor.kind must be one of {sorted(ANCHOR_KINDS)}.", location)
    if expected_kind and kind != expected_kind:
        issue(errors, "anchor_kind_mismatch", f"source_anchor.kind must be '{expected_kind}'.", location)
    if not nonempty(anchor.get("label")):
        issue(errors, "missing_anchor_label", "source_anchor.label must be non-empty.", location)


def validate_text_list(value, errors, location, minimum=1):
    if not isinstance(value, list) or len(value) < minimum or any(not nonempty(v) for v in value):
        issue(errors, "invalid_text_list", f"Expected at least {minimum} non-empty text item(s).", location)


def validate_data(data, page_count, strict=False):
    errors = []
    warnings = []

    if not isinstance(data, dict):
        issue(errors, "invalid_root", "Web brief root must be a JSON object.")
        return errors, warnings, {}

    if data.get("schema_version") != 1:
        issue(errors, "schema_version", "schema_version must be 1.")

    brand_profile = data.get("brand_profile")
    if brand_profile not in (None, "", BRAND_PROFILE):
        issue(errors, "unsupported_brand_profile", f"Unsupported brand_profile: {brand_profile}.")

    paper = data.get("paper")
    if not isinstance(paper, dict):
        issue(errors, "missing_paper", "paper must be an object.")
    else:
        if not nonempty(paper.get("title")):
            issue(errors, "missing_title", "paper.title is required.", "paper.title")
        authors = paper.get("authors")
        if not isinstance(authors, list) or not authors or any(not nonempty(v) for v in authors):
            issue(errors, "invalid_authors", "paper.authors must contain one or more names.", "paper.authors")
        declared_pages = paper.get("page_count")
        if declared_pages is not None and declared_pages != page_count:
            issue(errors, "page_count_mismatch", f"paper.page_count is {declared_pages}, PDF has {page_count} pages.", "paper.page_count")

    summary = data.get("summary")
    if not isinstance(summary, dict):
        issue(errors, "missing_summary", "summary must be an object.")
    else:
        if not nonempty(summary.get("one_sentence")):
            issue(errors, "missing_one_sentence", "summary.one_sentence is required.", "summary.one_sentence")
        validate_text_list(summary.get("quick_points"), errors, "summary.quick_points", minimum=3)
        if not nonempty(summary.get("three_minute")):
            issue(errors, "missing_three_minute", "summary.three_minute is required.", "summary.three_minute")

    logic_map = data.get("logic_map")
    if not isinstance(logic_map, list) or len(logic_map) < 3:
        issue(errors, "invalid_logic_map", "logic_map must contain at least three stages.")
    else:
        for index, item in enumerate(logic_map, start=1):
            loc = f"logic_map[{index}]"
            if not isinstance(item, dict) or not all(nonempty(item.get(k)) for k in ("stage", "title", "body")):
                issue(errors, "invalid_logic_stage", "Each logic stage needs stage, title, and body.", loc)
                continue
            validate_anchor(item.get("source_anchor"), page_count, errors, loc)

    claims = data.get("claims")
    claim_ids = set()
    if not isinstance(claims, list) or not claims:
        issue(errors, "missing_claims", "claims must be a non-empty array.")
    else:
        for index, claim in enumerate(claims, start=1):
            loc = f"claims[{index}]"
            if not isinstance(claim, dict):
                issue(errors, "invalid_claim", "Each claim must be an object.", loc)
                continue
            claim_id = claim.get("id")
            if not nonempty(claim_id) or claim_id in claim_ids:
                issue(errors, "invalid_claim_id", "Claim id must be non-empty and unique.", loc)
            else:
                claim_ids.add(claim_id)
            for field in ("title", "summary", "why_it_matters"):
                if not nonempty(claim.get(field)):
                    issue(errors, f"missing_{field}", f"Claim field '{field}' is required.", loc)
            if claim.get("claim_type") not in CLAIM_TYPES:
                issue(errors, "invalid_claim_type", f"claim_type must be one of {sorted(CLAIM_TYPES)}.", loc)
            if claim.get("evidence_strength") not in EVIDENCE_STRENGTHS:
                issue(errors, "invalid_evidence_strength", f"evidence_strength must be one of {sorted(EVIDENCE_STRENGTHS)}.", loc)
            validate_text_list(claim.get("evidence"), errors, f"{loc}.evidence")
            validate_anchor(claim.get("source_anchor"), page_count, errors, loc)

    visuals = data.get("visuals")
    visual_ids = set()
    visual_counts = Counter()
    if not isinstance(visuals, list):
        issue(errors, "invalid_visuals", "visuals must be an array.")
        visuals = []
    for index, visual in enumerate(visuals, start=1):
        loc = f"visuals[{index}]"
        if not isinstance(visual, dict):
            issue(errors, "invalid_visual", "Each visual must be an object.", loc)
            continue
        visual_id = visual.get("id")
        if not nonempty(visual_id) or visual_id in visual_ids:
            issue(errors, "invalid_visual_id", "Visual id must be non-empty and unique.", loc)
        else:
            visual_ids.add(visual_id)
        kind = visual.get("kind")
        if kind not in VISUAL_KINDS:
            issue(errors, "invalid_visual_kind", f"kind must be one of {sorted(VISUAL_KINDS)}.", loc)
        else:
            visual_counts[kind] += 1
        page = visual.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or page < 1 or (page_count and page > page_count):
            issue(errors, "invalid_visual_page", f"page must be within 1..{page_count}.", loc)
        if not valid_bbox(visual.get("bbox_norm")):
            issue(errors, "invalid_bbox", "bbox_norm must be [x0,y0,x1,y1] within 0..1.", loc)
        for field in ("label", "caption", "alt", "why_it_matters"):
            if not nonempty(visual.get(field)):
                issue(errors, f"missing_{field}", f"Visual field '{field}' is required.", loc)
        validate_anchor(visual.get("source_anchor"), page_count, errors, loc, expected_kind=kind if kind in VISUAL_KINDS else None)

    excluded = data.get("excluded_visuals", [])
    excluded_counts = Counter()
    if not isinstance(excluded, list):
        issue(errors, "invalid_excluded_visuals", "excluded_visuals must be an array.")
        excluded = []
    for index, item in enumerate(excluded, start=1):
        loc = f"excluded_visuals[{index}]"
        if not isinstance(item, dict) or item.get("kind") not in VISUAL_KINDS:
            issue(errors, "invalid_excluded_visual", "Excluded visual needs a valid kind.", loc)
            continue
        excluded_counts[item["kind"]] += 1
        if not nonempty(item.get("label")) or not nonempty(item.get("reason")):
            issue(errors, "incomplete_exclusion", "Excluded visual needs label and reason.", loc)

    inventory = data.get("inventory")
    if not isinstance(inventory, dict):
        issue(errors, "missing_inventory", "inventory must document visual coverage.")
    else:
        status = inventory.get("status")
        if status not in {"complete", "partial"}:
            issue(errors, "invalid_inventory_status", "inventory.status must be complete or partial.")
        if strict and status != "complete":
            issue(errors, "incomplete_inventory", "Strict mode requires inventory.status='complete'.")
        declared = inventory.get("declared_regions")
        if not isinstance(declared, dict):
            issue(errors, "missing_declared_regions", "inventory.declared_regions must be an object.")
        else:
            for kind in VISUAL_KINDS:
                count = declared.get(kind, 0)
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    issue(errors, "invalid_declared_count", f"Declared {kind} count must be a non-negative integer.")
                    continue
                accounted = visual_counts[kind] + excluded_counts[kind]
                if count != accounted:
                    issue(errors, "inventory_count_mismatch", f"Declared {kind} regions={count}, accounted={accounted}.")

    sections = data.get("sections")
    section_ids = set()
    if not isinstance(sections, list) or not sections:
        issue(errors, "missing_sections", "sections must be a non-empty array.")
    else:
        for index, section in enumerate(sections, start=1):
            loc = f"sections[{index}]"
            if not isinstance(section, dict):
                issue(errors, "invalid_section", "Each section must be an object.", loc)
                continue
            section_id = section.get("id")
            if not nonempty(section_id) or section_id in section_ids:
                issue(errors, "invalid_section_id", "Section id must be non-empty and unique.", loc)
            else:
                section_ids.add(section_id)
            for field in ("nav_title", "title", "lede"):
                if not nonempty(section.get(field)):
                    issue(errors, f"missing_{field}", f"Section field '{field}' is required.", loc)
            validate_text_list(section.get("body"), errors, f"{loc}.body")
            validate_text_list(section.get("takeaways"), errors, f"{loc}.takeaways")
            anchors = section.get("source_anchors")
            if not isinstance(anchors, list) or not anchors:
                issue(errors, "missing_section_anchors", "Section needs at least one source anchor.", loc)
            else:
                for anchor_index, anchor in enumerate(anchors, start=1):
                    validate_anchor(anchor, page_count, errors, f"{loc}.source_anchors[{anchor_index}]")
            linked_visuals = section.get("visual_ids", [])
            if not isinstance(linked_visuals, list):
                issue(errors, "invalid_visual_links", "visual_ids must be an array.", loc)
            else:
                for visual_id in linked_visuals:
                    if visual_id not in visual_ids:
                        issue(errors, "unknown_visual_id", f"Unknown visual id '{visual_id}'.", loc)

    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        target = errors if strict else warnings
        issue(target, "missing_limitations", "Include at least one author limitation or explicit critique.")
    else:
        for index, item in enumerate(limitations, start=1):
            loc = f"limitations[{index}]"
            if not isinstance(item, dict) or not nonempty(item.get("title")) or not nonempty(item.get("body")):
                issue(errors, "invalid_limitation", "Limitation needs title and body.", loc)
                continue
            if item.get("claim_type") not in {"author_claim", "critique"}:
                issue(errors, "invalid_limitation_type", "Limitation claim_type must be author_claim or critique.", loc)
            validate_anchor(item.get("source_anchor"), page_count, errors, loc)

    questions = data.get("questions", [])
    if not isinstance(questions, list) or any(not nonempty(v) for v in questions):
        issue(errors, "invalid_questions", "questions must be an array of non-empty strings.")

    glossary = data.get("glossary", [])
    if not isinstance(glossary, list):
        issue(errors, "invalid_glossary", "glossary must be an array.")
    else:
        for index, item in enumerate(glossary, start=1):
            loc = f"glossary[{index}]"
            if not isinstance(item, dict) or not nonempty(item.get("term")) or not nonempty(item.get("definition")):
                issue(errors, "invalid_glossary_item", "Glossary item needs term and definition.", loc)

    source_excerpt = data.get("source_excerpt")
    if isinstance(source_excerpt, str) and len(source_excerpt.split()) > 25:
        issue(warnings, "long_source_excerpt", "Keep any verbatim source excerpt at or below 25 words.")

    stats = {
        "pages": page_count,
        "brand_profile": brand_profile or None,
        "claims": len(claims) if isinstance(claims, list) else 0,
        "sections": len(sections) if isinstance(sections, list) else 0,
        "visuals": len(visuals),
        "visual_kinds": dict(visual_counts),
        "excluded_visuals": len(excluded),
    }
    return errors, warnings, stats


def validate_web_source_binding(data, pdf_path, brief_path, page_count):
    identity = collect_input_identity(pdf_path, brief_path, page_count)
    result = validate_document_binding(
        data,
        identity,
        brief_path,
        require_source_document=data.get("brand_profile") == BRAND_PROFILE,
        artifact_label="web brief",
    )
    return result, {
        "source_document": identity["source_document"],
        "pdf_sha256": identity["pdf_sha256"],
        "pdf_pages": identity["pdf_pages"],
        "web_brief": identity["dialogue_script"],
        "brief_sha256": identity["script_sha256"],
    }


def main():
    parser = argparse.ArgumentParser(description="Validate a Paper Ear interactive web-reader brief.")
    parser.add_argument("--pdf", required=True, help="Input PDF paper")
    parser.add_argument("--brief", required=True, help="Web brief JSON")
    parser.add_argument("--strict", action="store_true", help="Require complete visual inventory and limitations")
    parser.add_argument("--json-out", help="Optional validation report")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    brief_path = Path(args.brief).expanduser().resolve()
    errors = []
    warnings = []
    page_count = 0
    data = {}

    if not pdf_path.is_file():
        issue(errors, "missing_pdf", f"PDF does not exist: {pdf_path}")
    else:
        page_count = load_page_count(pdf_path, errors)

    if not brief_path.is_file():
        issue(errors, "missing_brief", f"Brief does not exist: {brief_path}")
    else:
        try:
            data = json.loads(brief_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            issue(errors, "invalid_json", f"Could not read brief as UTF-8 JSON: {exc}")

    stats = {"pages": page_count, "claims": 0, "sections": 0, "visuals": 0}
    source_binding = {"declared": False, "required": False, "verified": False, "issues": []}
    identity = {}
    if data and not errors:
        found_errors, found_warnings, stats = validate_data(data, page_count, strict=args.strict)
        errors.extend(found_errors)
        warnings.extend(found_warnings)
        source_binding, identity = validate_web_source_binding(data, pdf_path, brief_path, page_count)
        errors.extend(source_binding["issues"])
        stats["source_binding_verified"] = bool(source_binding["verified"])

    report = {
        "ok": not errors,
        "strict": bool(args.strict),
        "pdf": str(pdf_path),
        "brief": str(brief_path),
        "identity": identity,
        "source_binding": source_binding,
        "stats": stats,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json_out:
        out = Path(args.json_out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "PASS" if report["ok"] else "FAIL"
    print(
        f"{status}: pages={stats.get('pages', 0)}, claims={stats.get('claims', 0)}, "
        f"sections={stats.get('sections', 0)}, visuals={stats.get('visuals', 0)}, "
        f"errors={len(errors)}, warnings={len(warnings)}"
    )
    for item in errors:
        where = f" {item['location']}:" if item.get("location") else ""
        print(f"ERROR [{item['code']}]{where} {item['message']}")
    for item in warnings:
        where = f" {item['location']}:" if item.get("location") else ""
        print(f"WARN  [{item['code']}]{where} {item['message']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
