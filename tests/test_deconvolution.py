"""Tests for the optional calibrated 3D deconvolution stage."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fiji_automated_analysis.config import FileConfig
from fiji_automated_analysis.core_processor import CoreProcessor, DocumentInfo, ProcessingOptions
from fiji_automated_analysis.utils.general.deconvolution import (
    ImageGeometry,
    PSF_MODE_THEORETICAL,
    TheoreticalPSFChannel,
    TheoreticalPSFConfig,
    build_image_geometry_probe_macro,
    build_theoretical_psf_command,
    build_deconvolution_macro,
    parse_image_geometry,
    read_image_geometry_with_fiji,
    validate_theoretical_psf_config,
    validate_psf_paths,
)
from fiji_automated_analysis.utils.general.fiji_utils import find_deconvolutionlab2_plugin
from fiji_automated_analysis.utils.general.macro_builder import MacroBuilder


def _processor() -> CoreProcessor:
    processor = CoreProcessor.__new__(CoreProcessor)
    processor.fiji_path = "/Applications/Fiji.app/fiji-macos-arm64"
    processor.file_config = FileConfig(supported_extensions=(".tif",))
    processor.macro_builder = MacroBuilder()
    return processor


def test_deconvolution_macro_uses_scientific_safety_checks() -> None:
    macro = build_deconvolution_macro(
        input_path="/data/image.czi",
        output_path="/data/Deconvolved/image_deconvolved.tif",
        working_directory="/tmp/deconv",
        psf_paths=["/data/psf/C1.tif", "/data/psf/C2.tif"],
        iterations=10,
    )

    assert 'run("Bio-Formats Macro Extensions");' in macro
    assert "sliceCount < 2" in macro
    assert "frameCount != 1" in macro
    assert "psfPaths.length != channelCount" in macro
    assert "image and PSF voxel sizes differ by more than 2%" in macro
    assert "PSF dimensions must not exceed image dimensions" in macro
    assert '" -algorithm RL " + iterations' in macro
    assert '" -constraint nonnegativity"' in macro
    assert '" -norm 1"' in macro
    assert '" -pad X23 X23"' in macro
    assert '" -apo NO NO"' in macro
    assert '" -out stack intact float noshow " + outputName' in macro
    assert '" -multithreading no"' in macro
    assert '" -stats false"' in macro
    assert "-fft jtransforms" not in macro
    assert "setVoxelSize(pixelWidth, pixelHeight, voxelDepth, spatialUnit);" in macro


def test_theoretical_psf_macro_uses_dl2_synthetic_model() -> None:
    config = TheoreticalPSFConfig(
        width=31,
        height=33,
        slices=15,
        channels=(
            TheoreticalPSFChannel(9.0, 11.0, 1.8),
            TheoreticalPSFChannel(10.0, 12.0, 2.1),
        ),
    )

    macro = build_deconvolution_macro(
        input_path="/data/image.czi",
        output_path="/data/Deconvolved/image_deconvolved.tif",
        working_directory="/tmp/deconv",
        iterations=10,
        theoretical_psf=config,
    )

    assert 'psfMode = "theoretical";' in macro
    assert (
        "AxialDiffractionSimulation 9 11 1.8 "
        "size 31 33 15 intensity 255 center 0.5 0.5 0.5"
        in macro
    )
    assert '" -psf synthetic " + theoreticalPSFCommands[channelIndex]' in macro
    assert "theoretical PSF dimensions must not exceed image dimensions" in macro


def test_theoretical_psf_uses_reference_sampling_as_a_compatibility_check() -> None:
    config = TheoreticalPSFConfig(
        width=31,
        height=31,
        slices=9,
        channels=(TheoreticalPSFChannel(),),
        reference_geometry=ImageGeometry(
            width=512,
            height=512,
            channels=1,
            slices=21,
            frames=1,
            pixel_width_um=0.2,
            pixel_height_um=0.2,
            voxel_depth_um=0.5,
        ),
    )

    macro = build_deconvolution_macro(
        input_path="/data/image.czi",
        output_path="/data/output.tif",
        working_directory="/tmp/deconv",
        iterations=10,
        theoretical_psf=config,
    )

    assert "theoreticalPixelWidthUm = 0.2;" in macro
    assert "theoreticalPixelHeightUm = 0.2;" in macro
    assert "theoreticalVoxelDepthUm = 0.5;" in macro
    assert "input voxel sampling differs by more than 2%" in macro


def test_theoretical_psf_settings_are_validated() -> None:
    config = TheoreticalPSFConfig(
        channels=(TheoreticalPSFChannel(),),
    )

    assert validate_theoretical_psf_config(config) is config
    assert build_theoretical_psf_command(config, config.channels[0]).startswith(
        "AxialDiffractionSimulation 10 10 2"
    )

    with pytest.raises(ValueError, match="1 to 7 channels"):
        validate_theoretical_psf_config(TheoreticalPSFConfig())
    with pytest.raises(ValueError, match="center_x"):
        validate_theoretical_psf_config(
            TheoreticalPSFConfig(
                center_x=1.5,
                channels=(TheoreticalPSFChannel(),),
            )
        )
    with pytest.raises(ValueError, match="pupil size"):
        validate_theoretical_psf_config(
            TheoreticalPSFConfig(
                channels=(TheoreticalPSFChannel(pupil_size=0),),
            )
        )
    with pytest.raises(ValueError, match="must not exceed"):
        validate_theoretical_psf_config(
            TheoreticalPSFConfig(
                width=31,
                height=31,
                slices=15,
                channels=(TheoreticalPSFChannel(),),
                reference_geometry=ImageGeometry(
                    width=512,
                    height=512,
                    channels=1,
                    slices=4,
                    frames=1,
                ),
            )
        )


def test_geometry_probe_reads_metadata_without_loading_pixels() -> None:
    macro = build_image_geometry_probe_macro(
        input_path="/data/image.czi",
        result_path="/tmp/geometry.txt",
    )

    assert "Ext.setId(inputPath);" in macro
    assert "Ext.setSeries(0);" in macro
    assert "Ext.getSizeX(imageWidth);" in macro
    assert "Ext.getSizeC(channelCount);" in macro
    assert "Ext.getPixelsPhysicalSizeX(pixelWidthUm);" in macro
    assert "Ext.getPixelsPhysicalSizeZ(voxelDepthUm);" in macro
    assert "Ext.openImagePlus" not in macro


def test_image_geometry_parser_and_fiji_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "image.nd2"
    source.write_bytes(b"source")

    def fake_run_fiji_macro(_fiji_path, macro_code, **_kwargs):
        match = re.search(r'^resultPath = "([^"]+)";$', macro_code, re.MULTILINE)
        assert match is not None
        Path(match.group(1)).write_text(
            "width=512\nheight=256\nchannels=4\nslices=21\nframes=1\n"
            "pixel_width_um=0.21\npixel_height_um=0.22\n"
            "voxel_depth_um=0.75\n",
            encoding="utf-8",
        )
        return {"success": True, "stdout": "", "stderr": "", "error": None}

    monkeypatch.setattr(
        "utils.general.macros_operation.run_fiji_macro",
        fake_run_fiji_macro,
    )

    geometry = read_image_geometry_with_fiji(
        "/Applications/Fiji.app/fiji",
        str(source),
    )

    assert geometry == parse_image_geometry(
        "width=512\nheight=256\nchannels=4\nslices=21\nframes=1\n"
        "pixel_width_um=0.21\npixel_height_um=0.22\n"
        "voxel_depth_um=0.75\n"
    )
    assert geometry.channels == 4
    assert geometry.slices == 21
    assert geometry.pixel_width_um == 0.21
    assert geometry.voxel_depth_um == 0.75


def test_psf_paths_must_exist_and_be_tiff(tmp_path: Path) -> None:
    psf = tmp_path / "C1.tif"
    psf.write_bytes(b"tiff")

    assert validate_psf_paths([str(psf)]) == [str(psf.resolve())]

    with pytest.raises(ValueError, match="does not exist"):
        validate_psf_paths([str(tmp_path / "missing.tif")])
    invalid = tmp_path / "C2.png"
    invalid.write_bytes(b"png")
    with pytest.raises(ValueError, match="TIFF"):
        validate_psf_paths([str(invalid)])


def test_deconvolution_plugin_is_detected_in_fiji_plugins(tmp_path: Path) -> None:
    root = tmp_path / "Fiji.app"
    launcher = root / "fiji"
    plugin = root / "plugins" / "DeconvolutionLab_2.jar"
    plugin.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    plugin.write_bytes(b"jar")

    assert find_deconvolutionlab2_plugin(str(launcher)) == str(plugin)


def test_deconvolution_options_require_plugin_and_psf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    psf = tmp_path / "C1.tif"
    psf.write_bytes(b"tiff")
    processor = _processor()
    options = ProcessingOptions(
        deconvolution_enabled=True,
        deconvolution_psf_paths=[str(psf)],
    )

    monkeypatch.setattr("fiji_automated_analysis.core_processor.find_deconvolutionlab2_plugin", lambda _path: None)
    with pytest.raises(ValueError, match="not installed"):
        processor._validate_deconvolution_options(options)


def test_deconvolution_writes_output_and_reproducibility_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "Control_stack.tif"
    psf = tmp_path / "C1.tif"
    source.write_bytes(b"source")
    psf.write_bytes(b"psf")
    output_dir = tmp_path / "Deconvolved"
    captured = {}

    def fake_run_fiji_macro(_fiji_path, macro_code, **kwargs):
        captured["macro_code"] = macro_code
        captured["kwargs"] = kwargs
        match = re.search(r'^outputPath = "([^"]+)";$', macro_code, re.MULTILINE)
        assert match is not None
        Path(match.group(1)).write_bytes(b"deconvolved")
        return {"success": True, "stdout": "", "stderr": "", "error": None}

    monkeypatch.setattr("fiji_automated_analysis.core_processor.run_fiji_macro", fake_run_fiji_macro)
    monkeypatch.setattr(
        "core_processor.find_deconvolutionlab2_plugin",
        lambda _path: "/Applications/Fiji.app/plugins/DeconvolutionLab_2.jar",
    )
    processor = _processor()
    options = ProcessingOptions(
        deconvolution_enabled=True,
        deconvolution_psf_paths=[str(psf)],
        deconvolution_iterations=12,
        deconvolution_memory_gb=10,
        deconvolution_timeout_seconds=900,
    )
    document = DocumentInfo(
        file_path=str(source),
        filename="Control_stack",
        keywords=("Control",),
    )

    result = processor._deconvolve_document(
        document,
        options,
        str(output_dir),
        verbose=False,
        cancel_event=None,
    )

    assert result["success"] is True
    assert Path(result["output_path"]).is_file()
    assert captured["kwargs"]["timeout"] == 900
    assert captured["kwargs"]["additional_args"] == ["--memory", "10G"]
    manifest = json.loads(
        (output_dir / "Control_stack_deconvolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["algorithm"] == "Richardson-Lucy"
    assert manifest["iterations"] == 12
    assert manifest["psf_images_by_channel"] == [str(psf)]


def test_theoretical_deconvolution_writes_model_to_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "Control_stack.tif"
    source.write_bytes(b"source")
    output_dir = tmp_path / "Deconvolved"
    captured = {}

    def fake_run_fiji_macro(_fiji_path, macro_code, **kwargs):
        captured["macro_code"] = macro_code
        match = re.search(r'^outputPath = "([^"]+)";$', macro_code, re.MULTILINE)
        assert match is not None
        Path(match.group(1)).write_bytes(b"deconvolved")
        return {"success": True, "stdout": "", "stderr": "", "error": None}

    monkeypatch.setattr("fiji_automated_analysis.core_processor.run_fiji_macro", fake_run_fiji_macro)
    monkeypatch.setattr(
        "core_processor.find_deconvolutionlab2_plugin",
        lambda _path: "/Applications/Fiji.app/plugins/DeconvolutionLab_2.jar",
    )
    config = TheoreticalPSFConfig(
        width=31,
        height=31,
        slices=15,
        channels=(TheoreticalPSFChannel(9.5, 10.5, 2.2),),
    )
    processor = _processor()
    options = ProcessingOptions(
        deconvolution_enabled=True,
        deconvolution_psf_mode=PSF_MODE_THEORETICAL,
        deconvolution_theoretical_psf=config,
    )
    processor._validate_deconvolution_options(options)
    document = DocumentInfo(
        file_path=str(source),
        filename="Control_stack",
        keywords=("Control",),
    )

    result = processor._deconvolve_document(
        document,
        options,
        str(output_dir),
        verbose=False,
        cancel_event=None,
    )

    assert result["success"] is True
    assert " -psf synthetic " in captured["macro_code"]
    manifest = json.loads(
        (output_dir / "Control_stack_deconvolution.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["psf_mode"] == PSF_MODE_THEORETICAL
    assert manifest["psf_images_by_channel"] == []
    assert manifest["theoretical_psf"]["model"] == "AxialDiffractionSimulation"
    assert manifest["theoretical_psf"]["channels"][0]["wave_number_axial"] == 2.2
