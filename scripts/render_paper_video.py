#!/usr/bin/env python3
"""
Render a group-meeting style MP4 video from a PDF paper and a dialogue script JSON.
Features:
- Two-person (Male & Female) conversational turn-taking with animated speaking waveform bars
- Dynamic Red Bounding Box (红框) with corner target brackets highlighting the exact paragraph/figure/formula
- Zoomed-in focus preview + Term Explanation Card (专业名词解析卡片) on the side panel
- Synchronized Bilingual Subtitles (中英双语字幕) + Chapter Progress Bar at the bottom
- Audio synthesis: supports on-device Kokoro v1.1-zh + Misaki for Mandarin,
  the optional Bubu/Yier F5-TTS cast, local Lemonade/MOSS, Microsoft Edge
  Neural TTS, and Azure Speech SSML.
- Explicit safety fallback: cadence-only audio is available for visual previews,
  while --require-tts rejects every fallback or provider mismatch.
- Optional --export-gif flag to export an animated GIF preview for GitHub READMEs.
"""

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
import numpy as np
import pdfplumber
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from bubu_yier_voice import (
    BUBU_YIER_BACKEND,
    BUBU_YIER_DEFAULT_VOICES,
    BUBU_YIER_MODEL,
    BUBU_YIER_REFERENCE_SPECS,
    resolve_f5_options,
    resolve_reference,
    synthesize_bubu_yier,
)
from character_library import CharacterLibrary
from document_binding import RAW_BYTES_HASH_MODE, collect_input_identity, enforce_document_binding, sha256_file


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUBU_YIER_BRAND_PROFILE = "bubu-yier-v1"
BUBU_YIER_INTRO_BACKGROUND = os.path.join(REPO_ROOT, "assets", "bubu_yier_intro_bg.png")
FINAL_AUDIO_GAIN_DB = -1.5
FINAL_AUDIO_LIMITER_CEILING = 0.89
FINAL_AUDIO_BITRATE = "128k"
FINAL_AUDIO_FILTER = (
    f"volume={FINAL_AUDIO_GAIN_DB}dB,"
    f"alimiter=limit={FINAL_AUDIO_LIMITER_CEILING}:level=false"
)
_CHARACTER_IMAGE_CACHE = {}


FONT_REGULAR_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

VOICE_BACKENDS = {
    "edge-tts",
    "azure-speech",
    "kokoro-zh-local",
    "lemonade-local",
    BUBU_YIER_BACKEND,
}
NATIVE_EMPHASIS_VOICES = {"en-US-GuyNeural", "en-US-DavisNeural", "en-US-JaneNeural"}

KOKORO_ZH_MODEL = "kokoro-v1.1-zh"
KOKORO_ZH_DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".cache", "paper-ear", "kokoro-zh-v1.1")
KOKORO_ZH_FILES = {
    "model": "kokoro-v1.1-zh.onnx",
    "voices": "voices-v1.1-zh.bin",
    "config": "config.json",
}
KOKORO_ZH_VOICES = {
    "female": ("zf_001", "zf_018", "zf_046", "zf_090"),
    "male": ("zm_010", "zm_033", "zm_066", "zm_098"),
}
KOKORO_ZH_DEFAULT_VOICES = {"female": "zf_090", "male": "zm_033"}
_KOKORO_ZH_RUNTIMES = {}

LEMONADE_DEFAULT_BASE_URL = "http://127.0.0.1:13305/api/v1"
LEMONADE_KOKORO_MODEL = "kokoro-v1"
LEMONADE_EXPRESSIVE_MODELS = {"MOSS-TTS-Local", "OpenMOSS-TTS"}
LEMONADE_KOKORO_ZH_VOICES = {
    "female": ("zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi"),
    "male": ("zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang"),
}

DEFAULT_STYLE_BY_EMOTION = {
    "female": {
        "neutral": "chat",
        "curious": "chat",
        "skeptical": "serious",
        "serious": "serious",
        "surprised": "excited",
        "excited": "excited",
        "reflective": "calm",
    },
    "male": {
        "neutral": "narration-relaxed",
        "curious": "narration-relaxed",
        "skeptical": "serious",
        "serious": "serious",
        "surprised": "documentary-narration",
        "excited": "documentary-narration",
        "reflective": "documentary-narration",
    },
}

LOCAL_STYLE_BY_EMOTION = {
    "female": {
        "neutral": "natural conversation",
        "curious": "curious and engaged",
        "skeptical": "skeptical but respectful",
        "serious": "focused and serious",
        "surprised": "genuinely surprised",
        "excited": "animated but not theatrical",
        "reflective": "thoughtful and measured",
    },
    "male": {
        "neutral": "natural conversation",
        "curious": "probing and curious",
        "skeptical": "firm and skeptical",
        "serious": "focused and serious",
        "surprised": "genuinely surprised",
        "excited": "energetic but controlled",
        "reflective": "calm and reflective",
    },
}


def strip_unsupported_emoji(text):
    """Strip supplementary-plane emojis that CJK TTC fonts render as tofu boxes."""
    if not text:
        return ""
    return re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f]", "", text).strip()


def page_file_sort_key(path):
    """Sort pdftoppm outputs numerically so page-10 never precedes page-2."""
    match = re.search(r"-(\d+)\.png$", os.path.basename(path), flags=re.IGNORECASE)
    return (int(match.group(1)), path) if match else (math.inf, path)


def load_font(candidates, size):
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def locate_text_bbox_on_page(pdf_path, page_num, search_terms):
    """Locate normalized [x0, y0, x1, y1] bounding box on 1-indexed page_num matching search_terms."""
    if not search_terms:
        return None
    if isinstance(search_terms, str):
        search_terms = [search_terms]
    search_terms = [s.strip().lower() for s in search_terms if s and s.strip()]
    if not search_terms:
        return None

    with pdfplumber.open(pdf_path) as pdf:
        if page_num < 1 or page_num > len(pdf.pages):
            return None
        page = pdf.pages[page_num - 1]
        pw, ph = float(page.width), float(page.height)
        words = page.extract_words() or []
        if not words:
            return None

        sorted_words = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
        lines = []
        curr = [sorted_words[0]]
        for w in sorted_words[1:]:
            if abs(w["top"] - curr[-1]["top"]) <= 5.0:
                curr.append(w)
            else:
                lines.append(curr)
                curr = [w]
        lines.append(curr)

        line_objs = []
        for ln in lines:
            ln_s = sorted(ln, key=lambda w: w["x0"])
            txt = " ".join(w["text"] for w in ln_s)
            line_objs.append({
                "text": txt,
                "text_low": txt.lower(),
                "x0": min(w["x0"] for w in ln_s),
                "top": min(w["top"] for w in ln_s),
                "x1": max(w["x1"] for w in ln_s),
                "bottom": max(w["bottom"] for w in ln_s),
            })

        matched_indices = []
        for idx, lo in enumerate(line_objs):
            for term in search_terms:
                if term in lo["text_low"]:
                    matched_indices.append(idx)
                    break

        if not matched_indices:
            for idx, lo in enumerate(line_objs):
                for term in search_terms:
                    tokens = [t for t in term.split() if len(t) > 2]
                    if tokens and sum(1 for t in tokens if t in lo["text_low"]) >= max(1, int(len(tokens) * 0.6)):
                        matched_indices.append(idx)
                        break

        if not matched_indices:
            return None

        first_idx = matched_indices[0]
        cluster = [first_idx]
        for idx in range(first_idx + 1, min(len(line_objs), first_idx + 12)):
            gap = line_objs[idx]["top"] - line_objs[cluster[-1]]["bottom"]
            if gap <= 10.0:
                cluster.append(idx)
            else:
                break

        x0 = max(0.0, min(line_objs[i]["x0"] for i in cluster) / pw - 0.01)
        y0 = max(0.0, min(line_objs[i]["top"] for i in cluster) / ph - 0.008)
        x1 = min(1.0, max(line_objs[i]["x1"] for i in cluster) / pw + 0.01)
        y1 = min(1.0, max(line_objs[i]["bottom"] for i in cluster) / ph + 0.008)
        return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def wrap_text(draw, text, font, max_width):
    """Wrap CJK and Latin text cleanly within max_width pixels."""
    if not text:
        return []
    lines = []
    for paragraph in text.split("\n"):
        curr = ""
        i = 0
        tokens = []
        while i < len(paragraph):
            ch = paragraph[i]
            if ch.isascii() and (ch.isalnum() or ch in "-_./()"):
                j = i
                while j < len(paragraph) and paragraph[j].isascii() and (paragraph[j].isalnum() or paragraph[j] in "-_./()"):
                    j += 1
                tokens.append(paragraph[i:j])
                i = j
            else:
                tokens.append(ch)
                i += 1

        for tok in tokens:
            candidate = curr + tok
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if (bbox[2] - bbox[0]) <= max_width or not curr:
                curr = candidate
            else:
                lines.append(curr.strip())
                curr = tok.lstrip()
        if curr.strip():
            lines.append(curr.strip())
    return lines


def _xml_attr(value):
    return xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


