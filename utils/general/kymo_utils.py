"""Cross-platform KymographDirect utilities for finding and validating the executable."""

import os
import stat
import subprocess
import platform
from typing import List, Optional

from config import DEFAULT_KYMOGRAPH_DIRECT_PATHS


def find_kymograph_direct(custom_paths: Optional[List[str]] = None) -> Optional[str]:
    """
    Find KymographDirect executable across different platforms.

    Args:
        custom_paths: Optional list of custom paths to search

    Returns:
        Path to KymographDirect executable if found, None otherwise
    """
    search_paths = custom_paths or DEFAULT_KYMOGRAPH_DIRECT_PATHS

    # Check known locations
    for path in search_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    # Platform-specific fallback searches
    system = platform.system().lower()

    if system == "darwin":  # macOS
        try:
            result = subprocess.check_output(
                ["find", "/Applications", "-name", "KymographDirect"],
                text=True,
                timeout=30,
            ).strip()
            if result:
                return result.split("\n")[0]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

    elif system == "windows":
        common_paths = [
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            os.path.expanduser("~"),
        ]

        for base_path in common_paths:
            try:
                result = subprocess.check_output(
                    ["where", "/R", base_path, "KymographDirect.exe"],
                    text=True,
                    timeout=30,
                ).strip()
                if result:
                    return result.split("\n")[0]
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue

    else:  # Linux and other Unix-like systems
        try:
            result = subprocess.check_output(
                ["which", "KymographDirect"],
                text=True,
                timeout=10,
            ).strip()
            if result:
                return result
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

        try:
            result = subprocess.check_output(
                [
                    "find",
                    "/opt",
                    "/usr/local",
                    os.path.expanduser("~"),
                    "-name",
                    "KymographDirect",
                    "-type",
                    "f",
                ],
                text=True,
                timeout=30,
            ).strip()
            if result:
                return result.split("\n")[0]
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass

    return None


def validate_kymograph_direct_path(path: str) -> bool:
    """Validate that the given path points to a usable KymographDirect executable.

    Validation is intentionally lightweight to avoid launching the application.
    We rely on filesystem checks rather than executing the binary.

    Args:
        path: Path to KymographDirect executable

    Returns:
        True if the path looks like a valid executable, False otherwise
    """
    if not path:
        return False

    try:
        file_stat = os.stat(path, follow_symlinks=True)
    except OSError:
        return False

    if not stat.S_ISREG(file_stat.st_mode):
        return False

    if file_stat.st_size <= 0:
        return False

    if not os.access(path, os.X_OK):
        return False

    return True
