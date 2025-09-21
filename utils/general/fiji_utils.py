"""
Cross-platform Fiji utilities for finding and running Fiji.
"""

import os
import subprocess
import platform
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
    """
    Validate that the given path points to a working Fiji executable.
    
    Args:
        fiji_path: Path to Fiji executable
        
    Returns:
        True if valid, False otherwise
    """
    if not os.path.isfile(fiji_path):
        return False
    
    if not os.access(fiji_path, os.X_OK):
        return False
    
    # Try to run Fiji with version flag
    try:
        result = subprocess.run(
            [fiji_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # If version check fails, try a simpler validation
        try:
            # Just check if the file exists and is executable
            return os.path.isfile(fiji_path) and os.access(fiji_path, os.X_OK)
        except:
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
