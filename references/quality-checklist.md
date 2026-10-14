# Publication Quality Checklist

Use this checklist after strict dialogue validation and before delivering a final MP4.

## Source and evidence

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
- Include the complete figure/table/equation and caption when practical.
- Ensure the zoom panel is sharp and meaningful, not an enlarged blank margin.
- Check that subtitles, labels, and cards remain inside their panels.
- Check that no overlay obscures the exact row, axis, legend, formula symbol, or caption being discussed.
- Sample at least one frame per turn; always inspect the first, middle, and final turns.

## Audio and timing

- Require real TTS for a publishable video; `offline-cadence` is preview-only.
- For offline Mandarin, confirm the report records `kokoro-zh-local`, `kokoro-v1.1-zh`, `language: zh-CN`, `g2p: misaki-zh-1.1`, and `endpoint_scope: on-device`.
- Treat a valid WAV as a transport check only. A human listener must understand every word in the same-line audition and four-turn micro-scene before a full render.
- Reject legacy Lemonade/Kokoro v1.0 Mandarin even when synthesis technically succeeds; it failed the intelligibility gate.
- For `lemonade-local`, confirm the render report records the intended model, voice, and `endpoint_scope: loopback`; treat provider-style labels as script direction unless that model explicitly supports them.
- Listen to technical terms, acronyms, symbols, and mixed Chinese-English phrases for pronunciation problems.
- Confirm the final word of every turn is audible and the last turn is not truncated.
- Keep speech at a comprehensible rate; shorten text before using extreme speed.

## Media gate

- Run `scripts/verify_video.py` and fix every error.
- Confirm a video stream and an audio stream are present.
- Confirm the expected 1920×1080 resolution and a positive duration.
- Confirm audio/video stream durations do not drift beyond the configured tolerance.
- Confirm the file opens from beginning to end in a real player when feasible.

## Delivery

- Deliver the final MP4 from the successful publish run, not the low-DPI preview.
- State which TTS provider, model, and role voices were used, and which validation gates passed.
- Disclose any source region that could not be verified.
- Do not claim a clean result if a strict gate failed or was skipped.
