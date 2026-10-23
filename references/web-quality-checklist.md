# Interactive web-reader quality checklist

Use this after strict JSON validation and deterministic website verification.

## Evidence fidelity

- [ ] The full accessible paper—not only the abstract—was read.
- [ ] Every number, method detail, and empirical conclusion has a valid PDF page
      and section/figure/table/equation anchor.
- [ ] Author claims, direct paper evidence, explanatory inferences, and critiques
      are visibly separated.
- [ ] Exact values agree across prose, plots, and tables; any source conflict is
      described rather than silently resolved.
- [ ] The summary does not generalize beyond the evaluated data, population,
      baselines, or measurement range.
- [ ] Any interpretive caveat that materially changes the headline conclusion is
      visible before the deep-reading section.

## Complete visual coverage

- [ ] `build_visual_inventory.py` was run when text extraction was available.
- [ ] Every rendered PDF page was visually inspected, including appendices used
      by the reader.
- [ ] Every numbered figure, table, and substantive displayed equation is either
      in `visuals` or has a defensible entry in `excluded_visuals`.
- [ ] `inventory.declared_regions` equals included plus excluded items by kind.
- [ ] Each crop includes all panels, axes, legends, units, and the caption when
      practical; no crop changes or redraws the source data.
- [ ] Each "原页定位" image clearly marks the same region on the correct PDF page.
- [ ] Alt text describes the visible structure and trend without inventing values.

## Reading experience

- [ ] The 30-second mode delivers a useful answer without requiring scrolling
      through hidden deep-reading sections.
- [ ] The argument map follows question → method → evidence → boundary rather
      than repeating the paper's table of contents.
- [ ] Search finds claims, visual labels, metrics, and terminology.
- [ ] Figure/table/equation filters work and do not hide unrelated content.
- [ ] Crop zoom, original-page view, and close controls work with mouse and keyboard.
- [ ] Bookmarks persist when local storage is available and fail harmlessly when
      it is blocked by local-file privacy settings.
- [ ] Motion is limited to orientation and navigation; `prefers-reduced-motion`
      disables reveal animation and smooth scrolling.
- [ ] The page remains legible at 390 px mobile width, standard desktop width,
      and in print.

## Offline and privacy checks

- [ ] `verify_web_reader.py --strict` passes with no errors.
- [ ] HTML, CSS, JavaScript, crop images, and optional source PDF open without a
      network connection.
- [ ] There are no remote scripts, remote stylesheets, analytics, trackers, or
      hidden API calls.
- [ ] Source-paper links and DOI links are ordinary user-initiated links only.

## 一二 × 布布主题检查

- [ ] `source_document.filename`、`sha256` 与 `page_count` 来自本次真实 PDF，
      且 brief 校验、渲染报告与站点 `site-identity.json` 均为 `verified`。
- [ ] 品牌运行未使用 `--pages-dir`；所有页图都由当前 `--pdf` 重新渲染，
      不存在上一份论文的缓存 PNG。
- [ ] Hero 与陪伴栏都同时显示一二和布布：一二为白色棕耳女主讲，布布为
      棕色男追问，页面明确写出“一二讲证据、布布问边界”。
- [ ] 角色 PNG 只来自站点自己的 `assets/characters/`，断网后仍能显示；
      `source.pdf`、`source-brief.json` 与全部站点文件的哈希复核通过。
- [ ] `site-identity.json` 使用 schema v2：算法为 `sha256`，可识别 UTF-8
      文本使用 `utf8-lf-v1`，二进制使用 `raw-bytes-v1`；LF/CRLF 的 Git
      checkout 差异可通过，但真实文本改动或任一二进制字节变化必须失败。
- [ ] 角色只作导读，不覆盖正文或视觉证据，也不把动作说明当成论文主张；
      390 px 下陪伴栏回到正常文档流，不悬浮遮挡图表。

## Browser inspection

- [ ] A headless Chromium run reaches network idle with no uncaught JavaScript errors.
- [ ] Desktop and mobile full-page screenshots were inspected, not only generated.
- [ ] Long titles, long captions, dense tables, and portrait figures do not overflow.
- [ ] Opening every visual does not reveal broken images or mismatched source pages.

Do not call the reader complete if deterministic checks pass but page-by-page visual
inspection has not happened. Completeness is a content judgment, not merely a schema
property.
