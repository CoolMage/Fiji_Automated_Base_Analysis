"""Tests for macro templates, configuration, and CLI macro sources."""

import pytest

import fiji_automated_analysis.cli as cli
import fiji_automated_analysis.utils.general.fiji_utils as fiji_utils
from fiji_automated_analysis.config import FijiConfig, FileConfig
from fiji_automated_analysis.macros_lib import MACROS_LIB
from fiji_automated_analysis.gui import (
    DEFAULT_UI_SCALE,
    _format_macro_profile_summary,
    _fit_window_size,
    _get_ui_scale,
    _linux_directory_dialog,
    _selection_indicator_size,
)
from fiji_automated_analysis.cli import (
    _build_parser,
    _collect_keywords,
    _collect_psf_paths,
    _collect_roi_templates,
    _resolve_macro_code,
    main as cli_main,
)
from fiji_automated_analysis.utils.general.fiji_utils import find_fiji
from fiji_automated_analysis.utils.general.macro_builder import DEFAULT_MACRO_CODE, ImageData, MacroBuilder

BASE_MACRO_NAMES = {
    "inspect_image_metadata",
    "split_channels_to_folder",
    "create_mip_per_channel",
    "create_rgb_mip",
    "export_channel_mip_with_display_range",
    "measure_full_image_per_channel",
    "measure_mip_full_image_per_channel",
    "measure_rois_per_channel",
    "measure_mip_rois_per_channel",
    "measure_channel_mip_in_rois",
    "measure_thresholded_area_full_image",
    "measure_thresholded_area_in_rois",
    "create_threshold_mask",
    "detect_particles_full_image",
    "detect_particles_in_roi",
    "measure_thresholded_area_and_particles_in_roi",
    "measure_3d_mask_overlap",
    "measure_local_enrichment_around_mask",
}


def test_configuration_imports() -> None:
    assert FijiConfig.get_fiji_paths()
    assert ".tif" in FileConfig().supported_extensions


