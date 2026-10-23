# Publication Quality Checklist

Use this checklist after strict dialogue validation and before delivering a final MP4.

## Source and evidence

- Confirm the production script was regenerated from the user's current PDF. Never use the repository demo MP4 or `examples/sample_dialogue.json` as production input.
- For `bubu-yier-v1`, confirm `source_document.sha256` and `source_document.page_count` match the current `--pdf`. The render report must record the canonical PDF/script paths, byte-exact `pdf_sha256` and `script_sha256`, LF-normalized `script_content_sha256`, `input_hash_contract`, and byte-exact `video_sha256`/`video_hash_mode`.
- Treat file identity as an anti-mix-up control, not semantic proof: manually confirm every turn's narration, page, red box, numbers, and evidence anchor against the current PDF. Never carry old turns forward by changing only `source_document`.
- Read the complete accessible paper, not only the abstract and conclusion.
- Trace every displayed number and factual statement to `source_anchor`.
- Verify metric direction, experimental setting, and baseline before stating an improvement.
- Distinguish `paper_evidence`, `author_claim`, `inference`, and `critique` in wording.
- Report prose-table or prose-figure mismatches conservatively.
- Mark unreadable scanned content instead of guessing.

## Dialogue and teaching

- Match terminology depth to the selected audience.
- Give each turn one main teaching point.
- Use the discussant for substantive questions about mechanisms, assumptions, baselines, ablations, or limitations.
- Map every analogy back to the paper's real mechanism.
- Remove filler greetings, repeated summaries, and theatrical disagreement that adds no understanding.

## Visuals

- Confirm the highlighted page and target match the spoken claim.
- Reject any branded turn whose page is outside the current PDF; do not clamp it to page 1 or the last page.
- Include the complete figure/table/equation and caption when practical.
- Ensure the zoom panel is sharp and meaningful, not an enlarged blank margin.
- Check that subtitles, labels, and cards remain inside their panels.
- Check that no overlay obscures the exact row, axis, legend, formula symbol, or caption being discussed.
- Sample at least one frame per turn; always inspect the first, middle, and final turns.

## Audio and timing

- Require real TTS for a publishable video; `offline-cadence` is preview-only.
- For offline Mandarin, confirm the report records `kokoro-zh-local`, `kokoro-v1.1-zh`, `language: zh-CN`, `g2p: misaki-zh-1.1`, and `endpoint_scope: on-device`.
- For the Bubu/Yier cast, confirm the report records `bubu-yier-local`, `F5TTS_v1_Base`, `reference_voice: yier` on female turns, `reference_voice: bubu` on male turns, `reference_verified: true`, `input_scope: spoken_text-only`, and `endpoint_scope: on-device`. Confirm the published use is compatible with the model's CC-BY-NC-4.0 limit and the separate character/reference-performance rights boundary.
- For `bubu-yier-v1`, confirm the first three rendered segments are the fixed 一二 → 布布 → 一二 opening, with the 250 ms and 350 ms post-line pauses intact; `--max-turns` must not remove them. Confirm `character_poses` contains one entry for each opening segment and each rendered paper turn, both characters remain visible, the active pose belongs to the active speaker, and no pose bubble obscures the source crop, red box, or subtitles.
- Treat a valid WAV as a transport check only. A human listener must understand every word in the same-line audition and four-turn micro-scene before a full render.
- Reject legacy Lemonade/Kokoro v1.0 Mandarin even when synthesis technically succeeds; it failed the intelligibility gate.
- For `lemonade-local`, confirm the render report records the intended model, voice, and `endpoint_scope: loopback`; treat provider-style labels as script direction unless that model explicitly supports them.
- Listen to technical terms, acronyms, symbols, and mixed Chinese-English phrases for pronunciation problems.
- Confirm the final word of every turn is audible and the last turn is not truncated.
- Keep speech at a comprehensible rate; shorten text before using extreme speed.
- For `bubu-yier-v1`, confirm the final report records the standard mastering pass: `-1.5 dB` gain, `0.89` limiter ceiling, `128k` AAC re-encode, 24 kHz, and mono. Do not publish a direct AAC-segment copy with discontinuous timestamps.

## Media gate

- Run `scripts/verify_video.py` and fix every error.
- Confirm the gate rehashes the current PDF as raw bytes and the current UTF-8 dialogue after CRLF/lone-CR normalization. A Windows LF↔CRLF checkout is allowed; any other script-content change or any PDF/video byte change is a hard failure.
- Confirm a video stream and an audio stream are present.
- Confirm the expected 1920×1080 resolution and a positive duration.
- Confirm audio/video stream durations do not drift beyond the configured tolerance.
- Confirm the file opens from beginning to end in a real player when feasible.

## Delivery

- Deliver the final MP4 from the successful publish run, not the low-DPI preview.
- State which TTS provider, model, and role voices were used, and which validation gates passed.
- Disclose any source region that could not be verified.
- Do not claim a clean result if a strict gate failed or was skipped.
