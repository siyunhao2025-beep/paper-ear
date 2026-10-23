#!/usr/bin/env python3
"""Verify the basic media contract of a rendered Paper Ear MP4."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from bubu_yier_voice import (
    BUBU_YIER_BACKEND,
    BUBU_YIER_DEFAULT_VOICES,
    BUBU_YIER_MODEL,
    BUBU_YIER_REFERENCE_SPECS,
)
from document_binding import (
    INPUT_HASH_CONTRACT,
    RAW_BYTES_HASH_MODE,
    sha256_file,
    sha256_utf8_lf_file,
)

EXPECTED_AUDIO_MASTERING = {
    "final_gain_db": -1.5,
    "limiter_ceiling_linear": 0.89,
    "audio_codec": "aac",
    "audio_bitrate": "128k",
    "final_audio_reencode": True,
}


def add_issue(items, code, message):
    items.append({"code": code, "message": message})


def parse_duration(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def probe(video_path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(completed.stdout)


def verify_render_report(report_path, video_path, errors, warnings):
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        add_issue(errors, "missing_render_report", f"Render report does not exist: {report_path}")
        return {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        add_issue(errors, "invalid_render_report", f"Could not read render report: {exc}")
        return {}

    branded = report.get("brand_profile") == "bubu-yier-v1"
    verified_video_path = Path(video_path).expanduser().resolve()
    reported_output = report.get("output")
    if not isinstance(reported_output, str) or not reported_output.strip():
        if branded:
            add_issue(errors, "brand_render_report_output", "Branded render report must declare its output video path.")
    elif Path(reported_output).expanduser().resolve() != verified_video_path:
        target = errors if branded else warnings
        add_issue(target, "render_report_output", "Render report output path differs from the verified video path.")

    if branded:
        source_binding = report.get("source_binding")
        if not isinstance(source_binding, dict) or source_binding.get("verified") is not True:
            add_issue(
                errors,
                "brand_source_binding",
                "bubu-yier-v1 requires source_binding.verified=true in the render report.",
            )

        if report.get("input_hash_contract") != INPUT_HASH_CONTRACT:
            add_issue(
                errors,
                "brand_input_hash_contract",
                "bubu-yier-v1 requires the supported SHA-256 input hash contract; regenerate legacy reports.",
            )
        if report.get("video_hash_mode") != RAW_BYTES_HASH_MODE:
            add_issue(
                errors,
                "brand_video_hash_mode",
                f"bubu-yier-v1 requires video_hash_mode={RAW_BYTES_HASH_MODE}.",
            )

        valid_hashes = {}
        for field in ("pdf_sha256", "script_sha256", "script_content_sha256", "video_sha256"):
            value = report.get(field)
            valid = isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", value.strip()))
            valid_hashes[field] = valid
            if not valid:
                add_issue(
                    errors,
                    f"brand_{field}",
                    f"bubu-yier-v1 render report requires a valid 64-character {field}.",
                )

        input_paths = {}
        for field in ("source_document", "dialogue_script"):
            value = report.get(field)
            candidate = Path(value).expanduser() if isinstance(value, str) and value.strip() else None
            if candidate is None or not candidate.is_file():
                add_issue(
                    errors,
                    f"brand_{field}",
                    f"bubu-yier-v1 render report requires an existing {field} file.",
                )
            else:
                input_paths[field] = candidate

        source_document = input_paths.get("source_document")
        if source_document is not None and valid_hashes["pdf_sha256"]:
            if sha256_file(source_document).lower() != report["pdf_sha256"].strip().lower():
                add_issue(
                    errors,
                    "brand_pdf_sha256_mismatch",
                    "The current source PDF bytes do not match render report pdf_sha256.",
                )

        dialogue_script = input_paths.get("dialogue_script")
        if dialogue_script is not None and valid_hashes["script_content_sha256"]:
            try:
                actual_script_content_sha256 = sha256_utf8_lf_file(dialogue_script)
            except UnicodeDecodeError:
                add_issue(
                    errors,
                    "brand_script_not_utf8",
                    "The current dialogue script is not valid UTF-8 and cannot be content-verified.",
                )
            else:
                if actual_script_content_sha256.lower() != report["script_content_sha256"].strip().lower():
                    add_issue(
                        errors,
                        "brand_script_content_sha256_mismatch",
                        "The current dialogue content does not match the render report; LF/CRLF-only changes are allowed.",
                    )

        if not verified_video_path.is_file():
            add_issue(
                errors,
                "brand_video_hash_unverifiable",
                f"Cannot verify video_sha256 because the video does not exist: {verified_video_path}",
            )
        elif valid_hashes["video_sha256"]:
            actual_video_sha256 = sha256_file(verified_video_path)
            if actual_video_sha256.lower() != report["video_sha256"].strip().lower():
                add_issue(
                    errors,
                    "brand_video_sha256_mismatch",
                    "The verified video bytes do not match render report video_sha256; the video may be stale or replaced.",
                )

        paper_turns = report.get("rendered_turns")
        intro_turns = report.get("mandatory_intro_turns")
        segments = report.get("rendered_segments")
        if intro_turns != 3:
            add_issue(errors, "brand_intro_count", f"bubu-yier-v1 requires 3 intro turns, found {intro_turns}.")
        if not isinstance(paper_turns, int) or segments != paper_turns + 3:
            add_issue(errors, "brand_segment_count", "Rendered segments must equal paper turns plus the 3-turn opening.")
        if report.get("voice_backend") != BUBU_YIER_BACKEND:
            add_issue(errors, "brand_voice_backend", f"bubu-yier-v1 must report {BUBU_YIER_BACKEND}.")
        if report.get("audio_mastering") != EXPECTED_AUDIO_MASTERING:
            add_issue(
                errors,
                "brand_audio_mastering",
                "bubu-yier-v1 requires the standard -1.5 dB gain, 0.89 limiter, and 128k AAC final mastering pass.",
            )

        audio = report.get("turn_audio")
        if not isinstance(audio, list) or len(audio) != segments:
            add_issue(errors, "brand_audio_records", "Audio report must contain one record per rendered segment.")
        else:
            invalid_records = [index for index, item in enumerate(audio, start=1) if not isinstance(item, dict)]
            if invalid_records:
                add_issue(
                    errors,
                    "brand_audio_record_type",
                    f"Audio records must be objects; invalid records: {invalid_records}.",
                )
                audio = [item if isinstance(item, dict) else {} for item in audio]
            if isinstance(paper_turns, int):
                expected_kinds = ["intro"] * 3 + ["paper"] * paper_turns
                if [item.get("kind") for item in audio] != expected_kinds:
                    add_issue(errors, "brand_intro_order", "Audio records must contain exactly 3 intro segments followed by all paper turns.")
            if [item.get("speaker") for item in audio[:3]] != ["female", "male", "female"]:
                add_issue(errors, "brand_intro_cast_order", "The fixed intro cast order must be female, male, female.")
            wrong_modes = [item for item in audio if item.get("mode") != BUBU_YIER_BACKEND]
            if wrong_modes:
                add_issue(errors, "brand_audio_fallback", f"One or more branded turns did not use {BUBU_YIER_BACKEND}.")
            for index, item in enumerate(audio, start=1):
                kind = item.get("kind")
                speaker = item.get("speaker")
                if kind not in {"intro", "paper"}:
                    add_issue(errors, "brand_audio_kind", f"Audio record {index} has invalid kind '{kind}'.")
                if speaker not in BUBU_YIER_DEFAULT_VOICES:
                    add_issue(errors, "brand_audio_speaker", f"Audio record {index} has invalid speaker '{speaker}'.")
                    continue
                expected_voice = BUBU_YIER_DEFAULT_VOICES[speaker]
                if item.get("reference_voice") != expected_voice:
                    add_issue(
                        errors,
                        "brand_reference_cast",
                        f"Audio record {index} speaker '{speaker}' must use reference_voice "
                        f"'{expected_voice}', not '{item.get('reference_voice')}'.",
                    )
                if item.get("voice") != expected_voice:
                    add_issue(
                        errors,
                        "brand_resolved_voice",
                        f"Audio record {index} speaker '{speaker}' must resolve voice '{expected_voice}'.",
                    )
                if item.get("reference_verified") is not True:
                    add_issue(
                        errors,
                        "brand_reference_unverified",
                        f"Audio record {index} must report reference_verified=true.",
                    )
                reference_hash = str(item.get("reference_sha256") or "").lower()
                expected_reference_hash = BUBU_YIER_REFERENCE_SPECS[expected_voice]["sha256"]
                if reference_hash != expected_reference_hash:
                    add_issue(
                        errors,
                        "brand_reference_hash",
                        f"Audio record {index} must report the pinned {expected_voice} "
                        f"reference_sha256 '{expected_reference_hash}'.",
                    )
                if item.get("model") != BUBU_YIER_MODEL:
                    add_issue(
                        errors,
                        "brand_voice_model",
                        f"Audio record {index} must report model '{BUBU_YIER_MODEL}'.",
                    )
                if item.get("input_scope") != "spoken_text-only":
                    add_issue(
                        errors,
                        "brand_input_scope",
                        f"Audio record {index} must report input_scope='spoken_text-only'.",
                    )
                if item.get("endpoint_scope") != "on-device":
                    add_issue(
                        errors,
                        "brand_endpoint_scope",
                        f"Audio record {index} must report endpoint_scope='on-device'.",
                    )

        poses = report.get("character_poses")
        if not isinstance(poses, list) or len(poses) != segments:
            add_issue(errors, "brand_pose_records", "Character pose report must contain one record per segment.")
        else:
            for item in poses:
                pose = str(item.get("pose") or "")
                speaker = item.get("speaker")
                expected_prefix = "bubu_" if speaker == "male" else "yier_" if speaker == "female" else ""
                if not expected_prefix or not pose.startswith(expected_prefix):
                    add_issue(errors, "brand_pose_cast", f"Pose '{pose}' does not match speaker '{speaker}'.")
                    break
                if item.get("used_fallback"):
                    add_issue(warnings, "brand_pose_fallback", f"Pose '{pose}' used an asset fallback.")
    return report


def main():
    parser = argparse.ArgumentParser(description="Verify a Paper Ear MP4 with ffprobe.")
    parser.add_argument("--video", required=True, help="Rendered MP4 path")
    parser.add_argument("--expect-width", type=int, default=1920, help="Expected video width")
    parser.add_argument("--expect-height", type=int, default=1080, help="Expected video height")
    parser.add_argument("--min-duration", type=float, default=1.0, help="Minimum acceptable duration in seconds")
    parser.add_argument("--max-av-drift", type=float, default=0.75, help="Maximum audio/video duration drift in seconds")
    parser.add_argument("--render-report", help="Optional renderer JSON report for branded/cast contract checks")
    parser.add_argument("--json-out", help="Optional JSON report path")
    args = parser.parse_args()

    errors = []
    warnings = []
    video_path = Path(args.video).expanduser().resolve()
    render_report_path = Path(args.render_report).expanduser().resolve() if args.render_report else None
    media = {}
    render_report = verify_render_report(render_report_path, video_path, errors, warnings) if render_report_path else {}

    if shutil.which("ffprobe") is None:
        add_issue(errors, "missing_ffprobe", "Required executable 'ffprobe' was not found on PATH.")
    elif not video_path.is_file():
        add_issue(errors, "missing_video", f"Video does not exist: {video_path}")
    elif video_path.stat().st_size < 1024:
        add_issue(errors, "empty_video", "Video file is empty or implausibly small.")
    else:
        try:
            media = probe(video_path)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            add_issue(errors, "ffprobe_failed", f"ffprobe could not inspect the video: {exc}")

    streams = media.get("streams", []) if isinstance(media, dict) else []
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]

    if media and not video_streams:
        add_issue(errors, "missing_video_stream", "No video stream was found.")
    if media and not audio_streams:
        add_issue(errors, "missing_audio_stream", "No audio stream was found.")

    video_duration = None
    audio_duration = None
    format_duration = parse_duration(media.get("format", {}).get("duration")) if media else None

    if video_streams:
        primary_video = video_streams[0]
        width = primary_video.get("width")
        height = primary_video.get("height")
        if width != args.expect_width or height != args.expect_height:
            add_issue(
                errors,
                "unexpected_resolution",
                f"Expected {args.expect_width}x{args.expect_height}, found {width}x{height}.",
            )
        video_duration = parse_duration(primary_video.get("duration")) or format_duration
        if primary_video.get("pix_fmt") != "yuv420p":
            add_issue(warnings, "pixel_format", f"Expected yuv420p for broad compatibility, found {primary_video.get('pix_fmt')}.")

    if audio_streams:
        primary_audio = audio_streams[0]
        audio_duration = parse_duration(primary_audio.get("duration")) or format_duration
        if render_report.get("brand_profile") == "bubu-yier-v1":
            if primary_audio.get("codec_name") != "aac":
                add_issue(errors, "brand_audio_codec", "bubu-yier-v1 requires an AAC final audio stream.")
            if primary_audio.get("channels") != 1:
                add_issue(errors, "brand_audio_channels", "bubu-yier-v1 requires a mono final audio stream.")
            if str(primary_audio.get("sample_rate")) != "24000":
                add_issue(errors, "brand_audio_sample_rate", "bubu-yier-v1 requires a 24 kHz final audio stream.")

    effective_duration = format_duration or video_duration or audio_duration
    if effective_duration is None or effective_duration < args.min_duration:
        add_issue(errors, "invalid_duration", f"Duration must be at least {args.min_duration:.2f} seconds.")

    if video_duration is not None and audio_duration is not None:
        drift = abs(video_duration - audio_duration)
        if drift > args.max_av_drift:
            add_issue(errors, "av_drift", f"Audio/video duration drift is {drift:.3f}s, above {args.max_av_drift:.3f}s.")
    else:
        drift = None

    report = {
        "ok": not errors,
        "video": str(video_path),
        "file_size_bytes": video_path.stat().st_size if video_path.is_file() else 0,
        "duration_seconds": effective_duration,
        "video_duration_seconds": video_duration,
        "audio_duration_seconds": audio_duration,
        "av_drift_seconds": drift,
        "video_streams": len(video_streams),
        "audio_streams": len(audio_streams),
        "render_report": str(render_report_path) if render_report_path else None,
        "render_report_brand_profile": render_report.get("brand_profile") if render_report else None,
        "errors": errors,
        "warnings": warnings,
    }

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "PASS" if report["ok"] else "FAIL"
    print(
        f"{status}: duration={effective_duration}, video_streams={len(video_streams)}, "
        f"audio_streams={len(audio_streams)}, errors={len(errors)}, warnings={len(warnings)}"
    )
    for issue in errors:
        print(f"ERROR [{issue['code']}] {issue['message']}")
    for issue in warnings:
        print(f"WARN  [{issue['code']}] {issue['message']}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
