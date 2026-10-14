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

## Browser inspection

- [ ] A headless Chromium run reaches network idle with no uncaught JavaScript errors.
- [ ] Desktop and mobile full-page screenshots were inspected, not only generated.
- [ ] Long titles, long captions, dense tables, and portrait figures do not overflow.
- [ ] Opening every visual does not reveal broken images or mismatched source pages.

Do not call the reader complete if deterministic checks pass but page-by-page visual
inspection has not happened. Completeness is a content judgment, not merely a schema
property.
