#!/usr/bin/env python3
"""Persist Paper-Ear's chat-first workflow across the voice-selection pause."""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "paper-ear-chat-v1"
FEMALE_VOICES = {
    "A": ("zf_001", "女声 A · 明快主讲"),
    "B": ("zf_018", "女声 B · 轻柔讲解"),
    "C": ("zf_046", "女声 C · 沉稳分析"),
    "D": ("zf_090", "女声 D · 均衡主讲"),
}
MALE_VOICES = {
    "A": ("zm_010", "男声 A · 快速追问"),
    "B": ("zm_033", "男声 B · 厚实质疑"),
    "C": ("zm_066", "男声 C · 温和讨论"),
    "D": ("zm_098", "男声 D · 稳重收束"),
}
DEFAULT_FEMALE = "D"
DEFAULT_MALE = "B"


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_state(path):
    state_path = Path(path).expanduser().resolve()
    if not state_path.is_file():
        raise ValueError(f"Workflow state not found: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported workflow schema: {state.get('schema_version')!r}; expected {SCHEMA_VERSION!r}"
        )
    return state_path, state


def save_state(path, state):
    state_path = Path(path).expanduser().resolve()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now()
    payload = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{state_path.name}.", suffix=".tmp", dir=str(state_path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
        os.replace(temp_name, state_path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def add_history(state, event, details=None):
    record = {"at": utc_now(), "event": event}
    if details:
        record["details"] = details
    state.setdefault("history", []).append(record)


def outputs_for(mode):
    if mode == "both":
        return ["web", "video"]
    return [mode]


def voice_from_token(token, role):
    options = FEMALE_VOICES if role == "female" else MALE_VOICES
    prefix = "zf_" if role == "female" else "zm_"
    value = str(token or "").strip()
    if not value:
        raise ValueError(f"Missing {role} voice choice.")
    lowered = value.lower()
    id_match = re.search(rf"{prefix}\d{{3}}", lowered)
    if id_match:
        voice_id = id_match.group(0)
        for letter, (known_id, label) in options.items():
            if known_id == voice_id:
                return letter, known_id, label
        raise ValueError(f"Unknown {role} voice ID: {voice_id}")
    letter_match = re.search(r"(?<![A-Za-z])[A-Da-d](?![A-Za-z])", value)
    if not letter_match:
        compact = value.strip().upper()
        if compact in options:
            letter_match = re.match(r"[A-D]", compact)
    if not letter_match:
        raise ValueError(
            f"Cannot read {role} voice choice {value!r}; use A-D or a full voice ID."
        )
    letter = letter_match.group(0).upper()
    voice_id, label = options[letter]
    return letter, voice_id, label


def choices_from_reply(reply):
    text = str(reply or "").strip()
    if not text:
        raise ValueError("Empty chat reply.")
    if "默认" in text or re.search(r"\bdefault\b", text, re.IGNORECASE):
        return DEFAULT_FEMALE, DEFAULT_MALE

    female_match = re.search(
        r"(?:女声|女|(?<![A-Za-z])female(?![A-Za-z])|主讲人?|(?<![A-Za-z])presenter(?![A-Za-z]))\s*(?:音色|声线|voice)?\s*[:：=\-]?\s*([A-Da-d]|zf_\d{3})",
        text,
        re.IGNORECASE,
    )
    male_match = re.search(
        r"(?:男声|男|(?<![A-Za-z])male(?![A-Za-z])|质疑者?|讨论者?|(?<![A-Za-z])discussant(?![A-Za-z]))\s*(?:音色|声线|voice)?\s*[:：=\-]?\s*([A-Da-d]|zm_\d{3})",
        text,
        re.IGNORECASE,
    )
    if not female_match:
        female_match = re.search(r"zf_\d{3}", text, re.IGNORECASE)
    if not male_match:
        male_match = re.search(r"zm_\d{3}", text, re.IGNORECASE)
    if not female_match or not male_match:
        raise ValueError(
            "Could not identify both roles. Reply in the form '女声 D，男声 B' or provide both voice IDs."
        )
    return female_match.group(1) if female_match.lastindex else female_match.group(0), male_match.group(
        1
    ) if male_match.lastindex else male_match.group(0)


def casting_payload(female, male):
    female_letter, female_id, female_label = voice_from_token(female, "female")
    male_letter, male_id, male_label = voice_from_token(male, "male")
    return {
        "voice_backend": "kokoro-zh-local",
        "voice_model": "kokoro-v1.1-zh",
        "language": "zh-CN",
        "g2p": "misaki-zh-1.1",
        "female_voice": female_id,
        "male_voice": male_id,
        "selection": {
            "female": {"choice": female_letter, "voice": female_id, "label": female_label},
            "male": {"choice": male_letter, "voice": male_id, "label": male_label},
            "source": "chat_reply",
            "user_listening_confirmed": True,
        },
        "voice_profiles": {
            "female": {
                "model": "kokoro-v1.1-zh",
                "voice": female_id,
                "default_style": "natural conversation",
                "style_degree": 1.0,
                "rate": "+1%",
                "pitch": "+0Hz",
                "volume": "+0%",
            },
            "male": {
                "model": "kokoro-v1.1-zh",
                "voice": male_id,
                "default_style": "natural conversation",
                "style_degree": 1.0,
                "rate": "-2%",
                "pitch": "+0Hz",
                "volume": "+0%",
            },
        },
    }


def command_init(args):
    state_path = Path(args.state).expanduser().resolve()
    if state_path.exists() and not args.force:
        raise ValueError(f"Workflow state already exists: {state_path}; pass --force to replace it.")
    source_path = Path(args.source_pdf).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"Source PDF not found: {source_path}")
    if source_path.suffix.lower() != ".pdf":
        raise ValueError(f"Source must be a PDF: {source_path}")
    source = str(source_path)
    requested_outputs = outputs_for(args.output_mode)
    now = utc_now()
    state = {
        "schema_version": SCHEMA_VERSION,
        "status": "preparing",
        "created_at": now,
        "updated_at": now,
        "source": {"pdf": source, "privacy": "private-local", "publish_allowed": False},
        "requested_outputs": requested_outputs,
        "preferences": {
            "audience": args.audience,
            "focus": args.focus,
            "coverage": args.coverage,
            "language": args.language,
        },
        "voice_selection": {
            "required": "video" in requested_outputs,
            "confirmed": False,
            "backend": "kokoro-zh-local",
            "model": "kokoro-v1.1-zh",
            "female_voice": None,
            "male_voice": None,
        },
        "artifacts": {},
        "resume": {
            "next_action": "inspect_source_then_prepare_voice_menu"
            if "video" in requested_outputs
            else "build_web_reader_and_run_qa"
        },
        "history": [],
    }
    add_history(state, "initialized", {"requested_outputs": requested_outputs})
    save_state(state_path, state)
    return state_path, state


