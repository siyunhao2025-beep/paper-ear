#!/usr/bin/env python3
"""Deterministically verify a rendered Paper Ear static web reader."""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.resources = []
        self.images = []
        self.title_parts = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag in {"script", "link", "img"}:
            key = "href" if tag == "link" else "src"
            if values.get(key):
                self.resources.append((tag, values[key], values))
        if tag == "img":
            self.images.append(values)
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)


def add_issue(items, code, message, location=None):
    item = {"code": code, "message": message}
    if location:
        item["location"] = location
    items.append(item)


def local_path(site_dir, value):
    parsed = urlparse(value)
    if parsed.scheme or value.startswith(("//", "#", "data:")):
        return None
    clean = unquote(parsed.path).lstrip("/")
    return (site_dir / clean).resolve()


def inspect_image(path, errors, location, minimum=(120, 80)):
    if not path.is_file():
        add_issue(errors, "missing_image", f"Referenced image does not exist: {path}", location)
        return None
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
    except Exception as exc:
        add_issue(errors, "unreadable_image", f"Could not open image {path}: {exc}", location)
        return None
    if width < minimum[0] or height < minimum[1]:
        add_issue(
            errors,
            "tiny_image",
            f"Image is only {width}x{height}; expected at least {minimum[0]}x{minimum[1]}.",
            location,
        )
    return [width, height]


