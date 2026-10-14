#!/usr/bin/env python3
"""Verify the basic media contract of a rendered Paper Ear MP4."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


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


def main():
    parser = argparse.ArgumentParser(description="Verify a Paper Ear MP4 with ffprobe.")
    parser.add_argument("--video", required=True, help="Rendered MP4 path")
    parser.add_argument("--expect-width", type=int, default=1920, help="Expected video width")
    parser.add_argument("--expect-height", type=int, default=1080, help="Expected video height")
    parser.add_argument("--min-duration", type=float, default=1.0, help="Minimum acceptable duration in seconds")
    parser.add_argument("--max-av-drift", type=float, default=0.75, help="Maximum audio/video duration drift in seconds")
    parser.add_argument("--json-out", help="Optional JSON report path")
    args = parser.parse_args()

    errors = []
    warnings = []
    video_path = Path(args.video).expanduser().resolve()
    media = {}

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
        audio_duration = parse_duration(audio_streams[0].get("duration")) or format_duration

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
