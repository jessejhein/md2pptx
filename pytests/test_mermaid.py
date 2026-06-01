import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mermaid


GANTT_SVG = """<svg viewBox=\"0 0 400 200\" xmlns=\"http://www.w3.org/2000/svg\">
  <g class=\"grid\">
    <g class=\"tick\"><text x=\"10\" y=\"20\" style=\"text-anchor: middle; fill: #333\">12:00</text></g>
    <g class=\"tick\"><text x=\"40\" y=\"20\" style=\"text-anchor: middle; fill: #333\">Tue 02</text></g>
  </g>
  <g class=\"tasks\"><text x=\"10\" y=\"80\">Deploy at 12:00</text></g>
</svg>"""


def test_default_config_disables_flowchart_html_labels():
    config = mermaid.build_mermaid_config(mermaid.MermaidRenderOptions())

    assert config["flowchart"]["htmlLabels"] is False
    assert "gantt" not in config


def test_config_includes_gantt_use_width_when_enabled():
    options = mermaid.MermaidRenderOptions(gantt_use_width=1600)

    assert mermaid.build_mermaid_config(options)["gantt"] == {"useWidth": 1600}


def test_detect_diagram_type_uses_first_non_empty_line():
    assert mermaid.detect_diagram_type("\n  gantt\n title Sprint") == "gantt"


def test_gantt_postprocess_removes_matching_axis_labels_only():
    processed = mermaid.postprocess_gantt_svg(GANTT_SVG, mermaid.MermaidRenderOptions())

    assert ">12:00</" not in processed
    assert "Tue 02" in processed
    assert "Deploy at 12:00" in processed


def test_gantt_postprocess_rotates_remaining_axis_labels():
    processed = mermaid.postprocess_gantt_svg(GANTT_SVG, mermaid.MermaidRenderOptions())

    assert "rotate(-35 40 20)" in processed
    assert "text-anchor: end" in processed


def test_empty_gantt_regex_disables_decimation():
    options = mermaid.MermaidRenderOptions(gantt_axis_label_regex="")
    processed = mermaid.postprocess_gantt_svg(GANTT_SVG, options)

    assert "12:00" in processed


def test_invalid_gantt_regex_raises_clear_error():
    options = mermaid.MermaidRenderOptions(gantt_axis_label_regex="[")

    with pytest.raises(mermaid.MermaidRenderError, match="Invalid mermaidGanttAxisLabelRegex"):
        mermaid.postprocess_gantt_svg(GANTT_SVG, options)


def test_gantt_postprocess_warns_and_preserves_unknown_structure():
    warnings = []
    source = "<svg viewBox=\"0 0 10 10\"><text>12:00</text></svg>"

    processed = mermaid.postprocess_gantt_svg(
        source,
        mermaid.MermaidRenderOptions(),
        warnings.append,
    )

    assert processed == source
    assert warnings == [
        "Gantt SVG post-processing skipped because the expected axis tick "
        "structure was not recognized."
    ]


def test_validate_svg_rejects_malformed_xml():
    with pytest.raises(mermaid.MermaidRenderError, match="well-formed XML"):
        mermaid.validate_svg("<svg>")


def test_validate_svg_requires_svg_root():
    with pytest.raises(mermaid.MermaidRenderError, match="not an SVG"):
        mermaid.validate_svg("<html></html>")


def test_convert_svg_to_png_writes_non_empty_file(tmp_path: Path):
    svg_file = tmp_path / "diagram.svg"
    png_file = tmp_path / "diagram.png"
    svg_file.write_text(
        "<svg viewBox='0 0 20 20' xmlns='http://www.w3.org/2000/svg'>"
        "<text x='1' y='12'>ok</text></svg>",
        encoding="utf-8",
    )

    mermaid.convert_svg_to_png(str(svg_file), str(png_file), 200)

    assert png_file.stat().st_size > 0
