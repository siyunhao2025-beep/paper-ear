# Interactive web-reader brief schema

`render_paper_web.py` turns one validated UTF-8 JSON brief into a fully local,
responsive paper reader. The brief is not a free-form summary: it is an evidence
map whose factual items point back to the supplied PDF.

## Top-level object

```json
{
  "schema_version": 1,
  "brand_profile": "bubu-yier-v1",
  "source_document": {
    "filename": "the-current-user-upload.pdf",
    "sha256": "sha256-of-that-exact-pdf",
    "page_count": 12
  },
  "paper": {},
  "reader": {},
  "summary": {},
  "logic_map": [],
  "claims": [],
  "inventory": {},
  "visuals": [],
  "excluded_visuals": [],
  "sections": [],
  "limitations": [],
  "questions": [],
  "glossary": []
}
```

## 一二 × 布布网页主题与真实文献绑定

将根字段 `brand_profile` 设为 `bubu-yier-v1` 后，`source_document`
是必填项。`filename`、`sha256` 和 `page_count` 必须来自本次传入
`--pdf` 的真实文件；严格校验器与网页渲染器都会在写出站点前重新计算
并比对，任何缺失或不一致都会直接失败。渲染报告同时记录 PDF 与
`web_brief.json` 的规范路径、SHA-256、页数和 `verified` 状态。

品牌站点还会生成 `site-identity.json` schema v2。清单明确记录 SHA-256
算法与每个文件的哈希模式：HTML、CSS、JavaScript、JSON 等可识别 UTF-8
文本先按 `utf8-lf-v1` 统一换行后哈希，PDF 与图片等二进制按
`raw-bytes-v1` 逐字节哈希。因此 Git 在 Windows checkout 时仅把 LF 改成
CRLF 不会产生误报，但正文、代码、图片或 PDF 的真实内容变化仍会失败。
旧 schema 必须用当前渲染器重新生成，不会被验证器静默接受。

仓库里的 `sample_paper.pdf`、`sample_web_brief.json` 与
`examples/web-reader-demo/` 只用于展示功能。用户上传新论文时，必须重新
完成全文读取、逐页视觉盘点、主张与来源锚定，并重新生成网页；不得复制
示例的摘要、页码、结论或站点成品。文件哈希只能防止“串档”，不能替代
逐条语义审校和原页核对。

品牌网页固定显示一二（白色棕耳、女主讲）与布布（棕色、男追问），并
明确标注“一二讲证据、布布问边界”。角色 PNG 会被复制到站点自己的
`assets/characters/`，不依赖网络或仓库外路径。角色姿态属于阅读导航，
不得作为论文证据，也不得改写 `summary`、`claims`、`sections` 或视觉说明。

Validate the file before rendering:

```bash
python <SKILL_DIR>/scripts/validate_web_brief.py \
  --pdf /absolute/path/to/paper.pdf \
  --brief <run_dir>/web_brief.json \
  --strict \
  --json-out <run_dir>/web_brief_qa.json
```

## Paper and summaries

`paper` fields:

- `title` (required string)
- `authors` (required non-empty string array)
- `page_count` (required for strict authoring; must match the PDF)
- `venue`, `year`, `doi`, and `url` (optional metadata)

`reader.reading_minutes` is an optional integer estimate.

`summary` requires:

- `one_sentence`: the narrowest useful statement of the paper's contribution;
- `quick_points`: at least three short points for the 30-second view;
- `three_minute`: one compact synthesis covering problem, method, result, and
  the most important boundary.

Paraphrase rather than paste. If `source_excerpt` is present, the validator warns
when it exceeds 25 words.

## Source anchors and declaration types

A source anchor is always 1-indexed:

```json
{
  "page": 7,
  "kind": "figure",
  "label": "Figure 3"
}
```

Allowed `kind` values are `section`, `figure`, `table`, `equation`, `appendix`,
and `page`.

Every entry in `claims` requires:

```json
{
  "id": "claim-main-result",
  "title": "Short claim label",
  "summary": "What the paper reports, in your own words.",
  "evidence": ["Exact reported metric or directly visible observation."],
  "why_it_matters": "Why a reader should care.",
  "claim_type": "paper_evidence",
  "evidence_strength": "strong",
  "source_anchor": {"page": 7, "kind": "table", "label": "Table 2"}
}
```

`claim_type` must be one of:

- `paper_evidence`: directly visible data, method description, or reported result;
- `author_claim`: the authors' interpretation or stated contribution;
- `inference`: a teaching explanation that follows from the paper but is not stated;
- `critique`: an explicit reviewer-style concern or alternative interpretation.

`evidence_strength` is `strong`, `moderate`, or `tentative`. Strength describes
support inside this paper, not whether a result is universally true.

## Argument map

`logic_map` contains at least three ordered objects. Each needs `stage`, `title`,
`body`, and `source_anchor`. Prefer the paper's causal/argument structure—problem,
method, test, result, boundary—over a table-of-contents recap.

## Visual inventory

The invariant is:

```text
declared region count = included visual count + intentional exclusion count
```

Declare it explicitly:

```json
{
  "inventory": {
    "status": "complete",
    "declared_regions": {"figure": 4, "table": 2, "equation": 6}
  }
}
```

`status: complete` is permitted only after reviewing every rendered PDF page.
`build_visual_inventory.py` provides candidates, not proof of completeness.

Each included visual requires:

```json
{
  "id": "fig-3",
  "kind": "figure",
  "page": 7,
  "bbox_norm": [0.08, 0.12, 0.93, 0.67],
  "label": "Figure 3",
  "caption": "Faithful paraphrase of what is plotted.",
  "alt": "Accessible description of axes, panels, and visible trend.",
  "why_it_matters": "The claim this visual supports—or fails to support.",
  "source_anchor": {"page": 7, "kind": "figure", "label": "Figure 3"}
}
```

`bbox_norm` is `[x0, y0, x1, y1]` in page-relative coordinates from `0.0` to
`1.0`. Include the complete numbered visual and caption when practical. Do not
redraw or alter source data.

Decorative graphics, duplicated appendix copies, or regions that are genuinely
unreadable can be placed in `excluded_visuals`; every item requires `kind`,
`label`, and a concrete `reason`. Never use exclusions to hide missed content.

## Deep-reading sections

Each object in `sections` requires:

- unique `id`, compact `nav_title`, full `title`, and `lede`;
- `body`: one or more paraphrased paragraphs;
- `takeaways`: one or more reader-facing conclusions;
- `source_anchors`: one or more PDF anchors;
- `visual_ids`: optional links to included visual IDs.

Organize by reasoning units such as research question, design, measurement,
results, and boundaries. Do not mechanically mirror every PDF heading.

## Limitations, questions, and glossary

`limitations` separates author-stated limitations from critique. Each item needs
`title`, `body`, `claim_type` (`author_claim` or `critique`), and `source_anchor`.
Strict validation requires at least one such item.

`questions` is a string array for group-meeting discussion. Ask questions that
could change interpretation, not generic prompts.

`glossary` is an array of `{ "term": "...", "definition": "..." }` objects.
Define terms in the paper's context and retain the original technical name.

See `examples/sample_web_brief.json` for a complete runnable example.
