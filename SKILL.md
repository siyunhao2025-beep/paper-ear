---
name: paper-ear
description: Turn academic-paper PDFs into evidence-grounded 1080p MP4 group-meeting videos with two-speaker dialogue, synchronized Chinese-English subtitles, and page-accurate red-box plus zoom tracking. Use when the user mentions paper-ear; asks to convert a research paper, PDF, or arXiv paper into a video or MP4 explanation; wants a bilingual paper walkthrough or lab-meeting presentation; or wants exact passages, equations, figures, and tables highlighted while they are discussed.
---

# Paper Ear

Create a two-speaker research-paper walkthrough that stays visibly tied to the source PDF. The final video combines a presenter and a critical discussant, bilingual subtitles, page-accurate red-box tracking, a synchronized zoom panel, and compact terminology cards.

Resolve `<SKILL_DIR>` to the directory containing this `SKILL.md`. Invoke bundled scripts with absolute paths under `<SKILL_DIR>`; do not assume the current working directory is the skill directory.

## Core contract

1. Treat the supplied PDF as the source of truth. Read the full accessible paper, including appendices relevant to claims shown in the video.
2. Anchor every factual statement, number, method detail, and experimental conclusion to a PDF page plus a section, figure, table, equation, or page label. If the source cannot be located, omit the statement or label it as not found.
3. Set each turn's `claim_type` to `paper_evidence`, `author_claim`, `inference`, or `critique`. Never blend an inference or critique into the authors' reported result.
4. Paraphrase the paper. Use short quotations only when exact wording is essential.
5. Do not guess at unreadable scans, tables, equations, or cropped figures. Report the unreadable region, try OCR or visual inspection when available, and lower the claim ceiling accordingly.
6. Do not silently deliver cadence-only fallback audio as narration. A publishable video must complete with real TTS under `--require-tts`.

## Run layout

Use one run directory so the work is resumable and inspectable:

```text
<run_dir>/
├── paper_structure.json
├── pages/
├── dialogue_script.json
├── script_qa.json
├── preview.mp4
├── final.mp4
├── render_report.json
├── video_qa.json
└── snapshots/
```

Keep intermediate artifacts in the run directory. Deliver the final MP4; provide QA artifacts only when the user asks or when a warning needs explanation.

## Workflow

### 1. Preflight the source and environment

Require a readable local PDF. If the user supplied a lawful public URL, download the PDF first. Do not claim success from an abstract page alone.

Check the PDF and required tools before doing content work:

```bash
python <SKILL_DIR>/scripts/validate_dialogue.py \
  --pdf /absolute/path/to/paper.pdf
```

Stop and explain any missing hard dependency. The renderer requires Python packages from `requirements.txt`, plus `ffmpeg`, `ffprobe`, and Poppler's `pdftoppm` on `PATH`.

### 2. Inspect the full paper

Extract text blocks, normalized coordinates, detected image regions, and rendered page images:

```bash
python <SKILL_DIR>/scripts/inspect_paper.py \
  --pdf /absolute/path/to/paper.pdf \
  --out <run_dir>/paper_structure.json \
  --render-dir <run_dir>/pages \
  --dpi 150
```

Read `paper_structure.json` and inspect the relevant page PNGs. Build a compact evidence map covering:

- the research problem and the limitation claimed by the authors;
- two to four core contributions;
- the method flow and important notation;
- headline experiments, settings, metrics, and exact reported numbers;
- limitations or scope boundaries stated in the paper;
- candidate paragraphs, equations, figures, and tables for visual highlighting.

For every candidate visual, record its page, label, normalized bounding box, and the claim it supports. For figures and tables, include the complete visual and its caption when practical; text extraction alone does not reveal the full vector-art boundary.

### 3. Resolve audience, focus, and depth

Use guided mode by default. Present one compact preference checkpoint containing:

- **Audience:** novice, general technical, or expert.
- **Focus:** the detected two to four contributions or a user-named section.
- **Coverage:** concise overview, standard full-paper walkthrough, or deep method/experiment focus.
- **Language:** Chinese narration with Chinese-English subtitles by default, or the user's requested language arrangement.

Do not ask questions the user already answered. If the user says to use defaults, skip the checkpoint and proceed with general-technical, standard coverage, and Chinese narration plus bilingual subtitles.

### 4. Confirm the dialogue storyboard

Create a short storyboard table before rendering. Each row must show:

- turn number and speaker;
- teaching point or critical question;
- PDF page and source anchor;
- red-box target;
- claim type;
- the exact reported number or conclusion, if any.

