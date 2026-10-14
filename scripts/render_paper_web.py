#!/usr/bin/env python3
"""Render an evidence-grounded, offline Paper Ear web reader from a PDF and JSON brief."""

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "web-reader"
CLAIM_LABELS = {
    "paper_evidence": "论文证据",
    "author_claim": "作者主张",
    "inference": "讲解推断",
    "critique": "批判性分析",
}
STRENGTH_LABELS = {"strong": "证据较强", "moderate": "证据中等", "tentative": "谨慎解读"}
KIND_LABELS = {"figure": "图", "table": "表", "equation": "公式"}


def esc(value):
    return html.escape(str(value or ""), quote=True)


def slugify(value):
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value)).strip("-").lower()
    return slug or "visual"


def anchor_chip(anchor):
    if not isinstance(anchor, dict):
        return ""
    page = anchor.get("page", "?")
    label = anchor.get("label", "source")
    return f'<span class="source-chip">PDF p.{esc(page)} · {esc(label)}</span>'


def page_image_map(page_dir):
    found = {}
    for path in page_dir.glob("*.png"):
        match = re.search(r"(?:^|[-_])(\d+)\.png$", path.name, re.IGNORECASE)
        if match:
            found[int(match.group(1))] = path
    return found


def render_pages(pdf_path, page_dir, dpi):
    page_dir.mkdir(parents=True, exist_ok=True)
    prefix = page_dir / "page"
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
        check=True,
    )


def crop_visuals(brief, page_dir, output_dir):
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    pages = page_image_map(page_dir)
    rendered = []
    for index, visual in enumerate(brief.get("visuals", []), start=1):
        page_number = int(visual["page"])
        page_path = pages.get(page_number)
        if page_path is None:
            raise FileNotFoundError(f"Rendered page image not found for PDF page {page_number} in {page_dir}")
        with Image.open(page_path) as page_image:
            page_image = page_image.convert("RGB")
            width, height = page_image.size
            x0, y0, x1, y1 = (float(v) for v in visual["bbox_norm"])
            pad = max(8, round(min(width, height) * 0.008))
            box = (
                max(0, round(x0 * width) - pad),
                max(0, round(y0 * height) - pad),
                min(width, round(x1 * width) + pad),
                min(height, round(y1 * height) + pad),
            )
            crop = page_image.crop(box)
            visual_slug = slugify(visual["id"])
            crop_name = f"visual-{index:02d}-{visual_slug}.png"
            source_name = f"source-{index:02d}-{visual_slug}.jpg"
            crop.save(assets_dir / crop_name, format="PNG", optimize=True)

            source = page_image.copy()
            draw = ImageDraw.Draw(source, "RGBA")
            rect = (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))
            line_width = max(5, round(min(width, height) * 0.004))
            draw.rectangle(rect, outline=(204, 60, 50, 255), width=line_width)
            source.save(assets_dir / source_name, format="JPEG", quality=88, optimize=True)

        enriched = dict(visual)
        enriched["crop_path"] = f"assets/{crop_name}"
        enriched["source_path"] = f"assets/{source_name}"
        enriched["crop_pixels"] = [crop.width, crop.height]
        rendered.append(enriched)
    return rendered


def render_logic_map(items):
    rows = []
    for item in items:
        rows.append(
            '<li class="logic-step reveal" data-search="{search}">'
            '<span class="logic-stage">{stage}</span>'
            '<h3>{title}</h3><p>{body}</p>{anchor}</li>'.format(
                search=esc(" ".join([item.get("stage", ""), item.get("title", ""), item.get("body", "")])),
                stage=esc(item.get("stage")),
                title=esc(item.get("title")),
                body=esc(item.get("body")),
                anchor=anchor_chip(item.get("source_anchor")),
            )
        )
    return "".join(rows)