def test_linux_search_paths_include_fiji_and_imagej(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fiji_automated_analysis.config.platform.system", lambda: "Linux")

    paths = FijiConfig.get_fiji_paths()

    assert "/opt/Fiji.app/ImageJ-linux64" in paths
    assert "/opt/fiji/ImageJ-linux64" in paths
    assert "/usr/local/bin/fiji" in paths
    assert any(path.endswith("Documents/Fiji.app/ImageJ-linux64") for path in paths)
    assert any(path.endswith("Downloads/Fiji.app/ImageJ-linux64") for path in paths)
    assert any(path.endswith("Downloads/Fiji*.AppImage") for path in paths)
    assert "/usr/bin/imagej" in paths
    assert paths.index("/opt/fiji/ImageJ-linux64") < paths.index("/usr/bin/imagej")


def test_windows_search_paths_include_fiji_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fiji_automated_analysis.config.platform.system", lambda: "Windows")

    paths = FijiConfig.get_fiji_paths()

    assert r"C:\Program Files\Fiji.app\ImageJ-win64.exe" in paths
    assert any(r"\Downloads\Fiji.app\ImageJ-win64.exe" in path for path in paths)
    assert any(r"\Documents\Fiji.app\ImageJ-win64.exe" in path for path in paths)


def test_gui_scale_uses_environment_and_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIJI_GUI_SCALE", "2.0")
    assert _get_ui_scale() == 2.0

    monkeypatch.setenv("FIJI_GUI_SCALE", "invalid")
    assert _get_ui_scale() == DEFAULT_UI_SCALE

    monkeypatch.setenv("FIJI_GUI_SCALE", "10")
    assert _get_ui_scale() == DEFAULT_UI_SCALE


def test_window_size_is_capped_to_small_linux_screen() -> None:
    assert _fit_window_size(900, 650, 1.5, 1366, 768) == (1286, 668)
    assert _fit_window_size(640, 520, 1.5, 1366, 768) == (960, 668)


def test_linux_selection_indicator_scales_with_gui() -> None:
    assert _selection_indicator_size(1.0) == 18
    assert _selection_indicator_size(1.5) == 24
    assert _selection_indicator_size(2.0) == 32


def test_macro_profile_summary_exposes_recommended_defaults() -> None:
    summary = _format_macro_profile_summary("measure_mip_rois_per_channel")

    assert "Defaults:" in summary
    assert "ROI on" in summary
    assert "measurement CSV on" in summary
    assert "Measurements folder: Measurements." in summary


def test_linux_directory_dialog_prefers_zenity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured = {}

    class Result:
        returncode = 0
        stdout = f"{tmp_path}\n"

    monkeypatch.setattr("fiji_automated_analysis.gui.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "fiji_automated_analysis.gui.shutil.which",
        lambda name: "/usr/bin/zenity" if name == "zenity" else None,
    )

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr("fiji_automated_analysis.gui.subprocess.run", fake_run)

    handled, selected = _linux_directory_dialog(str(tmp_path), "Select directory")

    assert handled is True
    assert selected == str(tmp_path)
    assert captured["command"][0] == "/usr/bin/zenity"
    assert "--directory" in captured["command"]


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


def test_linux_fiji_directory_resolves_to_launcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fiji_root = tmp_path / "Fiji.app"
    fiji_path = fiji_root / "ImageJ-linux64"
    fiji_root.mkdir()
    fiji_path.write_text("#!/bin/sh\n", encoding="utf-8")
    fiji_path.chmod(0o755)

    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Linux")

    assert fiji_utils.normalize_fiji_path(str(fiji_root)) == str(fiji_path.resolve())
    assert fiji_utils.validate_fiji_path(str(fiji_root)) is True


def test_linux_parent_directory_can_discover_nested_fiji_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fiji_root = tmp_path / "Fiji.app"
    fiji_path = fiji_root / "fiji-linux64"
    fiji_root.mkdir()
    fiji_path.write_text("#!/bin/sh\n", encoding="utf-8")
    fiji_path.chmod(0o755)

    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Linux")

    detected = find_fiji([str(tmp_path)])

    assert detected == str(fiji_path.resolve())


def test_linux_appimage_glob_is_supported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    appimage_path = tmp_path / "Downloads" / "Fiji-linux64.AppImage"
    appimage_path.parent.mkdir()
    appimage_path.write_text("#!/bin/sh\n", encoding="utf-8")
    appimage_path.chmod(0o755)

    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Linux")

    detected = find_fiji([str(appimage_path.parent / "Fiji*.AppImage")])

    assert detected == str(appimage_path.resolve())


def test_linux_filesystem_search_checks_common_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fiji_root = tmp_path / "apps" / "Fiji.app"
    fiji_path = fiji_root / "ImageJ-linux64"
    fiji_root.mkdir(parents=True)
    fiji_path.write_text("#!/bin/sh\n", encoding="utf-8")
    fiji_path.chmod(0o755)

    for variable in (
        "FIJI_PATH",
        "IMAGEJ_PATH",
        "FIJI_EXECUTABLE",
        "IMAGEJ_EXECUTABLE",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Linux")
    monkeypatch.setattr(fiji_utils, "DEFAULT_FIJI_PATHS", [])
    monkeypatch.setattr(fiji_utils, "_linux_search_roots", lambda: [str(tmp_path)])
    monkeypatch.setattr(fiji_utils.shutil, "which", lambda _name: None)

    detected = find_fiji([])

    assert detected == str(fiji_path.resolve())


def test_linux_contextual_search_finds_fiji_next_to_project_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    documents_dir = tmp_path / "Documents"
    project_dir = documents_dir / "Git_rep" / "Fiji_Automated_Base_Analysis"
    fiji_root = documents_dir / "Fiji.app"
    fiji_path = fiji_root / "ImageJ-linux64"
    project_dir.mkdir(parents=True)
    fiji_root.mkdir()
    fiji_path.write_text("#!/bin/sh\n", encoding="utf-8")
    fiji_path.chmod(0o755)

    for variable in (
        "FIJI_PATH",
        "IMAGEJ_PATH",
        "FIJI_EXECUTABLE",
        "IMAGEJ_EXECUTABLE",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Linux")
    monkeypatch.setattr(fiji_utils, "DEFAULT_FIJI_PATHS", [])
    monkeypatch.setattr(
        fiji_utils,
        "_linux_search_roots",
        fiji_utils._contextual_search_roots,
    )
    monkeypatch.setattr(fiji_utils.shutil, "which", lambda _name: None)

    detected = find_fiji([])

    assert detected == str(fiji_path.resolve())


def test_macos_contextual_search_finds_fiji_next_to_project_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    documents_dir = tmp_path / "Documents"
    project_dir = documents_dir / "Git_rep" / "Fiji_Automated_Base_Analysis"
    fiji_root = documents_dir / "Fiji.app"
    fiji_path = fiji_root / "Fiji.app" / "Contents" / "MacOS" / "fiji-macos-x64"
    project_dir.mkdir(parents=True)
    fiji_path.parent.mkdir(parents=True)
    fiji_path.write_text("#!/bin/sh\n", encoding="utf-8")
    fiji_path.chmod(0o755)

    for variable in (
        "FIJI_PATH",
        "IMAGEJ_PATH",
        "FIJI_EXECUTABLE",
        "IMAGEJ_EXECUTABLE",
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(fiji_utils, "DEFAULT_FIJI_PATHS", [])
    monkeypatch.setattr(
        fiji_utils,
        "_macos_search_roots",
        fiji_utils._contextual_search_roots,
    )
    monkeypatch.setattr(fiji_utils.shutil, "which", lambda _name: None)

    detected = find_fiji([])

    assert detected == str(fiji_path.resolve())


def test_executable_discovery_falls_back_to_imagej(tmp_path) -> None:
    imagej_path = tmp_path / "ImageJ" / "imagej"
    imagej_path.parent.mkdir()
    imagej_path.write_text("#!/bin/sh\n", encoding="utf-8")
    imagej_path.chmod(0o755)

    detected = find_fiji([str(imagej_path)])

    assert detected == str(imagej_path.resolve())


def test_windows_executable_discovery_uses_fiji_path_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fiji_path = tmp_path / "Fiji.app" / "ImageJ-win64.exe"
    fiji_path.parent.mkdir()
    fiji_path.write_bytes(b"fake exe")

    monkeypatch.setenv("FIJI_PATH", str(fiji_path))
    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Windows")

    detected = find_fiji([])

    assert detected == str(fiji_path.resolve())


def test_windows_validation_accepts_existing_exe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fiji_path = tmp_path / "Fiji.app" / "ImageJ-win64.exe"
    text_path = tmp_path / "Fiji.app" / "ImageJ.txt"
    fiji_path.parent.mkdir()
    fiji_path.write_bytes(b"fake exe")
    text_path.write_text("not executable", encoding="utf-8")

    monkeypatch.setattr(fiji_utils.platform, "system", lambda: "Windows")

    assert fiji_utils.validate_fiji_path(str(fiji_path)) is True
    assert fiji_utils.validate_fiji_path(str(text_path)) is False


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


def test_base_macro_library_contains_generic_templates() -> None:
    assert BASE_MACRO_NAMES.issubset(MACROS_LIB.keys())


def test_all_library_macros_have_headers_and_gui_profiles() -> None:
    for macro_name in MACROS_LIB.keys():
        macro_code = MACROS_LIB[macro_name]
        first_nonempty_line = next(
            line.strip() for line in macro_code.splitlines() if line.strip()
        )

        assert first_nonempty_line.startswith("//"), macro_name
        assert MACROS_LIB.get_profile(macro_name) is not None, macro_name


def test_base_macro_templates_include_expected_fiji_operations() -> None:
    expected_snippets = {
        "inspect_image_metadata": [
            'run("Bio-Formats Macro Extensions");',
            "Stack.getStatistics(",
            'setResult("Channels"',
            'saveAs("Results", resultsPath);',
        ],
        "measure_rois_per_channel": [
            'roiManager("Open"',
            'run("Set Measurements...", measurementsOptions);',
            'setResult("ROI"',
            'saveAs("Results", resultsPath);',
        ],
        "measure_thresholded_area_in_rois": [
            'run("Z Project...", "projection=[" + projectionMethod + "]");',
            "setThreshold(thresholdLow, thresholdHigh);",
            "area_fraction limit",
            'saveAs("Results", resultsPath);',
        ],
        "detect_particles_in_roi": [
            'run("Analyze Particles..."',
            'roiManager("Save"',
            'setResult("ParentROI"',
            'saveAs("Results", resultsPath);',
        ],
        "measure_3d_mask_overlap": [
            "Stack.getStatistics(",
            'imageCalculator("AND create stack"',
            'setResult("PrimarySecondaryJaccard"',
            'setResult("ThresholdCalibration"',
        ],
        "measure_local_enrichment_around_mask": [
            'run("Dilate", "stack");',
            'imageCalculator("Multiply create 32-bit stack"',
            'setResult("SecondaryLocalEnrichmentRatio"',
            'saveAs("Results", resultsPath);',
        ],
    }

    for macro_name, snippets in expected_snippets.items():
        macro_code = MACROS_LIB[macro_name]
        for snippet in snippets:
            assert snippet in macro_code, (macro_name, snippet)


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
    assert _collect_psf_paths(["C1.tif;C2.tif", "C3.tif"]) == [
        "C1.tif",
        "C2.tif",
        "C3.tif",
    ]


def test_cli_accepts_deconvolution_preset() -> None:
    args = _build_parser().parse_args(
        [
            "/tmp/data",
            "--keyword",
            "Control",
            "--deconvolve",
            "--psf",
            "/tmp/C1.tif",
            "--deconvolution-iterations",
            "15",
            "--deconvolution-memory-gb",
            "12",
        ]
    )

    assert args.deconvolve is True
    assert args.psf == ["/tmp/C1.tif"]
    assert args.deconvolution_iterations == 15
    assert args.deconvolution_memory_gb == 12


def test_cli_measurement_summary_is_opt_in() -> None:
    parser = _build_parser()

    default_args = parser.parse_args(["/tmp/data", "--keyword", "Control"])
    enabled_args = parser.parse_args(
        [
            "/tmp/data",
            "--keyword",
            "Control",
            "--generate-measurement-summary",
        ]
    )
    skipped_args = parser.parse_args(
        [
            "/tmp/data",
            "--keyword",
            "Control",
            "--generate-measurement-summary",
            "--skip-measurement-summary",
        ]
    )

    assert default_args.generate_measurement_summary is False
    assert default_args.skip_measurement_summary is False
    assert enabled_args.generate_measurement_summary is True
    assert skipped_args.generate_measurement_summary is True
    assert skipped_args.skip_measurement_summary is True


def test_cli_passes_measurement_summary_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_options = []

    class FakeProcessor:
        def __init__(self, fiji_path=None):
            self.fiji_path = fiji_path

        def process_documents(self, **kwargs):
            captured_options.append(kwargs["options"])
            return {"success": True, "processed_documents": [], "measurements": []}

    monkeypatch.setattr(cli, "CoreProcessor", FakeProcessor)

    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "/tmp/data", "--keyword", "Control"],
    )
    assert cli_main() == 0
    assert captured_options[-1].generate_measurement_summary is False

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "/tmp/data",
            "--keyword",
            "Control",
            "--generate-measurement-summary",
        ],
    )
    assert cli_main() == 0
    assert captured_options[-1].generate_measurement_summary is True
