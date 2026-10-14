#!/usr/bin/env python3
"""Render privacy-scoped voice auditions without uploading a PDF or page image."""

import argparse
import json
import re
import sys
from pathlib import Path

from render_paper_video import (
    VOICE_BACKENDS,
    build_azure_ssml,
    resolve_delivery,
    resolve_voice_profile,
    synthesize_turn_audio,
)


def safe_id(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-._")
    return cleaned or fallback


def selected_dialogue_turns(data, requested):
    turns = data.get("turns") if isinstance(data.get("turns"), list) else []
    if requested:
        indices = []
        for token in requested.split(","):
            token = token.strip()
            if not token:
                continue
            if not token.isdigit() or int(token) < 1:
                raise ValueError("--turns must be a comma-separated list of positive 1-based turn numbers.")
            indices.append(int(token))
    else:
        indices = [index for index, turn in enumerate(turns, start=1) if isinstance(turn, dict) and turn.get("audition")]

    auditions = []
    for index in indices:
        if index > len(turns):
            raise ValueError(f"Requested turn {index}, but the script contains only {len(turns)} turns.")
        source = turns[index - 1]
        if not isinstance(source, dict):
            raise ValueError(f"Turn {index} is not an object.")
        auditions.append(
            {
                **source,
                "id": source.get("id") or f"turn-{index:02d}",
                "text": source.get("spoken_text") or source.get("zh_text") or source.get("en_text") or "",
                "source_turn": index,
            }
        )
    return auditions


def load_auditions(data, requested_turns):
    if requested_turns:
        return selected_dialogue_turns(data, requested_turns)
    auditions = data.get("auditions")
    if isinstance(auditions, list) and auditions:
        return auditions
    turns = selected_dialogue_turns(data, None)
    if turns:
        return turns
    raise ValueError("Provide a non-empty auditions array, mark dialogue turns with audition=true, or pass --turns.")


def main():
    parser = argparse.ArgumentParser(description="Render Paper-Ear voice auditions from final narration text only.")
    parser.add_argument("--config", required=True, help="Voice-casting JSON or full dialogue JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for WAV/SSML files and manifest.json")
    parser.add_argument("--turns", help="Optional comma-separated 1-based dialogue turns to audition")
    parser.add_argument("--backend", choices=sorted(VOICE_BACKENDS), help="Override voice_backend for an A/B audition")
    parser.add_argument("--dry-run", action="store_true", help="Write the synthesis plan/SSML without making a network call")
    parser.add_argument(
        "--allow-cadence",
        action="store_true",
        help="Keep cadence-only placeholder audio after a provider failure (never use it for voice approval)",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    backend = str(args.backend or data.get("voice_backend") or "azure-speech").lower()
    if backend not in VOICE_BACKENDS:
        raise ValueError(f"Unsupported voice_backend '{backend}'. Choose one of {sorted(VOICE_BACKENDS)}.")

    auditions = load_auditions(data, args.turns)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "voice_backend": backend,
        "privacy_scope": "Only the final audition text is eligible for synthesis; no PDF or page image is read or sent.",
        "dry_run": bool(args.dry_run),
        "clips": [],
    }
    used_ids = set()

    for index, audition in enumerate(auditions, start=1):
        if not isinstance(audition, dict):
            raise ValueError(f"Audition {index} is not an object.")
        speaker = "male" if str(audition.get("speaker")).lower() == "male" else "female"
        text = audition.get("text") or audition.get("spoken_text") or audition.get("zh_text") or ""
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Audition {index} has no narration text.")
        clip_id = safe_id(audition.get("id"), f"audition-{index:02d}")
        if clip_id in used_ids:
            clip_id = f"{clip_id}-{index:02d}"
        used_ids.add(clip_id)
        profile = resolve_voice_profile(data, speaker)
        delivery = resolve_delivery(audition, profile)
        record = {
            "id": clip_id,
            "speaker": speaker,
            "provider": backend,
            "voice": profile["voice"],
            "emotion": delivery["emotion"],
            "provider_style": delivery["provider_style"],
            "style_degree": delivery["style_degree"],
            "character_count": len(text),
        }
        if "source_turn" in audition:
            record["source_turn"] = audition["source_turn"]

        if args.dry_run:
            if backend == "azure-speech":
                ssml_path = output_dir / f"{clip_id}.ssml"
                ssml_path.write_text(build_azure_ssml(text, profile["voice"], delivery) + "\n", encoding="utf-8")
                record["ssml_file"] = ssml_path.name
            record["status"] = "planned"
        else:
            wav_path = output_dir / f"{clip_id}.wav"
            synthesis_turn = {**audition, "speaker": speaker, "spoken_text": text}
            duration, mode, error, speech_meta = synthesize_turn_audio(
                synthesis_turn,
                backend,
                profile,
                str(wav_path),
            )
            record.update(speech_meta)
            record.update({"mode": mode, "duration_seconds": round(duration, 3), "audio_file": wav_path.name})
            if error:
                record["tts_error"] = error
            if mode != backend and not args.allow_cadence:
                wav_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Audition '{clip_id}' fell back to {mode}; voice approval requires {backend}. Root cause: {error}"
                )
            record["status"] = "rendered" if mode == backend else "cadence-placeholder"
        manifest["clips"].append(record)

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    action = "Planned" if args.dry_run else "Rendered"
    print(f"{action} {len(manifest['clips'])} voice audition(s): {manifest_path}")
    print("Privacy: this workflow does not open or upload the source PDF; online synthesis receives narration text only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