def render_claims(items):
    rows = []
    for claim in items:
        evidence = "".join(f"<li>{esc(value)}</li>" for value in claim.get("evidence", []))
        claim_type = claim.get("claim_type", "paper_evidence")
        strength = claim.get("evidence_strength", "moderate")
        rows.append(
            '<article class="claim-row reveal" id="{id}" data-search="{search}">'
            '<div class="claim-type" data-type="{claim_type}">{claim_label}</div>'
            '<div><h3>{title}</h3><p>{summary}</p><ul class="claim-evidence">{evidence}</ul>{anchor}</div>'
            '<aside class="claim-aside"><div class="strength" data-strength="{strength}">{strength_label}</div>'
            '<p>{why}</p></aside></article>'.format(
                id=esc(claim.get("id")),
                search=esc(
                    " ".join(
                        [claim.get("title", ""), claim.get("summary", ""), claim.get("why_it_matters", "")]
                        + claim.get("evidence", [])
                    )
                ),
                claim_type=esc(claim_type),
                claim_label=esc(CLAIM_LABELS.get(claim_type, claim_type)),
                title=esc(claim.get("title")),
                summary=esc(claim.get("summary")),
                evidence=evidence,
                anchor=anchor_chip(claim.get("source_anchor")),
                strength=esc(strength),
                strength_label=esc(STRENGTH_LABELS.get(strength, strength)),
                why=esc(claim.get("why_it_matters")),
            )
        )
    return "".join(rows)


def render_visuals(items, source_pdf):
    cards = []
    for visual in items:
        kind = visual.get("kind", "figure")
        source_link = ""
        if source_pdf:
            source_link = (
                f'<a href="{esc(source_pdf)}#page={esc(visual.get("page"))}" target="_blank" '
                'rel="noopener">打开 PDF 原页</a>'
            )
        search = " ".join(
            [visual.get("label", ""), visual.get("caption", ""), visual.get("why_it_matters", "")]
        )
        cards.append(
            '<article class="visual-card reveal" id="visual-{id}" data-kind="{kind}" data-search="{search}">'
            '<button class="visual-image-button" type="button" data-open-visual data-initial-view="crop" '
            'data-crop="{crop}" data-source="{source}" data-alt="{alt}" data-title="{label}">'
            '<img src="{crop}" alt="{alt}" loading="lazy" width="{width}" height="{height}"></button>'
            '<div class="visual-copy"><div><span class="visual-label">{kind_label} · PDF p.{page}</span>'
            '<h3>{label}</h3><p>{caption}</p><p class="visual-why">{why}</p></div>'
            '<div class="visual-actions"><button type="button" data-open-visual data-initial-view="source" '
            'data-crop="{crop}" data-source="{source}" data-alt="{alt}" data-title="{label}">查看原页定位</button>'
            '<button type="button" data-bookmark="{id}" aria-pressed="false">收藏证据</button>{source_link}</div>'
            '</div></article>'.format(
                id=esc(visual.get("id")),
                kind=esc(kind),
                search=esc(search),
                crop=esc(visual.get("crop_path")),
                source=esc(visual.get("source_path")),
                alt=esc(visual.get("alt")),
                label=esc(visual.get("label")),
                width=esc(visual.get("crop_pixels", [1200, 800])[0]),
                height=esc(visual.get("crop_pixels", [1200, 800])[1]),
                kind_label=esc(KIND_LABELS.get(kind, kind)),
                page=esc(visual.get("page")),
                caption=esc(visual.get("caption")),
                why=esc(visual.get("why_it_matters")),
                source_link=source_link,
            )
        )
    if not cards:
        return '<p class="section-note">这篇论文没有需要单独截取的编号图、表或公式。</p>'
    return "".join(cards)


