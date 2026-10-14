---
name: paper-ear
description: >-
  Turn academic PDF papers into group-meeting style MP4 videos featuring a
  male-female conversational dialogue, synchronized Chinese-English bilingual
  subtitles, and dynamic red-box highlighting on the exact PDF paragraphs,
  equations, and figures being discussed. Use whenever the user mentions
  paper-ear, asks to turn a PDF paper into a video or MP4 explanation, or wants
  an interactive group-meeting presentation from a research paper.
---

# paper-ear

Generate a group-meeting style 1080p MP4 video from an academic PDF paper after a structured multi-turn interaction with the user. The output MP4 features a male-female dialogue with animated speaker waveforms, synchronized Chinese-English subtitles, a dynamic red bounding box with target corner brackets on the exact paragraph, formula, table, or figure being explained, and a live zoomed-in callout view alongside a technical terminology card.

## When to Use

- The user uploads or references a research paper PDF and asks to explain it as an MP4 video or group-meeting presentation.
- The user invokes `paper-ear` to read, dissect, or present a paper with bilingual narration and visual red-box tracking.
- The user wants a two-person (male and female) academic discussion video highlighting specific innovations, technical terms, or sections of a PDF.

## Steps

### Step 1: Parse the PDF Structure and Coordinates

Run the bundled `scripts/inspect_paper.py` script on the user's PDF to extract text blocks, normalized bounding boxes (`[x0, y0, x1, y1]`), image coordinates, and rendered page PNGs:

```bash
python3 skills/paper-ear/scripts/inspect_paper.py \
  --pdf /path/to/input.pdf \
  --out /tmp/paper_structure.json \
  --render-dir /tmp/paper_pages \
  --dpi 150
```

Read `/tmp/paper_structure.json` (and inspect key page PNGs in `/tmp/paper_pages/` using `view_file` when locating multi-panel figures or equations) to identify the paper's title, section structure, core contributions, and key domain terminology.

### Step 2: Round 1 Interaction - Select Focus, Terms, and Sections

Do not generate the MP4 video on the first turn. Instead, present a brief summary of what you detected in the PDF and ask the user to choose their preferences across three dimensions:

- **Core Innovation Focus (选择创新点)**: List the 2 to 4 core contributions identified in the paper and ask which innovation points to emphasize.
- **Technical Terminology Depth (解析专业名词)**: List 4 to 6 key technical terms or acronyms from the paper and ask whether to explain them from first principles (cross-domain/beginner mode) or focus on advanced mechanism details (expert mode).
- **Target Sections and Figures (解读哪部分内容)**: Ask whether to cover the full paper (Motivation, Method, Experiments, Conclusion) or zoom in on specific sections, equations, or figures.

### Step 3: Round 2 Interaction - Confirm Dialogue Plan and Red-Box Targets

After the user responds to Round 1, synthesize their choices into a structured **Male-Female Dialogue Plan** and ask for final confirmation or adjustments before rendering:

- **Speaker Roles**: Present the conversational setup between the female presenter (`主讲人`, leading the paper walkthrough) and the male discussant (`师兄/提问者`, asking critical questions about motivation, baselines, equations, and terminology).
- **Page-by-Page Red-Box Map**: List the planned dialogue scenes, indicating which PDF page and which specific element (abstract claim, architecture figure, equation, or ablation table) will be framed in a red box (`红框`) during each exchange.
- **Adjustment Prompt**: Ask the user if they want to add any specific group-meeting questions, tweak the focus of any section, or start rendering the MP4 immediately.

### Step 4: Construct the Dialogue and Red-Box Script JSON

Once the user confirms the plan (after the multi-turn customization), create a `dialogue_script.json` file that maps every conversational turn to an exact region on the PDF page:

