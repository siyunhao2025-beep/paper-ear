#!/usr/bin/env python3
"""Local F5-TTS adapter for the public BoxAudio-0 Bubu/Yier references.

This module intentionally accepts one final narration string at a time.  It
does not know about PDFs, evidence records, page images, subtitles, or run
directories.  Reference clips and model weights live in user caches (or in
explicitly configured external paths), never in the Paper-Ear repository.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import inspect
import os
import re
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional, Union


BUBU_YIER_BACKEND = "bubu-yier-local"
BUBU_YIER_MODEL = "F5TTS_v1_Base"
BUBU_YIER_DEFAULT_DIR = Path.home() / ".cache" / "paper-ear" / "bubu-yier-f5"
BUBU_YIER_UPSTREAM_COMMIT = "66baffbdd5ba6e2f12efa4067778d420a9f422a7"
BUBU_YIER_UPSTREAM_REPOSITORY = "https://github.com/Boxjod/box2audio-0"
BUBU_YIER_MODEL_SOURCE = "hf://SWivid/F5-TTS/F5TTS_v1_Base"
BUBU_YIER_MODEL_LICENSE = "CC-BY-NC-4.0"

BUBU_YIER_DEFAULT_VOICES = {"female": "yier", "male": "bubu"}
BUBU_YIER_REFERENCE_SPECS = {
    "yier": {
        "filename": "yier_self_introduction.wav",
        "sha256": "190f80be27f1774a29e5443b6db3dfa0961e2e1ec72c4b5e951c042926dbad7b",
        "size": 350478,
        "reference_text": (
            "大家好，我叫一二。听说大家都在问我，为什么叫一二？"
            "下面我来介绍一下我的来历吧。"
        ),
    },
    "bubu": {
        "filename": "bubu_self_introduction.wav",
        "sha256": "47ba63de2a8efeb84d901c684c7fcf525d2b11f8af209916609f3c89caef3431",
        "size": 336078,
        "reference_text": (
            "大家好，我叫布布，上个视频，第二宝做了自我介绍，"
            "我也给大家做个自我介绍吧。"
        ),
    },
}

_F5_RUNTIMES: dict[tuple[str, ...], object] = {}


def sha256_file(path: Union[os.PathLike, str]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expanded_path(value: object) -> str:
    return os.path.abspath(os.path.expanduser(str(value)))


def _validated_optional_file(value: object, label: str) -> str:
    if value in (None, ""):
        return ""
    path = _expanded_path(value)
    if not os.path.isfile(path):
        raise RuntimeError(f"Configured F5-TTS {label} does not exist: {path}")
    return path


def _validated_optional_dir(value: object, label: str, must_exist: bool = True) -> str:
    if value in (None, ""):
        return ""
    path = _expanded_path(value)
    if must_exist and not os.path.isdir(path):
        raise RuntimeError(f"Configured F5-TTS {label} does not exist: {path}")
    return path


def resolve_reference(voice_profile: Optional[dict]) -> dict[str, object]:
    """Resolve and verify one external reference clip without network access."""
    profile = voice_profile if isinstance(voice_profile, dict) else {}
    voice = str(profile.get("voice") or "").strip().lower()
    if voice not in BUBU_YIER_REFERENCE_SPECS:
        raise RuntimeError(
            f"Voice '{voice}' is not supported by {BUBU_YIER_BACKEND}; "
            f"choose one of {sorted(BUBU_YIER_REFERENCE_SPECS)}."
        )
    spec = BUBU_YIER_REFERENCE_SPECS[voice]
    explicit_audio = profile.get("reference_audio")
    reference_dir = (
        os.environ.get("PAPER_EAR_BUBU_YIER_DIR")
        or profile.get("reference_dir")
        or BUBU_YIER_DEFAULT_DIR
    )
    audio_path = _expanded_path(
        explicit_audio or os.path.join(str(reference_dir), str(spec["filename"]))
    )
    if not os.path.isfile(audio_path):
        raise RuntimeError(
            f"Reference audio for '{voice}' is missing: {audio_path}. Run "
            "'python scripts/setup_bubu_yier_voice.py' or configure "
            "voice_profiles.<role>.reference_audio."
        )

    configured_hash = str(profile.get("reference_sha256") or "").strip().lower()
    if explicit_audio and not configured_hash:
        raise RuntimeError(
            "An explicit reference_audio requires reference_sha256 so Paper-Ear can "
            "verify the exact approved recording."
        )
    expected_hash = configured_hash or ("" if explicit_audio else str(spec["sha256"]))
    if expected_hash and not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise RuntimeError("reference_sha256 must contain exactly 64 hexadecimal characters.")
    actual_hash = sha256_file(audio_path)
    if expected_hash and actual_hash != expected_hash:
        raise RuntimeError(
            f"Reference audio checksum mismatch for '{voice}': expected "
            f"{expected_hash}, got {actual_hash}."
        )

    reference_text = str(
        profile.get("reference_text") or spec["reference_text"]
    ).strip()
    if not reference_text:
        raise RuntimeError(f"Reference text for '{voice}' must not be empty.")
    return {
        "voice": voice,
        "audio_path": audio_path,
        "reference_text": reference_text,
        "sha256": actual_hash,
        "verified": bool(expected_hash),
        "source": (
            f"{BUBU_YIER_UPSTREAM_REPOSITORY}/blob/"
            f"{BUBU_YIER_UPSTREAM_COMMIT}/assets/audio/{spec['filename']}"
            if not explicit_audio
            else "configured-local-reference"
        ),
    }


def resolve_f5_options(voice_profile: Optional[dict]) -> dict[str, str]:
    """Resolve optional external model/cache paths and validate explicit ones."""
    profile = voice_profile if isinstance(voice_profile, dict) else {}
    model = str(profile.get("model") or BUBU_YIER_MODEL).strip()
    if model != BUBU_YIER_MODEL:
        raise RuntimeError(
            f"{BUBU_YIER_BACKEND} requires model '{BUBU_YIER_MODEL}', not '{model}'."
        )
    return {
        "model": model,
        "ckpt_file": _validated_optional_file(
            os.environ.get("PAPER_EAR_F5_CHECKPOINT") or profile.get("checkpoint_path") or profile.get("ckpt_file"),
            "checkpoint",
        ),
        "vocab_file": _validated_optional_file(
            os.environ.get("PAPER_EAR_F5_VOCAB") or profile.get("vocab_path") or profile.get("vocab_file"),
            "vocabulary file",
        ),
        "vocoder_local_path": _validated_optional_dir(
            os.environ.get("PAPER_EAR_F5_VOCODER_DIR") or profile.get("vocoder_dir") or profile.get("vocoder_local_path"),
            "vocoder directory",
        ),
        "hf_cache_dir": _validated_optional_dir(
            os.environ.get("PAPER_EAR_F5_HF_CACHE_DIR") or profile.get("hf_cache_dir"),
            "Hugging Face cache directory",
            must_exist=False,
        ),
        "device": str(os.environ.get("PAPER_EAR_F5_DEVICE") or profile.get("device") or "").strip(),
    }


def _patch_torchaudio_load() -> None:
    """Add BoxAudio's SoundFile fallback for torchaudio builds needing torchcodec."""
    try:
        import torchaudio
    except ImportError:
        return
    if getattr(torchaudio.load, "_paper_ear_soundfile_fallback", False):
        return
    original_load = torchaudio.load

    def patched_load(uri, *args, **kwargs):
        try:
            return original_load(uri, *args, **kwargs)
        except (ImportError, RuntimeError):
            import soundfile as sf
            import torch

            data, sample_rate = sf.read(uri, dtype="float32", always_2d=True)
            waveform = torch.from_numpy(data.T)
            frame_offset = max(0, int(kwargs.get("frame_offset", 0) or 0))
            num_frames = int(kwargs.get("num_frames", -1) or -1)
            waveform = waveform[:, frame_offset:]
            if num_frames > 0:
                waveform = waveform[:, :num_frames]
            if kwargs.get("channels_first", True) is False:
                waveform = waveform.T
            return waveform, sample_rate

    patched_load._paper_ear_soundfile_fallback = True
    torchaudio.load = patched_load


