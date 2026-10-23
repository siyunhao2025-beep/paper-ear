import copy
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

import render_paper_video as renderer
import validate_dialogue as validator
import verify_video
from character_library import CharacterLibrary
from document_binding import (
    INPUT_HASH_CONTRACT,
    RAW_BYTES_HASH_MODE,
    sha256_file,
    sha256_utf8_lf_file,
)


class BubuYierBrandProfileTests(unittest.TestCase):
    def setUp(self):
        self.library = CharacterLibrary.from_file()
        self.fonts = {
            "header": renderer.load_font(renderer.FONT_BOLD_CANDIDATES, 24),
            "speaker": renderer.load_font(renderer.FONT_BOLD_CANDIDATES, 21),
            "card_title": renderer.load_font(renderer.FONT_BOLD_CANDIDATES, 21),
            "badge": renderer.load_font(renderer.FONT_BOLD_CANDIDATES, 18),
            "notes": renderer.load_font(renderer.FONT_REGULAR_CANDIDATES, 20),
            "meta": renderer.load_font(renderer.FONT_REGULAR_CANDIDATES, 18),
            "sub_zh": renderer.load_font(renderer.FONT_BOLD_CANDIDATES, 27),
            "sub_en": renderer.load_font(renderer.FONT_REGULAR_CANDIDATES, 21),
        }

    def test_mandatory_intro_contract_is_exact_and_three_turns(self):
        turns = renderer.bubu_yier_intro_turns()
        self.assertEqual([turn["speaker"] for turn in turns], ["female", "male", "female"])
        self.assertEqual(turns[0]["character_pose"], "yier_catchphrase_dash")
        self.assertIn("啊哒哒～啊哒哒哒哒～", turns[0]["spoken_text"])
        self.assertIn("小司在加油", turns[1]["spoken_text"])
        self.assertIn("相遇在科研视频中", turns[1]["spoken_text"])
        self.assertEqual(turns[0]["delivery"]["pause_after_ms"], 250)
        self.assertEqual(turns[1]["delivery"]["pause_after_ms"], 350)
        self.assertEqual(turns[2]["spoken_text"], "好啦，开始讲论文吧！")

    def test_intro_frame_contains_renderable_character_assets(self):
        turn = renderer.bubu_yier_intro_turns()[0]
        pose = self.library.select_pose("female", turn)
        listener = self.library.select_pose("male", {})
        frame = renderer.render_bubu_yier_intro_frame(turn, 0, 3, pose, listener, self.fonts)
        self.assertEqual(frame.size, (1920, 1080))
        self.assertEqual(frame.mode, "RGB")
        self.assertGreater(len(frame.getcolors(maxcolors=2_000_000)), 1_000)

    def test_paper_frame_renders_active_and_listener_state(self):
        turn = {
            "speaker": "male",
            "page": 1,
            "zh_text": "样本量够吗？",
            "en_text": "Is the sample size sufficient?",
            "section_tag": "Methods",
            "box_label": "Sample size",
            "card_title": "实验设计检查",
            "notes": ["先检查实验单位，再检查统计功效。"],
            "dialogue_act": "challenge",
            "emotion": "curious",
            "interaction_tags": ["question"],
            "character_pose": "bubu_sample_check",
        }
        pose = self.library.select_pose("male", turn)
        listener = self.library.select_pose("female", {})
        page = Image.new("RGB", (1200, 1600), "white")
        frame = renderer.render_frame(
            page,
            turn,
            0,
            1,
            "A Test Paper",
            "布布（追问）",
            "一二（主讲）",
            [0.1, 0.1, 0.8, 0.3],
            self.fonts,
            pose_info=pose,
            listener_pose_info=listener,
        )
        self.assertEqual(frame.size, (1920, 1080))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "frame.png"
            frame.save(output)
            self.assertGreater(output.stat().st_size, 50_000)

    def test_validator_rejects_cross_character_pose_in_branded_script(self):
        script = {
            "title": "Test",
            "brand_profile": "bubu-yier-v1",
            "voice_backend": "bubu-yier-local",
            "voice_model": "F5TTS_v1_Base",
            "female_name": "一二（主讲）",
            "male_name": "布布（追问）",
            "female_voice": "yier",
            "male_voice": "bubu",
            "turns": [
                {
                    "page": 1,
                    "speaker": "female",
                    "character_pose": "bubu_gentle_question",
                    "zh_text": "测试。",
                    "en_text": "Test.",
                    "section_tag": "Test",
                    "red_box": [0.1, 0.1, 0.9, 0.4],
                    "box_label": "Test",
                    "card_title": "Test",
                    "notes": ["Test"],
                    "claim_type": "paper_evidence",
                    "source_anchor": {"page": 1, "kind": "page", "label": "Page 1"},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "script.json"
            path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
            errors, warnings = [], []
            with mock.patch.object(validator, "validate_bubu_yier_runtime"):
                validator.validate_script(path, 1, False, errors, warnings)
        self.assertIn("invalid_character_pose", {issue["code"] for issue in errors})

    def test_renderer_rejects_branded_voice_or_model_drift_without_validator(self):
        base = {
            "brand_profile": "bubu-yier-v1",
            "voice_backend": "bubu-yier-local",
            "voice_model": "F5TTS_v1_Base",
            "female_voice": "yier",
            "male_voice": "bubu",
        }
        tampered = [
            ({"female_voice": "bubu"}, "female_voice='yier'"),
            ({"male_voice": "yier"}, "male_voice='bubu'"),
            ({"voice_model": "OtherModel"}, "voice_model='F5TTS_v1_Base'"),
            ({"voice_profiles": {"female": {"voice": "bubu"}}}, "voice_profiles.female.voice='yier'"),
            ({"voice_profiles": {"male": {"model": "OtherModel"}}}, "voice_profiles.male.model='F5TTS_v1_Base'"),
        ]
        for update, message in tampered:
            with self.subTest(update=update):
                config = {**base, **update}
                with self.assertRaisesRegex(ValueError, message):
                    renderer.resolve_voice_profile(config, "female" if "female" in str(update) else "male")

        female = renderer.resolve_voice_profile(base, "female")
        male = renderer.resolve_voice_profile(base, "male")
        self.assertEqual((female["voice"], female["model"]), ("yier", "F5TTS_v1_Base"))
        self.assertEqual((male["voice"], male["model"]), ("bubu", "F5TTS_v1_Base"))

    def test_renderer_rejects_branded_display_name_swaps_or_human_aliases(self):
        valid = {"female_name": "一二（主讲）", "male_name": "布布（追问）"}
        self.assertEqual(renderer.resolve_bubu_yier_display_name(valid, "female"), "一二（主讲）")
        self.assertEqual(renderer.resolve_bubu_yier_display_name(valid, "male"), "布布（追问）")
        for field, value, speaker in (
            ("female_name", "布布（主讲）", "female"),
            ("female_name", "主讲人 Lin", "female"),
            ("male_name", "一二（追问）", "male"),
            ("male_name", "师兄 Alex", "male"),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    renderer.resolve_bubu_yier_display_name({field: value}, speaker)

    def test_renderer_preflight_requires_verified_reference_hashes(self):
        profiles = {
            "female": {"voice": "yier", "model": "F5TTS_v1_Base"},
            "male": {"voice": "bubu", "model": "F5TTS_v1_Base"},
        }

        def valid_reference(profile):
            spec = renderer.BUBU_YIER_REFERENCE_SPECS[profile["voice"]]
            return {
                "voice": profile["voice"],
                "sha256": spec["sha256"],
                "reference_text": spec["reference_text"],
                "verified": True,
            }

        with mock.patch.object(renderer, "resolve_f5_options", return_value={"model": "F5TTS_v1_Base"}), mock.patch.object(
            renderer, "resolve_reference", side_effect=valid_reference
        ):
            resolved = renderer.preflight_bubu_yier_brand_references(profiles)
        self.assertEqual(resolved["female"]["voice"], "yier")
        self.assertEqual(resolved["male"]["voice"], "bubu")

        with mock.patch.object(renderer, "resolve_f5_options", return_value={"model": "F5TTS_v1_Base"}), mock.patch.object(
            renderer,
            "resolve_reference",
            return_value={"voice": "yier", "sha256": "a" * 64, "verified": False},
        ):
            with self.assertRaisesRegex(ValueError, "matching 64-character SHA-256"):
                renderer.preflight_bubu_yier_brand_references(profiles)

    def test_brand_profile_rejects_custom_reference_hash_and_transcript(self):
        base = {
            "brand_profile": "bubu-yier-v1",
            "voice_backend": "bubu-yier-local",
            "voice_model": "F5TTS_v1_Base",
        }
        with self.assertRaisesRegex(ValueError, "pinned yier reference_sha256"):
            renderer.resolve_voice_profile(
                {**base, "voice_profiles": {"female": {"reference_sha256": "a" * 64}}},
                "female",
            )
        with self.assertRaisesRegex(ValueError, "pinned bubu reference_text"):
            renderer.resolve_voice_profile(
                {**base, "voice_profiles": {"male": {"reference_text": "unrelated transcript"}}},
                "male",
            )

    def test_validator_rejects_non_pinned_brand_reference(self):
        errors = []
        with mock.patch.object(
            validator,
            "resolve_reference",
            return_value={
                "voice": "yier",
                "sha256": "b" * 64,
                "reference_text": "unrelated transcript",
                "verified": True,
            },
        ):
            validator.validate_bubu_yier_runtime(
                {"voice": "yier", "model": "F5TTS_v1_Base"},
                errors,
                "female",
                require_pinned=True,
            )
        codes = {issue["code"] for issue in errors}
        self.assertIn("brand_reference_hash", codes)
        self.assertIn("brand_reference_text", codes)

    def test_renderer_enforces_role_correct_natural_addressing(self):
        turns = [
            {"speaker": "female", "spoken_text": "布布，我们先看实验设计。"},
            {"speaker": "male", "spoken_text": "一二宝，这里的样本量够吗？"},
        ]
        counts = renderer.enforce_bubu_yier_addressing_contract(turns)
        self.assertEqual(counts, {"male_to_female": 1, "female_to_male": 1})

        invalid_turns = [
            [{"speaker": "female", "spoken_text": "一二宝，我们看结果。"}],
            [{"speaker": "male", "spoken_text": "臭布布，这个结论成立吗？"}],
            [
                {"speaker": "male", "spoken_text": "一二宝，先看这里。"},
                {"speaker": "male", "spoken_text": "一二宝，再看这里。"},
            ],
        ]
        for candidate in invalid_turns:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    renderer.enforce_bubu_yier_addressing_contract(candidate)

    def test_complete_branded_dialogue_requires_both_address_directions(self):
        turns = [
            {
                "speaker": "female" if index % 2 == 0 else "male",
                "spoken_text": f"这是第 {index + 1} 轮。",
            }
            for index in range(15)
        ]
        with self.assertRaisesRegex(ValueError, "一二宝"):
            renderer.enforce_bubu_yier_addressing_contract(turns, require_bidirectional=True)

        turns[0]["spoken_text"] = "布布，我们先看方法。"
        turns[1]["spoken_text"] = "一二宝，我想追问样本量。"
        counts = renderer.enforce_bubu_yier_addressing_contract(turns, require_bidirectional=True)
        self.assertEqual(counts, {"male_to_female": 1, "female_to_male": 1})

    def test_validator_reports_addressing_contract_codes(self):
        errors = []
        validator.validate_bubu_yier_addressing(
            [
                {"speaker": "female", "spoken_text": "一二宝，看这里。"},
                {"speaker": "male", "spoken_text": "臭布布，我有问题。"},
            ],
            errors,
            require_bidirectional=True,
        )
        codes = {issue["code"] for issue in errors}
        self.assertIn("brand_address_female_self_name", codes)
        self.assertIn("brand_address_male_self_name", codes)
        self.assertIn("brand_address_missing_male_to_female", codes)
        self.assertIn("brand_address_missing_female_to_male", codes)

    @staticmethod
    def complete_branded_report(video):
        video.write_bytes(b"paper-ear branded video fixture")
        source_document = video.parent / "paper.pdf"
        dialogue_script = video.parent / "dialogue.json"
        source_document.write_bytes(b"paper fixture")
        dialogue_script.write_bytes(b'{\n  "title": "fixture"\n}\n')

        def audio_record(kind, speaker):
            voice = "yier" if speaker == "female" else "bubu"
            return {
                "kind": kind,
                "speaker": speaker,
                "mode": "bubu-yier-local",
                "voice": voice,
                "reference_voice": voice,
                "reference_verified": True,
                "reference_sha256": renderer.BUBU_YIER_REFERENCE_SPECS[voice]["sha256"],
                "model": "F5TTS_v1_Base",
                "input_scope": "spoken_text-only",
                "endpoint_scope": "on-device",
            }

        return {
            "output": str(video),
            "source_document": str(source_document),
            "dialogue_script": str(dialogue_script),
            "pdf_sha256": sha256_file(source_document),
            "script_sha256": sha256_file(dialogue_script),
            "script_content_sha256": sha256_utf8_lf_file(dialogue_script),
            "input_hash_contract": dict(INPUT_HASH_CONTRACT),
            "video_sha256": sha256_file(video),
            "video_hash_mode": RAW_BYTES_HASH_MODE,
            "source_binding": {"declared": True, "required": True, "verified": True},
            "brand_profile": "bubu-yier-v1",
            "voice_backend": "bubu-yier-local",
            "audio_mastering": dict(verify_video.EXPECTED_AUDIO_MASTERING),
            "rendered_turns": 1,
            "mandatory_intro_turns": 3,
            "rendered_segments": 4,
            "turn_audio": [
                audio_record("intro", "female"),
                audio_record("intro", "male"),
                audio_record("intro", "female"),
                audio_record("paper", "male"),
            ],
            "character_poses": [
                {"speaker": "female", "pose": "yier_catchphrase_dash"},
                {"speaker": "male", "pose": "bubu_warm_greeting"},
                {"speaker": "female", "pose": "yier_neutral_intro"},
                {"speaker": "male", "pose": "bubu_gentle_question"},
            ],
        }

    def test_media_gate_accepts_complete_branded_render_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "placeholder.mp4"
            report = self.complete_branded_report(video)
            report_path = directory / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            errors, warnings = [], []
            loaded = verify_video.verify_render_report(report_path, video, errors, warnings)
        self.assertEqual(loaded["mandatory_intro_turns"], 3)
        self.assertEqual(errors, [])

    def test_media_gate_rejects_any_branded_audio_provenance_drift(self):
        mutations = [
            ("speaker", "female", "brand_reference_cast"),
            ("reference_voice", "yier", "brand_reference_cast"),
            ("voice", "yier", "brand_resolved_voice"),
            ("reference_verified", False, "brand_reference_unverified"),
            ("reference_sha256", "not-a-hash", "brand_reference_hash"),
            ("model", "OtherModel", "brand_voice_model"),
            ("input_scope", "full-document", "brand_input_scope"),
            ("endpoint_scope", "remote", "brand_endpoint_scope"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "placeholder.mp4"
            for field, value, expected_code in mutations:
                with self.subTest(field=field):
                    report = copy.deepcopy(self.complete_branded_report(video))
                    report["turn_audio"][3][field] = value
                    report_path = directory / f"report-{field}.json"
                    report_path.write_text(json.dumps(report), encoding="utf-8")
                    errors, warnings = [], []
                    verify_video.verify_render_report(report_path, video, errors, warnings)
                    self.assertIn(expected_code, {issue["code"] for issue in errors})

    def test_media_gate_rejects_different_but_valid_reference_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "placeholder.mp4"
            report = self.complete_branded_report(video)
            report["turn_audio"][3]["reference_sha256"] = "b" * 64
            report_path = directory / "report-custom-reference.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            errors, warnings = [], []
            verify_video.verify_render_report(report_path, video, errors, warnings)
        self.assertIn("brand_reference_hash", {issue["code"] for issue in errors})

    def test_media_gate_rejects_missing_or_changed_audio_mastering(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "placeholder.mp4"
            for mastering in (None, {**verify_video.EXPECTED_AUDIO_MASTERING, "final_gain_db": 0.0}):
                with self.subTest(mastering=mastering):
                    report = self.complete_branded_report(video)
                    report["audio_mastering"] = mastering
                    report_path = directory / "report-mastering.json"
                    report_path.write_text(json.dumps(report), encoding="utf-8")
                    errors, warnings = [], []
                    verify_video.verify_render_report(report_path, video, errors, warnings)
                    self.assertIn("brand_audio_mastering", {issue["code"] for issue in errors})

    def test_media_gate_rejects_report_for_a_different_output_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old_video = directory / "old.mp4"
            replacement_video = directory / "replacement.mp4"
            report = self.complete_branded_report(old_video)
            replacement_video.write_bytes(old_video.read_bytes())
            report_path = directory / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")

            errors, warnings = [], []
            verify_video.verify_render_report(report_path, replacement_video, errors, warnings)

        self.assertIn("render_report_output", {issue["code"] for issue in errors})
        self.assertNotIn("render_report_output", {issue["code"] for issue in warnings})

    def test_media_gate_rejects_video_replaced_after_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "paper.mp4"
            report = self.complete_branded_report(video)
            report_path = directory / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            video.write_bytes(b"different bytes substituted after rendering")

            errors, warnings = [], []
            verify_video.verify_render_report(report_path, video, errors, warnings)

        self.assertIn("brand_video_sha256_mismatch", {issue["code"] for issue in errors})

    def test_media_gate_allows_crlf_checkout_but_rejects_real_script_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "paper.mp4"
            report = self.complete_branded_report(video)
            report_path = directory / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            script_path = Path(report["dialogue_script"])

            script_path.write_bytes(script_path.read_bytes().replace(b"\n", b"\r\n"))
            errors, warnings = [], []
            verify_video.verify_render_report(report_path, video, errors, warnings)
            self.assertEqual(errors, [])

            script_path.write_bytes(script_path.read_bytes().replace(b"fixture", b"tampered"))
            errors, warnings = [], []
            verify_video.verify_render_report(report_path, video, errors, warnings)

        self.assertIn("brand_script_content_sha256_mismatch", {issue["code"] for issue in errors})

    def test_media_gate_rejects_source_pdf_replaced_after_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "paper.mp4"
            report = self.complete_branded_report(video)
            report_path = directory / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            Path(report["source_document"]).write_bytes(b"different PDF bytes")

            errors, warnings = [], []
            verify_video.verify_render_report(report_path, video, errors, warnings)

        self.assertIn("brand_pdf_sha256_mismatch", {issue["code"] for issue in errors})

    def test_media_gate_requires_complete_branded_source_binding(self):
        mutations = [
            ("source_binding", {"verified": False}, "brand_source_binding"),
            ("pdf_sha256", "not-a-hash", "brand_pdf_sha256"),
            ("script_sha256", None, "brand_script_sha256"),
            ("script_content_sha256", None, "brand_script_content_sha256"),
            ("input_hash_contract", None, "brand_input_hash_contract"),
            ("video_hash_mode", None, "brand_video_hash_mode"),
            ("source_document", "missing.pdf", "brand_source_document"),
            ("dialogue_script", "missing.json", "brand_dialogue_script"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            video = directory / "paper.mp4"
            for field, value, expected_code in mutations:
                with self.subTest(field=field):
                    report = self.complete_branded_report(video)
                    report[field] = value
                    report_path = directory / f"report-{field}.json"
                    report_path.write_text(json.dumps(report), encoding="utf-8")
                    errors, warnings = [], []
                    verify_video.verify_render_report(report_path, video, errors, warnings)
                    self.assertIn(expected_code, {issue["code"] for issue in errors})


if __name__ == "__main__":
    unittest.main()
