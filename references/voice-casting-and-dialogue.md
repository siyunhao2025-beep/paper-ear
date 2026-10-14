# Voice Casting and Evidence-Dialogue Guide

This guide adds human-sounding delivery without turning a paper review into staged banter. The default is Azure Speech because it supports SSML speaking styles, style intensity, prosody, pauses, and emphasis. Edge TTS remains a lightweight option for ordinary narration, but it cannot provide the same per-turn style control.

Official references:

- [Azure Speech language and voice support](https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=tts)
- [Azure SSML voice, style, and role controls](https://learn.microsoft.com/azure/ai-services/speech-service/speech-synthesis-markup-voice)
- [Azure Speech REST text-to-speech API](https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech)

## Default cast

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
| `azure-speech` | The user wants emotions, speaking styles, pauses, emphasis, and consistent casting. | Requires an Azure Speech key/region and sends final narration text to Azure. |
| `edge-tts` | The user wants a quick, no-key neural narration preview. | Supports voice/rate/volume/pitch but not custom expressive SSML styles. |
| `offline-cadence` | Visual timing only. | It is not intelligible speech and must never be presented as finished narration. |

## Privacy boundary

The online TTS request may contain only the final narration string plus SSML controls. Never send the PDF, page images, extracted full text, tables, figures, equations, citations, run directory, or local file paths. `render_voice_auditions.py` does not open the source PDF. `render_paper_video.py` reads the PDF locally for frames while sending only each turn's `spoken_text` (or subtitle fallback) to the selected TTS endpoint.

## Configure Azure Speech

Set credentials in the process environment; never put keys in JSON, logs, screenshots, commits, or generated reports.

```powershell
$env:AZURE_SPEECH_KEY = "<your key>"
$env:AZURE_SPEECH_REGION = "<your region, for example eastasia>"
```

The aliases `SPEECH_KEY` and `SPEECH_REGION` are also accepted. `AZURE_SPEECH_ENDPOINT` can replace the region-derived endpoint when a custom full TTS endpoint is required.

Use the voice profile in `examples/sample_voice_casting.json` as the default. Per-turn `delivery` fields override profile defaults.

## Audition before rendering

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

Do not render the full video until both the casting clips and the four-turn interaction preview are approved.

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

For each turn return: speaker, dialogue_act, responds_to_turn, emotion, emotion_intensity, delivery, question_target, interaction_tags, page, evidence_anchor, claim_type, Chinese spoken/subtitle text, English subtitle, red-box target, and concise notes.

Voice default:
- Presenter: zh-CN-XiaoxiaoNeural; chat/serious/excited/calm; normal style_degree <= 1.15.
- Discussant: zh-CN-YunjianNeural; narration-relaxed/serious/documentary-narration; normal style_degree <= 1.15.
- Use pauses and punctuation to communicate thought; never write stage directions such as “愤怒地说” into spoken text.
```
