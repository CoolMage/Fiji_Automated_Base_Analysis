"""Cross-platform utilities for finding Fiji or ImageJ installations."""

import os
import stat
import subprocess
import platform
import shutil
import fnmatch
from pathlib import Path
from typing import Iterable, Optional, List

from fiji_automated_analysis.config import DEFAULT_FIJI_PATHS


WINDOWS_EXECUTABLE_SUFFIXES = {".exe", ".bat", ".cmd"}
UNIX_SEARCH_MAX_DEPTH = 6


def _macos_fiji_fallback_names() -> List[str]:
    """Return Fiji launcher names in preferred order for modern macOS installs."""

    return [
        "fiji-macos-arm64",
        "fiji-macos-x64",
        "fiji",
        "ImageJ-macosx",
    ]


def _platform_launcher_names(system: str) -> List[str]:
    """Return Fiji launchers first, followed by common ImageJ launchers."""

    if system == "darwin":
        return _macos_fiji_fallback_names() + [
            "ImageJ",
            "JavaApplicationStub",
        ]
    if system == "windows":
        return [
            "fiji-win64.exe",
            "fiji-win32.exe",
            "fiji.exe",
            "ImageJ-win64.exe",
            "ImageJ-win32.exe",
            "ImageJ.exe",
            "imagej.exe",
        ]
    return [
        "fiji-linux64",
        "fiji-linux32",
        "fiji-linux",
        "fiji",
        "ImageJ-linux64",
        "ImageJ-linux32",
        "ImageJ-linux",
        "imagej",
        "ImageJ",
        "imagej1",
    ]


def _platform_launcher_globs(system: str) -> List[str]:
    """Return bounded filename globs for versioned launchers such as AppImages."""

    if system == "windows":
        return ["Fiji*.exe", "fiji*.exe", "ImageJ*.exe", "imagej*.exe"]
    if system == "darwin":
        return []
    return [
        "Fiji*.AppImage",
        "fiji*.AppImage",
        "ImageJ*.AppImage",
        "imagej*.AppImage",
        "Fiji*.appimage",
        "fiji*.appimage",
        "ImageJ*.appimage",
        "imagej*.appimage",
    ]


def _launcher_relative_paths(system: str) -> List[Path]:
    """Return launcher locations relative to an installation or parent directory."""

    names = _platform_launcher_names(system)
    relative_paths: list[Path] = [Path(name) for name in names]

    if system == "darwin":
        relative_paths.extend(
            [
                Path("Contents") / "MacOS" / name
                for name in _macos_fiji_fallback_names()
            ]
        )
        relative_paths.extend(
            [
                Path("Fiji.app") / "Contents" / "MacOS" / name
                for name in _macos_fiji_fallback_names()
            ]
        )
        relative_paths.extend(
            [
                Path("Fiji.app") / "Fiji.app" / "Contents" / "MacOS" / name
                for name in _macos_fiji_fallback_names()
            ]
        )
        relative_paths.extend(
            [
                Path("ImageJ.app") / "Contents" / "MacOS" / name
                for name in ("ImageJ", "ImageJ-macosx", "JavaApplicationStub")
            ]
        )
    elif system == "windows":
        relative_paths.extend(Path("Fiji.app") / name for name in names)
        relative_paths.extend(Path("Fiji") / name for name in names)
        relative_paths.extend(Path("ImageJ") / name for name in names)
    else:
        relative_paths.extend(Path("Fiji.app") / name for name in names)
        relative_paths.extend(Path("fiji") / name for name in names)
        relative_paths.extend(Path("ImageJ") / name for name in names)
        relative_paths.extend(Path("imagej") / name for name in names)

    unique_paths: list[Path] = []
    seen: set[str] = set()
    for relative_path in relative_paths:
        key = (
            relative_path.as_posix().lower()
            if system == "windows"
            else relative_path.as_posix()
        )
        if key not in seen:
            seen.add(key)
            unique_paths.append(relative_path)
    return unique_paths