def verify(site_dir, strict=False):
    errors = []
    warnings = []
    required = ["index.html", "styles.css", "app.js", "data.json"]
    for name in required:
        path = site_dir / name
        if not path.is_file():
            add_issue(errors, "missing_required_file", f"Missing required website file: {name}")

    if errors:
        return errors, warnings, {"site": str(site_dir), "visuals": 0}

    try:
        html_text = (site_dir / "index.html").read_text(encoding="utf-8")
        data = json.loads((site_dir / "data.json").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        add_issue(errors, "unreadable_site_data", f"Could not read UTF-8 HTML/JSON: {exc}")
        return errors, warnings, {"site": str(site_dir), "visuals": 0}

    parser = DocumentParser()
    parser.feed(html_text)
    title = str(data.get("paper", {}).get("title", "")).strip()
    html_title = "".join(parser.title_parts).strip()
    if not title or title not in html_text or title not in html_title:
        add_issue(errors, "title_mismatch", "Paper title is missing from the document title or page body.")

    required_ids = {
        "main-content",
        "quick",
        "logic",
        "claims",
        "visuals",
        "walkthrough",
        "boundaries",
        "reader-search",
        "visual-dialog",
    }
    for element_id in sorted(required_ids - parser.ids):
        add_issue(errors, "missing_interface_element", f"Missing required element id: {element_id}")

    for mode in ("scan", "standard", "deep"):
        if f'data-reader-mode="{mode}"' not in html_text:
            add_issue(errors, "missing_reader_mode", f"Missing reading mode control: {mode}")

    for marker in ("{{", "}}", "TODO", "__PLACEHOLDER__", "[PLACEHOLDER]", "Lorem ipsum"):
        if marker.lower() in html_text.lower():
            add_issue(errors, "template_placeholder", f"Unresolved template marker found: {marker}")

    if re.search(r"<script\b[^>]*\bsrc=[\"'](?:https?:)?//", html_text, re.IGNORECASE):
        add_issue(errors, "remote_script", "Remote scripts are not allowed in an offline reader.")
    if re.search(
        r"<link\b[^>]*\brel=[\"']stylesheet[\"'][^>]*\bhref=[\"'](?:https?:)?//",
        html_text,
        re.IGNORECASE,
    ):
        add_issue(errors, "remote_stylesheet", "Remote stylesheets are not allowed in an offline reader.")

    site_root = site_dir.resolve()
    for tag, value, _attrs in parser.resources:
        path = local_path(site_dir, value)
        if path is None:
            continue
        try:
            path.relative_to(site_root)
        except ValueError:
            add_issue(errors, "resource_escape", f"Local {tag} resource escapes the site directory: {value}")
            continue
        if not path.is_file():
            add_issue(errors, "missing_resource", f"Missing local {tag} resource: {value}")

    for index, attrs in enumerate(parser.images, start=1):
        if not str(attrs.get("alt", "")).strip():
            add_issue(errors, "missing_alt", "Image is missing meaningful alt text.", f"html.img[{index}]")

    visuals = data.get("visuals", [])
    if not isinstance(visuals, list):
        add_issue(errors, "invalid_visual_data", "data.json visuals must be an array.")
        visuals = []
    measured = []
    for index, visual in enumerate(visuals, start=1):
        loc = f"visuals[{index}]"
        visual_id = str(visual.get("id", "")).strip()
        if not visual_id or f"visual-{visual_id}" not in parser.ids:
            add_issue(errors, "missing_visual_card", f"Visual card not found in HTML: {visual_id or '(missing id)'}", loc)
        crop_value = visual.get("crop_path", "")
        source_value = visual.get("source_path", "")
        crop = local_path(site_dir, crop_value) if crop_value else None
        source = local_path(site_dir, source_value) if source_value else None
        if crop is None:
            add_issue(errors, "missing_crop_path", "Visual crop_path must be local and non-empty.", loc)
        else:
            crop_size = inspect_image(crop, errors, loc)
        if source is None:
            add_issue(errors, "missing_source_path", "Visual source_path must be local and non-empty.", loc)
            source_size = None
        else:
            source_size = inspect_image(source, errors, loc, minimum=(600, 700))
        if crop is not None and source is not None and crop.resolve() == source.resolve():
            add_issue(errors, "identical_visual_paths", "Crop and source-location image must be different files.", loc)
        measured.append({"id": visual_id, "crop_pixels": crop_size, "source_pixels": source_size})

    render = data.get("render", {})
    if render.get("source_pdf_included") and not (site_dir / "source.pdf").is_file():
        add_issue(errors, "missing_source_pdf", "data.json says source.pdf is included, but the file is missing.")
    if strict and not render.get("source_pdf_included"):
        add_issue(errors, "source_pdf_required", "Strict verification requires an included source.pdf.")

    inventory = data.get("inventory", {})
    if strict and inventory.get("status") != "complete":
        add_issue(errors, "incomplete_inventory", "Strict verification requires inventory.status='complete'.")
    declared = inventory.get("declared_regions", {})
    actual = {
        kind: sum(1 for item in visuals if item.get("kind") == kind)
        + sum(1 for item in data.get("excluded_visuals", []) if item.get("kind") == kind)
        for kind in ("figure", "table", "equation")
    }
    for kind in ("figure", "table", "equation"):
        if declared and declared.get(kind, 0) != actual[kind]:
            add_issue(
                errors,
                "inventory_count_mismatch",
                f"Declared {kind} regions={declared.get(kind, 0)}, rendered/excluded={actual[kind]}.",
            )

    for name in ("styles.css", "app.js"):
        size = (site_dir / name).stat().st_size
        if size < 1000:
            add_issue(warnings, "small_asset", f"{name} is unexpectedly small ({size} bytes).")

    stats = {
        "site": str(site_dir),
        "paper_title": title,
        "visuals": len(visuals),
        "visual_kinds": {kind: sum(1 for item in visuals if item.get("kind") == kind) for kind in actual},
        "images_checked": len(measured) * 2,
        "source_pdf_included": bool(render.get("source_pdf_included")),
        "measured_visuals": measured,
    }
    return errors, warnings, stats


def main():
    parser = argparse.ArgumentParser(description="Verify a rendered Paper Ear web reader.")
    parser.add_argument("--site", required=True, help="Rendered website directory")
    parser.add_argument("--strict", action="store_true", help="Require source PDF and complete inventory")
    parser.add_argument("--json-out", help="Optional verification report path")
    args = parser.parse_args()

    site_dir = Path(args.site).expanduser().resolve()
    errors = []
    warnings = []
    stats = {"site": str(site_dir), "visuals": 0}
    if not site_dir.is_dir():
        add_issue(errors, "missing_site", f"Website directory does not exist: {site_dir}")
    else:
        errors, warnings, stats = verify(site_dir, strict=args.strict)

    report = {
        "ok": not errors,
        "strict": bool(args.strict),
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
        f"{status}: visuals={stats.get('visuals', 0)}, images_checked={stats.get('images_checked', 0)}, "
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