def _load_f5_runtime(voice_profile: Optional[dict]):
    options = resolve_f5_options(voice_profile)
    cache_key = tuple(options[key] for key in sorted(options))
    cached = _F5_RUNTIMES.get(cache_key)
    if cached is not None:
        return cached, options
    try:
        _patch_torchaudio_load()
        from f5_tts.api import F5TTS
    except ImportError as exc:
        raise RuntimeError(
            "F5-TTS dependencies are missing. Install the optional backend with "
            "'python -m pip install -r requirements-bubu-yier.txt'."
        ) from exc

    candidate_kwargs = {
        "model": options["model"],
        "ckpt_file": options["ckpt_file"],
        "vocab_file": options["vocab_file"],
        "vocoder_local_path": options["vocoder_local_path"],
        "device": options["device"],
        "hf_cache_dir": options["hf_cache_dir"],
    }
    supported = inspect.signature(F5TTS).parameters
    init_kwargs = {
        key: value
        for key, value in candidate_kwargs.items()
        if key in supported and value not in (None, "")
    }
    engine = F5TTS(**init_kwargs)
    _F5_RUNTIMES[cache_key] = engine
    return engine, options


def rate_to_speed(rate: object) -> float:
    if isinstance(rate, (int, float)) and not isinstance(rate, bool):
        return max(0.3, min(2.0, float(rate)))
    match = re.fullmatch(r"([+-])(\d+)%", str(rate or "+0%").strip())
    if not match:
        return 1.0
    delta = int(match.group(2)) / 100.0
    return max(0.3, min(2.0, 1.0 + delta if match.group(1) == "+" else 1.0 - delta))


