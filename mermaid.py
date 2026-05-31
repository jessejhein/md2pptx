"""Mermaid diagram rendering support for md2pptx.

This module encapsulates Mermaid-specific rendering so the main md2pptx
script only needs to dispatch a fenced code block to a renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Optional, Sequence

import cairosvg
import mmdc
from mmdc import MermaidConverter


RenderedGraphicAdder = Callable[[Any, Any, str], None]
mmdc_version = getattr(mmdc, "__version__", "Installed")


class MermaidRenderError(RuntimeError):
    """Raised when Mermaid source cannot be rendered for a slide."""


@dataclass
class MermaidRenderer:
    """Render Mermaid source into a slide graphic.

    Parameters
    ----------
    temp_dir:
        Optional directory to use for temporary SVG and PNG files.
    export_graphics:
        Whether generated graphics should be preserved after rendering.
    """

    temp_dir: Optional[str]
    export_graphics: bool

    def render_slide(
        self,
        slide: Any,
        rendering_rectangle: Any,
        code_lines: Sequence[str],
        add_rendered_graphic: RenderedGraphicAdder,
    ) -> bool:
        """Render Mermaid code lines into the provided slide.

        The Mermaid source is rendered to SVG in-process and then converted to
        PNG via CairoSVG before being added to the slide.
        """
        svg_file: Optional[str] = None
        png_file: Optional[str] = None

        try:
            svg_content = self._render_svg("\n".join(code_lines))
            svg_file = self._write_svg(svg_content)
            png_file = self._convert_svg(svg_file)
            add_rendered_graphic(slide, rendering_rectangle, png_file)
            return True
        finally:
            self._cleanup_files(svg_file, png_file)

    def _render_svg(self, mermaid_source: str) -> str:
        """Render Mermaid source to SVG text using the Python API."""
        converter = MermaidConverter()
        svg_content = converter.convert(
            input=mermaid_source,
            output_file=None,
            background="white",
        )

        if not isinstance(svg_content, str) or svg_content == "":
            raise MermaidRenderError("No Mermaid SVG output was created.")

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
        cairosvg.svg2png(url=svg_file, write_to=png_file.name)
        return png_file.name

    def _cleanup_files(self, *filenames: Optional[str]) -> None:
        """Remove temporary files unless graphics export is enabled."""
        if self.export_graphics:
            return

        for filename in filenames:
            if filename is not None and Path(filename).exists():
                Path(filename).unlink()