def render_sections(items, visuals_by_id):
    rows = []
    for section in items:
        paragraphs = "".join(f"<p>{esc(value)}</p>" for value in section.get("body", []))
        takeaways = "".join(f"<li>{esc(value)}</li>" for value in section.get("takeaways", []))
        anchors = "".join(anchor_chip(anchor) for anchor in section.get("source_anchors", []))
        linked = []
        for visual_id in section.get("visual_ids", []):
            visual = visuals_by_id.get(visual_id)
            if visual:
                linked.append(f'<a href="#visual-{esc(visual_id)}">{esc(visual.get("label"))}</a>')
        linked_html = f'<div class="linked-visuals">{"".join(linked)}</div>' if linked else ""
        search = " ".join(
            [section.get("nav_title", ""), section.get("title", ""), section.get("lede", "")]
            + section.get("body", [])
            + section.get("takeaways", [])
        )
        rows.append(
            '<article class="walkthrough-section reveal" id="section-{id}" data-search="{search}">'
            '<div><h3>{title}</h3><p class="lede">{lede}</p>{paragraphs}'
            '<ul class="takeaways">{takeaways}</ul>{anchors}{linked}</div></article>'.format(
                id=esc(section.get("id")),
                search=esc(search),
                title=esc(section.get("title")),
                lede=esc(section.get("lede")),
                paragraphs=paragraphs,
                takeaways=takeaways,
                anchors=anchors,
                linked=linked_html,
            )
        )
    return "".join(rows)


def render_limitations(items):
    rows = []
    for item in items:
        claim_type = item.get("claim_type", "critique")
        rows.append(
            '<article class="boundary-item" data-search="{search}"><span class="boundary-badge">{badge}</span>'
            '<h3>{title}</h3><p>{body}</p>{anchor}</article>'.format(
                search=esc(" ".join([item.get("title", ""), item.get("body", "")])),
                badge=esc(CLAIM_LABELS.get(claim_type, claim_type)),
                title=esc(item.get("title")),
                body=esc(item.get("body")),
                anchor=anchor_chip(item.get("source_anchor")),
            )
        )
    return "".join(rows)


def render_glossary(items):
    return "".join(
        '<div data-search="{search}"><dt>{term}</dt><dd>{definition}</dd></div>'.format(
            search=esc(" ".join([item.get("term", ""), item.get("definition", "")])),
            term=esc(item.get("term")),
            definition=esc(item.get("definition")),
        )
        for item in items
    )


def canonical_source(paper):
    doi = str(paper.get("doi") or "").strip()
    url = str(paper.get("url") or "").strip()
    if doi:
        return f"https://doi.org/{doi.removeprefix('https://doi.org/')}"
    if url.startswith(("https://", "http://")):
        return url
    return ""


