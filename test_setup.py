#!/usr/bin/env python3
"""Test script to validate the Fiji Automated Analysis setup."""

import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    from config import FijiConfig, FileConfig, ProcessingConfig
    from core_processor import CoreProcessor, ProcessingOptions
    from utils.general.fiji_utils import find_fiji, validate_fiji_path
    from utils.general.file_utils import normalize_path
    from utils.general.macro_builder import ImageData, MacroBuilder, MacroCommand
    from utils.general.macros_operation import run_fiji_macro

    assert hasattr(FijiConfig, "get_fiji_paths")
    assert isinstance(FileConfig().supported_extensions, (list, tuple))
    assert isinstance(ProcessingConfig().duplicate_frames, str)
    assert hasattr(CoreProcessor, "process_documents")
    assert hasattr(ProcessingOptions, "__annotations__")
    assert callable(find_fiji)
    assert callable(validate_fiji_path)
    assert callable(normalize_path)
    assert callable(run_fiji_macro)
    assert hasattr(ImageData, "__annotations__")
    assert hasattr(MacroBuilder, "parse_simple_commands")
    assert hasattr(MacroCommand, "__annotations__")


def test_configuration():
    """Test configuration classes."""
    print("\nTesting configuration...")

    from config import FileConfig, ProcessingConfig

    proc_config = ProcessingConfig()
    assert isinstance(proc_config.rolling_radius, (int, float))
    assert isinstance(proc_config.median_radius, (int, float))

    file_config = FileConfig()
    assert ".tif" in file_config.supported_extensions
    assert isinstance(file_config.bioformats_extensions, (list, tuple))


def test_fiji_detection():
    """Test Fiji detection."""
    print("\nTesting Fiji detection...")

    from utils.general.fiji_utils import find_fiji, validate_fiji_path

    fiji_path = find_fiji()
    if fiji_path:
        print(f"✅ Fiji found at: {fiji_path}")
        assert isinstance(fiji_path, str)
        assert isinstance(validate_fiji_path(fiji_path), bool)
    else:
        print("⚠️  Fiji not found (this is expected if Fiji is not installed)")
        assert fiji_path is None


def test_macro_builder():
    """Test macro builder functionality."""
    print("\nTesting macro builder...")

    from config import FileConfig, ProcessingConfig
    from utils.general.macro_builder import ImageData, MacroBuilder, MacroCommand

    builder = MacroBuilder(ProcessingConfig(), FileConfig())
    assert builder.command_templates, "Macro builder should expose command templates"

    image_data = ImageData(
        input_path="/test/input.tif",
        output_path="/test/output.tif",
        file_extension=".tif",
        is_bioformats=False,
    )
    assert image_data.input_path.endswith("input.tif")

    command = MacroCommand("open_standard", comment="Test command")
    assert command.command == "open_standard"

    simple_commands = builder.parse_simple_commands("open_standard convert_8bit save_tiff")
    assert [cmd.command for cmd in simple_commands] == [
        "open_standard",
        "convert_8bit",
        "save_tiff",
    ]


def test_cli_helpers():
    """Test keyword and ROI template collection helpers."""
    print("\nTesting CLI helpers...")

    from main import _collect_keywords, _collect_roi_templates

    keywords = _collect_keywords(["4MU, Control", "treated"])
    assert keywords == ["4MU", "Control", "treated"]

    templates = _collect_roi_templates(["{name}.roi", "{name}_ROI.zip, RoiSet_{name}.zip"])
    assert templates == ["{name}.roi", "{name}_ROI.zip", "RoiSet_{name}.zip"]


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    import pytest

    raise SystemExit(pytest.main([__file__]))
