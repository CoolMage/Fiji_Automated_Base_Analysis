"""Tests for macro templates, configuration, and CLI macro sources."""

import pytest

from config import FijiConfig, FileConfig
from examples.macros_lib import MACROS_LIB
from gui import DEFAULT_UI_SCALE, _get_ui_scale
from main import _build_parser, _collect_keywords, _collect_roi_templates, _resolve_macro_code
from utils.general.fiji_utils import find_fiji
from utils.general.macro_builder import DEFAULT_MACRO_CODE, ImageData, MacroBuilder


def test_configuration_imports() -> None:
    assert FijiConfig.get_fiji_paths()
    assert ".tif" in FileConfig().supported_extensions


def test_linux_search_paths_include_fiji_and_imagej(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("config.platform.system", lambda: "Linux")

    paths = FijiConfig.get_fiji_paths()

    assert "/opt/fiji/ImageJ-linux64" in paths
    assert "/usr/bin/imagej" in paths
    assert paths.index("/opt/fiji/ImageJ-linux64") < paths.index("/usr/bin/imagej")


def test_gui_scale_uses_environment_and_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIJI_GUI_SCALE", "2.0")
    assert _get_ui_scale() == 2.0

    monkeypatch.setenv("FIJI_GUI_SCALE", "invalid")
    assert _get_ui_scale() == DEFAULT_UI_SCALE

    monkeypatch.setenv("FIJI_GUI_SCALE", "10")
    assert _get_ui_scale() == DEFAULT_UI_SCALE


def test_executable_discovery_prefers_fiji_over_imagej(tmp_path) -> None:
    imagej_path = tmp_path / "ImageJ" / "imagej"
    fiji_path = tmp_path / "Fiji.app" / "ImageJ-linux64"
    imagej_path.parent.mkdir()
    fiji_path.parent.mkdir()
    imagej_path.write_text("#!/bin/sh\n", encoding="utf-8")
    fiji_path.write_text("#!/bin/sh\n", encoding="utf-8")
    imagej_path.chmod(0o755)
    fiji_path.chmod(0o755)

    detected = find_fiji([str(imagej_path), str(fiji_path)])

    assert detected == str(fiji_path.resolve())


def test_executable_discovery_falls_back_to_imagej(tmp_path) -> None:
    imagej_path = tmp_path / "ImageJ" / "imagej"
    imagej_path.parent.mkdir()
    imagej_path.write_text("#!/bin/sh\n", encoding="utf-8")
    imagej_path.chmod(0o755)

    detected = find_fiji([str(imagej_path)])

    assert detected == str(imagej_path.resolve())


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


def test_rgb_mip_macro_maps_channels_and_saves_tiff() -> None:
    macro_name = "create_rgb_mip_blue_green_red"
    macro_code = MACROS_LIB[macro_name]
    profile = MACROS_LIB.get_profile(macro_name)

    assert 'run("Arrange Channels...", "new=134");' in macro_code
    assert 'run("Z Project...", "projection=[" + projectionMethod + "]");' in macro_code
    assert 'fileOutputDir = outputDir + outputStem + outputSuffix;' in macro_code
    assert '"c1=[" + blueSource + "] "' in macro_code
    assert '+ "c2=[" + greenSource + "] "' in macro_code
    assert '+ "c3=[" + redSource + "] create"' in macro_code
    assert 'Stack.setDisplayMode("composite");' in macro_code
    assert 'outputStem + blueSuffix + ".tif"' in macro_code
    assert 'outputStem + greenSuffix + ".tif"' in macro_code
    assert 'outputStem + redSuffix + ".tif"' in macro_code
    assert "blueSource = getTitle();" in macro_code
    assert "greenSource = getTitle();" in macro_code
    assert "redSource = getTitle();" in macro_code
    assert (
        'saveAs("Tiff", fileOutputDir + "/" + outputStem + outputSuffix + ".tif");'
        in macro_code
    )
    assert profile is not None
    assert profile.save_processed_images is True
    assert profile.save_measurement_csv is False


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
    assert _collect_keywords(["Exp, Control", "treated"]) == [
        "Exp",
        "Control",
        "treated",
    ]
    assert _collect_roi_templates(
        ["{name}.roi", "{name}_ROI.zip, RoiSet_{name}.zip"]
    ) == ["{name}.roi", "{name}_ROI.zip", "RoiSet_{name}.zip"]
