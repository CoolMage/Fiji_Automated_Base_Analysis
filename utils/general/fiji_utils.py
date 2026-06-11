"""Cross-platform Fiji utilities for finding and running Fiji."""

import os
import stat
import subprocess
import platform
from pathlib import Path
from typing import Optional, List

from config import DEFAULT_FIJI_PATHS


def _macos_fiji_fallback_names() -> List[str]:
    """Return Fiji launcher names in preferred order for modern macOS installs."""

    return [
        "fiji-macos-arm64",
        "fiji-macos-x64",
        "fiji",
        "ImageJ-macosx",
    ]


def _macos_launcher_arch(path: Path) -> Optional[str]:
    """Infer the launcher architecture from a Fiji executable path."""

    name = path.name.lower()
    full = str(path).lower()
    if "arm64" in name or "aarch64" in full:
        return "arm64"
    if "x64" in name or "x64" in full or "x86_64" in full or "amd64" in full:
        return "x64"
    return None


def _list_macos_bundled_java_homes(fiji_root: Path) -> List[Path]:
    """Return bundled Java homes from a Fiji.app installation."""

    java_root = fiji_root / "java"
    if not java_root.exists():
        return []

    homes: list[Path] = []
    for java_bin in java_root.glob("**/Contents/Home/bin/java"):
        homes.append(java_bin.parent.parent)
    return homes


def _select_macos_launcher_for_root(fiji_root: Path, current_path: Optional[Path] = None) -> Optional[Path]:
    """Pick the Fiji launcher that matches the bundled Java architecture best."""

    launcher_candidates = [
        fiji_root / "Fiji.app" / "Contents" / "MacOS" / "fiji-macos-arm64",
        fiji_root / "Fiji.app" / "Contents" / "MacOS" / "fiji-macos-x64",
        fiji_root / "Contents" / "MacOS" / "ImageJ-macosx",
        fiji_root / "fiji",
    ]
    existing_launchers = [candidate for candidate in launcher_candidates if candidate.is_file() and os.access(candidate, os.X_OK)]
    if not existing_launchers:
        return current_path if current_path and current_path.exists() else None

    java_homes = _list_macos_bundled_java_homes(fiji_root)
    java_arches = {_macos_launcher_arch(home) for home in java_homes}
    java_arches.discard(None)

    preferred_arches: List[str] = []
    if len(java_arches) == 1:
        preferred_arches = [next(iter(java_arches))]
    else:
        machine = platform.machine().lower()
        if machine in {"arm64", "aarch64"}:
            preferred_arches.append("arm64")
        elif machine in {"x86_64", "amd64"}:
            preferred_arches.append("x64")

    def _score(candidate: Path) -> tuple[int, int, int, str]:
        candidate_arch = _macos_launcher_arch(candidate)
        matches_java = 1 if candidate_arch and candidate_arch in java_arches else 0
        matches_machine = 1 if preferred_arches and candidate_arch == preferred_arches[0] else 0
        current_bonus = 1 if current_path and candidate.resolve() == current_path.resolve() else 0
        return (matches_java, matches_machine, current_bonus, str(candidate))

    return sorted(existing_launchers, key=_score, reverse=True)[0]


def normalize_fiji_path(fiji_path: str) -> str:
    """Return the best Fiji launcher path for the current installation layout."""

    if not fiji_path:
        return fiji_path

    path = Path(fiji_path).expanduser()
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    if platform.system().lower() != "darwin":
        return str(resolved)

    root = _resolve_fiji_root(str(resolved))
    if root is None:
        return str(resolved)

    selected = _select_macos_launcher_for_root(root, resolved)
    return str(selected or resolved)


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
            return normalize_fiji_path(path)
    
    # Platform-specific fallback searches
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        for executable_name in _macos_fiji_fallback_names():
            try:
                result = subprocess.check_output(
                    ["find", "/Applications", "-name", executable_name, "-type", "f"],
                    text=True,
                    timeout=30,
                ).strip()
                if result:
                    return normalize_fiji_path(result.split("\n")[0])
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
    
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

    fiji_path = normalize_fiji_path(fiji_path)

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
