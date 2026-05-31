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

## Current Fragile Areas

The parser issues found during the stress-deck build have been repaired in `md2pptx` and the corresponding markdown controls have been re-enabled in `pptx-test`.

Fixed areas:

- Styled TOC rendering now flattens nested bullet lists locally and normalizes TOC section link keys.
- Dynamic `addTableRowLines` / `addTableColumnLines` uses `sortedNumericList()` from `processingOptions.py`.
- `addTableLines: both` is accepted as the documented alias for all-cell-edge table lines.
- Dynamic card graphic metadata accepts `cardGraphicSize`, `cardGraphicPadding`, and `cardGraphicPosition` case-insensitively, then stores canonical camelCase option names.
- Dynamic funnel metadata accepts documented `funnelLabelsPosition` plus singular `funnelLabelPosition`, parses dynamic funnel colours through `parseColour()`, and stores canonical camelCase option names.

Remaining intentional exclusions:

- Embedded audio/video slides are still excluded from the default stress deck. LibreOffice media playback and poster handling was unstable and could hang review.
- Slide notes appeared to hang LibreOffice review on one machine. Track this in `pptx-test/TODO.md` and test on another machine before drawing conclusions about PowerPoint behavior.
- Single-row three-image tables should still be avoided; use documented image layouts instead.

## Option Casing

Deck authors can use camelCase or lowercase option names. Top-level and dynamic metadata keys are lowercased while parsing, and `ProcessingOptions` stores option keys in lowercase internally.

Prefer documenting and writing options in canonical camelCase because that matches default declarations and read sites, for example:

- `cardGraphicPadding`
- `funnelLabelsPosition`
- `funnelBorderColour`
- `addTableLines`
- `tocStyle`

The lower-case dynamic forms in the stress deck are accepted input aliases, not separate option names.

## Repro And Validation

Isolated repro decks were created under:

```text
/home/heinjj/Compile/pptx-test/tmp/repro
```

Useful repros:

- `toc.md`: styled TOC and TOC links.
- `table-lines.md`: dynamic row/column line metadata.
- `card-padding.md`: dynamic card graphic padding.
- `funnel-colour.md`: dynamic funnel colour metadata.
- `funnel-labels.md`: documented funnel label-position alias.

Each repro should build with:

```bash
cd /home/heinjj/Compile/md2pptx
uv run python ./md2pptx \
  /home/heinjj/Compile/pptx-test/tmp/repro/toc.md \
  /home/heinjj/Compile/pptx-test/tmp/repro/toc.pptx
```

The stress deck should build with all repaired TOC, table, card, and funnel metadata enabled. If a future change breaks one of these, prefer creating or updating a small repro in `pptx-test/tmp/repro` before changing the full stress deck.

## Current Stress Deck State

The stress deck currently builds with `uv run python ./md2pptx` and includes the repaired TOC, dynamic table line, card graphic padding, and funnel styling metadata.

The Flatpak LibreOffice path can convert it to PDF when input and output are under `/home/heinjj/...`.

The deck intentionally avoids embedded audio/video.