```json
{
  "title": "Paper Title Here",
  "male_name": "师兄 Alex (提问/思辨)",
  "female_name": "主讲人 Lin (精读讲解)",
  "male_voice": "zh-CN-YunxiNeural",
  "female_voice": "zh-CN-XiaoxiaoNeural",
  "turns": [
    {
      "page": 1,
      "section_tag": "Page 1 • Abstract & Motivation",
      "speaker": "female",
      "zh_text": "大家好，今天组会我们精读这篇论文，先看红框里摘要指出的核心痛点。",
      "en_text": "Hi everyone, today we are reading this paper, starting with the core bottleneck highlighted in the Abstract.",
      "search_text": "Abstract",
      "red_box": [0.10, 0.20, 0.90, 0.42],
      "box_label": "Abstract / 核心背景与痛点",
      "card_title": "💡 核心背景与痛点 (Motivation)",
      "notes": [
        "传统方法在长序列推理下计算开销呈二次方增长",
        "本文提出轻量化稀疏注意力机制解决内存瓶颈"
      ]
    },
    {
      "page": 2,
      "section_tag": "Page 2 • Terminology & Mechanism",
      "speaker": "male",
      "zh_text": "这里有个关键专业名词 Sparse Routing，它和传统的 Top-K 门控有什么本质区别？",
      "en_text": "There is a key term here, Sparse Routing. How does it fundamentally differ from standard Top-K gating?",
      "search_text": "Sparse Routing",
      "red_box": [0.08, 0.45, 0.48, 0.72],
      "box_label": "专业名词解析: Sparse Routing",
      "card_title": "📖 专业名词解析 (Terminology)",
      "notes": [
        "Sparse Routing (稀疏路由): 动态分配计算资源的门控机制",
        "核心优势: 避免硬截断带来的梯度消失，保持端到端可微"
      ]
    }
  ]
}
```

Follow these rules when constructing `turns`:

- Alternate naturally between `"female"` and `"male"` speakers so the video feels like an authentic, interactive lab group meeting.
- Provide accurate `red_box` normalized coordinates `[x0, y0, x1, y1]` (ranging from `0.0` to `1.0` relative to page width and height) taken from `inspect_paper.py` or visual inspection of the rendered page PNGs.
- Also populate `search_text` with a distinctive phrase from that paragraph or caption so `render_paper_video.py` can automatically locate or refine text bounding boxes.
- For figures, architecture diagrams, and tables, always verify the full visual extent `[x0, y0, x1, y1]` on the rendered page PNG so the red box frames the entire diagram plus its caption cleanly.

### Step 5: Render and Deliver Only the MP4 Video

Execute `scripts/render_paper_video.py` to synthesize the audio track, draw the red bounding boxes, corner target brackets, zoomed callout views, speaker waveforms, and bilingual subtitles, and encode the final 1080p MP4:

```bash
python3 skills/paper-ear/scripts/render_paper_video.py \
  --pdf /path/to/input.pdf \
  --script /tmp/dialogue_script.json \
  --output /working_dir/<conversation_id>/artifacts/file_generation/ttl=63d/output/paper_ear_meeting.mp4 \
  --dpi 180
```

Verify that the output `.mp4` file exists and is non-empty, then present **only** the MP4 video to the user using `google:show_file`. Do not output extra PPTX or Markdown files unless the user explicitly asks for them.

## Gotchas

- **Never skip the multi-turn interaction**: Even if the user uploads a PDF and says "run paper-ear", always complete the interactive selection rounds first unless the user explicitly says "skip questions and use defaults".
- **Verify figure bounding boxes visually**: `pdfplumber` text blocks only cover text captions, not vector drawings. When highlighting a figure or architecture diagram, inspect the rendered PNG page from `inspect_paper.py` to set `red_box` coordinates that cover the entire visual figure.
- **Audio environment transparency**: `render_paper_video.py` uses `edge-tts` neural male/female voices (`zh-CN-YunxiNeural` and `zh-CN-XiaoxiaoNeural`) when internet access is available (such as in a local GitHub clone), and automatically falls back to offline acoustic turn-cadence timing in air-gapped environments. Briefly note this when delivering videos rendered in an offline environment.
