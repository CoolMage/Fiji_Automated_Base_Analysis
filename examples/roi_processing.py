#!/usr/bin/env python3
"""
ROI processing example using Fiji Automated Analysis Tool.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fiji_processor import FijiProcessor
from config import GroupConfig


def main():
    """ROI processing example."""
    print("Fiji Automated Analysis - ROI Processing Example")
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
    
    # Example 1: Basic ROI processing
    print("Example 1: Basic ROI processing")
    print("-" * 35)
    
    result = processor.process_rois(
        base_path=base_path,
        group_keywords=["Experimental", "Control"],
        roi_name_pattern="roi_cut",
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ ROI processing completed: {len(result['processed_files'])} files")
    else:
        print(f"❌ ROI processing failed: {result['error']}")
    
    # Example 2: ROI processing with custom group configuration
    print("\nExample 2: ROI processing with custom groups")
    print("-" * 45)
    
    # Create custom group configuration
    group_config = GroupConfig(
        groups={
            "Treatment": "Drug_A",
            "Control": "Vehicle",
            "Positive": "Reference"
        }
    )
    
    # Update processor configuration
    processor.update_config(group_config=group_config)
    
    result = processor.process_rois(
        base_path=base_path,
        group_keywords=["Treatment", "Control"],
        roi_name_pattern="roi_cut",
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ Custom group ROI processing completed: {len(result['processed_files'])} files")
    else:
        print(f"❌ Custom group ROI processing failed: {result['error']}")
    
    # Example 3: ROI processing with different naming patterns
    print("\nExample 3: ROI processing with different naming patterns")
    print("-" * 55)
    
    # Try different ROI naming patterns
    roi_patterns = ["roi_cut", "roi_cut_invert", "ROI_cut", "region_cut"]
    
    for pattern in roi_patterns:
        print(f"Trying pattern: {pattern}")
        
        result = processor.process_rois(
            base_path=base_path,
            group_keywords=["Experimental", "Control"],
            roi_name_pattern=pattern,
            verbose=False  # Less verbose for multiple attempts
        )
        
        if result["success"]:
            print(f"  ✅ Pattern '{pattern}' worked: {len(result['processed_files'])} files")
        else:
            print(f"  ❌ Pattern '{pattern}' failed: {result['error']}")
    
    return 0


if __name__ == "__main__":
    exit(main())
