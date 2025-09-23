"""Configuration module for the Fiji document processor."""

import os
import platform
from dataclasses import dataclass, field
from typing import List, Sequence


@dataclass
class ProcessingConfig:
    """Configuration for macro builder defaults."""

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
    """Configuration for supported files and ROI discovery."""

    supported_extensions: Sequence[str] = field(
        default_factory=lambda: [".tif", ".tiff", ".ims", ".czi", ".nd2"]
    )
    roi_search_templates: Sequence[str] = field(
        default_factory=lambda: ["{name}.roi", "{name}.zip", "RoiSet_{name}.zip"]
    )
    bioformats_extensions: Sequence[str] = field(
        default_factory=lambda: [".ims", ".czi", ".nd2", ".lsm", ".oib", ".oif"]
    )


class FijiConfig:
    """Cross-platform Fiji installation hints used during auto-discovery."""

    @staticmethod
    def get_fiji_paths() -> List[str]:
        """Return platform-specific search paths for a Fiji executable."""

        system = platform.system().lower()

        if system == "darwin":  # macOS
            return [
                "/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx",
                os.path.expanduser("~/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"),
                os.path.expanduser("~/Downloads/Fiji.app/Contents/MacOS/ImageJ-macosx"),
                os.path.expanduser("~/Desktop/Fiji.app/Contents/MacOS/ImageJ-macosx"),
            ]

        if system == "windows":
            return [
                r"C:\\Program Files\\Fiji\\ImageJ-win64.exe",
                r"C:\\Program Files (x86)\\Fiji\\ImageJ-win64.exe",
                os.path.expanduser(r"~\\Fiji\\ImageJ-win64.exe"),
                os.path.expanduser(r"~\\Desktop\\Fiji\\ImageJ-win64.exe"),
                os.path.expanduser(r"~\\Downloads\\Fiji\\ImageJ-win64.exe"),
            ]

        # Linux / other Unix-like
        return [
            "/opt/fiji/ImageJ-linux64",
            "/usr/local/fiji/ImageJ-linux64",
            os.path.expanduser("~/fiji/ImageJ-linux64"),
            os.path.expanduser("~/Fiji.app/ImageJ-linux64"),
            os.path.expanduser("~/Desktop/fiji/ImageJ-linux64"),
        ]


DEFAULT_PROCESSING_CONFIG = ProcessingConfig()
DEFAULT_FILE_CONFIG = FileConfig()
DEFAULT_FIJI_PATHS = FijiConfig.get_fiji_paths()
