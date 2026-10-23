import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bubu_yier_voice as backend
import render_paper_video as renderer
import setup_bubu_yier_voice as setup_voice
import validate_dialogue as validator


def write_pcm_wav(path: Path, seconds: float = 0.08, sample_rate: int = 24000) -> None:
    frame_count = max(1, int(seconds * sample_rate))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * frame_count)


class BubuYierBackendTests(unittest.TestCase):
    def test_setup_rejects_python_older_than_310(self):
        with self.assertRaisesRegex(RuntimeError, "Python 3.10 or newer"):
            setup_voice.require_supported_python((3, 9, 18))

    def test_setup_accepts_python_310_or_newer(self):
        setup_voice.require_supported_python((3, 10, 0))
        setup_voice.require_supported_python((3, 13, 1))

    def test_default_cast_is_female_yier_and_male_bubu(self):
        config = {
            "brand_profile": "bubu-yier-v1",
            "voice_backend": "bubu-yier-local",
            "voice_model": "F5TTS_v1_Base",
        }
        female = renderer.resolve_voice_profile(config, "female")
        male = renderer.resolve_voice_profile(config, "male")
        self.assertEqual(female["voice"], "yier")
        self.assertEqual(male["voice"], "bubu")
        self.assertEqual(female["model"], "F5TTS_v1_Base")
        self.assertEqual(male["model"], "F5TTS_v1_Base")

    def test_synthesize_turn_sends_only_final_spoken_text(self):
        turn = {
            "speaker": "female",
            "spoken_text": "啊哒哒～现在开始。",
            "zh_text": "这段字幕不应送给后端。",
            "en_text": "Nor should this subtitle be sent.",
            "evidence_anchor": {"page": 1, "kind": "page", "label": "private evidence"},
        }
        profile = renderer.resolve_voice_profile(
            {"voice_backend": "bubu-yier-local", "voice_model": "F5TTS_v1_Base"},
            "female",
        )
        seen = {}

        def fake_synthesis(text, voice_profile, delivery, out_wav):
            seen.update(
                {
                    "text": text,
                    "voice": voice_profile["voice"],
                    "delivery": delivery,
                }
            )
            write_pcm_wav(Path(out_wav))
            return {
                "endpoint_scope": "on-device",
                "input_scope": "spoken_text-only",
                "reference_voice": voice_profile["voice"],
            }

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            renderer, "synthesize_bubu_yier", side_effect=fake_synthesis
        ):
            output = Path(temporary) / "opening.wav"
            duration, mode, error, metadata = renderer.synthesize_turn_audio(
                turn,
                "bubu-yier-local",
                profile,
                str(output),
            )
        self.assertGreater(duration, 0)
        self.assertEqual(mode, "bubu-yier-local")
        self.assertIsNone(error)
        self.assertEqual(seen["text"], turn["spoken_text"])
        self.assertEqual(seen["voice"], "yier")
        self.assertNotIn(turn["zh_text"], seen["text"])
        self.assertEqual(metadata["input_scope"], "spoken_text-only")

    def test_f5_adapter_uses_configured_reference_and_exact_text(self):
        calls = []

        class FakeEngine:
            def infer(self, ref_file, ref_text, gen_text, speed=1.0, seed=None):
                calls.append(
                    {
                        "ref_file": ref_file,
                        "ref_text": ref_text,
                        "gen_text": gen_text,
                        "speed": speed,
                        "seed": seed,
                    }
                )
                return np.zeros(2400, dtype=np.float32), 24000, None

        with tempfile.TemporaryDirectory() as temporary:
            temp_dir = Path(temporary)
            reference = temp_dir / "reference.wav"
            output = temp_dir / "result.wav"
            write_pcm_wav(reference)
            digest = hashlib.sha256(reference.read_bytes()).hexdigest()
            profile = {
                "voice": "bubu",
                "model": "F5TTS_v1_Base",
                "reference_audio": str(reference),
                "reference_text": "这是经过核对的参考文本。",
                "reference_sha256": digest,
                "trim_silence": False,
                "seed": 17,
            }
            delivery = {
                "rate": "-5%",
                "pause_before_ms": 0,
                "pause_after_ms": 0,
            }
            with mock.patch.object(
                backend,
                "_load_f5_runtime",
                return_value=(FakeEngine(), {"model": "F5TTS_v1_Base"}),
            ):
                metadata = backend.synthesize_bubu_yier(
                    "感谢「小司在加油」做了这个 Skill——让我们，相遇在科研视频中。",
                    profile,
                    delivery,
                    str(output),
                )
            self.assertTrue(output.is_file())
            self.assertEqual(len(calls), 1)
            self.assertEqual(
                calls[0]["gen_text"],
                "感谢「小司在加油」做了这个 Skill——让我们，相遇在科研视频中。",
            )
            self.assertEqual(calls[0]["ref_text"], profile["reference_text"])
            self.assertEqual(calls[0]["speed"], 0.95)
            self.assertEqual(calls[0]["seed"], 17)
            self.assertEqual(metadata["reference_voice"], "bubu")
            self.assertTrue(metadata["reference_verified"])
            self.assertEqual(metadata["input_scope"], "spoken_text-only")

    def test_setup_inspector_checks_sha_and_wav(self):
        with tempfile.TemporaryDirectory() as temporary:
            reference = Path(temporary) / "fixture.wav"
            write_pcm_wav(reference, seconds=0.6)
            spec = {
                "sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
                "size": reference.stat().st_size,
            }
            report = setup_voice.inspect_reference(reference, spec)
            self.assertTrue(report["ok"])
            self.assertTrue(report["checksum_ok"])
            self.assertTrue(report["wav_ok"])

    def test_explicit_reference_requires_and_matches_sha256(self):
        with tempfile.TemporaryDirectory() as temporary:
            reference = Path(temporary) / "custom.wav"
            write_pcm_wav(reference, seconds=0.6)
            profile = {
                "voice": "yier",
                "reference_audio": str(reference),
                "reference_text": "这是自定义参考音频。",
            }
            with self.assertRaisesRegex(RuntimeError, "requires reference_sha256"):
                backend.resolve_reference(profile)
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                backend.resolve_reference({**profile, "reference_sha256": "0" * 64})
            digest = hashlib.sha256(reference.read_bytes()).hexdigest()
            resolved = backend.resolve_reference({**profile, "reference_sha256": digest})
            self.assertTrue(resolved["verified"])
            self.assertEqual(resolved["sha256"], digest)

    def test_audition_dry_run_parses_two_role_config_without_loading_model(self):
        config = {
            "brand_profile": "bubu-yier-v1",
            "voice_backend": "bubu-yier-local",
            "voice_model": "F5TTS_v1_Base",
            "female_voice": "yier",
            "male_voice": "bubu",
            "auditions": [
                {"id": "yier-line", "speaker": "female", "text": "先看这张图。"},
                {"id": "bubu-line", "speaker": "male", "text": "这个差异，还能成立吗？"},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            temp_dir = Path(temporary)
            config_path = temp_dir / "voice.json"
            output_dir = temp_dir / "audition"
            config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "render_voice_auditions.py"),
                    "--config",
                    str(config_path),
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["voice"] for item in manifest["clips"]], ["yier", "bubu"])
            for item in manifest["clips"]:
                plan = json.loads((output_dir / item["plan_file"]).read_text(encoding="utf-8"))
                self.assertEqual(plan["input_scope"], "spoken_text-only")

    def test_dialogue_validator_applies_default_cast_for_backend(self):
        script = {
            "title": "Fixture",
            "voice_backend": "bubu-yier-local",
            "voice_model": "F5TTS_v1_Base",
            "turns": [
                {
                    "page": 1,
                    "speaker": "female",
                    "zh_text": "先看这张图。",
                    "en_text": "Look at this figure first.",
                    "section_tag": "Page 1",
                    "box_label": "Figure",
                    "card_title": "Evidence",
                    "notes": ["Fixture"],
                    "claim_type": "paper_evidence",
                    "evidence_anchor": {"page": 1, "kind": "page", "label": "Page 1"},
                    "red_box": [0.1, 0.1, 0.9, 0.9],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            script_path = Path(temporary) / "dialogue.json"
            script_path.write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
            errors = []
            warnings = []
            with mock.patch.object(validator, "validate_bubu_yier_runtime") as runtime_check:
                _, turn_count, _ = validator.validate_script(
                    script_path,
                    page_count=1,
                    strict=False,
                    errors=errors,
                    warnings=warnings,
                )
        self.assertEqual(turn_count, 1)
        self.assertFalse(any(issue["code"] == "invalid_voice_backend" for issue in errors))
        checked = {
            call.args[2]: call.args[0]["voice"]
            for call in runtime_check.call_args_list
        }
        self.assertEqual(checked, {"male": "bubu", "female": "yier"})


if __name__ == "__main__":
    unittest.main()
