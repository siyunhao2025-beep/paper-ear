# Local voice provenance and selection

Snapshot date: 2026-10-14. Repository stars are discovery signals, not voice-quality scores. A successful API call or valid WAV is also not evidence that a listener can understand the speech.

| Project | License | Paper-Ear decision |
|---|---|---|
| [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) | MIT | Follow its dedicated Chinese example: Kokoro v1.1-zh plus Misaki `ZHG2P(version="1.1")`. |
| [Kokoro-82M-v1.1-zh](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh) | Apache-2.0 | Default lightweight Mandarin model; keep weights in the user's cache, never in the repository. |
| [Misaki](https://github.com/hexgrad/misaki) / `misaki-fork` | Apache-2.0 | Use its tone-aware v1.1 Chinese frontend instead of eSpeak Mandarin phonemization. |
| [AMD Skills](https://github.com/amd/skills) (`local-ai-use`) | MIT | Retain its local-first/privacy pattern; do not copy its implementation. |
| [Lemonade](https://github.com/lemonade-sdk/lemonade) | Apache-2.0 | Keep the loopback adapter for optional local models such as MOSS, but not as the default Mandarin Kokoro path. |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Apache-2.0 | Strong voice design and instruction control, but the surveyed local path is heavier and GPU-oriented; not the lightweight default. |
| [CosyVoice](https://github.com/FunAudioLLM/CosyVoice) | Apache-2.0 | Strong Chinese and instruction-guided speech, but substantially heavier; not the lightweight default. |
| [MOSS-TTS](https://github.com/OpenMOSS/MOSS-TTS) | Apache-2.0 | Optional expressive local tier. The tested catalog was roughly 8.5–12.5 GB, with additional voice-design weights possible. |
| [F5-TTS](https://github.com/SWivid/F5-TTS) + [BoxAudio-0](https://github.com/Boxjod/box2audio-0) | F5TTS v1 Base: CC-BY-NC-4.0; BoxAudio-0 repository: MIT | Optional `bubu-yier-local` character cast. Keep weights/references outside the repository, verify the pinned reference hashes, and do not infer commercial character/voice rights from public availability. |

## Default Mandarin tier

Use `kokoro-zh-local`, which combines:

- `kokoro-v1.1-zh.onnx` — 325,506,167 bytes;
- `voices-v1.1-zh.bin` — 53,815,880 bytes;
- the upstream v1.1 vocabulary `config.json`;
- `misaki-fork[zh]` with `ZHG2P(version="1.1")`;
- an English eSpeak callable only for embedded Latin terms, while Chinese remains on the Misaki Chinese frontend.

Install and verify all three model files with `scripts/setup_mandarin_voice.py`. The setup script downloads from the official Kokoro ONNX release and Hexgrad model repository, checks the pinned byte sizes and SHA-256 hashes, and stores the files under `~/.cache/paper-ear/kokoro-zh-v1.1` by default. `PAPER_EAR_KOKORO_ZH_DIR` may point to another local cache.

Paper-Ear's eight-option same-line menu uses:

- Female: `zf_001`, `zf_018`, `zf_046`, `zf_090`
- Male: `zm_010`, `zm_033`, `zm_066`, `zm_098`
- Recommended starting pair: `zf_090` presenter + `zm_033` discussant

The descriptions beside the players combine same-line duration, relative RMS loudness, median pitch estimates, and casting judgment. They are not official personality labels. Never render the full paper solely because all eight files were generated. The listener must confirm that the selected pair is understandable.

## Invalidated legacy route

Lemonade 2026.41.1 with `kokoro-v1` and the `zf_xiaobei`/`zm_yunjian` family produced structurally valid audio, but a real listening check found the Mandarin unintelligible. Investigation showed that explicit `lang_code=cmn` produced the same bytes as automatic language selection, while the underlying v1.0 route still relied on the weaker eSpeak Mandarin frontend. Therefore:

1. Do not call that route "tested Mandarin" merely because synthesis returned a WAV.
2. Paper-Ear disables `lemonade-local` + `kokoro-v1` Mandarin by default.
3. `PAPER_EAR_ALLOW_LEGACY_KOKORO_ZH=1` exists only for an explicitly labeled comparison, never for a publishable default.
4. A fresh same-line listening decision is required after changing model, G2P, voice, rate, or text normalization.

## Quality boundary

The dedicated Chinese path improves pronunciation routing; it does not add true emotion or acting controls. Kokoro honors speed, but local `provider_style`, pitch, volume, and emphasis labels remain script/report guidance unless the selected engine explicitly implements them. Natural interaction still depends on concise clauses, semantic pauses, real questions, interruptions in the script structure, evidence-based answers, and role contrast.

Use MOSS or Azure as an explicit quality upgrade when the user needs stronger acting. Do not hide their download, hardware, cost, account, or privacy trade-offs.

## Privacy and redistribution

- Keep model weights in the user's system cache; never commit them.
- On `kokoro-zh-local`, synthesis happens in process and no narration text is uploaded.
- On `bubu-yier-local`, F5-TTS runs in process and receives only each turn's final `spoken_text` plus local controls. See [bubu-yier-local-backend.md](bubu-yier-local-backend.md) for setup, hashes, and licensing limits.
- On a loopback Lemonade model, send only the final narration string plus voice controls. Do not send the PDF, page images, extracted full text, visual crops, local paths, or credentials.
- Reject non-loopback Lemonade endpoints unless the user explicitly enables `PAPER_EAR_ALLOW_REMOTE_LEMONADE=1` after approving that privacy boundary.
- Do not bundle downloaded weights into the MIT Paper-Ear repository. Link to upstream sources and preserve their licenses independently.
- Do not enable voice cloning from a real person's sample without explicit authorization for that voice.
