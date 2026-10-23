#!/usr/bin/env python3
"""Install and verify the external Bubu/Yier reference clips.

The two small WAV files are pinned to one BoxAudio-0 commit and verified by
SHA-256.  F5-TTS model weights are deliberately not copied into this
repository; the upstream package resolves them into its normal Hugging Face
cache, or callers can configure explicit external paths.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import urllib.request
import wave
from pathlib import Path
from typing import Optional

from bubu_yier_voice import (
    BUBU_YIER_DEFAULT_DIR,
    BUBU_YIER_MODEL,
    BUBU_YIER_MODEL_LICENSE,
    BUBU_YIER_MODEL_SOURCE,
    BUBU_YIER_REFERENCE_SPECS,
    BUBU_YIER_UPSTREAM_COMMIT,
    BUBU_YIER_UPSTREAM_REPOSITORY,
    sha256_file,
)


RAW_ROOT = (
    "https://raw.githubusercontent.com/Boxjod/box2audio-0/"
    f"{BUBU_YIER_UPSTREAM_COMMIT}/assets/audio"
)
MINIMUM_PYTHON = (3, 10)


def require_supported_python(version_info=None) -> None:
    """Fail early with an actionable error before installing the F5 backend."""
    version = sys.version_info if version_info is None else version_info
    if tuple(version[:2]) < MINIMUM_PYTHON:
        current = ".".join(str(part) for part in version[:3])
        raise RuntimeError(
            "The Bubu/Yier F5-TTS backend requires Python 3.10 or newer "
            f"(current runtime: {current}). Create a Python 3.10+ environment, "
            "then reinstall requirements-bubu-yier.txt."
        )


def inspect_reference(path: Path, spec: dict[str, object]) -> dict[str, object]:
    record: dict[str, object] = {
        "path": str(path),
        "exists": path.is_file(),
        "expected_sha256": spec["sha256"],
        "expected_size": spec["size"],
    }
    if not path.is_file():
        record.update({"ok": False, "error": "missing"})
        return record
    record["size"] = path.stat().st_size
    record["sha256"] = sha256_file(path)
    record["checksum_ok"] = record["sha256"] == spec["sha256"]
    try:
        with wave.open(str(path), "rb") as audio:
            duration = audio.getnframes() / float(audio.getframerate())
            record.update(
                {
                    "sample_rate": audio.getframerate(),
                    "channels": audio.getnchannels(),
                    "sample_width": audio.getsampwidth(),
                    "duration_seconds": round(duration, 3),
                    "wav_ok": duration >= 0.5 and audio.getnchannels() >= 1,
                }
            )
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        record.update({"wav_ok": False, "wav_error": str(exc)})
    record["ok"] = bool(record.get("checksum_ok") and record.get("wav_ok"))
    return record


def install_reference(
    voice: str,
    spec: dict[str, object],
    target_dir: Path,
    source_dir: Optional[Path],
) -> dict[str, object]:
    target = target_dir / str(spec["filename"])
    existing = inspect_reference(target, spec)
    if existing["ok"]:
        existing["action"] = "already-verified"
        return existing

    temporary = target.with_suffix(target.suffix + ".download")
    temporary.unlink(missing_ok=True)
    try:
        if source_dir is not None:
            source = source_dir / str(spec["filename"])
            if not source.is_file():
                raise RuntimeError(f"Local source file is missing: {source}")
            shutil.copyfile(source, temporary)
            action = "copied-and-verified"
        else:
            url = f"{RAW_ROOT}/{spec['filename']}"
            request = urllib.request.Request(url, headers={"User-Agent": "paper-ear"})
            with urllib.request.urlopen(request, timeout=90) as response, open(temporary, "wb") as output:
                shutil.copyfileobj(response, output)
            action = "downloaded-and-verified"

        checked = inspect_reference(temporary, spec)
        if not checked["ok"]:
            raise RuntimeError(
                f"Downloaded reference for {voice} failed verification: "
                f"expected {spec['sha256']}, got {checked.get('sha256', 'unavailable')}."
            )
        os.replace(temporary, target)
        installed = inspect_reference(target, spec)
        installed["action"] = action
        return installed
    finally:
        temporary.unlink(missing_ok=True)


def build_report(reference_dir: Path, records: dict[str, dict[str, object]]) -> dict[str, object]:
    package_available = importlib.util.find_spec("f5_tts") is not None
    return {
        "ok": all(record.get("ok") for record in records.values()) and package_available,
        "reference_dir": str(reference_dir),
        "references": records,
        "python_package": {
            "name": "f5-tts",
            "available": package_available,
            "install_file": "requirements-bubu-yier.txt",
        },
        "upstream": {
            "repository": BUBU_YIER_UPSTREAM_REPOSITORY,
            "commit": BUBU_YIER_UPSTREAM_COMMIT,
        },
        "model": {
            "name": BUBU_YIER_MODEL,
            "source": BUBU_YIER_MODEL_SOURCE,
            "license": BUBU_YIER_MODEL_LICENSE,
            "storage": "external Hugging Face cache or explicitly configured external paths",
        },
    }


def main() -> int:
    require_supported_python()
    parser = argparse.ArgumentParser(
        description="Install and verify external Bubu/Yier F5-TTS reference audio."
    )
    parser.add_argument(
        "--reference-dir",
        default=os.environ.get("PAPER_EAR_BUBU_YIER_DIR") or str(BUBU_YIER_DEFAULT_DIR),
        help="External cache directory for the two reference WAV files",
    )
    parser.add_argument(
        "--source-dir",
        help="Optional local BoxAudio-0 assets/audio directory; files are still checksum-verified",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify references and the f5-tts package without downloading or copying",
    )
    parser.add_argument("--json-out", help="Optional machine-readable verification report")
    args = parser.parse_args()

    reference_dir = Path(args.reference_dir).expanduser().resolve()
    source_dir = Path(args.source_dir).expanduser().resolve() if args.source_dir else None
    if source_dir is not None and not source_dir.is_dir():
        raise ValueError(f"--source-dir does not exist or is not a directory: {source_dir}")

    records: dict[str, dict[str, object]] = {}
    if args.check_only:
        for voice, spec in BUBU_YIER_REFERENCE_SPECS.items():
            records[voice] = inspect_reference(reference_dir / str(spec["filename"]), spec)
    else:
        reference_dir.mkdir(parents=True, exist_ok=True)
        for voice, spec in BUBU_YIER_REFERENCE_SPECS.items():
            records[voice] = install_reference(voice, spec, reference_dir, source_dir)

    report = build_report(reference_dir, records)
    provenance_path = reference_dir / "provenance.json"
    if not args.check_only and all(record.get("ok") for record in records.values()):
        provenance_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.json_out:
        output = Path(args.json_out).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = "PASS" if report["ok"] else "FAIL"
    print(
        f"{status}: references={sum(bool(item.get('ok')) for item in records.values())}/"
        f"{len(records)}, f5_tts={report['python_package']['available']}, dir={reference_dir}"
    )
    for voice, record in records.items():
        print(
            f"{voice}: {'verified' if record.get('ok') else record.get('error', 'invalid')} "
            f"sha256={record.get('sha256', 'unavailable')}"
        )
    if not report["python_package"]["available"]:
        print("Install the optional engine with: python -m pip install -r requirements-bubu-yier.txt")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
