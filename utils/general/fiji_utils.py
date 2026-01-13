"""Cross-platform Fiji utilities for finding and running Fiji."""

import os
import stat
import subprocess
import platform
from pathlib import Path
from typing import Optional, List

from config import DEFAULT_FIJI_PATHS


def find_fiji(custom_paths: Optional[List[str]] = None) -> Optional[str]:
    """
    Find Fiji executable across different platforms.
    
    Args:
        custom_paths: Optional list of custom paths to search
        
    Returns:
        Path to Fiji executable if found, None otherwise
    """
    search_paths = custom_paths or DEFAULT_FIJI_PATHS
    
    # Check known locations
    for path in search_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    # Platform-specific fallback searches
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        try:
            result = subprocess.check_output(
                ["find", "/Applications", "-name", "ImageJ-macosx"],
                text=True,
                timeout=30
            ).strip()
            if result:
                return result.split("\n")[0]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    elif system == "windows":
        # Search in common Windows locations
        common_paths = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            os.path.expanduser("~")
        ]
        
        for base_path in common_paths:
            try:
                result = subprocess.check_output(
                    ["where", "/R", base_path, "ImageJ-win64.exe"],
                    text=True,
                    timeout=30
                ).strip()
                if result:
                    return result.split("\n")[0]
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
    
    else:  # Linux
        try:
            result = subprocess.check_output(
                ["which", "ImageJ-linux64"],
                text=True,
                timeout=10
            ).strip()
            if result:
                return result
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Search in common Linux locations
        try:
            result = subprocess.check_output(
                ["find", "/opt", "/usr/local", os.path.expanduser("~"), "-name", "ImageJ-linux64", "-type", "f"],
                text=True,
                timeout=30
            ).strip()
            if result:
                return result.split("\n")[0]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
    
    return None


def validate_fiji_path(fiji_path: str) -> bool:
    """Validate that the given path points to a usable Fiji executable.

    Validation is intentionally lightweight to avoid spawning a Fiji GUI
    process.  We rely on filesystem checks rather than executing the binary.

    Args:
        fiji_path: Path to Fiji executable

    Returns:
        True if the path looks like a valid executable, False otherwise
    """

    if not fiji_path:
        return False

    try:
        file_stat = os.stat(fiji_path, follow_symlinks=True)
    except OSError:
        return False

    if not stat.S_ISREG(file_stat.st_mode):
        return False

    if file_stat.st_size <= 0:
        return False

    if not os.access(fiji_path, os.X_OK):
        return False

    return True


def _resolve_fiji_root(fiji_path: str) -> Optional[Path]:
    """Best-effort resolver for the Fiji installation root directory."""
    if not fiji_path:
        return None

    path = Path(fiji_path).resolve()
    parts = [part.lower() for part in path.parts]
    if "fiji.app" in parts:
        idx = parts.index("fiji.app")
        return Path(*path.parts[: idx + 1])

    return path.parent


def detect_ffmpeg_plugin(fiji_path: str) -> bool:
    """Check whether the Movie (FFMPEG) plugin is present in the Fiji install."""
    root = _resolve_fiji_root(fiji_path)
    if root is None or not root.exists():
        return False

    plugin_dir = root / "plugins"
    if not plugin_dir.exists():
        return False

    for candidate in (plugin_dir / "ffmpeg", plugin_dir / "FFMPEG"):
        if candidate.is_dir():
            return True

    for pattern in ("ffmpeg*.jar", "*ffmpeg*.jar"):
        if list(plugin_dir.glob(pattern)):
            return True

    jars_dir = root / "jars"
    if jars_dir.exists():
        for pattern in ("ffmpeg*.jar", "*ffmpeg*.jar"):
            if list(jars_dir.glob(pattern)):
                return True

    for binary in ("ffmpeg", "ffmpeg.exe", "ffmpeg64", "ffmpeg64.exe"):
        if (plugin_dir / "ffmpeg" / binary).exists() or (plugin_dir / binary).exists():
            return True

    return False


def get_platform_info() -> dict:
    """
    Get platform-specific information for debugging.
    
    Returns:
        Dictionary with platform information
    """
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version()
    }