def _ssml_text_with_emphasis(text, emphasis_terms, voice):
    """Apply supported emphasis, or a conservative prosody cue for other voices."""
    terms = []
    for term in emphasis_terms or []:
        if isinstance(term, str) and term.strip() and term not in terms:
            terms.append(term)
    if not terms:
        return xml_escape(text)

    pattern = re.compile("(" + "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)) + ")")
    parts = []
    cursor = 0
    for match in pattern.finditer(text):
        parts.append(xml_escape(text[cursor:match.start()]))
        escaped_term = xml_escape(match.group(0))
        if voice in NATIVE_EMPHASIS_VOICES:
            parts.append(f'<emphasis level="moderate">{escaped_term}</emphasis>')
        else:
            # Azure currently documents native word-level emphasis for only three
            # en-US voices. A slight local slowdown is a portable cue for zh-CN.
            parts.append(f'<prosody rate="-8%" pitch="+1Hz">{escaped_term}</prosody>')
        cursor = match.end()
    parts.append(xml_escape(text[cursor:]))
    return "".join(parts)


def resolve_voice_profile(data, speaker):
    """Resolve the selected voice while retaining the legacy male/female fields."""
    speaker = "male" if str(speaker).lower() == "male" else "female"
    backend = str(data.get("voice_backend") or "edge-tts").lower()
    branded = str(data.get("brand_profile") or "").strip().lower() == BUBU_YIER_BRAND_PROFILE
    if branded and backend != BUBU_YIER_BACKEND:
        raise ValueError(
            f"brand_profile '{BUBU_YIER_BRAND_PROFILE}' requires voice_backend "
            f"'{BUBU_YIER_BACKEND}', not '{backend}'."
        )
    if backend == "kokoro-zh-local":
        default_voice = KOKORO_ZH_DEFAULT_VOICES[speaker]
        default_model = KOKORO_ZH_MODEL
        default_styles = LOCAL_STYLE_BY_EMOTION[speaker]
    elif backend == BUBU_YIER_BACKEND:
        default_voice = BUBU_YIER_DEFAULT_VOICES[speaker]
        default_model = BUBU_YIER_MODEL
        default_styles = LOCAL_STYLE_BY_EMOTION[speaker]
    elif backend == "lemonade-local":
        default_voice = "zm_yunjian" if speaker == "male" else "zf_xiaobei"
        default_model = LEMONADE_KOKORO_MODEL
        default_styles = LOCAL_STYLE_BY_EMOTION[speaker]
    else:
        default_voice = "zh-CN-YunjianNeural" if speaker == "male" else "zh-CN-XiaoxiaoNeural"
        default_model = LEMONADE_KOKORO_MODEL
        default_styles = DEFAULT_STYLE_BY_EMOTION[speaker]
    legacy_voice = data.get(f"{speaker}_voice") or default_voice
    profiles = data.get("voice_profiles") or {}
    profile = profiles.get(speaker) if isinstance(profiles, dict) else None
    profile = dict(profile) if isinstance(profile, dict) else {}
    if branded:
        expected_voice = BUBU_YIER_DEFAULT_VOICES[speaker]
        root_voice = data.get(f"{speaker}_voice")
        profile_voice = profile.get("voice")
        for location, configured_voice in (
            (f"{speaker}_voice", root_voice),
            (f"voice_profiles.{speaker}.voice", profile_voice),
        ):
            if configured_voice not in (None, "") and str(configured_voice).strip().lower() != expected_voice:
                raise ValueError(
                    f"{BUBU_YIER_BRAND_PROFILE} requires {location}='{expected_voice}', "
                    f"not '{configured_voice}'."
                )
        root_model = data.get("voice_model")
        profile_model = profile.get("model")
        for location, configured_model in (
            ("voice_model", root_model),
            (f"voice_profiles.{speaker}.model", profile_model),
        ):
            if configured_model not in (None, "") and str(configured_model).strip() != BUBU_YIER_MODEL:
                raise ValueError(
                    f"{BUBU_YIER_BRAND_PROFILE} requires {location}='{BUBU_YIER_MODEL}', "
                    f"not '{configured_model}'."
                )
        profile["voice"] = expected_voice
        profile["model"] = BUBU_YIER_MODEL
        expected_reference = BUBU_YIER_REFERENCE_SPECS[expected_voice]
        configured_hash = str(profile.get("reference_sha256") or "").strip().lower()
        if configured_hash and configured_hash != expected_reference["sha256"]:
            raise ValueError(
                f"{BUBU_YIER_BRAND_PROFILE} requires the pinned {expected_voice} "
                "reference_sha256; use a separate non-branded profile for an authorized "
                "replacement recording."
            )
        configured_text = profile.get("reference_text")
        if configured_text not in (None, "") and str(configured_text).strip() != expected_reference["reference_text"]:
            raise ValueError(
                f"{BUBU_YIER_BRAND_PROFILE} requires the pinned {expected_voice} reference_text "
                "to match the verified recording."
            )
    else:
        profile["voice"] = profile.get("voice") or legacy_voice
        profile.setdefault("model", data.get("voice_model") or default_model)
    profile.setdefault("default_style", default_styles["neutral"])
    profile.setdefault("styles_by_emotion", default_styles)
    profile.setdefault("rate", "+0%")
    profile.setdefault("pitch", "+0Hz")
    profile.setdefault("volume", "+0%")
    profile.setdefault("style_degree", 1.0)
    profile.setdefault("voice_design_description", "")
    return profile


def resolve_bubu_yier_display_name(data, speaker):
    """Resolve a branded display name while preventing cast swaps or human aliases."""
    speaker = "male" if str(speaker).lower() == "male" else "female"
    expected_name = "布布" if speaker == "male" else "一二"
    field = f"{speaker}_name"
    default_name = f"{expected_name}（{'追问' if speaker == 'male' else '主讲'}）"
    value = data.get(field, default_name)
    if not isinstance(value, str) or not value.strip().startswith(expected_name):
        raise ValueError(
            f"{BUBU_YIER_BRAND_PROFILE} requires {field} to start with '{expected_name}'; "
            f"got {value!r}."
        )
    return value.strip()


def preflight_bubu_yier_brand_references(voice_profiles):
    """Fail closed on cast, model, or unverified external reference drift."""
    resolved = {}
    for speaker in ("female", "male"):
        profile = voice_profiles.get(speaker)
        if not isinstance(profile, dict):
            raise ValueError(f"Missing resolved {speaker} voice profile for {BUBU_YIER_BRAND_PROFILE}.")
        expected_voice = BUBU_YIER_DEFAULT_VOICES[speaker]
        if profile.get("voice") != expected_voice:
            raise ValueError(
                f"Resolved {speaker} voice must be '{expected_voice}', not '{profile.get('voice')}'."
            )
        options = resolve_f5_options(profile)
        if options.get("model") != BUBU_YIER_MODEL:
            raise ValueError(
                f"Resolved {speaker} model must be '{BUBU_YIER_MODEL}', not '{options.get('model')}'."
            )
        reference = resolve_reference(profile)
        reference_hash = str(reference.get("sha256") or "").lower()
        expected_reference = BUBU_YIER_REFERENCE_SPECS[expected_voice]
        if reference.get("voice") != expected_voice:
            raise ValueError(
                f"Resolved {speaker} reference must use '{expected_voice}', not '{reference.get('voice')}'."
            )
        if reference.get("verified") is not True or not re.fullmatch(r"[0-9a-f]{64}", reference_hash):
            raise ValueError(
                f"Resolved {speaker} reference must have a matching 64-character SHA-256 checksum."
            )
        if reference_hash != expected_reference["sha256"]:
            raise ValueError(
                f"Resolved {speaker} reference must match the pinned {expected_voice} SHA-256 "
                f"{expected_reference['sha256']}."
            )
        if reference.get("reference_text") != expected_reference["reference_text"]:
            raise ValueError(
                f"Resolved {speaker} reference_text must match the pinned {expected_voice} transcript."
            )
        resolved[speaker] = reference
    return resolved


def enforce_bubu_yier_addressing_contract(turns, require_bidirectional=False):
    """Enforce the branded characters' natural forms of address."""
    records = []
    for index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            continue
        speaker = str(turn.get("speaker") or "").strip().lower()
        text = turn.get("spoken_text") or turn.get("zh_text") or ""
        text = text if isinstance(text, str) else ""
        records.append((index, speaker, text))
        if speaker == "female" and "一二宝" in text:
            raise ValueError(
                f"Branded turn {index}: 一二 cannot address 布布 as '一二宝'. "
                "Use 布布、臭布布或香布布 according to context."
            )
        if speaker == "male" and any(nickname in text for nickname in ("臭布布", "香布布")):
            raise ValueError(
                f"Branded turn {index}: 布布 cannot address 一二 as 臭布布 or 香布布; use '一二宝'."
            )

    for nickname in ("一二宝", "臭布布", "香布布"):
        count = sum(text.count(nickname) for _, _, text in records)
        if count > 1:
            raise ValueError(
                f"Branded dialogue uses special nickname '{nickname}' {count} times; "
                "keep each special nickname to at most one natural occurrence."
            )

    if require_bidirectional:
        male_addresses = any(speaker == "male" and "一二宝" in text for _, speaker, text in records)
        female_addresses = any(
            speaker == "female" and any(name in text for name in ("布布", "臭布布", "香布布"))
            for _, speaker, text in records
        )
        if not male_addresses:
            raise ValueError("A complete 15-20 turn branded dialogue must have 布布 address 一二 as '一二宝' once.")
        if not female_addresses:
            raise ValueError("A complete 15-20 turn branded dialogue must have 一二 address 布布 naturally at least once.")

    return {
        "male_to_female": sum(speaker == "male" and "一二宝" in text for _, speaker, text in records),
        "female_to_male": sum(
            speaker == "female" and any(name in text for name in ("布布", "臭布布", "香布布"))
            for _, speaker, text in records
        ),
    }


