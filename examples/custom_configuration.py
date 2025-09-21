#!/usr/bin/env python3
"""
Custom configuration example using Fiji Automated Analysis Tool.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fiji_processor import FijiProcessor
from config import ProcessingConfig, FileConfig, GroupConfig


def main():
    """Custom configuration example."""
    print("Fiji Automated Analysis - Custom Configuration Example")
    print("=" * 60)
    
    # Create custom configurations
    print("Creating custom configurations...")
    
    # Custom processing configuration
    processing_config = ProcessingConfig(
        rolling_radius=50,        # Larger background subtraction radius
        median_radius=3,          # Larger median filter radius
        saturated_pixels=0.4,     # Different contrast enhancement
        convert_to_8bit=True,     # Convert to 8-bit
        duplicate_channels=1,     # Duplicate first channel only
        duplicate_slices="1-end", # All slices
        duplicate_frames="1-end"  # All frames
    )
    
    # Custom file configuration
    file_config = FileConfig(
        supported_extensions=['.tif', '.ims', '.czi', '.nd2', '.lsm'],
        mip_keywords=['_MIP_', '_MIP.tif', '_MIP.ims', '_MIP.czi', '_MIP.nd2'],
        roi_patterns={
            'roiset': 'RoiSet_{cut_number}.zip',
            'single_roi': 'roi_{cut_number}.roi',
            'inverted_roi': 'roi_{cut_number}_inverted.roi'
        }
    )
    
    # Custom group configuration
    group_config = GroupConfig(
        groups={
            "Treatment": "Drug_A",
            "Control": "Vehicle",
            "Positive": "Reference",
            "Negative": "Blank"
        }
    )
    
    print(f"Processing config: rolling_radius={processing_config.rolling_radius}")
    print(f"File config: {len(file_config.supported_extensions)} supported extensions")
    print(f"Group config: {len(group_config.groups)} groups")
    print()
    
    # Initialize processor with custom configurations
    processor = FijiProcessor(
        processing_config=processing_config,
        file_config=file_config,
        group_config=group_config
    )
    
    # Validate setup
    validation = processor.validate_setup()
    print(f"Fiji path: {validation['fiji_path']}")
    print(f"Fiji valid: {validation['fiji_valid']}")
    print(f"Available commands: {validation['available_commands']}")
    print()
    
    if not validation['fiji_valid']:
        print("Error: Fiji not found or invalid. Please install Fiji or provide the correct path.")
        return 1
    
    # Example 1: Process with custom group keywords
    print("Example 1: Processing with custom group keywords")
    print("-" * 50)
    
    base_path = "/path/to/your/images"
    
    if not os.path.exists(base_path):
        print(f"Please update the base_path variable to point to your image directory.")
        print(f"Current path: {base_path}")
        return 1
    
    result = processor.process_images(
        base_path=base_path,
        group_keywords=["Treatment", "Control"],
        mip_only=False,
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ Successfully processed {len(result['processed_files'])} files")
    else:
        print(f"❌ Processing failed: {result['error']}")
    
    # Example 2: Process only MIP files
    print("\nExample 2: Processing only MIP files")
    print("-" * 50)
    
    result = processor.process_images(
        base_path=base_path,
        group_keywords=["Treatment", "Control"],
        mip_only=True,
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ Successfully processed {len(result['processed_files'])} MIP files")
    else:
        print(f"❌ MIP processing failed: {result['error']}")
    
    return 0


if __name__ == "__main__":
    exit(main())
