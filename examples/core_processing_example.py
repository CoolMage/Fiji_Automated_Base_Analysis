#!/usr/bin/env python3
"""
Core processing example using the new database-driven approach.
Demonstrates keyword-based document processing with measurements.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_processor import CoreProcessor, ProcessingOptions


def main():
    """Core processing example."""
    print("Fiji Document Processor - Core Processing Example")
    print("=" * 55)
    
    # Initialize processor
    processor = CoreProcessor()
    
    # Validate setup
    validation = processor.validate_setup()
    print(f"Fiji path: {validation['fiji_path']}")
    print(f"Fiji valid: {validation['fiji_valid']}")
    print(f"Available commands: {validation['available_commands']}")
    print()
    
    if not validation['fiji_valid']:
        print("Error: Fiji not found or invalid. Please install Fiji or provide the correct path.")
        return 1
    
    # Example 1: Basic processing - find documents by keyword and measure them
    print("Example 1: Basic processing (default behavior)")
    print("-" * 50)
    
    base_path = "/Users/savvaarutsev/Documents/Data_Test/Detile_astrocytes"
    
    if not os.path.exists(base_path):
        print(f"Please update the base_path variable to point to your document directory.")
        print(f"Current path: {base_path}")
        return 1
    
    ## Basic processing with default options
    #result = processor.process_documents(
    #    base_path=base_path,
    #    keyword="experimental",  # Find documents containing "experimental"
    #    verbose=True
    #)
    #
    #if result["success"]:
    #    print(f"✅ Processed {len(result['processed_documents'])} documents")
    #    print(f"📊 Collected {len(result['measurements'])} measurement sets")
    #else:
    #    print(f"❌ Processing failed: {result['error']}")
    
    # # Example 2: Processing with secondary filter
    # print("\nExample 2: Processing with secondary filter (e.g., MIP files)")
    # print("-" * 60)
    
    # options = ProcessingOptions(secondary_filter="MIP")
    
    # result = processor.process_documents(
    #     base_path=base_path,
    #     keyword="data",
    #     options=options,
    #     verbose=True
    # )
    
    # if result["success"]:
    #     print(f"✅ Processed {len(result['processed_documents'])} MIP documents")
    # else:
    #     print(f"❌ MIP processing failed: {result['error']}")
    
    # Example 3: Custom commands
    print("\nExample 3: Custom processing commands")
    print("-" * 40)
    
    custom_commands = [
        "open_standard",
        "convert_8bit",
        "subtract_background radius=50",
        "enhance_contrast saturated=0.4",
        "measure",
        "save_csv"
    ]
    
    options = ProcessingOptions(secondary_filter="MIP")

    result = processor.process_documents(
        base_path=base_path,
        group_keywords=["4MU", "Control"],
        options=options,
        macro_commands=custom_commands,
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ Custom processing completed: {len(result['processed_documents'])} documents")
    else:
        print(f"❌ Custom processing failed: {result['error']}")
    
    # # Example 4: ROI processing with file saving
    # print("\nExample 4: ROI processing with file saving")
    # print("-" * 45)
    
    # options = ProcessingOptions(
    #     apply_roi=True,
    #     save_processed_files=True,
    #     custom_suffix="analyzed",
    #     measurements_folder="ROI_Measurements",
    #     processed_folder="ROI_Processed"
    # )
    
    # result = processor.process_documents(
    #     base_path=base_path,
    #     keyword="roi_data",
    #     macro_commands=["open_standard", "roi_manager_open", "roi_manager_measure", "save_csv"],
    #     options=options,
    #     verbose=True
    # )
    
    # if result["success"]:
    #     print(f"✅ ROI processing completed: {len(result['processed_documents'])} documents")
    #     print(f"📁 Processed files saved with suffix 'analyzed'")
    # else:
    #     print(f"❌ ROI processing failed: {result['error']}")
    
    # # Example 5: Show available commands
    # print("\nExample 5: Available commands")
    # print("-" * 30)
    
    # commands = processor.get_available_commands()
    # print(f"Total commands available: {len(commands)}")
    # print("\nFile operations:")
    # for cmd in ["open_standard", "open_bioformats", "save_tiff", "save_csv"]:
    #     if cmd in commands:
    #         print(f"  - {cmd}: {commands[cmd]['description']}")
    
    # print("\nImage processing:")
    # for cmd in ["convert_8bit", "subtract_background", "median_filter", "enhance_contrast"]:
    #     if cmd in commands:
    #         print(f"  - {cmd}: {commands[cmd]['description']}")
    
    # print("\nMeasurements:")
    # for cmd in ["measure", "set_measurements", "clear_measurements"]:
    #     if cmd in commands:
    #         print(f"  - {cmd}: {commands[cmd]['description']}")
    
    return 0


if __name__ == "__main__":
    exit(main())
