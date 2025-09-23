#!/usr/bin/env python3
"""Test script to validate the new core processor setup."""

import os
import sys
from typing import Iterable
from unittest.mock import patch

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _ensure_iterable(values: Iterable[str]) -> Iterable[str]:
    """Helper to materialize iterables for assertions while logging."""
    materialized = list(values)
    print(f"Collected {len(materialized)} entries: {materialized}")
    return materialized


def test_core_imports():
    """Test that core modules can be imported."""
    print("Testing core imports...")

    from core_processor import (
        CommandLibrary,
        CoreProcessor,
        DocumentInfo,
        ProcessingOptions,
    )
    from config import FileConfig, ProcessingConfig
    from utils.general.fiji_utils import find_fiji, validate_fiji_path

    # Basic attribute sanity checks to ensure the imports expose expected items
    assert CommandLibrary.COMMANDS, "Command library should define commands"
    assert hasattr(CoreProcessor, "process_documents")
    assert DocumentInfo.__annotations__["keywords"]
    assert isinstance(ProcessingOptions(), ProcessingOptions)
    assert callable(find_fiji)
    assert callable(validate_fiji_path)
    assert isinstance(FileConfig().supported_extensions, (list, tuple))
    assert isinstance(ProcessingConfig().rolling_radius, (int, float))


def test_command_library():
    """Test command library functionality."""
    print("\nTesting command library...")

    from core_processor import CommandLibrary

    library = CommandLibrary()
    commands = library.list_commands()

    assert isinstance(commands, dict)
    assert commands, "Command library should not be empty"

    expected_commands = ["open_standard", "measure", "convert_8bit", "roi_manager_open"]
    for cmd in expected_commands:
        assert cmd in commands, f"Expected command '{cmd}' to be available"
        print(f"  ✅ {cmd}: {commands[cmd]['description']}")


def test_processing_options():
    """Test processing options."""
    print("\nTesting processing options...")

    from core_processor import ProcessingOptions

    # Test default options
    options = ProcessingOptions()
    assert not options.apply_roi
    assert not options.save_processed_files
    assert options.measurement_summary_prefix == "measurements_summary"

    # Test custom options
    custom_options = ProcessingOptions(
        apply_roi=True,
        save_processed_files=True,
        custom_suffix="test",
        secondary_filter="MIP",
        measurement_summary_prefix="demo",
        roi_search_templates=("{name}.roi",),
    )

    assert custom_options.apply_roi is True
    assert custom_options.save_processed_files is True
    assert custom_options.custom_suffix == "test"
    assert custom_options.secondary_filter == "MIP"
    assert custom_options.measurement_summary_prefix == "demo"
    assert custom_options.roi_search_templates == ("{name}.roi",)



def test_document_info():
    """Test DocumentInfo class."""
    print("\nTesting DocumentInfo...")

    from core_processor import DocumentInfo

    doc = DocumentInfo(
        file_path="/test/path/image.tif",
        filename="image",
        keywords=("test",),
        matched_keyword="test",
        secondary_key="MIP",
        roi_path="/test/path/roi.zip",
    )

    assert doc.filename == "image"
    assert doc.keywords == ("test",)
    assert doc.matched_keyword == "test"
    assert doc.secondary_key == "MIP"
    assert doc.roi_path.endswith("roi.zip")

    multi_doc = DocumentInfo(
        file_path="/test/path/other_image.tif",
        filename="other_image",
        keywords=("alpha", "beta"),
        matched_keyword="beta",
    )

    assert multi_doc.keywords == ("alpha", "beta")
    assert multi_doc.matched_keyword == "beta"



def test_core_processor():
    """Test CoreProcessor initialization."""
    print("\nTesting CoreProcessor...")

    from core_processor import CoreProcessor

    fake_fiji_path = "/fake/path/ImageJ-linux64"
    with patch("core_processor.find_fiji", return_value=fake_fiji_path), patch(
        "core_processor.validate_fiji_path", return_value=True
    ):
        processor = CoreProcessor()
        validation = processor.validate_setup()

    assert processor.fiji_path == fake_fiji_path
    assert validation["fiji_path"] == fake_fiji_path
    assert validation["fiji_valid"] is True
    assert validation["available_commands"] == len(processor.command_library.COMMANDS)



def test_command_parsing():
    """Test command parsing functionality."""
    print("\nTesting command parsing...")

    from core_processor import CoreProcessor

    fake_fiji_path = "/fake/path/ImageJ-linux64"
    with patch("core_processor.find_fiji", return_value=fake_fiji_path), patch(
        "core_processor.validate_fiji_path", return_value=True
    ):
        processor = CoreProcessor()

    builder = processor.macro_builder
    commands = builder.parse_simple_commands(
        "open_standard convert_8bit subtract_background enhance_contrast measure save_csv"
    )

    parsed_commands = _ensure_iterable(cmd.command for cmd in commands)
    assert parsed_commands[:2] == ["open_standard", "convert_8bit"]
    assert "measure" in parsed_commands
    assert "save_csv" in parsed_commands


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    import pytest

    raise SystemExit(pytest.main([__file__]))
