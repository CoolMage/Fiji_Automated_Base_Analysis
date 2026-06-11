"""Tests for macro templates, configuration, and CLI macro sources."""

import pytest

from config import FijiConfig, FileConfig
from examples.macros_lib import MACROS_LIB
from main import _build_parser, _collect_keywords, _collect_roi_templates, _resolve_macro_code
from utils.general.macro_builder import DEFAULT_MACRO_CODE, ImageData, MacroBuilder


def test_configuration_imports() -> None:
    assert FijiConfig.get_fiji_paths()
    assert ".tif" in FileConfig().supported_extensions


def test_complete_macro_template_expands_placeholders() -> None:
    builder = MacroBuilder()
    image_data = ImageData(
        input_path="/converted/input.tif",
        output_path="/converted/output.tif",
        file_extension=".tif",
        roi_paths=["/converted/roi1.zip", "/converted/roi2.zip"],
        roi_paths_native=["/native/roi1.zip", "/native/roi2.zip"],
        measurements_path="/converted/results.csv",
        source_path="/native/input.tif",
        output_path_native="/native/output.tif",
        measurements_path_native="/native/results.csv",
        document_name="sample.image",
    )

    macro_code = builder.build_macro(
        'open("{img_path_fiji}");\n'
        "{roi_manager_open_block}\n"
        'saveAs("Results", "{out_csv}");',
        image_data,
    )

    assert 'open("/converted/input.tif");' in macro_code
    assert 'roiManager("Open", "/converted/roi1.zip");' in macro_code
    assert 'saveAs("Results", "/converted/results.csv");' in macro_code
    assert image_data.document_name == "sample.image"


def test_pasted_fiji_block_braces_do_not_need_escaping() -> None:
    builder = MacroBuilder()
    image_data = ImageData(
        input_path="/converted/input.tif",
        output_path="",
        file_extension=".tif",
    )

    macro_code = builder.build_macro(
        'if (nImages > 0) {\nprint("{input_path}");\n}',
        image_data,
    )

    assert 'if (nImages > 0) {' in macro_code
    assert 'print("/converted/input.tif");' in macro_code
    assert macro_code.rstrip().endswith("}")


def test_all_library_macros_format_without_escaped_block_braces() -> None:
    builder = MacroBuilder()
    image_data = ImageData(
        input_path="/converted/input.tif",
        output_path="/converted/output.tif",
        file_extension=".tif",
        measurements_path="/converted/results.csv",
        source_path="/native/input.tif",
        document_name="sample",
    )

    for macro_code in MACROS_LIB.values():
        formatted = builder.build_macro(macro_code, image_data)
        assert "{{" not in formatted
        assert "}}" not in formatted


def test_cli_resolves_only_complete_code_or_library(tmp_path) -> None:
    macro_path = tmp_path / "analysis.ijm"
    macro_path.write_text('open("{input_path}");', encoding="utf-8")

    assert _resolve_macro_code(macro_code='run("Quit");') == 'run("Quit");'
    assert _resolve_macro_code(macro_file=str(macro_path)) == 'open("{input_path}");'

    library_name = sorted(MACROS_LIB.keys())[0]
    assert _resolve_macro_code(macro_library=library_name) == MACROS_LIB[library_name]
    assert _resolve_macro_code() == DEFAULT_MACRO_CODE


def test_cli_no_longer_accepts_pseudo_commands() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["/tmp", "--keyword", "Control", "--commands", "measure"])


def test_keyword_and_roi_helpers() -> None:
    assert _collect_keywords(["4MU, Control", "treated"]) == [
        "4MU",
        "Control",
        "treated",
    ]
    assert _collect_roi_templates(
        ["{name}.roi", "{name}_ROI.zip, RoiSet_{name}.zip"]
    ) == ["{name}.roi", "{name}_ROI.zip", "RoiSet_{name}.zip"]