def resolve_delivery(turn, voice_profile):
    delivery = turn.get("delivery") if isinstance(turn.get("delivery"), dict) else {}
    emotion = str(turn.get("emotion") or "neutral").lower()
    styles = voice_profile.get("styles_by_emotion")
    styles = styles if isinstance(styles, dict) else {}
    style = delivery.get("provider_style") or styles.get(emotion) or voice_profile.get("default_style") or ""
    intensity = turn.get("emotion_intensity", 0.5)
    style_degree = delivery.get("style_degree", voice_profile.get("style_degree", 1.0))
    try:
        style_degree = float(style_degree)
    except (TypeError, ValueError):
        style_degree = 1.0
    style_degree = max(0.01, min(2.0, style_degree))
    try:
        intensity = float(intensity)
    except (TypeError, ValueError):
        intensity = 0.5

    return {
        "emotion": emotion,
        "emotion_intensity": max(0.0, min(1.0, intensity)),
        "provider_style": str(style).strip(),
        "style_degree": style_degree,
        "rate": str(delivery.get("rate", voice_profile.get("rate", "+0%"))),
        "pitch": str(delivery.get("pitch", voice_profile.get("pitch", "+0Hz"))),
        "volume": str(delivery.get("volume", voice_profile.get("volume", "+0%"))),
        "pause_before_ms": max(0, int(delivery.get("pause_before_ms", 0) or 0)),
        "pause_after_ms": max(0, int(delivery.get("pause_after_ms", 250) or 0)),
        "emphasis_terms": delivery.get("emphasis_terms") if isinstance(delivery.get("emphasis_terms"), list) else [],
    }


def build_azure_ssml(text, voice, delivery):
    """Build Azure Speech SSML without sending source files or evidence images."""
    lang_parts = str(voice).split("-")
    language = "-".join(lang_parts[:2]) if len(lang_parts) >= 2 else "zh-CN"
    spoken = _ssml_text_with_emphasis(text, delivery.get("emphasis_terms"), voice)
    before = f'<break time="{int(delivery["pause_before_ms"])}ms"/>' if delivery.get("pause_before_ms") else ""
    after = f'<break time="{int(delivery["pause_after_ms"])}ms"/>' if delivery.get("pause_after_ms") else ""
    prosody = (
        f'<prosody rate="{_xml_attr(delivery["rate"])}" '
        f'pitch="{_xml_attr(delivery["pitch"])}" '
        f'volume="{_xml_attr(delivery["volume"])}">{spoken}</prosody>'
    )
    body = before + prosody + after
    style = delivery.get("provider_style")
    if style:
        body = (
            f'<mstts:express-as style="{_xml_attr(style)}" '
            f'styledegree="{delivery["style_degree"]:.2f}">{body}</mstts:express-as>'
        )
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{_xml_attr(language)}">'
        f'<voice name="{_xml_attr(voice)}">{body}</voice></speak>'
    )


def _convert_audio_to_wav(input_audio, out_wav, sample_rate=24000, channels=1):
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                input_audio,
                "-ar",
                str(sample_rate),
                "-ac",
                str(channels),
                "-c:a",
                "pcm_s16le",
                out_wav,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    # Voice auditions should not need a full video toolchain. SoundFile handles
    # Lemonade's float WAV response and writes a wave-module-compatible PCM WAV.
    import soundfile as sf

    audio, source_rate = sf.read(input_audio, dtype="float32", always_2d=True)
    if channels == 1 and audio.shape[1] != 1:
        audio = np.mean(audio, axis=1, keepdims=True)
    elif channels > 1 and audio.shape[1] == 1:
        audio = np.repeat(audio, channels, axis=1)
    if source_rate != sample_rate and len(audio) > 1:
        source_x = np.arange(len(audio), dtype=np.float64)
        target_len = max(1, int(round(len(audio) * sample_rate / source_rate)))
        target_x = np.linspace(0, len(audio) - 1, target_len)
        audio = np.column_stack(
            [np.interp(target_x, source_x, audio[:, channel]) for channel in range(audio.shape[1])]
        ).astype(np.float32)
    sf.write(out_wav, audio, sample_rate, subtype="PCM_16")


def _convert_mp3_to_wav(tmp_mp3, out_wav):
    _convert_audio_to_wav(tmp_mp3, out_wav)


def _pad_pcm_wav(out_wav, before_ms=0, after_ms=0):
    before_ms = max(0, int(before_ms or 0))
    after_ms = max(0, int(after_ms or 0))
    if not before_ms and not after_ms:
        return
    padded_path = out_wav + ".padded.wav"
    try:
        with wave.open(out_wav, "rb") as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
        bytes_per_frame = params.nchannels * params.sampwidth
        prefix = b"\x00" * int(params.framerate * before_ms / 1000.0) * bytes_per_frame
        suffix = b"\x00" * int(params.framerate * after_ms / 1000.0) * bytes_per_frame
        with wave.open(padded_path, "wb") as target:
            target.setparams(params)
            target.writeframes(prefix + frames + suffix)
        os.replace(padded_path, out_wav)
    finally:
        if os.path.exists(padded_path):
            os.remove(padded_path)


def _rate_to_speed(rate):
    if isinstance(rate, (int, float)) and not isinstance(rate, bool):
        return max(0.5, min(2.0, float(rate)))
    match = re.fullmatch(r"([+-])(\d+)%", str(rate or "+0%").strip())
    if not match:
        return 1.0
    delta = int(match.group(2)) / 100.0
    speed = 1.0 + delta if match.group(1) == "+" else 1.0 - delta
    return max(0.5, min(2.0, speed))


def resolve_kokoro_zh_paths(voice_profile=None):
    """Resolve the dedicated Mandarin model files without making a network call."""
    profile = voice_profile if isinstance(voice_profile, dict) else {}
    model_dir = (
        os.environ.get("PAPER_EAR_KOKORO_ZH_DIR")
        or profile.get("model_dir")
        or KOKORO_ZH_DEFAULT_DIR
    )
    model_dir = os.path.abspath(os.path.expanduser(str(model_dir)))
    paths = {
        key: os.path.abspath(
            os.path.expanduser(str(profile.get(f"{key}_path") or os.path.join(model_dir, filename)))
        )
        for key, filename in KOKORO_ZH_FILES.items()
    }
    missing = [path for path in paths.values() if not os.path.isfile(path)]
    if missing:
        raise RuntimeError(
            "Dedicated Mandarin model files are missing. Run "
            "'python scripts/setup_mandarin_voice.py' first. Missing: " + ", ".join(missing)
        )
    return paths


def _load_kokoro_zh_runtime(voice_profile=None):
    """Load and cache Kokoro v1.1-zh with Misaki's tone-aware Chinese frontend."""
    paths = resolve_kokoro_zh_paths(voice_profile)
    cache_key = tuple(paths[key] for key in ("model", "voices", "config"))
    cached = _KOKORO_ZH_RUNTIMES.get(cache_key)
    if cached is not None:
        return cached
    try:
        from kokoro_onnx import Kokoro
        from misaki import zh
        from misaki.espeak import EspeakG2P
    except ImportError as exc:
        raise RuntimeError(
            "Mandarin dependencies are missing. Install requirements.txt, including "
            "kokoro-onnx and misaki-fork[zh]."
        ) from exc

    english_g2p = EspeakG2P(language="en-us", version="1.1")
    chinese_g2p = zh.ZHG2P(
        version="1.1",
        en_callable=lambda segment: english_g2p(segment)[0],
    )
    engine = Kokoro(
        paths["model"],
        paths["voices"],
        vocab_config=paths["config"],
    )
    cached = (engine, chinese_g2p, set(engine.get_voices()))
    _KOKORO_ZH_RUNTIMES[cache_key] = cached
    return cached


def try_kokoro_zh_tts(text, voice_profile, delivery, out_wav):
    """Synthesize on-device Mandarin through Kokoro v1.1-zh + Misaki ZHG2P."""
    engine, g2p, available_voices = _load_kokoro_zh_runtime(voice_profile)
    voice = str(voice_profile.get("voice") or "").strip()
    if voice not in available_voices:
        raise RuntimeError(
            f"Voice '{voice}' is not present in the dedicated Mandarin voice pack. "
            f"Choose one of {sorted(KOKORO_ZH_VOICES['female'] + KOKORO_ZH_VOICES['male'])}."
        )
    phonemes, _ = g2p(text)
    if not isinstance(phonemes, str) or not phonemes.strip() or phonemes.strip() == "❓":
        raise RuntimeError("The Mandarin frontend could not produce usable phonemes for this narration.")
    samples, sample_rate = engine.create(
        phonemes,
        voice=voice,
        speed=_rate_to_speed(delivery.get("rate")),
        is_phonemes=True,
    )
    import soundfile as sf

    sf.write(out_wav, samples, sample_rate, subtype="PCM_16")
    _pad_pcm_wav(out_wav, delivery.get("pause_before_ms"), delivery.get("pause_after_ms"))
    return {
        "model": KOKORO_ZH_MODEL,
        "language": "zh-CN",
        "g2p": "misaki-zh-1.1",
        "endpoint_scope": "on-device",
        "voice_design": False,
    }


