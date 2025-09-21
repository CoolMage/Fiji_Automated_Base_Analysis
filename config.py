"""
Configuration module for Fiji Automated Analysis.
This module provides default configurations and allows easy customization.
"""

import os
import platform
from typing import Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class ProcessingConfig:
    """Configuration for image processing parameters."""
    rolling_radius: int = 30
    median_radius: int = 2
    saturated_pixels: float = 0.35
    normalize: bool = True
    convert_to_8bit: bool = True
    duplicate_channels: int = 1
    duplicate_slices: str = "1-end"
    duplicate_frames: str = "1-end"


@dataclass
class FileConfig:
    """Configuration for file patterns and extensions."""
    supported_extensions: List[str] = None
    mip_keywords: List[str] = None
    roi_patterns: Dict[str, str] = None
    
    def __post_init__(self):
        if self.supported_extensions is None:
            self.supported_extensions = ['.tif', '.ims', '.czi', '.tiff']
        
        if self.mip_keywords is None:
            self.mip_keywords = ['_MIP_', '_MIP.tif', '_MIP.ims', '_MIP.czi']
        
        if self.roi_patterns is None:
            self.roi_patterns = {
                'roiset': 'RoiSet_{cut_number}.zip',
                'single_roi': 'roi_{cut_number}.roi',
                'inverted_roi': 'roi_{cut_number}_inverted.roi'
            }


@dataclass
class GroupConfig:
    """Configuration for group and subject mappings."""
    groups: Dict[str, str] = None
    group_keywords: List[str] = None
    
    def __post_init__(self):
        if self.groups is None:
            self.groups = {
                "Experimental": "A",
                "Control": "B"
            }
        
        if self.group_keywords is None:
            self.group_keywords = list(self.groups.keys())


class FijiConfig:
    """Cross-platform Fiji configuration."""
    
    @staticmethod
    def get_fiji_paths() -> List[str]:
        """Get platform-specific Fiji executable paths."""
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            return [
                "/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx",
                os.path.expanduser("~/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"),
                os.path.expanduser("~/Downloads/Fiji.app/Contents/MacOS/ImageJ-macosx"),
                os.path.expanduser("~/Desktop/Fiji.app/Contents/MacOS/ImageJ-macosx"),
            ]
        elif system == "windows":
            return [
                r"C:\Program Files\Fiji\ImageJ-win64.exe",
                r"C:\Program Files (x86)\Fiji\ImageJ-win64.exe",
                os.path.expanduser(r"~\Fiji\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Desktop\Fiji\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Downloads\Fiji\ImageJ-win64.exe"),
            ]
        else:  # Linux
            return [
                "/opt/fiji/ImageJ-linux64",
                "/usr/local/fiji/ImageJ-linux64",
                os.path.expanduser("~/fiji/ImageJ-linux64"),
                os.path.expanduser("~/Fiji.app/ImageJ-linux64"),
                os.path.expanduser("~/Desktop/fiji/ImageJ-linux64"),
            ]


# Default configurations
DEFAULT_PROCESSING_CONFIG = ProcessingConfig()
DEFAULT_FILE_CONFIG = FileConfig()
DEFAULT_GROUP_CONFIG = GroupConfig()
DEFAULT_FIJI_PATHS = FijiConfig.get_fiji_paths()