Use the presenter to explain the paper and the discussant to probe assumptions, mechanisms, baselines, ablations, and limitations. Avoid fake disagreement and filler banter. Keep one main teaching point per turn.

Ask for confirmation only when the user requested an interactive workflow or when changing the focus would materially alter the video. Otherwise continue with the approved/default plan.

### 5. Write and validate the dialogue script

Write `<run_dir>/dialogue_script.json`. Read [references/dialogue-schema.md](references/dialogue-schema.md) for the complete field contract and example.

Important rules:

- Use 1-indexed PDF page numbers.
- Use normalized `red_box` coordinates `[x0, y0, x1, y1]` in the range `0.0..1.0`, with `x0 < x1` and `y0 < y1`.
- Add a distinctive `search_text` for paragraphs, captions, and equations when text extraction can locate it.
- Add `source_anchor` and `claim_type` to every turn.
- Keep subtitles concise enough to fit: split long explanations into multiple turns rather than shrinking text excessively.
- Map every analogy back to the real mechanism before moving on.

Run the strict gate:

```bash
python <SKILL_DIR>/scripts/validate_dialogue.py \
  --pdf /absolute/path/to/paper.pdf \
  --script <run_dir>/dialogue_script.json \
  --strict \
  --json-out <run_dir>/script_qa.json
```

Fix every error before rendering. Review warnings instead of suppressing them blindly.

### 6. Render a fast preview

Render the first two turns at lower DPI to catch wrong pages, bad crops, overflowing subtitles, awkward terminology cards, and voice problems before paying the full render cost:

```bash
python <SKILL_DIR>/scripts/render_paper_video.py \
  --pdf /absolute/path/to/paper.pdf \
  --script <run_dir>/dialogue_script.json \
  --output <run_dir>/preview.mp4 \
  --dpi 110 \
  --max-turns 2 \
  --report-json <run_dir>/preview_render_report.json
```

Inspect at least one frame from each preview turn. If the preview uses `offline-cadence`, treat it only as a visual timing preview; it contains no intelligible narration.

### 7. Render the publishable video

After the preview passes, render the full video with real TTS required:

```bash
python <SKILL_DIR>/scripts/render_paper_video.py \
  --pdf /absolute/path/to/paper.pdf \
  --script <run_dir>/dialogue_script.json \
  --output <run_dir>/final.mp4 \
  --dpi 180 \
  --fps 12 \
  --require-tts \
  --report-json <run_dir>/render_report.json
```

Add `--export-gif <path>` only when the user also wants a README preview. If `--require-tts` fails, repair connectivity, the voice name, or the narration text; do not remove the flag merely to force a nominal success.

### 8. Verify the final artifact

Run the deterministic media gate:

```bash
python <SKILL_DIR>/scripts/verify_video.py \
  --video <run_dir>/final.mp4 \
  --expect-width 1920 \
  --expect-height 1080 \
  --json-out <run_dir>/video_qa.json
```

Then sample frames at the beginning, middle, end, and every figure/table turn. Follow [references/quality-checklist.md](references/quality-checklist.md). Do not report completion until:

- script validation has no errors;
- all factual turns have valid source anchors;
- every intended figure/table/equation is framed correctly;
- subtitles and cards stay within their panels and do not obscure evidence;
- the final file has both video and audio streams, the expected resolution, and no truncated final turn;
- `render_report.json` reports only `edge-tts` for a publishable run.

### 9. Deliver

Present the final MP4 and briefly state:

- the selected audience/focus;
- the number of dialogue turns;
- whether real TTS was used;
- which validation gates passed;
- any remaining limitation, such as an unreadable source figure.

Do not create PPTX, Markdown reports, social-media cuts, or additional deliverables unless the user requests them.

## Failure handling

- **Scanned or image-only PDF:** attempt OCR if an available PDF/OCR tool supports it; otherwise identify unreadable pages and avoid unsupported details.
- **Text locator misses a figure or equation:** set `red_box` manually from the rendered page and keep `search_text` only when it resolves to the same target.
- **TTS unavailable:** allow cadence audio only for preview. A publishable run must stop under `--require-tts`.
- **Long subtitle or card text:** split the turn or shorten the paraphrase; do not reduce the font until it becomes hard to read.
- **Source contradiction:** prefer the table/figure for exact numbers, note the prose mismatch, and phrase the video conservatively.
- **Missing dependency or failed QA:** repair the environment or artifact and rerun the same gate. Do not silently downgrade the output.
