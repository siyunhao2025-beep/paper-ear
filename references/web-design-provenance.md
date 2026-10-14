# Web-reader design provenance

This feature was designed after a GitHub survey on 2026-10-14. Star counts are
repository-level snapshots, not evidence that an individual skill inside a
monorepo has the same popularity. Paper Ear borrows workflow ideas only; it does
not copy source code or bundle these projects as required dependencies.

| Project | Snapshot | Mechanism retained in Paper Ear |
| --- | ---: | --- |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 48,774 stars | thematic synthesis, reproducible evidence boundaries, and avoiding study-by-study narration |
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | 83,836 stars | claim/evidence review, strengths/weaknesses, methodology, literature position, limitations, and reviewer questions |
| [opendatalab/MinerU](https://github.com/opendatalab/MinerU) | 81,696 stars | page/block locators and explicit image retrieval; suitable as an optional enhanced parser |
| [docling-project/docling](https://github.com/docling-project/docling) | 68,841 stars | reading order, table structure, formulas, and local execution; suitable as an optional enhanced parser |
| [datalab-to/marker](https://github.com/datalab-to/marker) | 40,431 stars | hybrid PDF conversion with images, formatted tables, LaTeX equations, and JSON; suitable as an optional enhanced parser |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | 9,364 stars | citation-grounded claims, metadata-aware retrieval, and contextual summaries |
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | 31,627 stars | hierarchical argument structure, perspective-guided questions, and reduced cognitive load |

Two design decisions follow from the survey:

1. A high-star *single-paper reader skill* was not found. The high-star ecosystem
   is split among scientific skill collections, layout-aware PDF parsers, and
   citation-grounded research systems. Therefore Paper Ear integrates the common
   mechanisms rather than presenting one project as a direct template.
2. MinerU, Docling, and Marker are not mandatory dependencies. The default path
   remains lightweight (`pdfplumber`, Pillow, Poppler); enhanced parsers may be
   used when a difficult paper needs better reading order, tables, or formulas.

The resulting reader keeps searchable text for synthesis and uses source-pixel
crops for figures, tables, and displayed equations. A region is never considered
covered merely because a parser mentioned its caption: all pages must still be
visually reviewed.
