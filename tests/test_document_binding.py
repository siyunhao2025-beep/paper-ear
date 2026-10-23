import json
import subprocess
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

import render_paper_video as renderer
import validate_dialogue as validator
from document_binding import (
    DocumentBindingError,
    INPUT_HASH_CONTRACT,
    RAW_BYTES_HASH_MODE,
    collect_input_identity,
    sha256_file,
    sha256_utf8_lf_file,
    validate_document_binding,
)


def write_pdf(path, pages=1):
    images = [Image.new("RGB", (220, 300), (245 - index, 245, 245)) for index in range(pages)]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:])


def one_turn(page=1):
    return {
        "page": page,
        "speaker": "female",
        "zh_text": "这一句只用于测试当前文献绑定。",
        "en_text": "This line tests current-document binding.",
        "section_tag": "Page 1",
        "red_box": [0.1, 0.1, 0.9, 0.4],
        "box_label": "Evidence",
        "card_title": "Binding",
        "notes": ["Bound to the current PDF."],
        "claim_type": "paper_evidence",
        "source_anchor": {"page": page, "kind": "page", "label": f"Page {page}"},
    }


def branded_script(pdf_path, page_count=1, turn_page=1):
    return {
        "title": "Bound paper",
        "source_document": {
            "filename": pdf_path.name,
            "sha256": sha256_file(pdf_path),
            "page_count": page_count,
        },
        "brand_profile": "bubu-yier-v1",
        "voice_backend": "bubu-yier-local",
        "voice_model": "F5TTS_v1_Base",
        "female_name": "一二（主讲）",
        "male_name": "布布（追问）",
        "female_voice": "yier",
        "male_voice": "bubu",
        "turns": [one_turn(turn_page)],
    }


class DocumentBindingTests(unittest.TestCase):
    def test_branded_binding_matches_current_pdf_hash_and_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            write_pdf(pdf, pages=2)
            script = branded_script(pdf, page_count=2)
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
            identity = collect_input_identity(pdf, script_path, 2)

            result = validate_document_binding(
                script,
                identity,
                script_path,
                require_source_document=True,
            )

        self.assertTrue(result["verified"])
        self.assertEqual(result["issues"], [])

    def test_validator_rejects_script_bound_to_another_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            write_pdf(pdf)
            script = branded_script(pdf)
            script["source_document"]["sha256"] = "0" * 64
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
            identity = collect_input_identity(pdf, script_path, 1)
            errors, warnings = [], []

            with mock.patch.object(validator, "validate_bubu_yier_runtime"):
                validator.validate_script(
                    script_path,
                    page_count=1,
                    strict=True,
                    errors=errors,
                    warnings=warnings,
                    pdf_identity=identity,
                )

        self.assertIn("pdf_sha256_mismatch", {issue["code"] for issue in errors})

    def test_renderer_requires_binding_for_every_branded_script(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            output = directory / "out.mp4"
            write_pdf(pdf)
            script = branded_script(pdf)
            del script["source_document"]
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(DocumentBindingError) as caught:
                renderer.render_video(pdf, script_path, output)

        self.assertIn("requires a source_document object", str(caught.exception))

    def test_renderer_rejects_pdf_sha256_mismatch_before_rendering(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            output = directory / "out.mp4"
            write_pdf(pdf)
            script = branded_script(pdf)
            script["source_document"]["sha256"] = "f" * 64
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(DocumentBindingError) as caught:
                renderer.render_video(pdf, script_path, output)

        self.assertIn("belongs to a different PDF", str(caught.exception))

    def test_renderer_rejects_page_count_mismatch_before_rendering(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            output = directory / "out.mp4"
            write_pdf(pdf, pages=2)
            script = branded_script(pdf, page_count=1)
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(DocumentBindingError) as caught:
                renderer.render_video(pdf, script_path, output)

        self.assertIn("declares 1 PDF pages", str(caught.exception))

    def test_branded_renderer_never_clamps_an_out_of_range_page(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            output = directory / "out.mp4"
            write_pdf(pdf)
            script = branded_script(pdf, turn_page=2)
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(ValueError) as caught:
                renderer.render_video(pdf, script_path, output)

        self.assertIn("Refusing to clamp", str(caught.exception))

    def test_branded_renderer_enforces_complete_dialogue_addressing_without_validator(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            output = directory / "out.mp4"
            write_pdf(pdf)
            script = branded_script(pdf)
            script["turns"] = []
            for index in range(15):
                turn = one_turn()
                turn["speaker"] = "female" if index % 2 == 0 else "male"
                turn["zh_text"] = f"这是第 {index + 1} 轮，没有角色称呼。"
                script["turns"].append(turn)
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

            with mock.patch.object(renderer, "preflight_bubu_yier_brand_references", return_value={}):
                with self.assertRaisesRegex(ValueError, "一二宝"):
                    renderer.render_video(pdf, script_path, output)

    def test_render_report_records_exact_pdf_and_script_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            script_path = directory / "dialogue.json"
            output = directory / "out.mp4"
            report_path = directory / "report.json"
            write_pdf(pdf)
            script = {
                "title": "Legacy-compatible bound paper",
                "source_document": {
                    "filename": pdf.name,
                    "sha256": sha256_file(pdf),
                    "page_count": 1,
                },
                "voice_backend": "edge-tts",
                "female_name": "Presenter",
                "male_name": "Discussant",
                "female_voice": "zh-CN-XiaoxiaoNeural",
                "male_voice": "zh-CN-YunjianNeural",
                "turns": [one_turn()],
            }
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")

            def fake_run(command, **kwargs):
                if command[0] == "pdftoppm":
                    Image.new("RGB", (500, 700), "white").save(f"{command[-1]}-1.png")
                elif command[0] == "ffmpeg":
                    Path(command[-1]).write_bytes(b"video" * 300)
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.object(renderer.subprocess, "run", side_effect=fake_run), mock.patch.object(
                renderer,
                "synthesize_turn_audio",
                return_value=(0.5, "edge-tts", None, {"voice": "test"}),
            ):
                renderer.render_video(
                    pdf,
                    script_path,
                    output,
                    report_json=report_path,
                )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["source_document"], str(pdf.resolve()))
            self.assertEqual(report["pdf_sha256"], sha256_file(pdf))
            self.assertEqual(report["pdf_pages"], 1)
            self.assertEqual(report["dialogue_script"], str(script_path.resolve()))
            self.assertEqual(report["script_sha256"], sha256_file(script_path))
            self.assertEqual(report["script_content_sha256"], sha256_utf8_lf_file(script_path))
            self.assertEqual(report["input_hash_contract"], INPUT_HASH_CONTRACT)
            self.assertEqual(report["video_sha256"], sha256_file(output))
            self.assertEqual(report["video_hash_mode"], RAW_BYTES_HASH_MODE)
            self.assertTrue(report["source_binding"]["verified"])


if __name__ == "__main__":
    unittest.main()
