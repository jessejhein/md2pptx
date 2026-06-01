"""Mermaid diagram rendering support for md2pptx.

This module encapsulates Mermaid-specific rendering so the main md2pptx
script only needs to dispatch a fenced code block to a renderer.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Optional, Sequence

import cairosvg
import mmdc
from mmdc import MermaidConverter


RenderedGraphicAdder = Callable[[Any, Any, str], None]
WarningWriter = Callable[[str], None]
mmdc_version = getattr(mmdc, "__version__", "Installed")


class MermaidRenderError(RuntimeError):
    """Raised when Mermaid source cannot be rendered for a slide."""


@dataclass
class MermaidRenderOptions:
    """User-configurable Mermaid rendering options."""

    png_width: Optional[int] = 1600
    flowchart_html_labels: bool = False
    gantt_axis_label_regex: str = r"\d{1,2}:\d{2}"
    gantt_rotate_axis_labels: bool = True
    gantt_axis_label_rotation: float = -35.0
    gantt_use_width: Optional[int] = None


def write_warning(message: str) -> None:
    """Write a Mermaid warning to stderr."""
    sys.stderr.write(f"Mermaid warning: {message}\n")


def build_mermaid_config(options: MermaidRenderOptions) -> dict[str, Any]:
    """Build the mmdc config object from renderer options."""
    config: dict[str, Any] = {
        "flowchart": {
            "htmlLabels": options.flowchart_html_labels,
        },
    }

    if options.gantt_use_width is not None and options.gantt_use_width > 0:
        config["gantt"] = {"useWidth": options.gantt_use_width}

    return config


def detect_diagram_type(mermaid_source: str) -> str:
    """Return the diagram type from the first non-empty Mermaid source line."""
    for line in mermaid_source.splitlines():
        stripped_line = line.strip()
        if stripped_line != "":
            return stripped_line.split(maxsplit=1)[0].lower()

    return ""


def postprocess_gantt_svg(
    svg_content: str,
    options: MermaidRenderOptions,
    warning_writer: WarningWriter = write_warning,
) -> str:
    """Apply conservative Gantt-axis cleanup to Mermaid SVG content.

    Only the Mermaid 7.1.2 axis tick shape ``g.grid > g.tick > text`` is
    modified. If that structure is not present, the original SVG is returned
    unchanged and a warning is emitted.
    """
    root = _parse_svg(svg_content)
    axis_text_nodes = _find_gantt_axis_text_nodes(root)

    if len(axis_text_nodes) == 0:
        warning_writer(
            "Gantt SVG post-processing skipped because the expected axis "
            "tick structure was not recognized."
        )
        return svg_content

    label_regex: Optional[re.Pattern[str]] = None
    if options.gantt_axis_label_regex != "":
        try:
            label_regex = re.compile(options.gantt_axis_label_regex)
        except re.error as exc:
            raise MermaidRenderError(
                f"Invalid mermaidGanttAxisLabelRegex: {exc}"
            ) from exc

    for text_element in axis_text_nodes:
        label = "".join(text_element.itertext()).strip()
        if label_regex is not None and label_regex.fullmatch(label):
            text_element.text = ""
            continue

        if options.gantt_rotate_axis_labels:
            _rotate_axis_label(text_element, options.gantt_axis_label_rotation)

    return ET.tostring(root, encoding="unicode")


def validate_svg(svg_content: str) -> None:
    """Validate that SVG content is well-formed and renderable."""
    root = _parse_svg(svg_content)

    if _local_name(root.tag) != "svg":
        raise MermaidRenderError("Mermaid output was not an SVG document.")

    if not _has_renderable_size(root):
        raise MermaidRenderError("Mermaid SVG has no viewBox, width, or height.")


def convert_svg_to_png(
    svg_file: str,
    png_file: str,
    output_width: Optional[int],
) -> None:
    """Convert an SVG file to PNG and verify the output was created."""
    kwargs: dict[str, Any] = {
        "url": svg_file,
        "write_to": png_file,
    }

    if output_width is not None and output_width > 0:
        kwargs["output_width"] = output_width

    try:
        cairosvg.svg2png(**kwargs)
    except Exception as exc:
        raise MermaidRenderError(f"Could not convert Mermaid SVG to PNG: {exc}") from exc

    png_path = Path(png_file)
    if not png_path.exists() or png_path.stat().st_size == 0:
        raise MermaidRenderError("Mermaid PNG output was not created.")


@dataclass
class MermaidRenderer:
    """Render Mermaid source into a slide graphic.

    Parameters
    ----------
    temp_dir:
        Optional directory to use for temporary SVG and PNG files.
    export_graphics:
        Whether generated graphics should be preserved after rendering.
    options:
        Mermaid-specific rendering options.
    warning_writer:
        Callable used for non-fatal Mermaid warnings.
    """

    temp_dir: Optional[str]
    export_graphics: bool
    options: MermaidRenderOptions = field(default_factory=MermaidRenderOptions)
    warning_writer: WarningWriter = write_warning

    def render_slide(
        self,
        slide: Any,
        rendering_rectangle: Any,
        code_lines: Sequence[str],
        add_rendered_graphic: RenderedGraphicAdder,
    ) -> bool:
        """Render Mermaid code lines into the provided slide."""
        svg_file: Optional[str] = None
        png_file: Optional[str] = None
        config_file: Optional[str] = None

        try:
            self._validate_temp_dir()
            mermaid_source = "\n".join(code_lines)
            config_file = self._write_config()
            svg_content = self._render_svg(mermaid_source, config_file)
            svg_content = self._postprocess_svg(mermaid_source, svg_content)
            validate_svg(svg_content)
            svg_file = self._write_svg(svg_content)
            png_file = self._convert_svg(svg_file)
            add_rendered_graphic(slide, rendering_rectangle, png_file)
            return True
        finally:
            self._cleanup_files(svg_file, png_file, config_file)

    def _validate_temp_dir(self) -> None:
        """Ensure configured temporary output can be written."""
        if self.temp_dir is None:
            return

        temp_path = Path(self.temp_dir)
        if not temp_path.exists():
            raise MermaidRenderError(
                f"Mermaid tempDir does not exist: {self.temp_dir}"
            )

        if not temp_path.is_dir():
            raise MermaidRenderError(
                f"Mermaid tempDir is not a directory: {self.temp_dir}"
            )

    def _write_config(self) -> str:
        """Write Mermaid config JSON to a temporary file."""
        config_file = NamedTemporaryFile(
            delete=False,
            suffix=".json",
            dir=self.temp_dir,
            mode="w",
            encoding="utf-8",
        )
        json.dump(build_mermaid_config(self.options), config_file)
        config_file.close()
        return config_file.name

    def _render_svg(self, mermaid_source: str, config_file: str) -> str:
        """Render Mermaid source to SVG text using the Python API."""
        converter = MermaidConverter()

        try:
            svg_content = converter.to_svg(
                input=mermaid_source,
                config_file=Path(config_file),
                background="white",
            )
        except Exception as exc:
            raise MermaidRenderError(f"Mermaid SVG rendering failed: {exc}") from exc

        if not isinstance(svg_content, str) or svg_content == "":
            raise MermaidRenderError("No Mermaid SVG output was created.")

        return svg_content

    def _postprocess_svg(self, mermaid_source: str, svg_content: str) -> str:
        """Apply diagram-specific SVG post-processing."""
        if detect_diagram_type(mermaid_source) == "gantt":
            return postprocess_gantt_svg(
                svg_content,
                self.options,
                self.warning_writer,
            )

        return svg_content

    def _write_svg(self, svg_content: str) -> str:
        """Persist SVG text to a temporary file and return its path."""
        svg_file = NamedTemporaryFile(
            delete=False,
            suffix=".svg",
            dir=self.temp_dir,
            mode="w",
            encoding="utf-8",
        )
        svg_file.write(svg_content)
        svg_file.close()
        return svg_file.name

    def _convert_svg(self, svg_file: str) -> str:
        """Convert an SVG file to a temporary PNG and return its path."""
        png_file = NamedTemporaryFile(
            delete=False,
            suffix=".png",
            dir=self.temp_dir,
        )
        png_file.close()
        convert_svg_to_png(svg_file, png_file.name, self.options.png_width)
        return png_file.name

    def _cleanup_files(self, *filenames: Optional[str]) -> None:
        """Remove temporary files unless graphics export is enabled."""
        if self.export_graphics:
            return

        for filename in filenames:
            if filename is not None and Path(filename).exists():
                Path(filename).unlink()


def _parse_svg(svg_content: str) -> ET.Element:
    """Parse SVG XML and raise a Mermaid-specific error on failure."""
    try:
        return ET.fromstring(svg_content)
    except ET.ParseError as exc:
        raise MermaidRenderError(f"Mermaid SVG is not well-formed XML: {exc}") from exc


def _has_renderable_size(root: ET.Element) -> bool:
    """Return whether an SVG root has usable size metadata."""
    view_box = root.attrib.get("viewBox")
    if view_box is not None and view_box.strip() != "":
        return True

    return (
        root.attrib.get("width", "").strip() != ""
        and root.attrib.get("height", "").strip() != ""
    )


def _find_gantt_axis_text_nodes(root: ET.Element) -> list[ET.Element]:
    """Find Mermaid Gantt axis text nodes using the known SVG structure."""
    axis_text_nodes: list[ET.Element] = []

    for grid_group in root.iter():
        if _local_name(grid_group.tag) != "g" or "grid" not in _class_names(grid_group):
            continue

        for tick_group in list(grid_group):
            if _local_name(tick_group.tag) != "g" or "tick" not in _class_names(tick_group):
                continue

            for child in list(tick_group):
                if _local_name(child.tag) == "text":
                    axis_text_nodes.append(child)

    return axis_text_nodes


def _rotate_axis_label(text_element: ET.Element, angle: float) -> None:
    """Rotate an axis label around its SVG text anchor point."""
    x = text_element.attrib.get("x", "0")
    y = text_element.attrib.get("y", "0")
    rotation = f"rotate({angle:g} {x} {y})"
    existing_transform = text_element.attrib.get("transform", "")

    if existing_transform == "":
        text_element.set("transform", rotation)
    else:
        text_element.set("transform", f"{existing_transform} {rotation}")

    _set_text_anchor(text_element, "end")


def _set_text_anchor(text_element: ET.Element, value: str) -> None:
    """Set text-anchor in inline style without discarding other style values."""
    style = text_element.attrib.get("style", "")
    style_parts = [part.strip() for part in style.split(";") if part.strip() != ""]
    updated_parts: list[str] = []
    found = False

    for part in style_parts:
        if part.split(":", 1)[0].strip() == "text-anchor":
            updated_parts.append(f"text-anchor: {value}")
            found = True
        else:
            updated_parts.append(part)

    if not found:
        updated_parts.append(f"text-anchor: {value}")

    text_element.set("style", "; ".join(updated_parts))


def _local_name(tag: str) -> str:
    """Return an XML tag name without its namespace."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]

    return tag


def _class_names(element: ET.Element) -> set[str]:
    """Return the whitespace-separated class names for an SVG element."""
    return set(element.attrib.get("class", "").split())