def command_set_preferences(args):
    state_path, state = load_state(args.state)
    changed = {}
    for key in ("audience", "focus", "coverage", "language"):
        value = getattr(args, key)
        if value is not None:
            state["preferences"][key] = value
            changed[key] = value
    if not changed:
        raise ValueError("No preference update supplied.")
    add_history(state, "preferences_updated", changed)
    save_state(state_path, state)
    return state_path, state


def command_wait_for_voice(args):
    state_path, state = load_state(args.state)
    if "video" not in state.get("requested_outputs", []):
        raise ValueError("Voice selection is only needed when video output is requested.")
    menu_path = Path(args.menu).expanduser().resolve()
    if not menu_path.is_file():
        raise ValueError(f"Voice menu not found: {menu_path}")
    state["status"] = "awaiting_voice_choice"
    state["artifacts"]["voice_menu"] = str(menu_path)
    state["resume"] = {
        "next_action": "wait_for_chat_reply",
        "expected_reply": "女声 D，男声 B",
        "do_not_continue_until_reply": True,
    }
    add_history(state, "voice_pause_started", {"voice_menu": str(menu_path)})
    save_state(state_path, state)
    return state_path, state


def command_select_voices(args):
    state_path, state = load_state(args.state)
    if "video" not in state.get("requested_outputs", []):
        raise ValueError("Voice selection is only needed when video output is requested.")
    if args.reply:
        female, male = choices_from_reply(args.reply)
    else:
        if not args.male:
            raise ValueError("--male is required when --female is used.")
        female = args.female
        male = args.male
    payload = casting_payload(female, male)
    casting_path = (
        Path(args.casting_out).expanduser().resolve()
        if args.casting_out
        else state_path.with_name("voice_casting.json")
    )
    casting_path.parent.mkdir(parents=True, exist_ok=True)
    casting_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    selection = payload["selection"]
    state["status"] = "running"
    state["voice_selection"].update(
        {
            "confirmed": True,
            "confirmed_at": utc_now(),
            "female_choice": selection["female"]["choice"],
            "female_voice": payload["female_voice"],
            "male_choice": selection["male"]["choice"],
            "male_voice": payload["male_voice"],
        }
    )
    state["artifacts"]["voice_casting"] = str(casting_path)
    state["resume"] = {
        "next_action": "finish_all_requested_outputs_and_qa",
        "routine_user_confirmation_required": False,
    }
    add_history(
        state,
        "voice_choice_confirmed",
        {"female": payload["female_voice"], "male": payload["male_voice"]},
    )
    save_state(state_path, state)
    return state_path, state


