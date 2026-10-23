# Dialogue Script Contract

Use this contract for `dialogue_script.json`. The renderer ignores unknown fields, but the validator enforces the evidence and geometry fields used by the Paper Ear workflow.

## Root fields

| Field | Required | Meaning |
|---|---:|---|
| `title` | yes | Exact paper title or a faithful shortened title. |
| `source_document` | yes for `bubu-yier-v1` | Immutable binding to the current PDF. Use an object with `filename`, lowercase `sha256`, and integer `page_count`. The branded renderer rejects a missing or mismatched hash/page count before TTS or video work begins. |
| `pdf_sha256` | legacy optional alias | Top-level SHA-256 alias for non-branded legacy scripts. New scripts should use `source_document.sha256`. If both are present, they must agree. |
| `brand_profile` | branded theme only | Set to `bubu-yier-v1` to require the fixed 一二/布布 cast, mandatory three-turn opening, and per-turn character layer. |
| `male_name` | yes in strict mode | Display name and role for the discussant. |
| `female_name` | yes in strict mode | Display name and role for the presenter. |
| `male_voice` | one voice source required | Backward-compatible male voice name; `voice_profiles.male.voice` may replace it. |
| `female_voice` | one voice source required | Backward-compatible female voice name; `voice_profiles.female.voice` may replace it. |
| `voice_backend` | no | `kokoro-zh-local` (recommended generic offline Mandarin), `bubu-yier-local` (F5-TTS character cast), `edge-tts`, `azure-speech`, or `lemonade-local`. |
| `voice_model` | recommended for local | Local model shared by both roles; use `kokoro-v1.1-zh` with `kokoro-zh-local`. A profile-level model overrides it. |
| `voice_profiles` | recommended | Female/male voice, optional local model/voice-design description, default style, emotion-to-style map, and baseline prosody. |
| `interaction_mode` | no | Set to `evidence-dialogue-v2` to enforce real question/answer dynamics. |
| `turns` | yes | Ordered, non-empty array of dialogue turns. |

## Current-PDF binding (mandatory for the branded profile)

Every `bubu-yier-v1` script must be generated from, and bound to, the PDF supplied in the current run:

```json
{
  "source_document": {
    "filename": "uploaded-paper.pdf",
    "sha256": "64-lowercase-hex-characters",
    "page_count": 14
  }
}
```

The validator and renderer recompute the hash and page count from `--pdf`. A mismatch is a hard failure; it is never repaired by substituting the repository demo or by reusing `examples/sample_dialogue.json`. The render report records the canonical paths, raw-byte PDF/script hashes, and a second `script_content_sha256` computed from UTF-8 dialogue text after normalizing CRLF and lone CR to LF. Its explicit `input_hash_contract` lets a fresh Windows checkout survive LF↔CRLF conversion without weakening content checks. The media gate rehashes the current PDF and normalized script; any non-line-ending script change, or any PDF byte change, fails. A branded turn whose `page` is outside the current PDF is also a hard failure and is never silently clamped to another page.

## Turn fields

| Field | Required | Meaning |
|---|---:|---|
| `page` | yes | 1-indexed PDF page number. |
| `speaker` | yes | `female` or `male`. |
| `zh_text` | yes in strict mode | Chinese subtitle and default spoken text. |
| `en_text` | yes in strict mode | English subtitle. |
| `spoken_text` | no | Optional narration override. When absent, the renderer uses `zh_text`, then `en_text`. For `kokoro-zh-local`, make this pronunciation-ready Mandarin; embedded Latin terms use an English fallback and must be auditioned. |
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
| `character_pose` | no | Exact pose ID from `assets/characters/manifest.json`. It overrides automatic semantic selection and must belong to the active speaker. |
| `character_caption` | no | Optional non-evidentiary bubble text replacing the pose's default short line; it is not narration and must not introduce a paper claim. |

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

For `kokoro-zh-local`, use model `kokoro-v1.1-zh`; the curated menu contains female voices `zf_001`, `zf_018`, `zf_046`, `zf_090` and male voices `zm_010`, `zm_033`, `zm_066`, `zm_098`. It uses Misaki 1.1 Chinese G2P and runs entirely on-device. Kokoro honors speed but does not implement Azure speaking styles; `provider_style`, pitch, volume, and emphasis remain semantic direction or report metadata rather than guaranteed acoustic controls. Legacy `lemonade-local` + `kokoro-v1` Mandarin is disabled because it failed intelligibility testing. Optional Lemonade MOSS models may accept `voice_design_description`, but require a much larger local download.

For `bubu-yier-local`, use model `F5TTS_v1_Base`; the default cast is female presenter `yier` and male discussant `bubu`. The F5-TTS adapter honors rate as synthesis speed and applies the configured before/after pauses after synthesis. `provider_style`, pitch, volume, emotion, and emphasis remain script/report guidance rather than guaranteed F5-TTS controls. Reference clips and weights stay in external caches. See [bubu-yier-local-backend.md](bubu-yier-local-backend.md) for pinned hashes, setup, model-license limits, and external path configuration.

When `brand_profile` is `bubu-yier-v1`, the renderer injects three fixed opening turns before this schema's evidence-bearing `turns`: 一二 says “啊哒哒～啊哒哒哒哒～！谢谢大家对我们的喜欢！”, 布布 says “感谢「小司在加油」做了这个 Skill——让我们，相遇在科研视频中。”, and 一二 closes with “好啦，开始讲论文吧！”. Do not duplicate them in `turns`; `--max-turns` limits only the paper turns. See [character-expression-system.md](character-expression-system.md) for the 20+20 pose contract and automatic-selection rules.

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
  "source_document": {
    "filename": "uploaded-paper.pdf",
    "sha256": "replace-with-the-current-pdf-sha256",
    "page_count": 12
  },
  "brand_profile": "bubu-yier-v1",
  "voice_backend": "bubu-yier-local",
  "voice_model": "F5TTS_v1_Base",
  "male_name": "布布（追问）",
  "female_name": "一二（主讲）",
  "male_voice": "bubu",
  "female_voice": "yier",
  "turns": [
    {
      "page": 3,
      "section_tag": "Page 3 • Method",
      "speaker": "female",
      "character_pose": "yier_evidence_point",
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
