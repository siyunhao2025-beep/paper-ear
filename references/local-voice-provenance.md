# Local voice provenance and selection

Snapshot date: 2026-10-14. Stars are repository-level GitHub API snapshots, not quality scores for an individual Skill.

| Project | Snapshot | License | Decision |
|---|---:|---|---|
| [AMD Skills](https://github.com/amd/skills) (`local-ai-use`) | 419 stars | MIT | Use its system-wide Lemonade setup pattern. Do not copy its implementation into Paper-Ear. |
| [Lemonade](https://github.com/lemonade-sdk/lemonade) | 5,890 stars | Apache-2.0 | Add its loopback OpenAI-compatible speech endpoint as `lemonade-local`. |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | 13,772 stars | Apache-2.0 | Strong voice design and instruction control, but the surveyed Agent Skill requires an NVIDIA GPU with at least 8 GB VRAM; do not make it the AMD Windows default. |
| [CosyVoice](https://github.com/QwenAudio/CosyVoice) | 23,947 stars | Apache-2.0 | Strong Chinese and instruction-guided speech, but its normal local path is substantially heavier and CUDA-oriented; keep it out of the lightweight default. |
| [MOSS-TTS](https://github.com/OpenMOSS/MOSS-TTS) | evolving 2026 project | Apache-2.0 | Lemonade 2026.41.1 exposes `MOSS-TTS-Local`/`OpenMOSS-TTS` on AMD Vulkan. Offer this as an optional expressive tier because the catalog reports roughly 8.5-12.5 GB, with additional voice-design weights possible. |

## Default local tier

Use Lemonade `kokoro-v1` for zero-key, offline, low-latency previews. The model cache is about 0.354 GB in the tested Lemonade catalog. The following Mandarin presets were synthesized successfully on Windows 11 with Lemonade 2026.41.1:

- Female: `zf_xiaobei`, `zf_xiaoni`, `zf_xiaoxiao`, `zf_xiaoyi`
- Male: `zm_yunjian`, `zm_yunxi`, `zm_yunxia`, `zm_yunyang`

The authoritative [Kokoro voice card](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) identifies these voices and licenses the model under Apache-2.0. It also grades the Mandarin presets D overall, warns that non-English support can be thin, and says very short or very long utterances can degrade. Therefore:

1. Call Kokoro a free offline preview/default, not a guaranteed human-level acting engine.
2. Audition all eight choices with the same 20-80 character line before casting.
3. Improve rhythm with punctuation, clause length, and real question/answer structure; do not claim unsupported emotion controls.
4. Offer MOSS/Azure as an explicit quality upgrade when the user needs stronger acting.

## Privacy and redistribution

- Keep Lemonade and model weights in the user's system cache; never commit them.
- Send only the final narration string to the loopback endpoint. Do not send the PDF, page images, extracted paper text, visual crops, local paths, or credentials.
- Reject non-loopback Lemonade endpoints unless the user explicitly enables `PAPER_EAR_ALLOW_REMOTE_LEMONADE=1` after approving the privacy boundary.
- Do not bundle downloaded voice-model weights into the MIT Paper-Ear repository. Link to upstream sources and retain their licenses independently.
- Do not enable voice cloning from a real person's sample without explicit authorization for that voice.