def command_complete(args):
    state_path, state = load_state(args.state)
    supplied = {"web": ("site", args.site), "video": ("video", args.video)}
    for kind in state.get("requested_outputs", []):
        artifact_key, value = supplied.get(kind, (kind, None))
        if not value:
            flag = "site" if kind == "web" else kind
            raise ValueError(f"Completion requires --{flag} for the requested {kind} output.")
        artifact = Path(value).expanduser().resolve()
        if not artifact.exists():
            raise ValueError(f"Completed {kind} artifact not found: {artifact}")
        state["artifacts"][artifact_key] = str(artifact)
    state["status"] = "complete"
    state["resume"] = {"next_action": "deliver_artifacts"}
    add_history(state, "completed")
    save_state(state_path, state)
    return state_path, state


def command_block(args):
    state_path, state = load_state(args.state)
    state["status"] = "blocked"
    state["resume"] = {
        "next_action": "request_only_the_missing_decision_or_authority",
        "reason": args.reason,
    }
    add_history(state, "blocked", {"reason": args.reason})
    save_state(state_path, state)
    return state_path, state


def build_parser():
    parser = argparse.ArgumentParser(
        description="Manage a resumable, chat-first Paper-Ear run without asking users to edit config files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a private local workflow state file.")
    init.add_argument("--state", required=True)
    init.add_argument("--source-pdf", required=True)
    init.add_argument("--output-mode", choices=("web", "video", "both"), default="video")
    init.add_argument("--audience", default="general-technical")
    init.add_argument("--focus", default="detected core contributions")
    init.add_argument("--coverage", default="standard full-paper walkthrough")
    init.add_argument("--language", default="Chinese narration with Chinese-English subtitles")
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=command_init)

    preferences = subparsers.add_parser("set-preferences", help="Record choices made in chat.")
    preferences.add_argument("--state", required=True)
    preferences.add_argument("--audience")
    preferences.add_argument("--focus")
    preferences.add_argument("--coverage")
    preferences.add_argument("--language")
    preferences.set_defaults(handler=command_set_preferences)

    waiting = subparsers.add_parser("wait-for-voice", help="Record the single intentional voice pause.")
    waiting.add_argument("--state", required=True)
    waiting.add_argument("--menu", required=True, help="Path to the local voice-menu index.html")
    waiting.set_defaults(handler=command_wait_for_voice)

    voices = subparsers.add_parser("select-voices", help="Resolve a chat reply and resume the run.")
    voices.add_argument("--state", required=True)
    choice = voices.add_mutually_exclusive_group(required=True)
    choice.add_argument("--reply", help="Chat reply such as '女声 D，男声 B' or '采用默认方案'.")
    choice.add_argument("--female", help="Female option A-D or zf_* ID.")
    voices.add_argument("--male", help="Male option A-D or zm_* ID; required with --female.")
    voices.add_argument("--casting-out")
    voices.set_defaults(handler=command_select_voices)

    complete = subparsers.add_parser("complete", help="Record final deliverables after QA passes.")
    complete.add_argument("--state", required=True)
    complete.add_argument("--site")
    complete.add_argument("--video")
    complete.set_defaults(handler=command_complete)

    blocked = subparsers.add_parser("block", help="Record a genuine blocker that needs user action.")
    blocked.add_argument("--state", required=True)
    blocked.add_argument("--reason", required=True)
    blocked.set_defaults(handler=command_block)

    show = subparsers.add_parser("show", help="Print the current state as JSON.")
    show.add_argument("--state", required=True)
    show.set_defaults(handler=lambda args: load_state(args.state))
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        state_path, state = args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"state_file": str(state_path), "state": state}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