def resolve_lemonade_base_url(voice_profile=None):
    profile = voice_profile if isinstance(voice_profile, dict) else {}
    base_url = (
        os.environ.get("PAPER_EAR_LEMONADE_BASE_URL")
        or profile.get("base_url")
        or LEMONADE_DEFAULT_BASE_URL
    )
    base_url = str(base_url).strip().rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("Lemonade base URL must be an absolute http(s) URL.")
    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    allow_remote = os.environ.get("PAPER_EAR_ALLOW_REMOTE_LEMONADE") == "1"
    if parsed.hostname.lower() not in loopback_hosts and not allow_remote:
        raise RuntimeError(
            "Refusing to send narration to a non-loopback Lemonade endpoint. "
            "Set PAPER_EAR_ALLOW_REMOTE_LEMONADE=1 only after approving that privacy boundary."
        )
    return base_url


def build_lemonade_request(text, voice_profile, delivery):
    model = str(voice_profile.get("model") or LEMONADE_KOKORO_MODEL).strip()
    voice = str(voice_profile.get("voice") or "").strip()
    payload = {
        "model": model,
        "input": text,
        "speed": _rate_to_speed(delivery.get("rate")),
        "response_format": "wav",
    }
    if voice:
        payload["voice"] = voice
    design = str(voice_profile.get("voice_design_description") or "").strip()
    if model in LEMONADE_EXPRESSIVE_MODELS and design:
        payload["voice_design_description"] = design
    return payload


def try_lemonade_tts(text, voice_profile, delivery, out_wav):
    """Synthesize locally through Lemonade; no paper artifact leaves the machine."""
    base_url = resolve_lemonade_base_url(voice_profile)
    payload = build_lemonade_request(text, voice_profile, delivery)
    if (
        payload["model"] == LEMONADE_KOKORO_MODEL
        and str(payload.get("voice") or "").startswith(("zf_", "zm_"))
        and os.environ.get("PAPER_EAR_ALLOW_LEGACY_KOKORO_ZH") != "1"
    ):
        raise RuntimeError(
            "Legacy Kokoro v1.0 Mandarin is disabled because intelligibility was not reliable. "
            "Use voice_backend='kokoro-zh-local' with kokoro-v1.1-zh. Set "
            "PAPER_EAR_ALLOW_LEGACY_KOKORO_ZH=1 only for an explicitly labeled legacy comparison."
        )
    headers = {"Content-Type": "application/json; charset=utf-8"}
    api_key = os.environ.get("LEMONADE_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url}/audio/speech",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    provider_wav = out_wav + ".lemonade.wav"
    try:
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                audio = response.read()
        except urllib.error.HTTPError as exc:
            exc.read()
            raise RuntimeError(f"Lemonade HTTP {exc.code} ({exc.reason}).") from exc
        if len(audio) < 1000:
            raise RuntimeError("Lemonade returned an empty or unexpectedly small audio payload.")
        with open(provider_wav, "wb") as audio_file:
            audio_file.write(audio)
        # Kokoro currently returns float WAV. Normalize to 16-bit PCM so Python's
        # wave module, ffmpeg, and downstream video verification agree on it.
        _convert_audio_to_wav(provider_wav, out_wav)
        _pad_pcm_wav(out_wav, delivery.get("pause_before_ms"), delivery.get("pause_after_ms"))
    finally:
        if os.path.exists(provider_wav):
            os.remove(provider_wav)
    return {
        "model": payload["model"],
        "endpoint_scope": "loopback" if urllib.parse.urlparse(base_url).hostname in {"localhost", "127.0.0.1", "::1"} else "remote",
        "voice_design": bool(payload.get("voice_design_description")),
    }


async def try_edge_tts(text, voice, delivery, out_wav):
    import edge_tts
    tmp_mp3 = out_wav + ".mp3"
    try:
        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=delivery["rate"],
            volume=delivery["volume"],
            pitch=delivery["pitch"],
        )
        await communicate.save(tmp_mp3)
        _convert_mp3_to_wav(tmp_mp3, out_wav)
    finally:
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)


def try_azure_speech(text, voice, delivery, out_wav):
    """Synthesize one final narration string through Azure Speech REST."""
    speech_key = os.environ.get("AZURE_SPEECH_KEY") or os.environ.get("SPEECH_KEY")
    speech_region = os.environ.get("AZURE_SPEECH_REGION") or os.environ.get("SPEECH_REGION")
    endpoint = os.environ.get("AZURE_SPEECH_ENDPOINT")
    if not speech_key:
        raise RuntimeError("Azure Speech credential is missing: set AZURE_SPEECH_KEY (or SPEECH_KEY).")
    if not endpoint and not speech_region:
        raise RuntimeError("Azure Speech region is missing: set AZURE_SPEECH_REGION (or SPEECH_REGION).")
    if speech_region and not re.fullmatch(r"[A-Za-z0-9-]+", speech_region):
        raise RuntimeError("Azure Speech region contains unexpected characters.")
    endpoint = endpoint or f"https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    if not endpoint.lower().startswith("https://"):
        raise RuntimeError("Azure Speech endpoint must use HTTPS.")
    ssml = build_azure_ssml(text, voice, delivery)
    request = urllib.request.Request(
        endpoint,
        data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": speech_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "User-Agent": "paper-ear",
        },
        method="POST",
    )
    tmp_mp3 = out_wav + ".mp3"
    try:
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            # Do not copy a provider response body into logs/reports: an error
            # payload could echo part of the private narration request.
            exc.read()
            raise RuntimeError(f"Azure Speech HTTP {exc.code} ({exc.reason}).") from exc
        if len(payload) < 1000:
            raise RuntimeError("Azure Speech returned an empty or unexpectedly small audio payload.")
        with open(tmp_mp3, "wb") as audio_file:
            audio_file.write(payload)
        _convert_mp3_to_wav(tmp_mp3, out_wav)
    finally:
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)


def generate_offline_dialogue_wav(text, speaker, out_wav, sample_rate=24000):
    clean_len = max(1, len(text.strip()))
    duration = max(3.5, min(14.0, clean_len / 4.2 + 0.8))
    n_samples = int(duration * sample_rate)

    base_freq = 135.0 if speaker == "male" else 225.0
    chime_dur = min(0.35, duration * 0.15)
    chime_samples = int(chime_dur * sample_rate)
    t_chime = np.linspace(0, chime_dur, chime_samples, endpoint=False)
    env = np.exp(-t_chime * 10.0) * np.sin(np.pi * t_chime / chime_dur)
    chime = 0.08 * env * (
        np.sin(2 * np.pi * base_freq * 2.0 * t_chime)
        + 0.5 * np.sin(2 * np.pi * base_freq * 3.0 * t_chime)
    )

    audio = np.zeros(n_samples, dtype=np.float32)
    audio[:chime_samples] += chime

    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return duration


