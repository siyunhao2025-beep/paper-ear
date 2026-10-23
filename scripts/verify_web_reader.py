#!/usr/bin/env python3
"""Deterministically verify a rendered Paper Ear static web reader."""

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image

from site_identity import (
    SITE_HASH_CONTRACT,
    SITE_IDENTITY_SCHEMA_VERSION,
    site_file_record,
    site_manifest_sha256,
    valid_site_file_record,
)


BRAND_PROFILE = "bubu-yier-v1"
BRAND_ASSET_KEYS = {
    "hero_yier",
    "hero_bubu",
    "evidence_yier",
    "evidence_bubu",
    "critique_yier",
    "critique_bubu",
}


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
        if tag in {"script", "link", "img", "source", "video", "audio", "iframe"}:
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


def sha256_file(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_page_count(path):
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        with pdfplumber.open(str(path)) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


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
        css_text = (site_dir / "styles.css").read_text(encoding="utf-8")
        js_text = (site_dir / "app.js").read_text(encoding="utf-8")
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
    if re.search(r"url\(\s*['\"]?(?:https?:)?//", css_text, re.IGNORECASE):
        add_issue(errors, "remote_css_resource", "Remote CSS resources are not allowed in an offline reader.")
    if re.search(r"\b(?:fetch|importScripts)\s*\(\s*['\"](?:https?:)?//", js_text, re.IGNORECASE):
        add_issue(errors, "remote_javascript_call", "Automatic remote JavaScript calls are not allowed.")

    site_root = site_dir.resolve()
    for tag, value, _attrs in parser.resources:
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} or value.startswith("//"):
            add_issue(errors, "remote_resource", f"Remote {tag} dependency is not allowed: {value}")
            continue
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

    brand_profile = data.get("brand_profile")
    brand_assets_checked = []
    site_identity_checked = False
    if brand_profile == BRAND_PROFILE:
        if 'data-brand-profile="bubu-yier-v1"' not in html_text:
            add_issue(errors, "missing_brand_marker", "Branded HTML is missing its bubu-yier-v1 marker.")
        for text in ("一二讲证据、布布问边界", "一二", "布布", "角色提示是阅读导航，不是论文证据"):
            if text not in html_text:
                add_issue(errors, "missing_brand_copy", f"Branded reader is missing required copy: {text}")
        brand = data.get("brand", {})
        cast = brand.get("cast", {}) if isinstance(brand, dict) else {}
        if cast.get("yier", {}).get("role") != "女主讲 · 讲证据":
            add_issue(errors, "invalid_yier_role", "Branded reader must keep 一二 as the female evidence presenter.")
        if cast.get("bubu", {}).get("role") != "男追问 · 问边界":
            add_issue(errors, "invalid_bubu_role", "Branded reader must keep 布布 as the male boundary discussant.")
        assets = brand.get("assets", {}) if isinstance(brand, dict) else {}
        if not isinstance(assets, dict) or not BRAND_ASSET_KEYS.issubset(assets):
            add_issue(errors, "missing_brand_assets", "Branded reader must declare every local character asset.")
        else:
            for key in sorted(BRAND_ASSET_KEYS):
                value = assets.get(key, "")
                path = local_path(site_dir, value) if value else None
                if path is None:
                    add_issue(errors, "remote_brand_asset", f"Brand asset must be local: {key}")
                    continue
                try:
                    path.relative_to(site_root)
                except ValueError:
                    add_issue(errors, "brand_asset_escape", f"Brand asset escapes the site: {value}")
                    continue
                size = inspect_image(path, errors, f"brand.assets.{key}", minimum=(256, 256))
                brand_assets_checked.append({"key": key, "path": value, "pixels": size})
        if not render.get("source_binding", {}).get("verified"):
            add_issue(errors, "unverified_source_binding", "Branded reader is not verified against the current PDF.")

        identity_error_start = len(errors)
        identity_path = site_dir / "site-identity.json"
        source_brief_path = site_dir / "source-brief.json"
        if not identity_path.is_file():
            add_issue(errors, "missing_site_identity", "Branded reader is missing site-identity.json.")
        if not source_brief_path.is_file():
            add_issue(errors, "missing_source_brief", "Branded reader is missing its hash-verifiable source-brief.json.")
        manifest = {}
        manifest_supported = False
        if identity_path.is_file():
            try:
                manifest = json.loads(identity_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                add_issue(errors, "invalid_site_identity", f"Could not read site-identity.json: {exc}")
        if manifest:
            schema_version = manifest.get("schema_version")
            if schema_version != SITE_IDENTITY_SCHEMA_VERSION:
                add_issue(
                    errors,
                    "unsupported_site_identity_schema",
                    "Unsupported site identity schema "
                    f"{schema_version!r}; expected {SITE_IDENTITY_SCHEMA_VERSION}. "
                    "Regenerate the branded reader with the current renderer.",
                )
            elif manifest.get("hash_contract") != SITE_HASH_CONTRACT:
                add_issue(
                    errors,
                    "unsupported_site_hash_contract",
                    "Site identity uses an unsupported hash contract; regenerate the branded reader.",
                )
            else:
                manifest_supported = True
                if manifest.get("brand_profile") != BRAND_PROFILE:
                    add_issue(errors, "site_identity_brand_mismatch", "Site identity records the wrong brand profile.")
                if not manifest.get("source_binding_verified"):
                    add_issue(errors, "site_identity_unverified", "Site identity does not record a verified source binding.")
        render_identity = render.get("input_identity", {})
        declared_source = data.get("source_document", {})
        if not isinstance(declared_source, dict):
            declared_source = {}

        if source_brief_path.is_file():
            if manifest_supported:
                expected_raw_brief_hashes = {
                    str(manifest.get("brief_sha256", "")).lower(),
                    str(render_identity.get("brief_sha256", "")).lower(),
                }
                actual_brief_record = site_file_record(source_brief_path)
                expected_content_hashes = {
                    str(manifest.get("brief_content_sha256", "")).lower(),
                    str(render_identity.get("brief_content_sha256", "")).lower(),
                }
                if (
                    "" in expected_raw_brief_hashes
                    or len(expected_raw_brief_hashes) != 1
                    or not all(re.fullmatch(r"[0-9a-f]{64}", value) for value in expected_raw_brief_hashes)
                ):
                    add_issue(errors, "brief_input_identity_mismatch", "Recorded input brief SHA-256 values disagree.")
                if (
                    actual_brief_record.get("mode") != SITE_HASH_CONTRACT["text_mode"]
                    or "" in expected_content_hashes
                    or expected_content_hashes != {actual_brief_record.get("sha256")}
                ):
                    add_issue(errors, "brief_identity_mismatch", "source-brief.json does not match the recorded normalized content SHA-256.")
            try:
                source_brief = json.loads(source_brief_path.read_text(encoding="utf-8"))
                if source_brief.get("brand_profile") != BRAND_PROFILE:
                    add_issue(errors, "brief_brand_mismatch", "source-brief.json is not bubu-yier-v1.")
                if source_brief.get("source_document") != data.get("source_document"):
                    add_issue(errors, "brief_binding_mismatch", "Rendered data and source brief declare different PDFs.")
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                add_issue(errors, "invalid_source_brief", f"Could not read source-brief.json: {exc}")

        source_pdf_path = site_dir / "source.pdf"
        if source_pdf_path.is_file():
            actual_pdf_sha = sha256_file(source_pdf_path)
            expected_pdf_hashes = {
                str(manifest.get("pdf_sha256", "")).lower(),
                str(render_identity.get("pdf_sha256", "")).lower(),
                str(declared_source.get("sha256", "")).lower(),
            }
            if "" in expected_pdf_hashes or expected_pdf_hashes != {actual_pdf_sha}:
                add_issue(errors, "pdf_identity_mismatch", "source.pdf does not match the recorded PDF SHA-256.")
            actual_pages = pdf_page_count(source_pdf_path)
            expected_pages = {
                manifest.get("pdf_pages"),
                render_identity.get("pdf_pages"),
                declared_source.get("page_count"),
            }
            if actual_pages is None or expected_pages != {actual_pages}:
                add_issue(errors, "pdf_page_identity_mismatch", "source.pdf page count does not match the recorded identity.")

        manifest_files = manifest.get("files", {}) if manifest_supported else {}
        if manifest_supported and (not isinstance(manifest_files, dict) or not manifest_files):
            add_issue(errors, "missing_site_manifest", "site-identity.json must contain hashed site files.")
        elif manifest_supported:
            actual_files = {
                path.relative_to(site_dir).as_posix()
                for path in site_dir.rglob("*")
                if path.is_file() and path.name != "site-identity.json"
            }
            if actual_files != set(manifest_files):
                add_issue(errors, "site_manifest_file_mismatch", "Site files differ from the signed identity manifest.")
            for relative, expected_record in sorted(manifest_files.items()):
                if not valid_site_file_record(expected_record):
                    add_issue(errors, "invalid_site_file_record", f"Invalid site hash record: {relative}")
                    continue
                path = local_path(site_dir, relative)
                if path is None:
                    add_issue(errors, "invalid_manifest_path", f"Manifest path must be local: {relative}")
                    continue
                try:
                    path.relative_to(site_root)
                except ValueError:
                    add_issue(errors, "manifest_path_escape", f"Manifest path escapes the site: {relative}")
                    continue
                if not path.is_file():
                    add_issue(errors, "site_file_hash_mismatch", f"Site file hash mismatch: {relative}")
                    continue
                actual_record = site_file_record(path)
                normalized_expected = {
                    "sha256": str(expected_record.get("sha256") or "").lower(),
                    "mode": expected_record.get("mode"),
                }
                if actual_record != normalized_expected:
                    add_issue(errors, "site_file_hash_mismatch", f"Site file hash mismatch: {relative}")
            actual_site_sha = site_manifest_sha256(manifest_files)
            if actual_site_sha != str(manifest.get("site_sha256", "")).lower():
                add_issue(errors, "site_identity_mismatch", "Site manifest digest is invalid.")
            site_identity_checked = len(errors) == identity_error_start

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
        "brand_profile": brand_profile or None,
        "brand_assets_checked": brand_assets_checked,
        "site_identity_checked": site_identity_checked,
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
