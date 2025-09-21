
"""
Legacy ROI processing functions for backward compatibility.
Use FijiProcessor.process_rois() for new code.
"""

import os
from typing import List, Dict, Optional
from fiji_processor import FijiProcessor
from config import GroupConfig


def ivert_ROIs(base_path: str, 
               fiji_path: str, 
               group_keywords: Optional[List[str]] = None, 
               roi_name: str = "roi_cut") -> Dict[str, any]:
    """
    Legacy function for ROI processing.
    
    Args:
        base_path: Base directory containing images
        fiji_path: Path to Fiji executable
        group_keywords: List of group keywords to search for
        roi_name: ROI naming pattern
        
    Returns:
        Dictionary with processing results
    """
    # Create group config if keywords provided
    group_config = None
    if group_keywords:
        group_config = GroupConfig(groups={kw: kw for kw in group_keywords})
    
    # Initialize processor
    processor = FijiProcessor(fiji_path=fiji_path, group_config=group_config)
    
    # Process ROIs
    return processor.process_rois(
        base_path=base_path,
        group_keywords=group_keywords,
        roi_name_pattern=roi_name,
        verbose=True
    )
