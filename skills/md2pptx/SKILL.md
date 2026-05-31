---
name: md2pptx
description: Build, test, and debug md2pptx Markdown-to-PowerPoint decks, including GraphViz, image layouts, tables, cards, funnels, inline Python, uv-managed dependencies, and LibreOffice Flatpak validation. Use when creating or repairing md2pptx markdown decks or diagnosing md2pptx parser/rendering issues.
---

# md2pptx

Use this skill when creating or debugging decks for the `md2pptx` project.

## Repositories

- Tool repo: `/home/heinjj/Compile/md2pptx`
- Test-deck repo: `/home/heinjj/Compile/pptx-test`
- Main stress deck: `/home/heinjj/Compile/pptx-test/feature-stress-test.md`
- Generated deck: `/home/heinjj/Compile/pptx-test/feature-stress-test.pptx`

`pptx-test` is also a Git repo. When changing test markdown to work around brittle behavior, commit each logical workaround there with a message explaining what changed and why.

## Environment

Run md2pptx through `uv` from the tool repo:

```bash
cd /home/heinjj/Compile/md2pptx
uv run python ./md2pptx \
  /home/heinjj/Compile/pptx-test/feature-stress-test.md \
  /home/heinjj/Compile/pptx-test/feature-stress-test.pptx
```

The project has `pyproject.toml` and `uv.lock` with the needed runtime dependencies:

- `python-pptx`
- `graphviz`
- `cairosvg`
- `pillow`
- `lxml`

GraphViz requires both the system Graphviz executable and the Python `graphviz` package.

## LibreOffice Testing

There are two LibreOffice installs on the machine. The native `/usr/bin/libreoffice` may lack Impress and fail every PPTX import with `Error: source file could not be loaded`.

Use the Flatpak for PPTX validation:

```bash
flatpak run org.libreoffice.LibreOffice \
  --headless \
  --convert-to pdf \
  --outdir /home/heinjj/Compile/pptx-test/libo-out \
  /home/heinjj/Compile/pptx-test/feature-stress-test.pptx
```

Keep Flatpak input and output under `/home/heinjj/...`. Host `/tmp` may not be visible inside the Flatpak sandbox.

For temporary bisection files, use:

```text
/home/heinjj/Compile/pptx-test/tmp
```

## Deck Creation Guidelines

Prefer feature-rich but stable markdown:

