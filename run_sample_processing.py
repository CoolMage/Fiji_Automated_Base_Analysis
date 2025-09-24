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

from examples.macros_lib import MACROS_LIB



def build_processor() -> CoreProcessor:
    """Create a CoreProcessor with example file configuration overrides."""
    file_config = FileConfig(
        supported_extensions=(".tif", ".tiff", ".ims", ".czi"),
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
        save_measurements_csv=True,
        custom_suffix="analyzed",
        measurements_folder="Measurements",
        processed_folder="Processed",
        measurement_summary_prefix="example_study",
        generate_measurement_summary=True,
        roi_search_templates=("{name}.roi", "{name}.zip", "RoiSet_{name}.zip"),
        secondary_filter="MIP",
    )


def main() -> None:
    #base_path = Path(__file__).parent / "sample_documents"
    base_path = "/Users/savvaarutsev/Documents/Data_Test/Detile_astrocytes"
    processor = build_processor()
    options = build_options()


    # macro_commands = [
    #     "open_bioformats",
    #     'subtract_background radius=30',
    #     'median_filter radius=2',
    #     'enhance_contrast saturated=0.4 normalize',
    #     "save_tiff",
    #     "measure",
    #     "save_csv",
    # ]

    macro_commands = MACROS_LIB["all_image_and_rois_measure_for_channel"]

    result = processor.process_documents(
        base_path=str(base_path),
        keyword=("Potkan1"),
        macro_commands=macro_commands,
        options=options,
        verbose=True,
    )

    print("\n=== Run summary ===")
    pprint(result)


if __name__ == "__main__":
    main()