import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import render_paper_web as renderer
import validate_web_brief as validator
import verify_web_reader as verifier
from document_binding import DocumentBindingError, sha256_file


def write_pdf(path):
    Image.new("RGB", (360, 480), "white").save(path, "PDF")


def web_brief(pdf_path, branded=True):
    data = {
        "schema_version": 1,
        "paper": {
            "title": "Current uploaded paper",
            "authors": ["Example Author"],
            "page_count": 1,
        },
        "reader": {"reading_minutes": 3},
        "summary": {
            "one_sentence": "This summary belongs only to the current test PDF.",
            "quick_points": ["Problem", "Method", "Evidence"],
            "three_minute": "A compact evidence-grounded synthesis.",
        },
        "logic_map": [],
        "claims": [],
        "inventory": {
            "status": "complete",
            "declared_regions": {"figure": 0, "table": 0, "equation": 0},
        },
        "visuals": [],
        "excluded_visuals": [],
        "sections": [],
        "limitations": [],
        "questions": [],
        "glossary": [],
    }
    if branded:
        data["brand_profile"] = "bubu-yier-v1"
        data["source_document"] = {
            "filename": pdf_path.name,
            "sha256": sha256_file(pdf_path),
            "page_count": 1,
        }
    return data


class BubuYierWebTests(unittest.TestCase):
    def render(self, directory, branded=True):
        pdf = directory / "paper.pdf"
        brief_path = directory / "web_brief.json"
        pages = directory / "pages"
        site = directory / "site"
        report = directory / "report.json"
        write_pdf(pdf)
        pages.mkdir()
        brief_path.write_text(
            json.dumps(web_brief(pdf, branded=branded), ensure_ascii=False),
            encoding="utf-8",
        )
        render_pages_dir = None if branded else pages
        with mock.patch.object(renderer, "render_pages"):
            result = renderer.render_web_reader(
                pdf,
                brief_path,
                site,
                pages_dir=render_pages_dir,
                copy_pdf=True,
                report_json=report,
            )
        return pdf, brief_path, site, result

    def test_branded_site_copies_local_cast_and_keeps_roles_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, site, report = self.render(Path(temporary), branded=True)
            html = (site / "index.html").read_text(encoding="utf-8")
            data = json.loads((site / "data.json").read_text(encoding="utf-8"))

            self.assertIn('data-brand-profile="bubu-yier-v1"', html)
            self.assertIn("一二讲证据、布布问边界", html)
            self.assertIn("白色棕耳的小熊女主讲", html)
            self.assertIn("棕色小熊男追问", html)
            self.assertNotRegex(html, r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://')
            for value in data["brand"]["assets"].values():
                self.assertTrue((site / value).is_file(), value)
                self.assertTrue(value.startswith("assets/characters/"))
            self.assertTrue(report["source_binding"]["verified"])
            self.assertEqual(report["pdf_sha256"], sha256_file(site / "source.pdf"))

            errors, warnings, stats = verifier.verify(site, strict=True)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertEqual(stats["brand_profile"], "bubu-yier-v1")
            self.assertEqual(len(stats["brand_assets_checked"]), 6)

    def test_branded_renderer_rejects_a_brief_bound_to_another_pdf_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            brief_path = directory / "web_brief.json"
            site = directory / "site"
            pages = directory / "pages"
            write_pdf(pdf)
            pages.mkdir()
            brief = web_brief(pdf)
            brief["source_document"]["sha256"] = "0" * 64
            brief_path.write_text(json.dumps(brief), encoding="utf-8")

            with self.assertRaises(DocumentBindingError):
                renderer.render_web_reader(pdf, brief_path, site, pages_dir=pages)

            self.assertFalse(site.exists())

    def test_validator_reports_branded_pdf_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            brief_path = directory / "web_brief.json"
            write_pdf(pdf)
            brief = web_brief(pdf)
            brief["source_document"]["filename"] = "some-other-paper.pdf"
            brief_path.write_text(json.dumps(brief), encoding="utf-8")

            result, _identity = validator.validate_web_source_binding(brief, pdf, brief_path, 1)

            self.assertFalse(result["verified"])
            self.assertIn("source_filename_mismatch", {item["code"] for item in result["issues"]})

    def test_branded_renderer_rejects_external_pages_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            brief_path = directory / "web_brief.json"
            pages = directory / "stale-pages"
            site = directory / "site"
            write_pdf(pdf)
            pages.mkdir()
            brief_path.write_text(json.dumps(web_brief(pdf)), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "does not accept --pages-dir"):
                renderer.render_web_reader(pdf, brief_path, site, pages_dir=pages)

            self.assertFalse(site.exists())

    def test_nonbranded_reader_remains_compatible_without_character_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, site, report = self.render(Path(temporary), branded=False)
            html = (site / "index.html").read_text(encoding="utf-8")

            self.assertNotIn("data-brand-profile", html)
            self.assertNotIn("brand-companion", html)
            self.assertFalse((site / "assets" / "characters").exists())
            self.assertFalse(report["source_binding"]["required"])
            errors, _warnings, stats = verifier.verify(site, strict=True)
            self.assertEqual(errors, [])
            self.assertIsNone(stats["brand_profile"])

    def test_verifier_rejects_a_character_asset_changed_after_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, site, _report = self.render(Path(temporary), branded=True)
            character = site / "assets" / "characters" / "yier_evidence_point.png"
            character.write_bytes(character.read_bytes() + b"changed-after-render")

            errors, _warnings, _stats = verifier.verify(site, strict=True)

            self.assertIn("site_file_hash_mismatch", {item["code"] for item in errors})

    def test_site_identity_survives_crlf_checkout_but_rejects_text_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, site, _report = self.render(Path(temporary), branded=True)
            identity = json.loads((site / "site-identity.json").read_text(encoding="utf-8"))

            self.assertEqual(identity["schema_version"], 2)
            self.assertEqual(identity["hash_contract"]["algorithm"], "sha256")
            text_files = [
                relative
                for relative, record in identity["files"].items()
                if record["mode"] == "utf8-lf-v1"
            ]
            self.assertIn("app.js", text_files)
            for relative in text_files:
                path = site / relative
                payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                path.write_bytes(payload.replace(b"\n", b"\r\n"))

            errors, warnings, stats = verifier.verify(site, strict=True)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertTrue(stats["site_identity_checked"])

            app = site / "app.js"
            app.write_bytes(app.read_bytes() + b"\r\n// real content change\r\n")
            errors, _warnings, stats = verifier.verify(site, strict=True)

            self.assertIn("site_file_hash_mismatch", {item["code"] for item in errors})
            self.assertFalse(stats["site_identity_checked"])

    def test_verifier_clearly_rejects_legacy_site_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, site, _report = self.render(Path(temporary), branded=True)
            identity_path = site / "site-identity.json"
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            identity["schema_version"] = 1
            identity.pop("hash_contract", None)
            identity_path.write_text(json.dumps(identity), encoding="utf-8")

            errors, _warnings, stats = verifier.verify(site, strict=True)

            self.assertIn("unsupported_site_identity_schema", {item["code"] for item in errors})
            self.assertFalse(stats["site_identity_checked"])


if __name__ == "__main__":
    unittest.main()