def _pad_pcm_wav(path: str, before_ms: int = 0, after_ms: int = 0) -> None:
    before_ms = max(0, int(before_ms or 0))
    after_ms = max(0, int(after_ms or 0))
    if not before_ms and not after_ms:
        return
    padded = path + ".padded.wav"
    try:
        with wave.open(path, "rb") as source:
            params = source.getparams()
            frames = source.readframes(source.getnframes())
        bytes_per_frame = params.nchannels * params.sampwidth
        prefix = b"\x00" * int(params.framerate * before_ms / 1000.0) * bytes_per_frame
        suffix = b"\x00" * int(params.framerate * after_ms / 1000.0) * bytes_per_frame
        with wave.open(padded, "wb") as target:
            target.setparams(params)
            target.writeframes(prefix + frames + suffix)
        os.replace(padded, path)
    finally:
        if os.path.exists(padded):
            os.remove(padded)


def _write_pcm_wav(samples, sample_rate: int, out_wav: str, trim_silence: bool) -> None:
    import numpy as np
    import soundfile as sf

    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=-1 if audio.shape[-1] <= 2 else 0)
    if not audio.size:
        raise RuntimeError("F5-TTS returned an empty audio array.")

    raw_path = out_wav + ".f5.raw.wav"
    sf.write(raw_path, audio, int(sample_rate), subtype="PCM_16")
    ffmpeg = shutil.which("ffmpeg")
    if trim_silence and ffmpeg:
        silence_filter = (
            "silenceremove=start_periods=1:start_duration=0:start_threshold=-40dB,"
            "areverse,"
            "silenceremove=start_periods=1:start_duration=0:start_threshold=-40dB,"
            "areverse"
        )
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                raw_path,
                "-af",
                silence_filter,
                "-ar",
                str(int(sample_rate)),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                out_wav,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0 and os.path.isfile(out_wav) and os.path.getsize(out_wav) > 44:
            os.remove(raw_path)
            return
    os.replace(raw_path, out_wav)


def synthesize_bubu_yier(
    text: str,
    voice_profile: dict,
    delivery: dict,
    out_wav: str,
) -> dict[str, object]:
    """Synthesize exactly one final ``spoken_text`` string on-device."""
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Final spoken_text must be a non-empty string.")
    reference = resolve_reference(voice_profile)
    engine, options = _load_f5_runtime(voice_profile)
    seed = voice_profile.get("seed", 42)
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        seed = 42

    candidate_kwargs = {
        "ref_file": reference["audio_path"],
        "ref_text": reference["reference_text"],
        "gen_text": text,
        "speed": rate_to_speed(delivery.get("rate")),
        "seed": seed,
    }
    supported = inspect.signature(engine.infer).parameters
    infer_kwargs = {key: value for key, value in candidate_kwargs.items() if key in supported}
    # F5-TTS prints the reference/generated text and a tqdm bar.  On Windows,
    # the parent console may still use GBK, which raises UnicodeEncodeError for
    # perfectly valid paper notation such as O(N²).  The renderer does not need
    # that third-party progress stream, so capture it in Unicode-safe buffers.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        samples, sample_rate, _ = engine.infer(**infer_kwargs)
    _write_pcm_wav(
        samples,
        int(sample_rate),
        out_wav,
        bool(voice_profile.get("trim_silence", True)),
    )
    _pad_pcm_wav(
        out_wav,
        delivery.get("pause_before_ms", 0),
        delivery.get("pause_after_ms", 0),
    )
    return {
        "model": options["model"],
        "model_source": BUBU_YIER_MODEL_SOURCE,
        "model_license": BUBU_YIER_MODEL_LICENSE,
        "language": "zh-CN",
        "g2p": "f5-tts-native",
        "endpoint_scope": "on-device",
        "input_scope": "spoken_text-only",
        "voice_design": False,
        "reference_conditioning": True,
        "reference_voice": reference["voice"],
        "reference_sha256": reference["sha256"],
        "reference_verified": reference["verified"],
        "reference_source": reference["source"],
        "seed": seed,
    }
