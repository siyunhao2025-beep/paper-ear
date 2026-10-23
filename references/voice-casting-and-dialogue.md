# Voice Casting and Evidence-Dialogue Guide

This guide adds human-sounding delivery without turning a paper review into staged banter. Prefer `kokoro-zh-local` with the dedicated Kokoro v1.1-zh model and Misaki Chinese frontend when the user wants free, account-free, offline Mandarin. Use Azure Speech or the optional local MOSS tier when stronger acting and fine-grained voice direction matter. Edge TTS remains a lightweight online alternative, but it cannot provide the same per-turn style control.

Official references:

- [AMD local-ai-use Skill](https://github.com/amd/skills/tree/main/skills/local-ai-use)
- [Kokoro ONNX dedicated Chinese example](https://github.com/thewh1teagle/kokoro-onnx/blob/main/examples/chinese.py)
- [Kokoro-82M-v1.1-zh model](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh)
- [Lemonade OpenAI-compatible speech endpoint](https://github.com/lemonade-sdk/lemonade/blob/main/docs/api/openai.md)
- [Kokoro voice card](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)
- [MOSS-TTS](https://github.com/OpenMOSS/MOSS-TTS)
- [Azure Speech language and voice support](https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts)
- [Azure SSML voice, style, and role controls](https://learn.microsoft.com/azure/ai-services/speech-service/speech-synthesis-markup-voice)
- [Azure Speech REST text-to-speech API](https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech)

## Default local cast

| Role | Voice | Delivery arc | Why it fits |
|---|---|---|---|
| Presenter | `zf_090` | punctuation + concise clauses + evidence pivots | Balanced female candidate from the dedicated Chinese voice pack; no account or key required. |
| Discussant | `zm_033` | short challenges + deliberate pauses + follow-ups | Lower, stronger male candidate with clear acoustic contrast. |

These are starting points, not objective winners. Run `render_local_voice_menu.py` and let the user compare all eight candidates. The menu's measurements do not replace a listening decision: a voice is approved only after the user can understand every word. The user should return to the same chat and reply with both A–D labels or full voice IDs; do not ask them to download or edit a configuration file. The dedicated Chinese path is not a human-level emotional acting engine. See [local-voice-provenance.md](local-voice-provenance.md).

## Azure expressive cast

| Role | Voice | Delivery arc | Why it fits |
|---|---|---|---|
| Presenter | `zh-CN-XiaoxiaoNeural` | `chat → serious → excited → calm` | Warm, clear, and capable of marking an evidence pivot without sounding like an announcer. |
| Discussant | `zh-CN-YunjianNeural` | `narration-relaxed → serious → documentary-narration` | A lower, firmer voice that can challenge a claim and later concede without becoming theatrical. |

Keep normal turns at `style_degree <= 1.15` and reserve `1.16–1.30` for a decisive challenge, discovery, or conclusion. Values above that range often sound performed rather than conversational. Azure currently documents native word-level `<emphasis>` tuning for only three English voices, so Paper-Ear renders `emphasis_terms` on the default Chinese voices as a conservative local rate/pitch cue instead of claiming unsupported native emphasis.

## Useful voice alternatives

These are casting directions, not promises that every style works with every voice. Check the current Microsoft voice table before synthesis.

| Role direction | Voice | Character |
|---|---|---|
| Warm senior presenter | `zh-CN-XiaoxiaoNeural` | Warm, fluent, broad style support. |
| Lively junior presenter | `zh-CN-XiaoyiNeural` | Brighter and quicker; suitable for approachable explainers. |
| Passionate defense discussant | `zh-CN-YunjianNeural` | Strong challenge energy; use intensity sparingly. |
| Young curious discussant | `zh-CN-YunxiNeural` | Lively, conversational, good for follow-up questions. |
| Calm professional discussant | `zh-CN-YunyangNeural` | Reliable broadcast/professional quality; less confrontational. |
| Youthful explainer | `zh-CN-YunxiaNeural` | Cute/young character; usually unsuitable for a formal expert review. |

Dialect voices can be offered as an optional creative choice, but do not make them the academic default. Voice names and supported styles change over time; validate them against the official service before a paid render.

## Provider choice

| Provider | Use when | Limitation |
|---|---|---|
| `kokoro-zh-local` + `kokoro-v1.1-zh` | The user wants free, offline, account-free Mandarin and several male/female candidates. | Fixed voices and speed control; no true emotion-style control; requires a one-time ~379 MB model download. |
| `bubu-yier-local` + `F5TTS_v1_Base` | The user has approved the 一二/布布 character cast and accepts an on-device F5-TTS setup. | Uses external reference clips and a substantially larger non-commercial model; rate and punctuation drive delivery, while style labels are not acoustic controls. |
| `lemonade-local` + `MOSS-TTS-Local` or `OpenMOSS-TTS` | The user accepts a much larger local download for stronger expressiveness or voice design on supported hardware. | Roughly 8.5-12.5 GB in the tested catalog, with additional voice-design weights possible; benchmark before promising speed. |
| `azure-speech` | The user wants emotions, speaking styles, pauses, emphasis, and consistent casting. | Requires an Azure Speech key/region and sends final narration text to Azure. |
| `edge-tts` | The user wants a quick, no-key neural narration preview. | Supports voice/rate/volume/pitch but not custom expressive SSML styles. |
| `offline-cadence` | Visual timing only. | It is not intelligible speech and must never be presented as finished narration. |

## Privacy boundary

`kokoro-zh-local` and `bubu-yier-local` run in the current process and upload nothing. A local Lemonade request may contain only the final narration string plus voice controls and must use a loopback endpoint by default. An online TTS request may contain only the final narration string plus SSML controls. Never send the PDF, page images, extracted full text, tables, figures, equations, citations, run directory, or local file paths. `render_voice_auditions.py` and `render_local_voice_menu.py` do not open the source PDF. `render_paper_video.py` reads the PDF locally for frames while exposing only each turn's final `spoken_text` (or subtitle fallback) to the selected speech backend. See [bubu-yier-local-backend.md](bubu-yier-local-backend.md) before enabling the character cast.

## Configure free local speech

Install the Python dependencies, then download and verify the three dedicated Mandarin model files:

```powershell
python -m pip install -r requirements.txt
python scripts/setup_mandarin_voice.py
python scripts/setup_mandarin_voice.py --check-only
```

Generate the eight-option Mandarin menu with one comparison line:

```powershell
python scripts/render_local_voice_menu.py `
  --output-dir .\voice-menu
```

Render the default two-role audition without opening a PDF:

```powershell
python scripts/render_voice_auditions.py `
  --config examples/sample_local_voice_casting.json `
  --output-dir .\local-audition
```

The default cache is `~/.cache/paper-ear/kokoro-zh-v1.1`. Override it with `PAPER_EAR_KOKORO_ZH_DIR` or the profile's `model_dir`. The weights are intentionally not vendored into the repository. Lemonade remains available for optional local models; its default endpoint is `http://127.0.0.1:13305/api/v1`, and a non-loopback endpoint is rejected unless `PAPER_EAR_ALLOW_REMOTE_LEMONADE=1` is explicitly set after the user approves that privacy boundary.

## Configure Azure Speech

Set credentials in the process environment; never put keys in JSON, logs, screenshots, commits, or generated reports.

```powershell
$env:AZURE_SPEECH_KEY = "<your key>"
$env:AZURE_SPEECH_REGION = "<your region, for example eastasia>"
```

The aliases `SPEECH_KEY` and `SPEECH_REGION` are also accepted. `AZURE_SPEECH_ENDPOINT` can replace the region-derived endpoint when a custom full TTS endpoint is required.

Use the voice profile in `examples/sample_voice_casting.json` as the default. Per-turn `delivery` fields override profile defaults.

## Audition before rendering

The voice menu is the single routine human pause. Give the user its clickable local `index.html`, then stop while the workflow state is `awaiting_voice_choice`. Accept a natural chat reply such as `女声 D，男声 B` or `女声 zf_090，男声 zm_033`. Once both voices are recorded, continue through the casting clips, interaction preview, full render, and final QA without asking the user to operate scripts or approve each internal checkpoint.

First create a request-only plan. This writes SSML and a manifest but makes no network call:

```bash
python scripts/render_voice_auditions.py \
  --config examples/sample_voice_casting.json \
  --output-dir /tmp/paper-ear-audition \
  --dry-run
```

After credentials are available, render the two casting clips:

```bash
python scripts/render_voice_auditions.py \
  --config examples/sample_voice_casting.json \
  --output-dir /tmp/paper-ear-audition
```

To hear the same lines through the lightweight provider before spending Azure quota, add `--backend edge-tts` and use a separate output directory. This is an A/B reference, not a substitute for approving the configured Azure styles.

For a paper-specific micro-scene, mark four turns with `"audition": true` or pass `--turns 8,9,10,11`. Aim for 45–75 seconds and include this arc:

1. Presenter makes a bounded evidence claim.
2. Discussant challenges the weakest assumption.
3. Presenter answers with a page/figure/number and narrows the claim if needed.
4. Discussant concedes what the evidence supports, then asks the next question.

Do not render the full video until both the casting clips and the four-turn interaction preview pass internal listening and visual QA. Ask the user again only when a failed gate presents a subjective tradeoff that cannot be resolved from their earlier choices.

## Evidence-dialogue writing contract

Set `"interaction_mode": "evidence-dialogue-v2"` to activate the strict interaction gate. For a 15–20 turn standard video, the validator requires:

- at least six substantive question/challenge/follow-up turns;
- at least three follow-ups and two explicit disagreements;
- at least two discovery/surprise moments;
- at least one discussant concession, presenter self-correction, presenter-to-discussant question, and unresolved research question;
- 35–50% question/challenge/follow-up turns;
- no three exposition turns in a row;
- every challenge or follow-up linked to an answer within one or two turns.

These are minimum structural checks, not a license for artificial conflict. A valid challenge must identify the claim, the vulnerable assumption, and what evidence would change the speaker's mind.

### Prompt for rewriting a paper discussion

```text
Turn this evidence map into a rigorous two-person lab meeting, not alternating narration.

Presenter: explains the paper, answers with exact page/figure/table/number anchors, admits uncertainty, and narrows claims when challenged.
Discussant: asks substantive questions about identification, measurement geometry, baselines, controls, alternative explanations, and generalizability. The discussant may disagree, but must concede when the evidence answers the objection.

Use a challenge → evidence answer → follow-up → concession/synthesis rhythm. Every question must be answered within one or two turns. Keep evidence, author interpretation, explainer inference, and critique visibly separate. Never invent a number, mechanism, or causal claim. If the paper cannot answer, label the point unresolved.

For `bubu-yier-v1`, keep the relationship natural and sparse rather than adding a nickname to every turn. 布布 may address 一二 as **一二宝**. 一二 normally says **布布**, may use **臭布布** once for a playful reaction to a sharp question, and may use **香布布** once after a useful correction or well-grounded synthesis. Never reverse these forms. In a complete 15–20-turn dialogue, include at least one correct address in each direction; keep each special nickname to at most one context-appropriate occurrence. Do not insert a nickname inside a formula, number, quotation, evidence label, or the fixed opening.

For each turn return: speaker, dialogue_act, responds_to_turn, emotion, emotion_intensity, delivery, question_target, interaction_tags, page, evidence_anchor, claim_type, Chinese spoken/subtitle text, English subtitle, red-box target, and concise notes.

Voice default:
- Free local presenter: zf_090 on `kokoro-zh-local`; use punctuation, compact clauses, and evidence pivots rather than unsupported style claims.
- Free local discussant: zm_033 on `kokoro-zh-local`; use short challenges, deliberate pauses, and follow-up questions.
- Azure upgrade: zh-CN-XiaoxiaoNeural + zh-CN-YunjianNeural with validated styles and normal style_degree <= 1.15.
- Use pauses and punctuation to communicate thought; never write stage directions such as “愤怒地说” into spoken text.
```
