"""Configuration module for the Fiji document processor."""

import os
import platform
from dataclasses import dataclass, field
from typing import List, Sequence


class FijiConfig:
    """Cross-platform Fiji and ImageJ installation hints used during discovery."""

    @staticmethod
    def get_fiji_paths() -> List[str]:
        """Return platform-specific paths, with Fiji candidates listed first."""

        system = platform.system().lower()

        if system == "darwin":  # macOS
            return [
                "/Applications/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-arm64",
                "/Applications/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-x64",
                "/Applications/Fiji.app/fiji",
                "/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx",
                os.path.expanduser(
                    "~/Applications/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-arm64"
                ),
                os.path.expanduser(
                    "~/Applications/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-x64"
                ),
                os.path.expanduser("~/Applications/Fiji.app/fiji"),
                os.path.expanduser(
                    "~/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"
                ),
                os.path.expanduser(
                    "~/Downloads/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-arm64"
                ),
                os.path.expanduser(
                    "~/Downloads/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-x64"
                ),
                os.path.expanduser("~/Downloads/Fiji.app/fiji"),
                os.path.expanduser("~/Downloads/Fiji.app/Contents/MacOS/ImageJ-macosx"),
                os.path.expanduser(
                    "~/Desktop/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-arm64"
                ),
                os.path.expanduser(
                    "~/Desktop/Fiji.app/Fiji.app/Contents/MacOS/fiji-macos-x64"
                ),
                os.path.expanduser("~/Desktop/Fiji.app/fiji"),
                os.path.expanduser("~/Desktop/Fiji.app/Contents/MacOS/ImageJ-macosx"),
                "/Applications/ImageJ.app/Contents/MacOS/ImageJ",
                "/Applications/ImageJ.app/Contents/MacOS/ImageJ-macosx",
                "/Applications/ImageJ.app/Contents/MacOS/JavaApplicationStub",
                os.path.expanduser("~/Applications/ImageJ.app/Contents/MacOS/ImageJ"),
                os.path.expanduser(
                    "~/Applications/ImageJ.app/Contents/MacOS/ImageJ-macosx"
                ),
                os.path.expanduser(
                    "~/Applications/ImageJ.app/Contents/MacOS/JavaApplicationStub"
                ),
                os.path.expanduser("~/Downloads/ImageJ.app/Contents/MacOS/ImageJ"),
                os.path.expanduser(
                    "~/Downloads/ImageJ.app/Contents/MacOS/ImageJ-macosx"
                ),
                os.path.expanduser(
                    "~/Downloads/ImageJ.app/Contents/MacOS/JavaApplicationStub"
                ),
            ]

        if system == "windows":
            return [
                r"%FIJI_PATH%",
                r"%IMAGEJ_PATH%",
                r"%FIJI_EXECUTABLE%",
                r"%IMAGEJ_EXECUTABLE%",
                r"C:\Program Files\Fiji\ImageJ-win64.exe",
                r"C:\Program Files\Fiji.app\ImageJ-win64.exe",
                r"C:\Program Files (x86)\Fiji\ImageJ-win64.exe",
                r"C:\Program Files (x86)\Fiji.app\ImageJ-win64.exe",
                os.path.expanduser(r"~\Fiji\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Fiji.app\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Desktop\Fiji\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Desktop\Fiji.app\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Downloads\Fiji\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Downloads\Fiji.app\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Documents\Fiji\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Documents\Fiji.app\ImageJ-win64.exe"),
                r"%LOCALAPPDATA%\Fiji\ImageJ-win64.exe",
                r"%LOCALAPPDATA%\Fiji.app\ImageJ-win64.exe",
                r"C:\Program Files\ImageJ\ImageJ.exe",
                r"C:\Program Files\ImageJ\ImageJ-win64.exe",
                r"C:\Program Files (x86)\ImageJ\ImageJ.exe",
                r"C:\Program Files (x86)\ImageJ\ImageJ-win64.exe",
                os.path.expanduser(r"~\ImageJ\ImageJ.exe"),
                os.path.expanduser(r"~\ImageJ\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Desktop\ImageJ\ImageJ.exe"),
                os.path.expanduser(r"~\Desktop\ImageJ\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Downloads\ImageJ\ImageJ.exe"),
                os.path.expanduser(r"~\Downloads\ImageJ\ImageJ-win64.exe"),
                os.path.expanduser(r"~\Documents\ImageJ\ImageJ.exe"),
                os.path.expanduser(r"~\Documents\ImageJ\ImageJ-win64.exe"),
                r"%LOCALAPPDATA%\ImageJ\ImageJ.exe",
                r"%LOCALAPPDATA%\ImageJ\ImageJ-win64.exe",
            ]

        # Linux / other Unix-like
        return [
            "/opt/fiji/ImageJ-linux64",
            "/usr/local/fiji/ImageJ-linux64",
            os.path.expanduser("~/fiji/ImageJ-linux64"),
            os.path.expanduser("~/Fiji.app/ImageJ-linux64"),
            os.path.expanduser("~/Desktop/fiji/ImageJ-linux64"),
            "/usr/bin/imagej",
            "/usr/local/bin/imagej",
            "/opt/ImageJ/ImageJ-linux64",
            "/opt/ImageJ/ImageJ",
            "/usr/local/ImageJ/ImageJ-linux64",
            os.path.expanduser("~/ImageJ/ImageJ-linux64"),
            os.path.expanduser("~/ImageJ/ImageJ"),
            os.path.expanduser("~/Desktop/ImageJ/ImageJ-linux64"),
            os.path.expanduser("~/Desktop/ImageJ/ImageJ"),
            os.path.expanduser("~/Downloads/ImageJ/ImageJ-linux64"),
            os.path.expanduser("~/Downloads/ImageJ/ImageJ"),
        ]


DEFAULT_FIJI_PATHS = FijiConfig.get_fiji_paths()


@dataclass
class FileConfig:
    """Configuration for supported files and ROI discovery."""

    supported_extensions: Sequence[str] = field(
        default_factory=lambda: [".tif", ".tiff", ".ims", ".czi", ".nd2", ".vsi", ".mp4"]
    )
    roi_search_templates: Sequence[str] = field(
        default_factory=lambda: ["{name}.roi", "{name}.zip", "RoiSet_{name}.zip"]
    )
    bioformats_extensions: Sequence[str] = field(
        default_factory=lambda: [".ims", ".czi", ".nd2", ".lsm", ".oib", ".oif", ".vsi"]
    )


DEFAULT_FILE_CONFIG = FileConfig()