def _candidate_priority(path: str, original_index: int) -> tuple[int, int]:
    """Rank Fiji installations before generic Fiji launchers and ImageJ."""

    candidate = Path(path).expanduser()
    try:
        comparison_path = str(candidate.resolve()).lower()
    except OSError:
        comparison_path = str(candidate).lower()

    if "fiji" in comparison_path:
        return (0, original_index)

    fiji_launcher_names = {
        "fiji",
        "fiji.exe",
        "fiji-win64.exe",
        "fiji-win32.exe",
        "fiji-linux64",
        "fiji-linux32",
        "fiji-linux",
        "fiji-macos-arm64",
        "fiji-macos-x64",
        "imagej-linux64",
        "imagej-linux32",
        "imagej-linux",
        "imagej-win64.exe",
        "imagej-win32.exe",
    }
    if candidate.name.lower() in fiji_launcher_names:
        return (1, original_index)
    return (2, original_index)


def _path_key(path: str) -> str:
    """Return a stable key for deduplicating candidate paths."""

    candidate = Path(path).expanduser()
    try:
        resolved = str(candidate.resolve())
    except OSError:
        resolved = os.path.abspath(str(candidate))
    if platform.system().lower() == "windows":
        return os.path.normcase(resolved)
    return resolved


def _select_executable_file(paths: Iterable[str]) -> Optional[str]:
    """Choose an executable file candidate while preserving Fiji preference."""

    candidates: list[tuple[tuple[int, int], str]] = []
    seen: set[str] = set()
    for index, raw_path in enumerate(paths):
        if not raw_path:
            continue
        path = str(Path(os.path.expandvars(raw_path)).expanduser())
        normalized_key = _path_key(path)
        if normalized_key in seen:
            continue
        seen.add(normalized_key)

        if _looks_executable_file(path):
            candidates.append((_candidate_priority(path, index), path))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def _directory_launcher_candidates(directory: Path, system: str) -> List[str]:
    """Return launcher candidates under a known installation or parent directory."""

    candidates: list[str] = [
        str(directory / relative_path)
        for relative_path in _launcher_relative_paths(system)
    ]

    for pattern in _platform_launcher_globs(system):
        try:
            candidates.extend(str(path) for path in directory.glob(pattern))
        except OSError:
            continue

    return candidates


def _resolve_launcher_from_path(raw_path: str) -> Optional[str]:
    """Resolve either an executable path or an installation directory to a launcher."""

    if not raw_path:
        return None

    system = platform.system().lower()
    expanded_path = os.path.expandvars(raw_path)
    path = Path(expanded_path).expanduser()

    if any(char in str(path) for char in "*?[]"):
        parent = path.parent
        try:
            matches = [str(candidate) for candidate in parent.glob(path.name)]
        except OSError:
            matches = []
        return _select_executable_file(matches)

    if path.is_file():
        return str(path) if _looks_executable_file(str(path)) else None

    if not path.is_dir():
        return None

    return _select_executable_file(_directory_launcher_candidates(path, system))


def _select_existing_executable(paths: Iterable[str]) -> Optional[str]:
    """Choose an executable candidate while accepting files or install roots."""

    candidates: list[str] = []
    for raw_path in paths:
        selected = _resolve_launcher_from_path(raw_path)
        if selected:
            candidates.append(selected)

    selected = _select_executable_file(candidates)
    return normalize_fiji_path(selected) if selected else None


def _looks_executable_file(path: str) -> bool:
    """Return whether a path is a launchable executable for the current OS."""

    if not os.path.isfile(path):
        return False
    if platform.system().lower() == "windows":
        return Path(path).suffix.lower() in WINDOWS_EXECUTABLE_SUFFIXES
    return os.access(path, os.X_OK)


