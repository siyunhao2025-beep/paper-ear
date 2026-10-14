#!/usr/bin/env python3
"""Build a reviewable figure/table/equation inventory from paper_structure.json.

The inventory is intentionally a candidate list rather than a completeness claim.
PDF text extraction can miss raster captions and can mistake in-text references for
captions, so a human/agent must still inspect every rendered page before setting a
web brief's inventory.status to ``complete``.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


NAMED_PATTERN = re.compile(
    r"\b(?P<kind>Figure|Fig\.?|Table|Equation|Eq\.?)\s*"
    r"(?P<number>\(?\d{1,3}[A-Za-z]?\)?)",
    re.IGNORECASE,
)
BARE_EQUATION_PATTERN = re.compile(r"(?<![A-Za-z0-9])\((?P<number>\d{1,3}[A-Za-z]?)\)(?![A-Za-z0-9])")


def canonical_kind(value):
    value = value.lower()
    if value.startswith("fig"):
        return "figure"
    if value.startswith("tab"):
        return "table"
    return "equation"


def canonical_label(kind, number):
    number = number.strip("()")
    prefix = {"figure": "Figure", "table": "Table", "equation": "Equation"}[kind]
    return f"{prefix} {number}"


def context_window(text, start, end, radius=150):
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    context = re.sub(r"\s+", " ", text[left:right]).strip()
    return context


def named_score(text, end, kind):
    tail = text[end : end + 8]
    punctuation = bool(re.match(r"\s*[:.\-–—]", tail))
    # Numbered equations are commonly referenced inline; an explicit Equation/Eq.
    # token is useful but not by itself a proof that the equation is printed here.
    if punctuation:
        return 0.96 if kind in {"figure", "table"} else 0.86, "caption-like punctuation"
    return 0.66 if kind in {"figure", "table"} else 0.58, "in-text named reference"


def iter_blocks(structure):
    for page in structure.get("pages", []):
        page_number = page.get("page")
        for block in page.get("blocks", []):
            text = block.get("full_text") or block.get("text") or ""
            if text.strip():
                yield page_number, block, text


def build_inventory(structure):
    named = defaultdict(list)
    bare_equations = []

    for page_number, block, text in iter_blocks(structure):
        for match in NAMED_PATTERN.finditer(text):
            kind = canonical_kind(match.group("kind"))
            label = canonical_label(kind, match.group("number"))
            score, reason = named_score(text, match.end(), kind)
            named[(kind, label.lower())].append(
                {
                    "label": label,
                    "page": page_number,
                    "block_id": block.get("block_id"),
                    "block_bbox_norm": block.get("bbox_norm"),
                    "confidence": score,
                    "reason": reason,
                    "context": context_window(text, match.start(), match.end()),
                }
            )

        # Bare parenthesized numbers are deliberately kept separate. They are
        # often equation labels, but may also be citations or enumerated items.
        for match in BARE_EQUATION_PATTERN.finditer(text):
            before = text[max(0, match.start() - 1) : match.start()]
            after = text[match.end() : match.end() + 1]
            if before == "[" or after == "]":
                continue
            bare_equations.append(
                {
                    "candidate_label": f"Equation {match.group('number')}",
                    "page": page_number,
                    "block_id": block.get("block_id"),
                    "block_bbox_norm": block.get("bbox_norm"),
                    "confidence": 0.35,
                    "reason": "bare parenthesized number; requires visual confirmation",
                    "context": context_window(text, match.start(), match.end(), radius=110),
                }
            )

    candidates = []
    for (kind, _), occurrences in named.items():
        occurrences.sort(key=lambda item: (-item["confidence"], item["page"] or 10**9))
        primary = occurrences[0]
        label = primary["label"]
        candidates.append(
            {
                "kind": kind,
                "label": label,
                "probable_page": primary["page"],
                "probable_block_id": primary["block_id"],
                "caption_block_bbox_norm": primary["block_bbox_norm"],
                "confidence": primary["confidence"],
                "reason": primary["reason"],
                "context": primary["context"],
                "reference_pages": sorted({item["page"] for item in occurrences if item["page"]}),
                "review_status": "needs_visual_review",
            }
        )

    kind_order = {"figure": 0, "table": 1, "equation": 2}

    def visual_order(item):
        number_match = re.search(r"\d+", item["label"])
        number = int(number_match.group()) if number_match else 10**9
        return kind_order[item["kind"]], number, item["label"], item["probable_page"] or 10**9

    candidates.sort(key=visual_order)
    counts = {
        kind: sum(1 for item in candidates if item["kind"] == kind)
        for kind in ("figure", "table", "equation")
    }
    return {
        "schema_version": 1,
        "source_structure": structure.get("pdf_path", ""),
        "page_count": structure.get("num_pages", len(structure.get("pages", []))),
        "status": "needs_visual_review",
        "notice": (
            "Candidate inventory only. Inspect every rendered page, correct crop boxes, "
            "add missed raster/formula regions, and record intentional exclusions before "
            "declaring complete coverage."
        ),
        "summary": {
            "named_candidates": counts,
            "bare_equation_candidates": len(bare_equations),
        },
        "candidates": candidates,
        "bare_equation_candidates": bare_equations,
    }


def main():
    parser = argparse.ArgumentParser(description="Build a reviewable PDF visual inventory.")
    parser.add_argument("--structure", required=True, help="paper_structure.json from inspect_paper.py")
    parser.add_argument("--out", required=True, help="Output visual_inventory.json")
    args = parser.parse_args()

    structure_path = Path(args.structure).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    if not structure_path.is_file():
        print(f"ERROR: structure file not found: {structure_path}", file=sys.stderr)
        return 1
    try:
        structure = json.loads(structure_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read structure JSON: {exc}", file=sys.stderr)
        return 1

    inventory = build_inventory(structure)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = inventory["summary"]["named_candidates"]
    print(
        f"Inventory candidates: figures={counts['figure']}, tables={counts['table']}, "
        f"named equations={counts['equation']}, bare equation labels="
        f"{inventory['summary']['bare_equation_candidates']}"
    )
    print("Review every rendered page before marking coverage complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
