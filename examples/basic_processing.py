#!/usr/bin/env python3
"""
Basic image processing example using Fiji Automated Analysis Tool.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fiji_processor import FijiProcessor
from config import ProcessingConfig, FileConfig, GroupConfig


def main():
    """Basic processing example."""
    print("Fiji Automated Analysis - Basic Processing Example")
    print("=" * 50)
    
    # Initialize processor with default settings
    processor = FijiProcessor()
    
    # Validate setup
    validation = processor.validate_setup()
    print(f"Fiji path: {validation['fiji_path']}")
    print(f"Fiji valid: {validation['fiji_valid']}")
    print(f"Platform: {validation['platform_info']['system']}")
    print()
    
    if not validation['fiji_valid']:
        print("Error: Fiji not found or invalid. Please install Fiji or provide the correct path.")
        return 1
    
    # Example 1: Basic processing with default settings
    print("Example 1: Basic processing with default settings")
    print("-" * 50)
    
    # Replace with your actual image directory
    base_path = "/Users/savvaarutsev/Documents/Data_Test/Detile_astrocytes"
    
    if not os.path.exists(base_path):
        print(f"Please update the base_path variable to point to your image directory.")
        print(f"Current path: {base_path}")
        return 1
    
    result = processor.process_images(
        base_path=base_path,
        verbose=True
    )
    
    if result["success"]:
        print(f"✅ Successfully processed {len(result['processed_files'])} files")
    else:
        print(f"❌ Processing failed: {result['error']}")
    
    return 0


if __name__ == "__main__":
    exit(main())