def _find_named_executables(
    roots: List[str],
    names: List[str],
    patterns: Optional[List[str]] = None,
    max_depth: int = UNIX_SEARCH_MAX_DEPTH,
) -> List[str]:
    """Find matching executable files under Unix roots with a bounded walk."""

    existing_roots = [root for root in roots if os.path.isdir(root)]
    if not existing_roots:
        return []

    matches: list[str] = []
    seen: set[str] = set()
    name_set = set(names)
    glob_patterns = patterns or []
    pruned_dirs = {
        ".cache",
        ".conda",
        ".git",
        ".hg",
        ".npm",
        ".venv",
        "__pycache__",
        "node_modules",
        "site-packages",
    }

    for raw_root in existing_roots:
        root = Path(raw_root)
        try:
            root = root.resolve()
        except OSError:
            continue

        for current_root, dirs, files in os.walk(root):
            current_path = Path(current_root)
            try:
                depth = len(current_path.relative_to(root).parts)
            except ValueError:
                depth = max_depth

            if depth >= max_depth:
                dirs[:] = []
            else:
                dirs[:] = [
                    name
                    for name in dirs
                    if name not in pruned_dirs and not name.endswith(".egg-info")
                ]

            for filename in files:
                if filename not in name_set and not any(
                    fnmatch.fnmatchcase(filename, pattern) for pattern in glob_patterns
                ):
                    continue

                candidate = str(current_path / filename)
                key = _path_key(candidate)
                if key in seen or not _looks_executable_file(candidate):
                    continue
                seen.add(key)
                matches.append(candidate)

    return matches