- Use `#` for the presentation title, `##` for sections, `###` for slides, and `####` for cards.
- Use `*` for bullets. `-` starts Taskpaper tasks.
- Use absolute local paths for test assets to avoid cwd ambiguity.
- Use ` ```dot ` blocks for GraphViz diagrams.
- Use documented image layouts: one image, two side-by-side images, two-over-one, one-over-two, two-by-two, or one-over-one.
- Avoid single-row three-image tables. They may render as literal `!` markers.
- Use `<figcaption>` only immediately below a single image.
- Put table captions immediately after the last table row with no blank line.
- Use inline Python only when needed, and keep it small.

Good GraphViz coding-session scenarios:

- Architecture graph: client, web, API, worker, DB, cache.
- Request/failure flow: validate, auth, persist, error paths.
- Dependency graph: markdown, md2pptx, python-pptx, GraphViz, CairoSVG, output.
- Incident decision tree: alert, reproduce, patch, rollback, observe, escalate.

## Known Bad Or Fragile Areas

These were disabled in the stress deck so it could build and open cleanly.

### TOC metadata

Disabled lines included:

```text
tocStyle: circle
tocTitle: Topics
tocLinks: yes
tocItemColour: E7EEF8
tocFontSize: 12
tocItemHeight: 1.1
tocRowGap: 0.4
sectionArrows: yes
sectionArrowsColour: E7EEF8
SectionsExpand: yes
```

Failure: `createTOCSlide()` crashes because `SlideInfo.bullets` is a list of bullet lists, but TOC code iterates it as if each item were a single `[level, text, type]` triple.

Do not re-enable TOC in the stress deck until md2pptx flattens TOC bullets locally.

### Table dynamic line metadata

Disabled lines included:

```text
<!-- md2pptx: tableheadingsize: 16 -->
<!-- md2pptx: addtablelines: both -->
<!-- md2pptx: addtablerowlines: 1 -->
<!-- md2pptx: addtablecolumnlines: 1 2 -->
<!-- md2pptx: addtablelinecolour: 808080 -->
```

Failure: dynamic `addTableRowLines` / `addTableColumnLines` calls `sortedNumericList()` from `processingOptions.py`, but that helper is defined in `md2pptx`, not in `processingOptions.py`.

Also, docs say `addTableLines: both`, while renderer appears to handle `all`. Treat this as a code/docs mismatch.

### Card graphic dynamic metadata

Disabled line:

```text
<!-- md2pptx: cardgraphicpadding: 0.1 -->
```

Failure: dynamic metadata parser lowercases keys but compares some keys against camelCase names, so this is rejected as invalid. Top-level `cardGraphicPadding` metadata is supported.

### Funnel dynamic metadata

Disabled lines included:

```text
<!-- md2pptx: funnelcolours: ACCENT 1, ACCENT 2, ACCENT 3, ACCENT 4, ACCENT 5 -->
<!-- md2pptx: funnelbordercolour: ACCENT 6 -->
<!-- md2pptx: funneltitlecolour: TEXT 1 -->
<!-- md2pptx: funneltextcolour: TEXT 1 -->
<!-- md2pptx: funnellabelspercent: 18 -->
<!-- md2pptx: funnellabelsposition: after -->
<!-- md2pptx: funnelwidest: pipe -->
```

Failures:

- `funnelLabelsPosition` is documented, but dynamic code accepts singular `funnelLabelPosition`.
- Dynamic funnel border/title/text color values are stored as raw strings, but rendering expects parsed `(type, value)` tuples from `parseColour()`.

Use default funnel styling in stress decks until code is fixed.

### Media slides

Audio/video slides were removed. LibreOffice media playback and poster handling was unstable and could hang review. The poster images came from the repo's battery sample images.

Do not include embedded audio/video in the default stress deck unless specifically testing media behavior.

### Notes review

Slide notes appeared to hang LibreOffice review on one machine. Track this in `pptx-test/TODO.md` and test on another machine before drawing conclusions about PowerPoint behavior.

## Minimal Code Repair Plan

There is an untracked local plan in:

```text
/home/heinjj/Compile/md2pptx/.plans/repair-toc-and-dynamic-metadata.md
```

The plan keeps fixes local:

- Add a helper that flattens bullet lists for TOC rendering.
- Add or move `sortedNumericList()` into `processingOptions.py`.
- Normalize dynamic metadata keys using lowercase comparisons.
- Parse dynamic funnel colors with `parseColour()`.
- Treat `addTableLines: both` as equivalent to `all`.

Do not change parser architecture, `SlideInfo`, or slide sequencing unless a minimal local fix is impossible.

## Repro And Validation

Isolated repro decks were created under:

```text
/home/heinjj/Compile/pptx-test/tmp/repro
```

Useful repros:

- `toc.md`: TOC crash.
- `table-lines.md`: dynamic row/column line crash.
- `card-padding.md`: invalid dynamic key warning.
- `funnel-colour.md`: dynamic color tuple crash.
- `funnel-labels.md`: invalid dynamic key warning.

After code fixes, each repro should build with:

```bash
cd /home/heinjj/Compile/md2pptx
uv run python ./md2pptx \
  /home/heinjj/Compile/pptx-test/tmp/repro/toc.md \
  /home/heinjj/Compile/pptx-test/tmp/repro/toc.pptx
```

Then re-enable the disabled stress-deck features one group at a time in `pptx-test`, committing each markdown re-enable with an explanation.

## Current Stress Deck State

The stress deck currently builds with `uv run python ./md2pptx`.

The Flatpak LibreOffice path can convert it to PDF when input and output are under `/home/heinjj/...`.

The deck intentionally avoids:

- TOC-specific styling metadata.
- Dynamic table line metadata.
- Dynamic funnel styling metadata.
- Dynamic card graphic padding.
- Embedded audio/video.
