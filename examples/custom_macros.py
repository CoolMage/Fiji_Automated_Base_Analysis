#!/usr/bin/env python3
"""
Custom macros example using Fiji Automated Analysis Tool.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fiji_processor import FijiProcessor
from utils.general.macro_builder import MacroCommand


def main():
    """Custom macros example."""
    print("Fiji Automated Analysis - Custom Macros Example")
    print("=" * 50)
    
    # Initialize processor
    processor = FijiProcessor()
    
    # Validate setup
    validation = processor.validate_setup()
    print(f"Fiji path: {validation['fiji_path']}")
    print(f"Fiji valid: {validation['fiji_valid']}")
    print()
    
    if not validation['fiji_valid']:
        print("Error: Fiji not found or invalid. Please install Fiji or provide the correct path.")
        return 1
    
    base_path = "/path/to/your/images"
    
    if not os.path.exists(base_path):
        print(f"Please update the base_path variable to point to your image directory.")
        print(f"Current path: {base_path}")
        return 1
    
    # Example 1: Custom macro code
    print("Example 1: Custom macro code")
    print("-" * 30)
    
    custom_macro = """
// Custom processing pipeline
open("{input_path}");

// Convert to 8-bit
run("8-bit");

// Apply Gaussian blur
run("Gaussian Blur...", "sigma=2");

// Enhance contrast
run("Enhance Contrast...", "saturated=0.35 normalize");

// Save result
saveAs("Tiff", "{output_path}");

// Cleanup
run("Close All");
run("Quit");
"""
    
    result = processor.process_images(
        base_path=base_path,
        custom_macro=custom_macro,
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ Custom macro processing completed: {len(result['processed_files'])} files")
    else:
        print(f"❌ Custom macro processing failed: {result['error']}")
    
    # Example 2: Simple command sequence
    print("\nExample 2: Simple command sequence")
    print("-" * 40)
    
    simple_commands = "open_standard convert_8bit subtract_background enhance_contrast save_tiff"
    
    result = processor.process_images(
        base_path=base_path,
        simple_commands=simple_commands,
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ Simple commands processing completed: {len(result['processed_files'])} files")
    else:
        print(f"❌ Simple commands processing failed: {result['error']}")
    
    # Example 3: Using MacroCommand objects
    print("\nExample 3: Using MacroCommand objects")
    print("-" * 40)
    
    # Create custom commands
    custom_commands = [
        MacroCommand("open_standard", comment="Open image"),
        MacroCommand("convert_8bit", comment="Convert to 8-bit"),
        MacroCommand("median_filter", {"radius": 3}, comment="Apply median filter"),
        MacroCommand("enhance_contrast", {"saturated": 0.4}, comment="Enhance contrast"),
        MacroCommand("save_tiff", comment="Save as TIFF"),
        MacroCommand("close_all", comment="Close all windows"),
        MacroCommand("quit", comment="Quit Fiji")
    ]
    
    # Build macro from commands
    macro_code = processor.macro_builder.build_macro_from_commands(custom_commands)
    print("Generated macro:")
    print(macro_code)
    print()
    
    result = processor.process_images(
        base_path=base_path,
        custom_macro=macro_code,
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ MacroCommand processing completed: {len(result['processed_files'])} files")
    else:
        print(f"❌ MacroCommand processing failed: {result['error']}")
    
    # Example 4: Available commands
    print("\nExample 4: Available commands")
    print("-" * 30)
    
    available_commands = processor.get_available_commands()
    print(f"Available commands ({len(available_commands)}):")
    for i, cmd in enumerate(available_commands, 1):
        print(f"  {i:2d}. {cmd}")
    
    return 0


if __name__ == "__main__":
    exit(main())