def _macos_search_roots() -> List[str]:
    """Return macOS locations that commonly contain Fiji or ImageJ apps."""

    return [
        "/Applications",
        os.path.expanduser("~/Applications"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Desktop"),
    ]


def _linux_search_roots() -> List[str]:
    """Return bounded Linux roots that commonly contain Fiji/ImageJ installs."""

    return [
        "/opt",
        "/usr/local",
        "/usr/lib",
        "/usr/bin",
        "/snap/bin",
        "/var/lib/flatpak/exports/bin",
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/.local/share/flatpak/exports/bin"),
        os.path.expanduser("~/Applications"),
        os.path.expanduser("~/Fiji.app"),
        os.path.expanduser("~/fiji"),
        os.path.expanduser("~/ImageJ"),
        os.path.expanduser("~/imagej"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/opt"),
        os.path.expanduser("~/apps"),
    ]


def _windows_search_roots() -> List[str]:
    """Return bounded Windows roots that commonly contain Fiji.app installs."""

    raw_roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
        os.path.expanduser(r"~\Desktop"),
        os.path.expanduser(r"~\Downloads"),
        os.path.expanduser(r"~\Documents"),
        os.path.expanduser("~"),
    ]
    roots: list[str] = []
    seen: set[str] = set()
    for raw_root in raw_roots:
        if not raw_root:
            continue
        root = os.path.abspath(os.path.expandvars(os.path.expanduser(raw_root)))
        normalized = os.path.normcase(root)
        if normalized in seen or not os.path.isdir(root):
            continue
        seen.add(normalized)
        roots.append(root)
    return roots


def _find_windows_executables(roots: List[str]) -> List[str]:
    """Find Windows executables with a bounded per-root recursive search."""

    candidates: list[str] = []
    patterns = ["ImageJ*.exe", "fiji*.exe"]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for pattern in patterns:
            try:
                result = subprocess.check_output(
                    ["where", "/R", root, pattern],
                    text=True,
                    timeout=10,
                    stderr=subprocess.DEVNULL,
                )
            except (
                subprocess.TimeoutExpired,
                subprocess.CalledProcessError,
                FileNotFoundError,
            ):
                continue
            candidates.extend(
                line.strip() for line in result.splitlines() if line.strip()
            )
    return candidates


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

    launcher = _resolve_launcher_from_path(fiji_path)
    path = Path(launcher or os.path.expandvars(fiji_path)).expanduser()
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
    Find Fiji or ImageJ across different platforms, preferring Fiji.

    Args:
        custom_paths: Optional list of custom paths to search

    Returns:
        Path to a Fiji or ImageJ executable if found, otherwise None
    """
    environment_paths = [
        os.environ.get("FIJI_PATH"),
        os.environ.get("IMAGEJ_PATH"),
        os.environ.get("FIJI_EXECUTABLE"),
        os.environ.get("IMAGEJ_EXECUTABLE"),
    ]
    search_paths = environment_paths + (
        custom_paths if custom_paths is not None else DEFAULT_FIJI_PATHS
    )
    selected = _select_existing_executable(search_paths)
    if selected:
        return selected

    system = platform.system().lower()
    launcher_names = _platform_launcher_names(system)

    path_candidates = [
        path
        for name in launcher_names
        if (path := shutil.which(name)) is not None
    ]

    filesystem_candidates: List[str] = []
    if system == "darwin":
        explicit_root_candidates = _select_existing_executable(_macos_search_roots())
        if explicit_root_candidates:
            filesystem_candidates.append(explicit_root_candidates)
        filesystem_candidates.extend(
            _find_named_executables(
                _macos_search_roots(),
                launcher_names,
                _platform_launcher_globs(system),
            )
        )
    elif system == "windows":
        explicit_root_candidates = _select_existing_executable(
            _windows_search_roots()
        )
        if explicit_root_candidates:
            filesystem_candidates.append(explicit_root_candidates)
        filesystem_candidates.extend(
            _find_windows_executables(
                _windows_search_roots()
            )
        )
    else:
        explicit_root_candidates = _select_existing_executable(_linux_search_roots())
        if explicit_root_candidates:
            filesystem_candidates.append(explicit_root_candidates)
        filesystem_candidates.extend(
            _find_named_executables(
                _linux_search_roots(),
                launcher_names,
                _platform_launcher_globs(system),
            )
        )

    return _select_existing_executable(path_candidates + filesystem_candidates)


def validate_fiji_path(fiji_path: str) -> bool:
    """Validate that the given path points to a usable Fiji or ImageJ executable.

    Validation is intentionally lightweight to avoid spawning a Fiji GUI
    process.  We rely on filesystem checks rather than executing the binary.

    Args:
        fiji_path: Path to a Fiji or ImageJ executable

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

    if not _looks_executable_file(fiji_path):
        return False

    return True


def _resolve_fiji_root(fiji_path: str) -> Optional[Path]:
    """Best-effort resolver for the Fiji installation root directory."""
    if not fiji_path:
        return None

    original_path = Path(os.path.expandvars(fiji_path)).expanduser()
    try:
        original_resolved = original_path.resolve()
    except OSError:
        original_resolved = original_path

    if original_resolved.is_dir() and (
        original_resolved.name.lower() == "fiji.app"
        or (original_resolved / "plugins").exists()
        or (original_resolved / "jars").exists()
    ):
        return original_resolved

    launcher = _resolve_launcher_from_path(fiji_path)
    path = Path(launcher or os.path.expandvars(fiji_path)).expanduser()
    try:
        path = path.resolve()
    except OSError:
        pass
    parts = [part.lower() for part in path.parts]
    if "fiji.app" in parts:
        idx = parts.index("fiji.app")
        return Path(*path.parts[: idx + 1])

    return path.parent if path.is_file() else path


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


def find_deconvolutionlab2_plugin(fiji_path: str) -> Optional[str]:
    """Return the installed DeconvolutionLab2 JAR path, if available."""

    root = _resolve_fiji_root(fiji_path)
    if root is None or not root.exists():
        return None

    patterns = (
        "DeconvolutionLab_2*.jar",
        "DeconvolutionLab2*.jar",
        "*deconvolutionlab_2*.jar",
        "*deconvolutionlab2*.jar",
    )
    for directory in (root / "plugins", root / "jars"):
        if not directory.exists():
            continue
        for pattern in patterns:
            matches = sorted(directory.glob(pattern))
            if matches:
                return str(matches[0])
    return None


def detect_deconvolutionlab2_plugin(fiji_path: str) -> bool:
    """Check whether the DeconvolutionLab2 ImageJ plugin is installed."""

    return find_deconvolutionlab2_plugin(fiji_path) is not None


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