def build_html(brief, visuals, source_pdf):
    paper = brief["paper"]
    summary = brief["summary"]
    title = paper["title"]
    authors = ", ".join(paper.get("authors", []))
    venue_bits = [str(paper.get(key, "")).strip() for key in ("venue", "year") if paper.get(key)]
    venue = " · ".join(venue_bits)
    source_url = canonical_source(paper)
    source_html = f'<a href="{esc(source_url)}" target="_blank" rel="noopener">论文入口</a>' if source_url else ""
    doi = str(paper.get("doi") or "").strip()
    doi_button = f'<button type="button" data-copy="{esc(doi)}">复制 DOI</button>' if doi else ""
    reading_minutes = brief.get("reader", {}).get("reading_minutes", max(3, len(brief.get("sections", [])) * 2))
    quick_points = "".join(
        f"<li><strong>重点 {index}</strong>{esc(point)}</li>"
        for index, point in enumerate(summary.get("quick_points", []), start=1)
    )
    visual_counts = {
        kind: sum(1 for item in visuals if item.get("kind") == kind) for kind in ("figure", "table", "equation")
    }
    visual_count_text = " · ".join(
        f"{KIND_LABELS[kind]} {count}" for kind, count in visual_counts.items() if count
    ) or "无编号视觉元素"
    visuals_by_id = {item.get("id"): item for item in visuals}
    questions = "".join(f"<li>{esc(value)}</li>" for value in brief.get("questions", []))
    glossary = render_glossary(brief.get("glossary", []))
    logic_count = max(1, min(5, len(brief.get("logic_map", []))))
    citation = " · ".join(value for value in [authors, venue, doi] if value)

    nav_items = [
        ("quick", "30 秒结论", "scan"),
        ("logic", "论证路径", "standard"),
        ("claims", "核心主张", "standard"),
        ("visuals", "图表公式", "standard"),
        ("walkthrough", "逐段深读", "deep"),
        ("boundaries", "边界与追问", "standard"),
    ]
    if glossary:
        nav_items.append(("glossary", "术语表", "deep"))
    nav = "".join(
        f'<li data-nav-depth="{depth}"><a href="#{section_id}">{label}</a></li>'
        for section_id, label, depth in nav_items
    )

    glossary_section = ""
    if glossary:
        glossary_section = f"""
        <section class="reader-section" id="glossary" data-depth="deep">
          <div class="section-head">
            <div><p class="section-kicker">Terminology</p><h2 class="section-title">先把术语说清楚</h2></div>
            <p class="section-note">保留英文术语，中文只解释本论文语境中的含义。</p>
          </div>
          <dl class="glossary reveal">{glossary}</dl>
        </section>"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(summary.get('one_sentence'))}">
  <title>{esc(title)} · Paper Ear</title>
  <link rel="stylesheet" href="styles.css">
  <script>document.documentElement.classList.add('js');</script>
</head>
<body data-mode="standard">
  <a class="skip-link" href="#main-content">跳到正文</a>
  <header class="paper-hero">
    <div class="hero-inner">
      <div>
        <p class="hero-kicker">Paper Ear · Interactive evidence reader</p>
        <h1 class="hero-title">{esc(title)}</h1>
        <p class="hero-authors">{esc(authors)}</p>
        <div class="hero-source"><span>{esc(venue)}</span><span>{esc(paper.get('doi', ''))}</span>{source_html}</div>
      </div>
      <div class="hero-summary">
        <span class="meta-label">一句话先读懂</span>
        <p>{esc(summary.get('one_sentence'))}</p>
      </div>
    </div>
    <div class="hero-orbit" aria-hidden="true"></div>
  </header>

  <div class="reader-shell">
    <aside class="reading-rail" aria-label="阅读控制">
      <h2 class="rail-title">选择阅读速度</h2>
      <div class="mode-switch" role="group" aria-label="阅读深度">
        <button type="button" data-reader-mode="scan" aria-pressed="false">30 秒</button>
        <button type="button" data-reader-mode="standard" aria-pressed="true">3 分钟</button>
        <button type="button" data-reader-mode="deep" aria-pressed="false">深读</button>
      </div>
      <label for="reader-search" class="meta-label">页面内检索</label>
      <input class="reader-search" id="reader-search" type="search" placeholder="例如：Figure 7、RMSD、局限">
      <p class="search-status" id="search-status" aria-live="polite">输入术语、结论、页码或图表编号</p>
      <nav aria-label="论文结构"><ol class="rail-nav">{nav}</ol></nav>
      <p class="rail-meta">预计阅读 {esc(reading_minutes)} 分钟<br>{esc(visual_count_text)}<br>PDF 共 {esc(paper.get('page_count'))} 页</p>
    </aside>

    <main class="reader-content" id="main-content">
      <section class="reader-section" id="quick" data-depth="scan">
        <div class="section-head">
          <div><p class="section-kicker">Fast pass</p><h2 class="section-title">30 秒，先抓住论文骨架</h2></div>
          <p class="section-note">这里是导航，不代替原论文；所有数字和结论都应能回到 PDF 页码。</p>
        </div>
        <ol class="quick-points reveal">{quick_points}</ol>
        <p class="three-minute reveal">{esc(summary.get('three_minute'))}</p>
      </section>

      <section class="reader-section" id="logic" data-depth="standard">
        <div class="section-head">
          <div><p class="section-kicker">Argument spine</p><h2 class="section-title">研究问题怎样走到结论</h2></div>
          <p class="section-note">沿着问题、方法、证据和边界阅读，避免把“作者说了什么”误当成“数据已经证明什么”。</p>
        </div>
        <ol class="logic-map" style="--logic-count:{logic_count}">{render_logic_map(brief.get('logic_map', []))}</ol>
      </section>

      <section class="reader-section" id="claims" data-depth="standard">
        <div class="section-head">
          <div><p class="section-kicker">Evidence ledger</p><h2 class="section-title">核心主张与证据强度</h2></div>
          <p class="section-note">红色是论文/作者内容；青色是讲解推断；琥珀色是批判性分析。</p>
        </div>
        <div class="claim-ledger">{render_claims(brief.get('claims', []))}</div>
      </section>

      <section class="reader-section" id="visuals" data-depth="standard">
        <div class="section-head">
          <div><p class="section-kicker">Original visual evidence</p><h2 class="section-title">图、表、公式，一个都不丢</h2></div>
          <p class="section-note">展示的是 PDF 原始像素裁切，不重画数据；点击可在高清裁图与原页定位之间切换。</p>
        </div>
        <div class="visual-toolbar" role="group" aria-label="视觉证据筛选">
          <button type="button" data-visual-filter="all" aria-pressed="true">全部</button>
          <button type="button" data-visual-filter="figure" aria-pressed="false">图</button>
          <button type="button" data-visual-filter="table" aria-pressed="false">表</button>
          <button type="button" data-visual-filter="equation" aria-pressed="false">公式</button>
        </div>
        <div class="visual-gallery">{render_visuals(visuals, source_pdf)}</div>
      </section>

      <section class="reader-section" id="walkthrough" data-depth="deep">
        <div class="section-head">
          <div><p class="section-kicker">Deep reading</p><h2 class="section-title">按论文逻辑逐段梳理</h2></div>
          <p class="section-note">正文采用可搜索文本；图表公式使用原图，兼顾浏览速度和版面忠实度。</p>
        </div>
        <div class="walkthrough">{render_sections(brief.get('sections', []), visuals_by_id)}</div>
      </section>

      <section class="reader-section" id="boundaries" data-depth="standard">
        <div class="section-head">
          <div><p class="section-kicker">Evidence boundary</p><h2 class="section-title">结论能走多远，哪里要刹车</h2></div>
          <p class="section-note">把作者自述的限制与我们的批判性判断分开，不替论文扩大结论。</p>
        </div>
        <div class="boundary-grid reveal">
          <div class="boundary-panel"><h3>局限与风险</h3>{render_limitations(brief.get('limitations', []))}</div>
          <aside class="boundary-panel"><h3>带去组会的问题</h3><ol class="questions">{questions}</ol></aside>
        </div>
      </section>

      {glossary_section.strip()}
    </main>
  </div>

  <footer class="reader-footer">
    <p><strong>引用线索：</strong>{esc(citation)}</p>
    <p>由 Paper Ear 生成。摘要、推断与批评均保留声明类型和 PDF 页码；请以原论文为最终依据。 {doi_button}</p>
  </footer>

  <dialog class="visual-dialog" id="visual-dialog" aria-labelledby="dialog-title">
    <div class="dialog-head"><h2 id="dialog-title">视觉证据</h2><button class="dialog-close" id="dialog-close" type="button" aria-label="关闭">×</button></div>
    <div class="dialog-body"><img id="dialog-image" src="" alt="论文视觉证据预览"></div>
    <div class="dialog-actions" role="group" aria-label="图像视图">
      <button type="button" data-dialog-view="crop" aria-pressed="true">高清裁图</button>
      <button type="button" data-dialog-view="source" aria-pressed="false">PDF 原页定位</button>
    </div>
  </dialog>
  <script src="app.js" defer></script>
</body>
</html>
"""


