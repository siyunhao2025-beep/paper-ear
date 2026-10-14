# Dialogue Script Contract

Use this contract for `dialogue_script.json`. The renderer ignores unknown fields, but the validator enforces the evidence and geometry fields used by the Paper Ear workflow.

## Root fields

| Field | Required | Meaning |
|---|---:|---|
| `title` | yes | Exact paper title or a faithful shortened title. |
| `male_name` | yes in strict mode | Display name and role for the discussant. |
| `female_name` | yes in strict mode | Display name and role for the presenter. |
| `male_voice` | one voice source required | Backward-compatible male voice name; `voice_profiles.male.voice` may replace it. |
| `female_voice` | one voice source required | Backward-compatible female voice name; `voice_profiles.female.voice` may replace it. |
| `voice_backend` | no | `edge-tts` (backward-compatible default) or `azure-speech`. |
| `voice_profiles` | recommended for Azure | Female/male voice, default style, emotion-to-style map, and baseline prosody. |
| `interaction_mode` | no | Set to `evidence-dialogue-v2` to enforce real question/answer dynamics. |
| `turns` | yes | Ordered, non-empty array of dialogue turns. |

## Turn fields

| Field | Required | Meaning |
|---|---:|---|
| `page` | yes | 1-indexed PDF page number. |
| `speaker` | yes | `female` or `male`. |
| `zh_text` | yes in strict mode | Chinese subtitle and default spoken text. |
| `en_text` | yes in strict mode | English subtitle. |
| `spoken_text` | no | Optional narration override. When absent, the renderer uses `zh_text`, then `en_text`. |
| `section_tag` | yes in strict mode | Short page/section label shown in the video. |
| `red_box` | conditional | Normalized `[x0, y0, x1, y1]`. Required unless `search_text` can locate the target. |
| `search_text` | recommended | A distinctive source phrase or caption used to find/refine the box. |
| `auto_refine_box` | no | When `true`, replace `red_box` with the matched text box if a match is found. |
| `box_label` | yes in strict mode | Label for the highlighted source region. |
| `card_title` | yes in strict mode | Title of the right-side explanation card. |
| `notes` | yes in strict mode | One to three concise explanation bullets. |
| `claim_type` | yes in strict mode | `paper_evidence`, `author_claim`, `inference`, or `critique`. |
| `source_anchor` | yes in strict mode | Object containing `page`, `kind`, and `label`. |
| `evidence_anchor` | alternative to `source_anchor` | Preferred v2 name for the same page/kind/label evidence object. |
| `dialogue_act` | yes in v2 | `claim`, `challenge`, `evidence_answer`, `followup`, `concession`, or `synthesis`. |
| `responds_to_turn` | yes in v2 | `0` or an earlier 1-based turn number; answers/follow-ups/concessions must link backward. |
| `emotion` | yes in v2 | `neutral`, `curious`, `skeptical`, `serious`, `surprised`, `excited`, or `reflective`. |
| `emotion_intensity` | yes in v2 | Number from `0.0` to `1.0`; semantic guidance, separate from provider style intensity. |
| `delivery` | yes in v2 | Style/prosody/pause/emphasis object described below. |
| `question_target` | for questions | Concrete assumption, result, baseline, or limitation being tested. |
| `interaction_tags` | yes in v2 | Machine-readable quality tags such as `question`, `disagreement`, or `concession`. |

`source_anchor.kind` / `evidence_anchor.kind` must be one of `section`, `figure`, `table`, `equation`, `appendix`, or `page`. Its `page` must match the turn's `page`. Use the paper's printed label when available, such as `Figure 2`, `Table 1`, `Eq. (4)`, or `Section 3.2`.

## Expressive delivery object

```json
{
  "provider_style": "serious",
  "style_degree": 1.12,
  "rate": "-2%",
  "pitch": "-1Hz",
  "volume": "+0%",
  "pause_before_ms": 160,
  "pause_after_ms": 320,
  "emphasis_terms": ["Figure 7", "所有高度"]
}
```

`style_degree` accepts `0.01..2.0`; prefer `<= 1.15` for ordinary turns and `<= 1.30` for a justified peak. Pauses accept `0..5000` milliseconds. Edge TTS uses rate/pitch/volume and ignores Azure-only style semantics; Azure Speech uses the complete SSML delivery object. For the default Chinese voices, `emphasis_terms` are expressed with a slight local slowdown/pitch lift because Azure documents native word-level `<emphasis>` tuning for only a small English-voice subset.

Allowed `interaction_tags` are `question`, `disagreement`, `surprise`, `concession`, `self_correction`, `reverse_question`, and `unresolved`. Use only tags that describe an actual conversational event.

Read [voice-casting-and-dialogue.md](voice-casting-and-dialogue.md) for casting options, the Azure privacy boundary, audition commands, and the v2 interaction-quality gate.

## Claim types

- `paper_evidence`: directly observable definition, method detail, procedure, or reported result.
- `author_claim`: an interpretation or conclusion asserted by the paper's authors.
- `inference`: a pedagogical analogy or conclusion added by the explainer.
- `critique`: an explicit limitation, caveat, or evaluation added by the explainer.

Keep `inference` and `critique` phrasing visibly separate from the authors' results. Anchor them to the source material they interpret, but do not imply that the wording came from the paper.

## Example

```json
{
  "title": "Example Paper",
  "male_name": "师兄 Alex (提问/思辨)",
  "female_name": "主讲人 Lin (精读讲解)",
  "male_voice": "zh-CN-YunxiNeural",
  "female_voice": "zh-CN-XiaoxiaoNeural",
  "turns": [
    {
      "page": 3,
      "section_tag": "Page 3 • Method",
      "speaker": "female",
      "zh_text": "先看 Figure 2：输入经过编码器后，被分到重计算与轻计算两条路径。",
      "en_text": "Figure 2 routes the encoded input through heavy and light computation paths.",
      "search_text": "Figure 2",
      "red_box": [0.08, 0.12, 0.92, 0.58],
      "box_label": "Figure 2 • Overall architecture",
      "card_title": "方法总览 (Method Overview)",
      "notes": [
        "先说明输入与输出，再解释两条路径的职责",
        "只陈述图和正文能共同支持的机制"
      ],
      "claim_type": "paper_evidence",
      "source_anchor": {
        "page": 3,
        "kind": "figure",
        "label": "Figure 2"
      }
    }
  ]
}
```

## Geometry rules

- Keep every coordinate between `0.0` and `1.0`.
- Require `x0 < x1` and `y0 < y1`.
- Include the complete figure/table and its caption when space permits.
- Avoid boxes smaller than the visible target or so large that the zoom panel becomes meaningless.
- Visually inspect vector figures and equations; PDF text boxes alone are not reliable boundaries for them.

## Subtitle rules

- Keep one main idea per turn.
- Prefer short spoken sentences and concrete nouns.
- Put at most one important number in a spoken sentence when possible.
- Define a technical term on first use, then reuse the same English term consistently.
- Write Chinese and English naturally; do not force word-for-word translation.
