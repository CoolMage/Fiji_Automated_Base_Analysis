"""
Universal file processing utilities for cross-platform compatibility.
"""

import os
import glob
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from config import FileConfig, GroupConfig


def normalize_path(path: str) -> str:
    """
    Normalize path for cross-platform compatibility.
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized path string
    """
    return str(Path(path).resolve())


def find_image_files(base_path: str, 
                    group_keywords: List[str],
                    file_config: Optional[FileConfig] = None,
                    mip_only: bool = False) -> List[str]:
    """
    Find image files in directories containing group keywords.
    
    Args:
        base_path: Base directory to search
        group_keywords: List of group keywords to search for
        file_config: File configuration object
        mip_only: Whether to filter for MIP files only
        
    Returns:
        List of found image file paths
    """
    if file_config is None:
        file_config = FileConfig()
    
    image_files = []
    
    for keyword in group_keywords:
        for extension in file_config.supported_extensions:
            search_pattern = os.path.join(base_path, f"**/*{keyword}*/*{extension}")
            found_files = glob.glob(search_pattern, recursive=True)
            image_files.extend(found_files)
    
    # Remove duplicates and sort
    image_files = sorted(list(set(image_files)))
    
    # Filter for MIP files if requested
    if mip_only:
        original_count = len(image_files)
        mip_files = []
        
        for file_path in image_files:
            filename = os.path.basename(file_path)
            if any(keyword in filename for keyword in file_config.mip_keywords):
                mip_files.append(file_path)
        
        image_files = mip_files
        print(f"MIP filtering: {original_count} files -> {len(image_files)} files (MIP only)")
    
    return image_files


def find_roi_files(image_path: str, 
                  cut_number: str,
                  file_config: Optional[FileConfig] = None) -> Tuple[List[str], List[str]]:
    """
    Find ROI files associated with an image.
    
    Args:
        image_path: Path to the image file
        cut_number: Cut number to search for
        file_config: File configuration object
        
    Returns:
        Tuple of (roi_paths, roi_names)
    """
    if file_config is None:
        file_config = FileConfig()
    
    img_dir = os.path.dirname(image_path)
    roi_paths = []
    roi_names = []
    
    # Try to find RoiSet first (multiple ROIs)
    roiset_pattern = os.path.join(img_dir, file_config.roi_patterns['roiset'].format(cut_number=cut_number))
    if os.path.exists(roiset_pattern):
        roi_paths.append(normalize_path(roiset_pattern))
        roi_names.append(f"RoiSet_{cut_number}")
    
    # Try to find single ROI
    single_roi_pattern = os.path.join(img_dir, file_config.roi_patterns['single_roi'].format(cut_number=cut_number))
    if os.path.exists(single_roi_pattern):
        roi_paths.append(normalize_path(single_roi_pattern))
        roi_names.append(f"roi_{cut_number}")
    
    return roi_paths, roi_names


def extract_cut_number(filename: str) -> Optional[str]:
    """
    Extract cut number from filename using regex.
    
    Args:
        filename: Name of the file
        
    Returns:
        Cut number as string, or None if not found
    """
    cut_match = re.search(r'cut(\d+)', filename, re.IGNORECASE)
    return cut_match.group(1) if cut_match else None


def create_output_directory(base_path: str, 
                          image_name: str, 
                          suffix: str = "processed") -> str:
    """
    Create output directory for processed images.
    
    Args:
        base_path: Base path for results
        image_name: Name of the image (without extension)
        suffix: Suffix for the output directory
        
    Returns:
        Path to created output directory
    """
    results_dir = os.path.join(base_path, "Processing_Results")
    out_dir = os.path.join(results_dir, f"{image_name}_{suffix}")
    os.makedirs(out_dir, exist_ok=True)
    return normalize_path(out_dir)


def get_file_extension(file_path: str) -> str:
    """
    Get file extension in lowercase.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File extension in lowercase
    """
    return os.path.splitext(file_path)[1].lower()


def is_bioformats_file(file_path: str, file_config: Optional[FileConfig] = None) -> bool:
    """
    Check if file requires Bio-Formats importer.
    
    Args:
        file_path: Path to the file
        file_config: File configuration object
        
    Returns:
        True if file requires Bio-Formats
    """
    if file_config is None:
        file_config = FileConfig()
    
    extension = get_file_extension(file_path)
    bioformats_extensions = ['.ims', '.czi', '.nd2', '.lsm', '.oib', '.oif']
    
    return extension in bioformats_extensions


def validate_input_directory(base_path: str) -> bool:
    """
    Validate that the input directory exists and is accessible.
    
    Args:
        base_path: Path to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not os.path.exists(base_path):
        print(f"Error: Base path does not exist: {base_path}")
        return False
    
    if not os.path.isdir(base_path):
        print(f"Error: Base path is not a directory: {base_path}")
        return False
    
    if not os.access(base_path, os.R_OK):
        print(f"Error: No read access to base path: {base_path}")
        return False
    
    return True


def get_platform_path_separator() -> str:
    """
    Get the appropriate path separator for the current platform.
    
    Returns:
        Path separator string
    """
    return os.sep


def convert_path_for_fiji(path: str) -> str:
    """
    Convert path to Fiji-compatible format (forward slashes).
    
    Args:
        path: Path to convert
        
    Returns:
        Fiji-compatible path
    """
    return path.replace("\\", "/")