def ensure_output_dir(output_dir, force):
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f"Output directory is not empty: {output_dir}. Use --force to overwrite known files.")
    output_dir.mkdir(parents=True, exist_ok=True)
    if force:
        # Remove only files produced by this renderer. User-created files and
        # unrelated subdirectories remain untouched.
        for name in ("index.html", "styles.css", "app.js", "data.json", "source.pdf"):
            path = output_dir / name
            if path.is_file():
                path.unlink()
        assets_dir = output_dir / "assets"
        if assets_dir.is_dir():
            for pattern in ("visual-*.png", "source-*.jpg"):
                for path in assets_dir.glob(pattern):
                    if path.is_file():
                        path.unlink()


def main():
    parser = argparse.ArgumentParser(description="Render a static interactive paper-reading website.")
    parser.add_argument("--pdf", required=True, help="Input PDF")
    parser.add_argument("--brief", required=True, help="Validated web_brief.json")
    parser.add_argument("--output-dir", required=True, help="Website output directory")
    parser.add_argument("--pages-dir", help="Optional existing rendered page PNG directory")
    parser.add_argument("--dpi", type=int, default=180, help="PDF render DPI when --pages-dir is omitted")
    parser.add_argument("--copy-pdf", action="store_true", help="Copy the source PDF into the website for page links")
    parser.add_argument("--force", action="store_true", help="Overwrite known output files in a non-empty directory")
    parser.add_argument("--report-json", help="Optional render report path")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    brief_path = Path(args.brief).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not brief_path.is_file():
        raise FileNotFoundError(f"Brief not found: {brief_path}")
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(f"Web template assets not found: {TEMPLATE_DIR}")

    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    ensure_output_dir(output_dir, args.force)
    generated_pages = False
    temporary_pages = None
    if args.pages_dir:
        pages_dir = Path(args.pages_dir).expanduser().resolve()
        if not pages_dir.is_dir():
            raise FileNotFoundError(f"Pages directory not found: {pages_dir}")
    else:
        temporary_pages = tempfile.TemporaryDirectory(prefix="paper-ear-pages-")
        pages_dir = Path(temporary_pages.name)
        render_pages(pdf_path, pages_dir, args.dpi)
        generated_pages = True

    visuals = crop_visuals(brief, pages_dir, output_dir)
    shutil.copy2(TEMPLATE_DIR / "styles.css", output_dir / "styles.css")
    shutil.copy2(TEMPLATE_DIR / "app.js", output_dir / "app.js")

    source_pdf = ""
    if args.copy_pdf:
        shutil.copy2(pdf_path, output_dir / "source.pdf")
        source_pdf = "source.pdf"

    website_data = dict(brief)
    website_data["visuals"] = visuals
    website_data["render"] = {
        "source_pdf_included": bool(source_pdf),
        "dpi": args.dpi,
        "generated_pages": generated_pages,
    }
    (output_dir / "data.json").write_text(
        json.dumps(website_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "index.html").write_text(
        build_html(website_data, visuals, source_pdf), encoding="utf-8"
    )

    report = {
        "ok": True,
        "pdf": str(pdf_path),
        "brief": str(brief_path),
        "output_dir": str(output_dir),
        "index": str(output_dir / "index.html"),
        "source_pdf_included": bool(source_pdf),
        "stats": {
            "visuals": len(visuals),
            "figures": sum(1 for item in visuals if item.get("kind") == "figure"),
            "tables": sum(1 for item in visuals if item.get("kind") == "table"),
            "equations": sum(1 for item in visuals if item.get("kind") == "equation"),
            "sections": len(brief.get("sections", [])),
            "claims": len(brief.get("claims", [])),
        },
    }
    if args.report_json:
        report_path = Path(args.report_json).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if temporary_pages is not None:
        temporary_pages.cleanup()
    print(
        f"Rendered web reader: {output_dir / 'index.html'} "
        f"({len(visuals)} visual(s), {len(brief.get('claims', []))} claim(s))"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