def get_wav_duration(wav_path):
    with wave.open(wav_path, "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def synthesize_turn_audio(turn, voice_backend, voice_profile, out_wav):
    speaker = turn.get("speaker", "female").lower()
    voice = voice_profile["voice"]
    spoken_text = turn.get("spoken_text") or turn.get("zh_text") or turn.get("en_text") or ""
    delivery = resolve_delivery(turn, voice_profile)
    metadata = {
        "provider": voice_backend,
        "voice": voice,
        "emotion": delivery["emotion"],
        "emotion_intensity": delivery["emotion_intensity"],
        "provider_style": delivery["provider_style"],
        "style_degree": delivery["style_degree"],
        "rate": delivery["rate"],
        "pitch": delivery["pitch"],
        "volume": delivery["volume"],
    }

    try:
        if voice_backend == "edge-tts":
            asyncio.run(try_edge_tts(spoken_text, voice, delivery, out_wav))
        elif voice_backend == "azure-speech":
            try_azure_speech(spoken_text, voice, delivery, out_wav)
        elif voice_backend == "kokoro-zh-local":
            metadata.update(try_kokoro_zh_tts(spoken_text, voice_profile, delivery, out_wav))
        elif voice_backend == "lemonade-local":
            metadata.update(try_lemonade_tts(spoken_text, voice_profile, delivery, out_wav))
        elif voice_backend == BUBU_YIER_BACKEND:
            metadata.update(synthesize_bubu_yier(spoken_text, voice_profile, delivery, out_wav))
        else:
            raise ValueError(f"Unsupported voice_backend '{voice_backend}'. Choose one of {sorted(VOICE_BACKENDS)}.")
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
            return get_wav_duration(out_wav), voice_backend, None, metadata
    except Exception as exc:
        tts_error = f"{type(exc).__name__}: {exc}"[:500]
    else:
        tts_error = f"{voice_backend} did not create a valid WAV file."

    dur = generate_offline_dialogue_wav(spoken_text, speaker, out_wav)
    return dur, "offline-cadence", tts_error, metadata


def draw_corner_brackets(draw, x0, y0, x1, y1, color, length=18, width=5):
    draw.line([(x0, y0), (x0 + length, y0)], fill=color, width=width)
    draw.line([(x0, y0), (x0, y0 + length)], fill=color, width=width)
    draw.line([(x1 - length, y0), (x1, y0)], fill=color, width=width)
    draw.line([(x1, y0), (x1, y0 + length)], fill=color, width=width)
    draw.line([(x0, y1 - length), (x0, y1)], fill=color, width=width)
    draw.line([(x0, y1), (x0 + length, y1)], fill=color, width=width)
    draw.line([(x1 - length, y1), (x1, y1)], fill=color, width=width)
    draw.line([(x1, y1 - length), (x1, y1)], fill=color, width=width)


def draw_soundwave_bars(draw, x_start, y_center, num_bars, max_h, color, phase):
    bar_w = 4
    gap = 4
    for i in range(num_bars):
        h = int(5 + (max_h - 5) * (0.5 + 0.5 * math.sin(phase + i * 0.75)))
        bx = x_start + i * (bar_w + gap)
        draw.rounded_rectangle(
            [bx, y_center - h // 2, bx + bar_w, y_center + h // 2],
            radius=2,
            fill=color,
        )


def bubu_yier_intro_turns():
    """Return the mandatory, source-independent opening for the branded profile."""
    return [
        {
            "speaker": "female",
            "spoken_text": "啊哒哒～啊哒哒哒哒～！谢谢大家对我们的喜欢！",
            "zh_text": "啊哒哒～啊哒哒哒哒～！谢谢大家对我们的喜欢！",
            "en_text": "Thank you for all the love and support!",
            "emotion": "excited",
            "emotion_intensity": 0.86,
            "character_pose": "yier_catchphrase_dash",
            "character_caption": "啊哒哒～谢谢大家！",
            "delivery": {
                "rate": "-6%",
                "pitch": "+2Hz",
                "pause_after_ms": 250,
                "emphasis_terms": ["谢谢大家"],
            },
        },
        {
            "speaker": "male",
            "spoken_text": "感谢「小司在加油」做了这个 Skill——让我们，相遇在科研视频中。",
            "zh_text": "感谢「小司在加油」做了这个 Skill——让我们，相遇在科研视频中。",
            "en_text": "Thanks to Xiao Si Zai Jiayou for creating this Skill and bringing us into research videos.",
            "emotion": "reflective",
            "emotion_intensity": 0.64,
            "character_pose": "bubu_warm_greeting",
            "character_caption": "谢谢，让我们在科研视频中相遇。",
            "delivery": {
                "rate": "-8%",
                "pitch": "-1Hz",
                "pause_after_ms": 350,
                "emphasis_terms": ["小司在加油", "相遇"],
            },
        },
        {
            "speaker": "female",
            "spoken_text": "好啦，开始讲论文吧！",
            "zh_text": "好啦，开始讲论文吧！",
            "en_text": "All right, let us start with the paper!",
            "emotion": "excited",
            "emotion_intensity": 0.72,
            "character_pose": "yier_neutral_intro",
            "character_caption": "开讲啦！",
            "delivery": {
                "rate": "-4%",
                "pitch": "+1Hz",
                "pause_after_ms": 420,
            },
        },
    ]


def _cover_resize(image, size):
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _character_image(pose_info):
    if not pose_info or not pose_info.get("asset_available"):
        return None
    path = pose_info.get("asset_path")
    if not path or not os.path.isfile(path):
        return None
    cached = _CHARACTER_IMAGE_CACHE.get(path)
    if cached is None:
        cached = Image.open(path).convert("RGBA")
        _CHARACTER_IMAGE_CACHE[path] = cached
    return cached.copy()


def paste_character_sprite(canvas, pose_info, box, opacity=255):
    """Fit a transparent pose in ``box`` and return its pasted bounds."""
    sprite = _character_image(pose_info)
    if sprite is None:
        return None
    x0, y0, x1, y1 = [int(value) for value in box]
    sprite.thumbnail((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.LANCZOS)
    if opacity < 255:
        alpha = sprite.getchannel("A").point(lambda value: int(value * opacity / 255))
        sprite.putalpha(alpha)
    x = x0 + (x1 - x0 - sprite.width) // 2
    y = y1 - sprite.height
    canvas.alpha_composite(sprite, (x, y))
    return [x, y, x + sprite.width, y + sprite.height]


def draw_character_stage(canvas, draw, turn, pose_info, listener_pose_info, fonts, box, is_male):
    """Draw the active pose, the listening partner, and the pose's short line."""
    x0, y0, x1, y1 = box
    accent = (251, 146, 60, 235) if is_male else (56, 189, 248, 235)
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=12,
        fill=(15, 31, 54, 238),
        outline=accent,
        width=2,
    )
    emotion = strip_unsupported_emoji((pose_info or {}).get("emotion_zh") or "自然")
    draw.rounded_rectangle([x0 + 10, y0 + 8, x0 + 112, y0 + 38], radius=14, fill=accent)
    draw.text((x0 + 20, y0 + 10), emotion[:7], font=fonts["meta"], fill=(8, 20, 38, 255))

    # The listener remains visible as a soft, smaller silhouette while the
    # speaking character performs the selected action in the foreground.
    paste_character_sprite(canvas, listener_pose_info, [x0 + 4, y0 + 42, x0 + 105, y0 + 145], opacity=120)
    paste_character_sprite(canvas, pose_info, [x0 + 54, y0 + 36, x1 - 8, y1 - 54], opacity=255)

    caption = strip_unsupported_emoji(turn.get("character_caption") or (pose_info or {}).get("caption_zh") or "")
    bubble = [x0 + 10, y1 - 54, x1 - 10, y1 - 10]
    draw.rounded_rectangle(bubble, radius=18, fill=(248, 250, 252, 244), outline=accent, width=2)
    lines = wrap_text(draw, caption, fonts["meta"], (x1 - x0) - 36)
    line = lines[0] if lines else ""
    tb = draw.textbbox((0, 0), line, font=fonts["meta"])
    tx = x0 + (x1 - x0 - (tb[2] - tb[0])) // 2
    draw.text((tx, y1 - 45), line, font=fonts["meta"], fill=(15, 23, 42, 255))


def render_bubu_yier_intro_frame(turn, intro_idx, total_intro, pose_info, listener_pose_info, fonts):
    """Render one branded opening frame before any paper evidence turn."""
    W, H = 1920, 1080
    if not os.path.isfile(BUBU_YIER_INTRO_BACKGROUND):
        raise FileNotFoundError(f"Missing branded intro background: {BUBU_YIER_INTRO_BACKGROUND}")
    background = Image.open(BUBU_YIER_INTRO_BACKGROUND).convert("RGB")
    background = _cover_resize(background, (W, H)).filter(ImageFilter.GaussianBlur(radius=2.2))
    background = ImageEnhance.Brightness(background).enhance(0.48).convert("RGBA")
    canvas = Image.alpha_composite(background, Image.new("RGBA", (W, H), (3, 15, 36, 70)))
    draw = ImageDraw.Draw(canvas, "RGBA")

    draw.rounded_rectangle([42, 34, 205, 82], radius=12, fill=(220, 38, 38, 246))
    draw.text((62, 45), "PAPER-EAR", font=fonts["header"], fill="white")
    draw.text((960, 82), "一二 × 布布 · 科研视频见面礼", font=load_font(FONT_BOLD_CANDIDATES, 50), fill="white", anchor="ma")
    draw.text((960, 152), "两只小熊，把一篇论文讲明白", font=load_font(FONT_BOLD_CANDIDATES, 34), fill=(186, 230, 253, 255), anchor="ma")

    speaker = str(turn.get("speaker", "female")).lower()
    active_is_bubu = speaker == "male"
    yier_pose = listener_pose_info if active_is_bubu else pose_info
    bubu_pose = pose_info if active_is_bubu else listener_pose_info
    yier_opacity = 170 if active_is_bubu else 255
    bubu_opacity = 255 if active_is_bubu else 170
    paste_character_sprite(canvas, yier_pose, [78, 420, 610, 1025], opacity=yier_opacity)
    paste_character_sprite(canvas, bubu_pose, [1310, 420, 1842, 1025], opacity=bubu_opacity)

    card = [535, 318, 1385, 850]
    accent = (251, 146, 60, 245) if active_is_bubu else (56, 189, 248, 245)
    draw.rounded_rectangle(card, radius=42, fill=(5, 22, 48, 236), outline=accent, width=4)
    speaker_name = "布布 · 男声追问" if active_is_bubu else "一二 · 女声主讲"
    draw.rounded_rectangle([590, 362, 930, 420], radius=27, fill=accent)
    draw.text((615, 375), speaker_name, font=fonts["speaker"], fill=(7, 19, 38, 255))

    zh_text = strip_unsupported_emoji(turn.get("zh_text") or turn.get("spoken_text") or "")
    zh_lines = wrap_text(draw, zh_text, load_font(FONT_BOLD_CANDIDATES, 43), 720)
    sy = 470
    for line in zh_lines[:4]:
        draw.text((960, sy), line, font=load_font(FONT_BOLD_CANDIDATES, 43), fill="white", anchor="ma")
        sy += 66
    en_text = strip_unsupported_emoji(turn.get("en_text") or "")
    en_lines = wrap_text(draw, en_text, fonts["sub_en"], 700)
    for line in en_lines[:2]:
        draw.text((960, sy + 8), line, font=fonts["sub_en"], fill=(186, 230, 253, 255), anchor="ma")
        sy += 32

    for dot_idx in range(total_intro):
        x = 920 + dot_idx * 40
        fill = accent if dot_idx == intro_idx else (100, 116, 139, 210)
        draw.ellipse([x, 890, x + 18, 908], fill=fill)
    draw.text((960, 960), "AI 合成 · 非官方配音 · 学习与研究演示", font=fonts["meta"], fill=(203, 213, 225, 255), anchor="ma")
    return canvas.convert("RGB")


def render_frame(
    page_img,
    turn,
    turn_idx,
    total_turns,
    paper_title,
    male_name,
    female_name,
    red_box,
    fonts,
    pose_info=None,
    listener_pose_info=None,
    pulse_phase=0.0,
):
    W, H = 1920, 1080
    canvas = Image.new("RGBA", (W, H), (15, 23, 42, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 1. Top Header Bar
    draw.rectangle([0, 0, W, 56], fill=(30, 41, 59, 255))
    draw.rounded_rectangle([24, 12, 146, 44], radius=6, fill=(220, 38, 38, 255))
    draw.text((35, 14), "PAPER-EAR", font=fonts["badge"], fill=(255, 255, 255, 255))
    clean_title = strip_unsupported_emoji(paper_title)
    title_str = f"组会双语精读  |  {clean_title[:60]}"
    draw.text((162, 12), title_str, font=fonts["header"], fill=(248, 250, 252, 255))
    section_tag = strip_unsupported_emoji(turn.get("section_tag") or f"Page {turn.get('page', 1)}")
    prog_str = f"{section_tag}  •  Turn {turn_idx + 1}/{total_turns}"
    pb = draw.textbbox((0, 0), prog_str, font=fonts["meta"])
    draw.text((W - (pb[2] - pb[0]) - 28, 15), prog_str, font=fonts["meta"], fill=(148, 163, 184, 255))

    # 2. Left Panel: PDF Page with Dynamic Red Box (红框)
    left_x, left_y, left_w, left_h = 28, 68, 1140, 812
    draw.rounded_rectangle(
        [left_x, left_y, left_x + left_w, left_y + left_h],
        radius=12,
        fill=(30, 41, 59, 255),
        outline=(51, 65, 85, 255),
        width=2,
    )

    pw, ph = page_img.size
    scale = min((left_w - 32) / pw, (left_h - 32) / ph)
    disp_w, disp_h = int(pw * scale), int(ph * scale)
    ox = left_x + (left_w - disp_w) // 2
    oy = left_y + (left_h - disp_h) // 2

    resized_page = page_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS).convert("RGBA")

    if red_box and len(red_box) == 4:
        nx0, ny0, nx1, ny1 = [max(0.0, min(1.0, float(v))) for v in red_box]
        if nx1 > nx0 and ny1 > ny0:
            dim_overlay = Image.new("RGBA", (disp_w, disp_h), (15, 23, 42, 52))
            bx0, by0 = int(nx0 * disp_w), int(ny0 * disp_h)
            bx1, by1 = int(nx1 * disp_w), int(ny1 * disp_h)
            pad = 6
            bx0, by0 = max(0, bx0 - pad), max(0, by0 - pad)
            bx1, by1 = min(disp_w, bx1 + pad), min(disp_h, by1 + pad)
            dim_draw = ImageDraw.Draw(dim_overlay, "RGBA")
            dim_draw.rectangle([bx0, by0, bx1, by1], fill=(229, 57, 53, 24))
            resized_page = Image.alpha_composite(resized_page, dim_overlay)

    canvas.paste(resized_page, (ox, oy))

    crop_img = None
    if red_box and len(red_box) == 4:
        nx0, ny0, nx1, ny1 = [max(0.0, min(1.0, float(v))) for v in red_box]
        if nx1 > nx0 and ny1 > ny0:
            bx0 = ox + int(nx0 * disp_w) - 6
            by0 = oy + int(ny0 * disp_h) - 6
            bx1 = ox + int(nx1 * disp_w) + 6
            by1 = oy + int(ny1 * disp_h) + 6

            pulse_alpha = int(200 + 55 * math.sin(pulse_phase))
            draw.rounded_rectangle(
                [bx0 - 4, by0 - 4, bx1 + 4, by1 + 4],
                radius=6,
                outline=(255, 82, 82, 115),
                width=4,
            )
            draw.rounded_rectangle(
                [bx0, by0, bx1, by1],
                radius=4,
                outline=(229, 57, 53, pulse_alpha),
                width=4,
            )
            draw_corner_brackets(draw, bx0 - 2, by0 - 2, bx1 + 2, by1 + 2, (255, 59, 48, 255), length=18, width=5)

            clean_box_lbl = strip_unsupported_emoji(turn.get("box_label") or "当前讲解区域 / Focus Area")
            box_label = f"▶ #{turn_idx + 1}  {clean_box_lbl}"
            lb = draw.textbbox((0, 0), box_label, font=fonts["badge"])
            lw, lh = lb[2] - lb[0] + 20, lb[3] - lb[1] + 10
            tag_y = by0 - lh - 5 if by0 - lh - 5 > left_y + 4 else by1 + 5
            draw.rounded_rectangle(
                [bx0, tag_y, bx0 + lw, tag_y + lh],
                radius=6,
                fill=(220, 38, 38, 248),
            )
            draw.text((bx0 + 10, tag_y + 3), box_label, font=fonts["badge"], fill=(255, 255, 255, 255))

            cx0 = max(0, int(nx0 * pw) - 14)
            cy0 = max(0, int(ny0 * ph) - 14)
            cx1 = min(pw, int(nx1 * pw) + 14)
            cy1 = min(ph, int(ny1 * ph) + 14)
            if cx1 > cx0 + 10 and cy1 > cy0 + 10:
                crop_img = page_img.crop((cx0, cy0, cx1, cy1))

    # 3. Right Panel: Speakers + Zoomed Red-Box Callout + Term Card
    rx, ry, rw = 1192, 68, 700
    speaker = turn.get("speaker", "female").lower()
    is_male = speaker == "male"

    clean_female = strip_unsupported_emoji(female_name)
    clean_male = strip_unsupported_emoji(male_name)

    # Female speaker card
    f_box = [rx, ry, rx + 340, ry + 98]
    f_bg = (23, 47, 115, 255) if not is_male else (30, 41, 59, 255)
    f_border = (56, 189, 248, 255) if not is_male else (71, 85, 105, 255)
    draw.rounded_rectangle(f_box, radius=10, fill=f_bg, outline=f_border, width=3 if not is_male else 1)
    draw.text((rx + 16, ry + 14), f"● {clean_female}", font=fonts["speaker"], fill=(255, 255, 255, 255))
    f_status = "▶ 正在主讲 (Speaking)" if not is_male else "○ 倾听中 (Listening)"
    draw.text((rx + 16, ry + 54), f_status, font=fonts["meta"], fill=(125, 211, 252, 255) if not is_male else (148, 163, 184, 255))
    if not is_male:
        draw_soundwave_bars(draw, rx + 245, ry + 64, 9, 26, (56, 189, 248, 255), pulse_phase)

    # Male speaker card
    m_box = [rx + 356, ry, rx + rw, ry + 98]
    m_bg = (124, 45, 18, 255) if is_male else (30, 41, 59, 255)
    m_border = (251, 146, 60, 255) if is_male else (71, 85, 105, 255)
    draw.rounded_rectangle(m_box, radius=10, fill=m_bg, outline=m_border, width=3 if is_male else 1)
    draw.text((rx + 372, ry + 14), f"◆ {clean_male}", font=fonts["speaker"], fill=(255, 255, 255, 255))
    m_status = "▶ 提问/思辨 (Speaking)" if is_male else "○ 倾听中 (Listening)"
    draw.text((rx + 372, ry + 54), m_status, font=fonts["meta"], fill=(253, 186, 116, 255) if is_male else (148, 163, 184, 255))
    if is_male:
        draw_soundwave_bars(draw, rx + 602, ry + 64, 9, 26, (251, 146, 60, 255), pulse_phase)

    # Red-Box Zoomed Preview Panel
    zy = ry + 114
    zh = 372
    draw.rounded_rectangle(
        [rx, zy, rx + rw, zy + zh],
        radius=12,
        fill=(30, 41, 59, 255),
        outline=(229, 57, 53, 220),
        width=2,
    )
    draw.text(
        (rx + 18, zy + 12),
        "■ 红框区域放大视图 (Highlighted Region Zoom)",
        font=fonts["card_title"],
        fill=(252, 165, 165, 255),
    )
    if crop_img is not None:
        cw, ch = crop_img.size
        c_scale = min((rw - 36) / cw, (zh - 64) / ch)
        cdw, cdh = max(1, int(cw * c_scale)), max(1, int(ch * c_scale))
        c_resized = crop_img.resize((cdw, cdh), Image.Resampling.LANCZOS)
        cox = rx + (rw - cdw) // 2
        coy = zy + 48 + (zh - 56 - cdh) // 2
        canvas.paste(c_resized, (cox, coy))
        draw.rectangle([cox - 2, coy - 2, cox + cdw + 2, coy + cdh + 2], outline=(229, 57, 53, 255), width=2)

    # Key Point & Technical Term Card
    ty = zy + zh + 16
    th = (left_y + left_h) - ty
    draw.rounded_rectangle(
        [rx, ty, rx + rw, ty + th],
        radius=12,
        fill=(30, 41, 59, 255),
        outline=(56, 189, 248, 160),
        width=2,
    )
    raw_ct = strip_unsupported_emoji(turn.get("card_title") or "核心要点与专业名词解析 (Key Notes & Terms)")
    card_title = f"★ {raw_ct}"
    draw.text((rx + 20, ty + 14), card_title, font=fonts["card_title"], fill=(56, 189, 248, 255))

    notes = turn.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]
    if not notes and turn.get("box_label"):
        notes = [f"当前聚焦：{strip_unsupported_emoji(turn.get('box_label'))}"]

    character_stage_enabled = bool(pose_info)
    notes_width = 390 if character_stage_enabled else rw - 40
    ny_cursor = ty + 52
    for note in notes[:4]:
        clean_note = strip_unsupported_emoji(note)
        wrapped = wrap_text(draw, f"• {clean_note}", fonts["notes"], notes_width)
        for ln in wrapped[:3]:
            if ny_cursor + 28 > ty + th - 12:
                break
            draw.text((rx + 20, ny_cursor), ln, font=fonts["notes"], fill=(226, 232, 240, 255))
            ny_cursor += 30
        ny_cursor += 6

    if character_stage_enabled:
        draw_character_stage(
            canvas,
            draw,
            turn,
            pose_info,
            listener_pose_info,
            fonts,
            [rx + 426, ty + 44, rx + rw - 14, ty + th - 12],
            is_male,
        )

    # 4. Bottom Panel: Bilingual Subtitles (中英双语字幕) + Progress Bar
    sub_y = 892
    draw.rounded_rectangle(
        [28, sub_y, W - 28, H - 22],
        radius=12,
        fill=(9, 14, 26, 248),
        outline=(71, 85, 105, 200),
        width=2,
    )

    speaker_badge = f"[{clean_male}]" if is_male else f"[{clean_female}]"
    zh_line = f"{speaker_badge} {strip_unsupported_emoji(turn.get('zh_text', ''))}"
    en_line = strip_unsupported_emoji(turn.get("en_text", ""))

    zh_wrapped = wrap_text(draw, zh_line, fonts["sub_zh"], W - 100)
    en_wrapped = wrap_text(draw, en_line, fonts["sub_en"], W - 100)

    sy = sub_y + 14
    zh_color = (253, 186, 116, 255) if is_male else (254, 240, 138, 255)
    for ln in zh_wrapped[:2]:
        draw.text((48, sy), ln, font=fonts["sub_zh"], fill=zh_color)
        sy += 36

    sy += 4
    for ln in en_wrapped[:2]:
        draw.text((48, sy), ln, font=fonts["sub_en"], fill=(186, 230, 253, 255))
        sy += 29

    # Bottom timeline progress bar
    prog_ratio = (turn_idx + 1) / float(max(1, total_turns))
    bar_x0, bar_x1, bar_y = 36, W - 36, H - 12
    draw.rounded_rectangle([bar_x0, bar_y - 3, bar_x1, bar_y + 3], radius=3, fill=(51, 65, 85, 255))
    fill_x1 = bar_x0 + int((bar_x1 - bar_x0) * prog_ratio)
    draw.rounded_rectangle([bar_x0, bar_y - 3, fill_x1, bar_y + 3], radius=3, fill=(229, 57, 53, 255))

    return canvas.convert("RGB")


def encode_still_segment(frame_path, wav_path, output_path, duration, fps):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            frame_path,
            "-i",
            wav_path,
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(fps),
            "-shortest",
            "-t",
            f"{duration:.2f}",
            output_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def render_video(
    pdf_path,
    script_json_path,
    output_mp4,
    dpi=180,
    fps=12,
    export_gif=None,
    max_turns=None,
    require_tts=False,
    report_json=None,
):
    pdf_path = str(Path(pdf_path).expanduser().resolve(strict=True))
    script_json_path = str(Path(script_json_path).expanduser().resolve(strict=True))
    with open(script_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    with pdfplumber.open(pdf_path) as source_pdf:
        pdf_page_count = len(source_pdf.pages)
    if pdf_page_count < 1:
        raise ValueError("The input PDF contains no pages.")
    input_identity = collect_input_identity(pdf_path, script_json_path, pdf_page_count)

    paper_title = data.get("title", os.path.basename(pdf_path))
    brand_profile = str(data.get("brand_profile") or "").strip().lower()
    branded = brand_profile == BUBU_YIER_BRAND_PROFILE
    source_binding = enforce_document_binding(
        data,
        input_identity,
        script_json_path,
        require_source_document=branded,
    )
    if branded:
        male_name = resolve_bubu_yier_display_name(data, "male")
        female_name = resolve_bubu_yier_display_name(data, "female")
    else:
        male_name = data.get("male_name", "师兄 Alex (提问/思辨)")
        female_name = data.get("female_name", "主讲人 Lin (精读讲解)")
    voice_backend = str(data.get("voice_backend") or "edge-tts").lower()
    if voice_backend not in VOICE_BACKENDS:
        raise ValueError(f"Unsupported voice_backend '{voice_backend}'. Choose one of {sorted(VOICE_BACKENDS)}.")
    if branded and voice_backend != BUBU_YIER_BACKEND:
        raise ValueError(
            f"brand_profile '{BUBU_YIER_BRAND_PROFILE}' requires voice_backend "
            f"'{BUBU_YIER_BACKEND}' so the mandatory cast and opening cannot silently drift."
        )
    voice_profiles = {
        "male": resolve_voice_profile(data, "male"),
        "female": resolve_voice_profile(data, "female"),
    }
    character_library = CharacterLibrary.from_file() if branded else None
    intro_turns = bubu_yier_intro_turns() if branded else []
    turns = data.get("turns", [])
    if not turns:
        raise ValueError("Dialogue script JSON contains no 'turns'.")
    source_turn_count = len(turns)
    if branded:
        for turn_index, turn in enumerate(turns, start=1):
            page = turn.get("page") if isinstance(turn, dict) else None
            if isinstance(page, bool) or not isinstance(page, int):
                raise ValueError(f"Branded turn {turn_index} must declare an integer page number.")
            if page < 1 or page > pdf_page_count:
                raise ValueError(
                    f"Branded turn {turn_index} targets page {page}, but the current PDF has "
                    f"pages 1..{pdf_page_count}. Refusing to clamp it to a different evidence page."
                )
        preflight_bubu_yier_brand_references(voice_profiles)
        enforce_bubu_yier_addressing_contract(
            turns,
            require_bidirectional=15 <= source_turn_count <= 20,
        )
    if max_turns is not None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1.")
        turns = turns[:max_turns]
    if fps < 1:
        raise ValueError("fps must be at least 1.")

    fonts = {
        "header": load_font(FONT_BOLD_CANDIDATES, 24),
        "speaker": load_font(FONT_BOLD_CANDIDATES, 21),
        "card_title": load_font(FONT_BOLD_CANDIDATES, 21),
        "badge": load_font(FONT_BOLD_CANDIDATES, 18),
        "notes": load_font(FONT_REGULAR_CANDIDATES, 20),
        "meta": load_font(FONT_REGULAR_CANDIDATES, 18),
        "sub_zh": load_font(FONT_BOLD_CANDIDATES, 27),
        "sub_en": load_font(FONT_REGULAR_CANDIDATES, 21),
    }

    tmpdir = tempfile.mkdtemp(prefix="paper_ear_")
    gif_frames = []
    try:
        page_prefix = os.path.join(tmpdir, "page")
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), pdf_path, page_prefix], check=True)
        page_files = sorted(
            [os.path.join(tmpdir, fn) for fn in os.listdir(tmpdir) if fn.startswith("page-") and fn.endswith(".png")],
            key=page_file_sort_key,
        )
        if not page_files:
            raise RuntimeError("Failed to render PDF pages via pdftoppm.")
        if len(page_files) != pdf_page_count:
            raise RuntimeError(
                f"PDF page-count drift: pdfplumber found {pdf_page_count} pages but pdftoppm rendered "
                f"{len(page_files)}."
            )

        page_images = [Image.open(p).convert("RGB") for p in page_files]
        segment_files = []
        audio_modes = set()
        audio_mode_by_turn = []
        character_pose_by_turn = []

        # The branded opening is intentionally separate from paper turns.  It
        # never consumes an evidence anchor and is therefore unaffected by
        # --max-turns, which remains a paper-preview control.
        for intro_idx, intro_turn in enumerate(intro_turns):
            speaker = "male" if str(intro_turn.get("speaker", "female")).lower() == "male" else "female"
            listener_speaker = "female" if speaker == "male" else "male"
            pose_info = character_library.select_pose(speaker, intro_turn)
            listener_pose_info = character_library.select_pose(listener_speaker, {})

            wav_path = os.path.join(tmpdir, f"intro_{intro_idx:03d}.wav")
            duration, mode, tts_error, speech_meta = synthesize_turn_audio(
                intro_turn,
                voice_backend,
                voice_profiles[speaker],
                wav_path,
            )
            audio_modes.add(mode)
            intro_audio = {
                "kind": "intro",
                "intro_turn": intro_idx + 1,
                "speaker": speaker,
                "pose": pose_info["id"],
                "mode": mode,
                "duration_seconds": round(duration, 3),
                **speech_meta,
            }
            if tts_error:
                intro_audio["tts_error"] = tts_error
            audio_mode_by_turn.append(intro_audio)
            character_pose_by_turn.append(
                {
                    "kind": "intro",
                    "intro_turn": intro_idx + 1,
                    "speaker": speaker,
                    "pose": pose_info["id"],
                    "caption_zh": intro_turn.get("character_caption") or pose_info["caption_zh"],
                    "selected_by": pose_info["selected_by"],
                }
            )
            if (require_tts or branded) and mode != voice_backend:
                raise RuntimeError(
                    f"Intro turn {intro_idx + 1} fell back to '{mode}'. "
                    f"A publishable run requires '{voice_backend}'. Root cause: {tts_error}"
                )

            intro_frame = render_bubu_yier_intro_frame(
                intro_turn,
                intro_idx,
                len(intro_turns),
                pose_info,
                listener_pose_info,
                fonts,
            )
            frame_path = os.path.join(tmpdir, f"frame_intro_{intro_idx:03d}.png")
            intro_frame.save(frame_path, "PNG")
            if export_gif:
                gif_frames.append(intro_frame.resize((960, 540), Image.Resampling.LANCZOS))

            seg_mp4 = os.path.join(tmpdir, f"seg_intro_{intro_idx:03d}.mp4")
            encode_still_segment(frame_path, wav_path, seg_mp4, duration, fps)
            segment_files.append(seg_mp4)

        for idx, turn in enumerate(turns):
            if branded:
                page_num = turn["page"]
            else:
                page_num = max(1, min(len(page_images), int(turn.get("page", 1))))
            page_img = page_images[page_num - 1]

            red_box = turn.get("red_box")
            search_text = turn.get("search_text")
            if (not red_box or len(red_box) != 4) and search_text:
                red_box = locate_text_bbox_on_page(pdf_path, page_num, search_text)
            elif red_box and search_text and turn.get("auto_refine_box", False):
                auto_box = locate_text_bbox_on_page(pdf_path, page_num, search_text)
                if auto_box:
                    red_box = auto_box
            if not red_box or len(red_box) != 4:
                red_box = [0.08, 0.15, 0.92, 0.45]

            wav_path = os.path.join(tmpdir, f"turn_{idx:03d}.wav")
            speaker = "male" if str(turn.get("speaker", "female")).lower() == "male" else "female"
            pose_info = None
            listener_pose_info = None
            if character_library is not None:
                listener_speaker = "female" if speaker == "male" else "male"
                pose_info = character_library.select_pose(speaker, turn)
                listener_pose_info = character_library.select_pose(listener_speaker, {})
                character_pose_by_turn.append(
                    {
                        "kind": "paper",
                        "turn": idx + 1,
                        "speaker": speaker,
                        "pose": pose_info["id"],
                        "emotion_zh": pose_info["emotion_zh"],
                        "action_zh": pose_info["action_zh"],
                        "caption_zh": turn.get("character_caption") or pose_info["caption_zh"],
                        "selected_by": pose_info["selected_by"],
                        "used_fallback": pose_info["used_fallback"],
                    }
                )
            duration, mode, tts_error, speech_meta = synthesize_turn_audio(
                turn,
                voice_backend,
                voice_profiles[speaker],
                wav_path,
            )
            audio_modes.add(mode)
            turn_audio = {
                "kind": "paper",
                "turn": idx + 1,
                "speaker": speaker,
                "mode": mode,
                "duration_seconds": round(duration, 3),
                **speech_meta,
            }
            if tts_error:
                turn_audio["tts_error"] = tts_error
            audio_mode_by_turn.append(turn_audio)
            if (require_tts or branded) and mode != voice_backend:
                raise RuntimeError(
                    f"Turn {idx + 1} fell back to '{mode}'. "
                    f"A publishable run requires the configured provider '{voice_backend}'; check credentials, "
                    "connectivity, voice/style compatibility, "
                    f"and narration text. Root cause: {tts_error}"
                )

            frame_a = render_frame(
                page_img,
                turn,
                idx,
                len(turns),
                paper_title,
                male_name,
                female_name,
                red_box,
                fonts,
                pose_info=pose_info,
                listener_pose_info=listener_pose_info,
                pulse_phase=idx * 1.1,
            )
            frame_path = os.path.join(tmpdir, f"frame_{idx:03d}.png")
            frame_a.save(frame_path, "PNG")

            if export_gif:
                gif_frames.append(frame_a.resize((960, 540), Image.Resampling.LANCZOS))
                frame_b = render_frame(
                    page_img,
                    turn,
                    idx,
                    len(turns),
                    paper_title,
                    male_name,
                    female_name,
                    red_box,
                    fonts,
                    pose_info=pose_info,
                    listener_pose_info=listener_pose_info,
                    pulse_phase=idx * 1.1 + 1.6,
                )
                gif_frames.append(frame_b.resize((960, 540), Image.Resampling.LANCZOS))

            seg_mp4 = os.path.join(tmpdir, f"seg_{idx:03d}.mp4")
            encode_still_segment(frame_path, wav_path, seg_mp4, duration, fps)
            segment_files.append(seg_mp4)

        concat_list = os.path.join(tmpdir, "concat.txt")
        with open(concat_list, "w", encoding="utf-8") as cf:
            for seg in segment_files:
                cf.write(f"file '{seg}'\n")

        os.makedirs(os.path.dirname(os.path.abspath(output_mp4)), exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_list,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                FINAL_AUDIO_BITRATE,
                "-af",
                FINAL_AUDIO_FILTER,
                "-movflags",
                "+faststart",
                output_mp4,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if export_gif and gif_frames:
            os.makedirs(os.path.dirname(os.path.abspath(export_gif)), exist_ok=True)
            gif_frames[0].save(
                export_gif,
                save_all=True,
                append_images=gif_frames[1:],
                duration=900,
                loop=0,
                optimize=True,
            )
            print(f"Exported animated GIF preview: {export_gif}")

        if not os.path.exists(output_mp4) or os.path.getsize(output_mp4) < 1024:
            raise RuntimeError("ffmpeg returned successfully but the output MP4 is missing or empty.")

        final_identity = collect_input_identity(pdf_path, script_json_path, pdf_page_count)
        if (
            final_identity["pdf_sha256"] != input_identity["pdf_sha256"]
            or final_identity["script_sha256"] != input_identity["script_sha256"]
        ):
            raise RuntimeError("The input PDF or dialogue script changed during rendering; the output is not trusted.")
        video_sha256 = sha256_file(output_mp4)

        report = {
            "output": os.path.abspath(output_mp4),
            **input_identity,
            "video_sha256": video_sha256,
            "video_hash_mode": RAW_BYTES_HASH_MODE,
            "source_binding": {
                "declared": source_binding["declared"],
                "required": source_binding["required"],
                "verified": source_binding["verified"],
            },
            "brand_profile": brand_profile or None,
            "female_name": female_name,
            "male_name": male_name,
            "resolved_voices": {
                speaker: {
                    "voice": profile.get("voice"),
                    "model": profile.get("model"),
                }
                for speaker, profile in voice_profiles.items()
            },
            "source_turns": source_turn_count,
            "rendered_turns": len(turns),
            "mandatory_intro_turns": len(intro_turns),
            "rendered_segments": len(segment_files),
            "dpi": dpi,
            "fps": fps,
            "require_tts": bool(require_tts or branded),
            "require_tts_requested": bool(require_tts),
            "voice_backend": voice_backend,
            "audio_modes": sorted(audio_modes),
            "audio_mastering": {
                "final_gain_db": FINAL_AUDIO_GAIN_DB,
                "limiter_ceiling_linear": FINAL_AUDIO_LIMITER_CEILING,
                "audio_codec": "aac",
                "audio_bitrate": FINAL_AUDIO_BITRATE,
                "final_audio_reencode": True,
            },
            "turn_audio": audio_mode_by_turn,
            "character_poses": character_pose_by_turn,
            "file_size_bytes": os.path.getsize(output_mp4),
        }
        if report_json:
            os.makedirs(os.path.dirname(os.path.abspath(report_json)), exist_ok=True)
            with open(report_json, "w", encoding="utf-8") as report_file:
                json.dump(report, report_file, ensure_ascii=False, indent=2)
                report_file.write("\n")

        print(
            f"Successfully generated MP4: {output_mp4} "
            f"(intro={len(intro_turns)}, paper_turns={len(turns)}, "
            f"audio_modes={sorted(audio_modes)})"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Render Paper-Ear bilingual dialogue MP4 with red-box tracking.")
    parser.add_argument("--pdf", required=True, help="Input PDF paper path")
    parser.add_argument("--script", required=True, help="Input dialogue JSON script path")
    parser.add_argument("--output", required=True, help="Output MP4 path")
    parser.add_argument("--dpi", type=int, default=180, help="PDF page rendering DPI")
    parser.add_argument("--fps", type=int, default=12, help="Output frame rate")
    parser.add_argument("--max-turns", type=int, default=None, help="Render only the first N turns for a fast preview")
    parser.add_argument(
        "--require-tts",
        action="store_true",
        help="Fail instead of using cadence-only fallback or a provider other than voice_backend",
    )
    parser.add_argument("--export-gif", default=None, help="Optional path to export animated GIF preview")
    parser.add_argument("--report-json", default=None, help="Optional render report JSON path")
    args = parser.parse_args()
    render_video(
        args.pdf,
        args.script,
        args.output,
        dpi=args.dpi,
        fps=args.fps,
        export_gif=args.export_gif,
        max_turns=args.max_turns,
        require_tts=args.require_tts,
        report_json=args.report_json,
    )


if __name__ == "__main__":
    main()
