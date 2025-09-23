"""Standalone example for running the CoreProcessor against the sample dataset.

The script mirrors the configuration showcased in the project README. It sets up
custom file and processing options, feeds a multi-keyword search into the core
processor, and prints a compact summary of the run. Use it as a starting point
for your own automation scripts.
"""
from __future__ import annotations

from pathlib import Path
from pprint import pprint

from config import FileConfig
from core_processor import CoreProcessor, ProcessingOptions


def build_processor() -> CoreProcessor:
    """Create a CoreProcessor with example file configuration overrides."""
    file_config = FileConfig(
        supported_extensions=(".tif", ".tiff"),
        roi_search_templates=("{name}.roi", "{name}.zip", "RoiSet_{name}.zip"),
    )

    return CoreProcessor(
        file_config=file_config,
    )


def build_options() -> ProcessingOptions:
    """Configure processing options that showcase common customizations."""
    return ProcessingOptions(
        apply_roi=True,
        save_processed_files=False,
        custom_suffix="analyzed",
        measurements_folder="Measurements",
        processed_folder="Processed",
        measurement_summary_prefix="example_study",
        roi_search_templates=("{name}.roi", "{name}.zip", "RoiSet_{name}.zip"),
        secondary_filter="MIP",
    )


def main() -> None:
    base_path = Path(__file__).parent / "sample_documents"
    processor = build_processor()
    options = build_options()

    macro_commands = [
        "open_standard",
        "measure",
        "save_csv",
        "quit",
    ]

    result = processor.process_documents(
        base_path=str(base_path),
        keyword=("4MU", "Control"),
        macro_commands=macro_commands,
        options=options,
        verbose=True,
    )

    print("\n=== Run summary ===")
    pprint(result)


if __name__ == "__main__":
    main()